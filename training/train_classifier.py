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

from label_schema import VALID_LABELS, VALID_LABEL_SET
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
        descriptions: list[str],
        labels: list[list[float]],
        tokenizer,
        max_len: int = 128,
    ):
        self.encodings = tokenizer(
            titles,
            descriptions,
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


def load_data() -> tuple[list[str], list[str], list[list[float]], list[str]]:
    csv_files = [LABELED_TITLES_CSV, LABELED_PLAYERS_CSV]
    frames = []

    for path in csv_files:
        if not path.exists():
            print(f"  Skipped: {path.name} not found")
            continue

        dataframe = pd.read_csv(path, encoding="utf-8-sig")
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
    dataframe["label_set"] = dataframe.apply(
        lambda row: normalize_label_set(row.get("primary_label", ""), row.get("secondary_labels", "")),
        axis=1,
    )
    dataframe = dataframe[dataframe["label_set"].map(bool)].reset_index(drop=True)

    titles = dataframe["title"].tolist()
    descriptions = dataframe["description_snippet"].tolist()
    multilabels = [encode_multihot(label_set) for label_set in dataframe["label_set"]]
    primary_labels = [
        label if label in VALID_LABEL_SET else label_set[0]
        for label, label_set in zip(dataframe["primary_label"].tolist(), dataframe["label_set"].tolist(), strict=False)
    ]

    print(f"\nTotal usable rows: {len(titles)}")
    label_totals = np.array(multilabels, dtype=np.float32).sum(axis=0)
    for index, label in enumerate(VALID_LABELS):
        print(f"  {label:<25} {int(label_totals[index]):>4} positives")

    avg_labels = float(np.array(multilabels, dtype=np.float32).sum(axis=1).mean()) if multilabels else 0.0
    print(f"  Avg labels/article          {avg_labels:.2f}")

    return titles, descriptions, multilabels, primary_labels


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


def predict_from_logits(logits: torch.Tensor, threshold: float = DEFAULT_PREDICTION_THRESHOLD) -> np.ndarray:
    probs = torch.sigmoid(logits)
    preds = (probs >= threshold).to(torch.int64)

    # Ensure every sample keeps at least one label prediction.
    empty_mask = preds.sum(dim=1) == 0
    if empty_mask.any():
        top_indices = probs[empty_mask].argmax(dim=1)
        preds[empty_mask] = 0
        preds[empty_mask, top_indices] = 1

    # ETC should only be active when no other label is selected.
    etc_index = VALID_LABELS.index("ETC")
    other_positive_mask = preds[:, :etc_index].sum(dim=1) + preds[:, etc_index + 1 :].sum(dim=1) > 0
    preds[other_positive_mask, etc_index] = 0

    # If all labels were cleared by ETC suppression, restore the top scoring non-ETC label.
    empty_after_cleanup = preds.sum(dim=1) == 0
    if empty_after_cleanup.any():
        non_etc_probs = probs[empty_after_cleanup].clone()
        non_etc_probs[:, etc_index] = -1.0
        top_indices = non_etc_probs.argmax(dim=1)
        preds[empty_after_cleanup] = 0
        preds[empty_after_cleanup, top_indices] = 1

    return preds.cpu().numpy()


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

    titles, descriptions, multilabels, primary_labels = load_data()

    tr_t, va_t, tr_d, va_d, tr_l, va_l = train_test_split(
        titles,
        descriptions,
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
        problem_type="multi_label_classification",
    ).to(device)

    train_ds = ArticleDataset(tr_t, tr_d, tr_l, tokenizer)
    val_ds = ArticleDataset(va_t, va_d, va_l, tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    pos_weights = compute_pos_weights(multilabels).to(device)
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
            labels_batch = batch.pop("labels").to(device)
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            loss = loss_fn(logits, labels_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
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
    return best_f1


def evaluate():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    titles, descriptions, multilabels, _ = load_data()
    tokenizer, model, labels = _load(MODEL_DIR, device)

    dataset = ArticleDataset(titles, descriptions, multilabels, tokenizer)
    loader = DataLoader(dataset, batch_size=DEFAULT_EVAL_BATCH_SIZE)

    model.eval()
    all_preds, all_true = [], []
    with torch.no_grad():
        for batch in loader:
            labels_batch = batch.pop("labels")
            batch = {key: value.to(device) for key, value in batch.items()}
            logits = model(**batch).logits
            all_preds.append(predict_from_logits(logits))
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
    return tokenizer, model, labels


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

    best_f1 = train(epochs=args.epochs, lr=args.lr, batch_size=args.batch)
    print("\nFinal full-data evaluation")
    evaluate()
    if best_f1 < DEFAULT_MIN_MACRO_F1:
        print(f"\n[WARN] macro F1 {best_f1:.4f} < target {DEFAULT_MIN_MACRO_F1:.2f}")
        print("  Recommend: more data, threshold tuning, or label cleanup")


if __name__ == "__main__":
    main()
