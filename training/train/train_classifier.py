"""Train and evaluate the KoELECTRA classifier for multi-label article tags."""

import argparse
import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from collect.label_schema import VALID_LABELS, VALID_LABEL_SET
from settings import (
    ARTICLE_SNIPPET_LENGTH,
    DATA_DIR,
    DEFAULT_EVAL_BATCH_SIZE,
    DEFAULT_MIN_MACRO_F1,
    DEFAULT_TRAIN_BATCH_SIZE,
    DEFAULT_TRAIN_EPOCHS,
    DEFAULT_TRAIN_LR,
    DEFAULT_TRAIN_SEED,
    DEFAULT_TRAIN_WARMUP_RATIO,
    DEFAULT_VALIDATION_SPLIT,
    FALLBACK_ONLY_LABELS,
    LABEL_MIN_THRESHOLDS,
    LABELED_PLAYERS_CSV,
    LABELED_TITLES_CSV,
    MODEL_DIR,
)

PRETRAINED = "monologg/koelectra-small-v3-discriminator"
DEFAULT_PREDICTION_THRESHOLD = 0.5


class ArticleDataset(Dataset):
    def __init__(
        self,
        titles: list[str],
        auxiliary_texts: list[str],
        labels: list[list[float]],
        tokenizer,
        max_len: int = 128,
    ):
        self.encodings = tokenizer(
            titles,
            auxiliary_texts,
            truncation="only_second",
            padding="max_length",
            max_length=max_len,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.float)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: value[idx] for key, value in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def normalize_label_set(primary_label: str, secondary_labels: str) -> list[str]:
    labels: list[str] = []

    if primary_label in VALID_LABEL_SET:
        labels.append(primary_label)

    for label in str(secondary_labels or "").split(";"):
        label = label.strip()
        if label in VALID_LABEL_SET and label not in labels:
            labels.append(label)

    non_etc_labels = [label for label in labels if label != "ETC"]
    if non_etc_labels:
        return non_etc_labels
    if "ETC" in labels:
        return ["ETC"]
    return []


def encode_multihot(labels: list[str]) -> list[float]:
    encoded = [0.0] * len(VALID_LABELS)
    for label in labels:
        encoded[VALID_LABELS.index(label)] = 1.0
    return encoded


def build_auxiliary_text(description_snippet: str, game_context: str = "") -> str:
    parts: list[str] = []

    description = str(description_snippet or "").strip()
    if description:
        parts.append(description)

    ctx = str(game_context or "").strip()
    if ctx and ctx != "해당 날짜 경기 없음":
        parts.append(f"경기: {ctx}")

    return " [경기정보] ".join(parts)


def load_data() -> tuple[list[str], list[str], list[list[float]], list[str]]:
    csv_files = [LABELED_TITLES_CSV, LABELED_PLAYERS_CSV]
    frames = []

    for path in csv_files:
        if not path.exists():
            print(f"  Skipped: {path.name} not found")
            continue

        dataframe = pd.read_csv(path, encoding="utf-8-sig")
        if "game_context" not in dataframe.columns:
            dataframe["game_context"] = ""
        before = len(dataframe)
        dataframe = dataframe[dataframe["is_lotte_related"].astype(str).str.lower() == "true"].copy()
        removed = before - len(dataframe)
        print(f"  Loaded: {path.name} ({len(dataframe)} rows, filtered {removed} non-Lotte rows)")
        frames.append(dataframe)

    if not frames:
        raise FileNotFoundError(f"Training data not found under: {DATA_DIR}")

    dataframe = pd.concat(frames, ignore_index=True)
    dataframe = dataframe.drop_duplicates(subset=["title"]).reset_index(drop=True)
    dataframe["title"] = dataframe["title"].fillna("").astype(str).str.strip()
    dataframe["description_snippet"] = (
        dataframe["description_snippet"].fillna("").astype(str).str[:ARTICLE_SNIPPET_LENGTH].str.strip()
    )
    dataframe["game_context"] = dataframe["game_context"].fillna("").astype(str).str.strip()
    dataframe["label_set"] = dataframe.apply(
        lambda row: normalize_label_set(row.get("primary_label", ""), row.get("secondary_labels", "")),
        axis=1,
    )
    dataframe = dataframe[dataframe["label_set"].map(bool)].reset_index(drop=True)

    titles = dataframe["title"].tolist()
    auxiliary_texts = [
        build_auxiliary_text(description, game_context=ctx)
        for description, ctx in zip(
            dataframe["description_snippet"].tolist(),
            dataframe["game_context"].tolist(),
        )
    ]
    multilabels = [encode_multihot(label_set) for label_set in dataframe["label_set"]]
    primary_labels = [
        label if label in VALID_LABEL_SET else label_set[0]
        for label, label_set in zip(dataframe["primary_label"].tolist(), dataframe["label_set"].tolist(), strict=False)
    ]

    print(f"\nTotal usable rows: {len(titles)}")
    with_ctx = sum(
        1 for v in dataframe["game_context"].tolist()
        if v and v != "해당 날짜 경기 없음"
    )
    print(f"  Rows with game_context         {with_ctx:>4}")
    label_totals = np.array(multilabels, dtype=np.float32).sum(axis=0)
    for index, label in enumerate(VALID_LABELS):
        print(f"  {label:<25} {int(label_totals[index]):>4} positives")

    avg_labels = float(np.array(multilabels, dtype=np.float32).sum(axis=1).mean()) if multilabels else 0.0
    print(f"  Avg labels/article          {avg_labels:.2f}")

    return titles, auxiliary_texts, multilabels, primary_labels


def compute_pos_weights(multilabels: list[list[float]]) -> torch.Tensor:
    matrix = np.array(multilabels, dtype=np.float32)
    positives = matrix.sum(axis=0)
    negatives = len(matrix) - positives
    positives = np.clip(positives, 1.0, None)
    weights = negatives / positives
    weights = np.clip(weights, 0.5, 5.0)
    print("\nPositive class weights:")
    for index, label in enumerate(VALID_LABELS):
        print(f"  {label:<25} {weights[index]:.3f}")
    return torch.tensor(weights, dtype=torch.float)


def predict_from_logits(
    logits: torch.Tensor,
    thresholds: dict[str, float] | None = None,
) -> np.ndarray:
    probs = torch.sigmoid(logits)
    etc_index = VALID_LABELS.index("ETC")

    threshold_vec = torch.tensor(
        [thresholds.get(label, DEFAULT_PREDICTION_THRESHOLD) if thresholds else DEFAULT_PREDICTION_THRESHOLD
         for label in VALID_LABELS],
        dtype=torch.float,
        device=logits.device,
    )
    preds = (probs >= threshold_vec).to(torch.int64)

    # Suppress direct prediction for fallback-only labels (e.g. ETC).
    for label in FALLBACK_ONLY_LABELS:
        if label in VALID_LABELS:
            preds[:, VALID_LABELS.index(label)] = 0

    # ETC as fallback: assign only when nothing else fires.
    empty_mask = preds.sum(dim=1) == 0
    if empty_mask.any():
        preds[empty_mask, etc_index] = 1

    return preds.cpu().numpy()


def find_optimal_thresholds(y_true: np.ndarray, logits_all: np.ndarray) -> dict[str, float]:
    """Search per-label thresholds on the validation set to maximise per-label F1."""
    probs = 1.0 / (1.0 + np.exp(-logits_all))
    thresholds: dict[str, float] = {}
    print("\nPer-label optimal thresholds:")
    for i, label in enumerate(VALID_LABELS):
        if label in FALLBACK_ONLY_LABELS:
            thresholds[label] = 1.0  # never fires directly; assigned via fallback
            print(f"  {label:<25} t=fallback  (residual — direct prediction suppressed)")
            continue
        min_t = LABEL_MIN_THRESHOLDS.get(label, 0.0)
        best_t = max(DEFAULT_PREDICTION_THRESHOLD, min_t)
        best_f1 = 0.0
        for t in np.arange(0.10, 0.91, 0.05):
            if round(t, 2) < round(min_t, 2):
                continue
            preds = (probs[:, i] >= t).astype(int)
            score = f1_score(y_true[:, i], preds, zero_division=0)
            if score > best_f1:
                best_f1, best_t = score, float(round(t, 2))
        thresholds[label] = best_t
        print(f"  {label:<25} t={best_t:.2f}  F1={best_f1:.4f}")
    return thresholds


def _collect_logits(model, loader, device) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    all_logits: list[np.ndarray] = []
    all_true: list[np.ndarray] = []
    with torch.no_grad():
        for batch in loader:
            labels_batch = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            all_logits.append(logits.cpu().numpy())
            all_true.append(labels_batch.cpu().numpy().astype(np.int64))
    return np.vstack(all_logits), np.vstack(all_true)


def train(
    epochs: int = DEFAULT_TRAIN_EPOCHS,
    lr: float = DEFAULT_TRAIN_LR,
    batch_size: int = DEFAULT_TRAIN_BATCH_SIZE,
    warmup_ratio: float = DEFAULT_TRAIN_WARMUP_RATIO,
    seed: int = DEFAULT_TRAIN_SEED,
):
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    titles, auxiliary_texts, multilabels, primary_labels = load_data()

    tr_t, va_t, tr_aux, va_aux, tr_l, va_l = train_test_split(
        titles,
        auxiliary_texts,
        multilabels,
        test_size=DEFAULT_VALIDATION_SPLIT,
        random_state=seed,
        stratify=primary_labels,
    )
    print(f"\nTrain: {len(tr_t)} rows  Validation: {len(va_t)} rows")

    tokenizer = AutoTokenizer.from_pretrained(PRETRAINED)
    model = AutoModelForSequenceClassification.from_pretrained(
        PRETRAINED,
        num_labels=len(VALID_LABELS),
    ).to(device)

    pin = device.type == "cuda"
    num_workers = 2 if device.type == "cuda" else 0
    train_ds = ArticleDataset(tr_t, tr_aux, tr_l, tokenizer)
    val_ds = ArticleDataset(va_t, va_aux, va_l, tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=pin)
    val_loader = DataLoader(val_ds, batch_size=DEFAULT_EVAL_BATCH_SIZE, num_workers=num_workers, pin_memory=pin)

    pos_weights = compute_pos_weights(tr_l).to(device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weights)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    warmup_steps = int(total_steps * warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    best_f1 = 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for batch in train_loader:
            optimizer.zero_grad()
            labels_batch = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            loss = loss_fn(logits, labels_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)

        model.eval()
        all_preds, all_true = [], []
        with torch.no_grad():
            for batch in val_loader:
                labels_batch = batch.pop("labels").to(device)
                batch = {key: value.to(device) for key, value in batch.items()}
                logits = model(**batch).logits
                preds = predict_from_logits(logits)
                all_preds.append(preds)
                all_true.append(labels_batch.cpu().numpy().astype(np.int64))

        y_pred = np.vstack(all_preds)
        y_true = np.vstack(all_true)
        macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        micro_f1 = f1_score(y_true, y_pred, average="micro", zero_division=0)
        print(
            f"Epoch {epoch}/{epochs}  loss={avg_loss:.4f}  "
            f"val_macro_F1={macro_f1:.4f}  val_micro_F1={micro_f1:.4f}"
        )

        if macro_f1 > best_f1:
            best_f1 = macro_f1
            _save(model, tokenizer, MODEL_DIR)
            print("  Best validation macro-F1 updated, model saved")

    print(f"\nTraining complete - best val macro F1: {best_f1:.4f}")

    # Load best checkpoint and find per-label optimal thresholds on val set.
    best_model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR)).to(device)
    val_logits, val_true = _collect_logits(best_model, val_loader, device)
    thresholds = find_optimal_thresholds(val_true, val_logits)
    with (MODEL_DIR / "label_thresholds.json").open("w", encoding="utf-8") as f:
        json.dump(thresholds, f, ensure_ascii=False, indent=2)
    print(f"  Thresholds saved → {MODEL_DIR / 'label_thresholds.json'}")

    return best_f1, va_t, va_aux, va_l


def evaluate(titles=None, auxiliary_texts=None, multilabels=None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if titles is None:
        titles, auxiliary_texts, multilabels, _ = load_data()
        print("  [Note] Evaluating on full dataset (train+val combined)")
    tokenizer, model, labels, thresholds = _load(MODEL_DIR, device)
    if thresholds:
        print("  Using per-label thresholds from label_thresholds.json")

    dataset = ArticleDataset(titles, auxiliary_texts, multilabels, tokenizer)
    loader = DataLoader(dataset, batch_size=DEFAULT_EVAL_BATCH_SIZE)

    model.eval()
    all_preds, all_true = [], []
    with torch.no_grad():
        for batch in loader:
            labels_batch = batch.pop("labels")
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            all_preds.append(predict_from_logits(logits, thresholds))
            all_true.append(labels_batch.numpy().astype(np.int64))

    y_pred = np.vstack(all_preds)
    y_true = np.vstack(all_true)

    print("\nMulti-label metrics")
    print(f"  Macro F1: {f1_score(y_true, y_pred, average='macro', zero_division=0):.4f}")
    print(f"  Micro F1: {f1_score(y_true, y_pred, average='micro', zero_division=0):.4f}")
    print(f"  Samples F1: {f1_score(y_true, y_pred, average='samples', zero_division=0):.4f}")
    print("\nPer-label report")
    print(classification_report(y_true, y_pred, target_names=labels, zero_division=0))


def _save(model, tokenizer, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    with (out_dir / "label_encoder.json").open("w", encoding="utf-8") as file:
        json.dump(VALID_LABELS, file, ensure_ascii=False)


def _load(model_dir, device):
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    with (model_dir / "label_encoder.json").open(encoding="utf-8") as file:
        labels = json.load(file)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(device)
    thresholds_path = model_dir / "label_thresholds.json"
    thresholds: dict[str, float] | None = None
    if thresholds_path.exists():
        with thresholds_path.open(encoding="utf-8") as file:
            thresholds = json.load(file)
    return tokenizer, model, labels, thresholds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=DEFAULT_TRAIN_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_TRAIN_LR)
    parser.add_argument("--batch", type=int, default=DEFAULT_TRAIN_BATCH_SIZE)
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args()

    if args.eval_only:
        evaluate()
        return

    best_f1, va_t, va_aux, va_l = train(epochs=args.epochs, lr=args.lr, batch_size=args.batch)
    print("\nFinal validation-set evaluation (best checkpoint)")
    evaluate(va_t, va_aux, va_l)
    if best_f1 < DEFAULT_MIN_MACRO_F1:
        print(f"\n[WARN] macro F1 {best_f1:.4f} < target {DEFAULT_MIN_MACRO_F1:.2f}")
        print("  Recommend: more data, threshold tuning, or label cleanup")


if __name__ == "__main__":
    main()
