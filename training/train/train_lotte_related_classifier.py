"""
Train binary KoELECTRA classifier for is_lotte_related detection.

Usage (local):
    python train_lotte_related_classifier.py

Usage (Colab/Kaggle):
    python train_lotte_related_classifier.py \\
        --data-dir /kaggle/input/<dataset>/ \\
        --output-dir /kaggle/working/lotte_related_koelectra/

Model: monologg/koelectra-small-v3-discriminator
Loss:  BCEWithLogitsLoss (num_labels=1)
Goal:  recall >= 0.97, precision >= 0.90
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import precision_recall_curve
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from settings import (
    ARTICLE_SNIPPET_LENGTH,
    DATA_DIR,
    DEFAULT_EVAL_BATCH_SIZE,
    DEFAULT_LOTTE_RELATED_BATCH_SIZE,
    DEFAULT_LOTTE_RELATED_EPOCHS,
    DEFAULT_LOTTE_RELATED_LR,
    DEFAULT_LOTTE_RELATED_PRETRAINED,
    DEFAULT_LOTTE_RELATED_THRESHOLD,
    DEFAULT_TRAIN_SEED,
    DEFAULT_TRAIN_WARMUP_RATIO,
    DEFAULT_VALIDATION_SPLIT,
    LABELED_PLAYERS_CSV,
    LABELED_TITLES_CSV,
    LOTTE_RELATED_MODEL_DIR,
    LOTTE_RELATED_RECALL_TARGET,
)

PRETRAINED = DEFAULT_LOTTE_RELATED_PRETRAINED
DEFAULT_THRESHOLD = DEFAULT_LOTTE_RELATED_THRESHOLD
RECALL_TARGET = LOTTE_RELATED_RECALL_TARGET


class BinaryDataset(Dataset):
    def __init__(
        self,
        titles: list[str],
        snippets: list[str],
        labels: list[float],
        tokenizer,
        max_len: int = 128,
    ):
        self.encodings = tokenizer(
            titles,
            snippets,
            truncation="only_second",
            padding="max_length",
            max_length=max_len,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.float)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def load_data(data_dir: Path | None = None) -> tuple[list[str], list[str], list[float]]:
    csv_files = [
        (data_dir or DATA_DIR) / LABELED_TITLES_CSV.name,
        (data_dir or DATA_DIR) / LABELED_PLAYERS_CSV.name,
    ]
    frames = []
    for path in csv_files:
        if not path.exists():
            print(f"  Skipped: {path.name} not found")
            continue
        df = pd.read_csv(path, encoding="utf-8-sig")
        if "is_lotte_related" not in df.columns:
            print(f"  Skipped: {path.name} has no is_lotte_related column")
            continue
        before = len(df)
        df = df.dropna(subset=["is_lotte_related"]).copy()
        print(f"  Loaded: {path.name} ({len(df)} rows with label, dropped {before - len(df)} nulls)")
        frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No labeled data found under: {data_dir or DATA_DIR}")

    df = pd.concat(frames, ignore_index=True)
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["description_snippet"] = (
        df["description_snippet"].fillna("").astype(str)
        .str[:ARTICLE_SNIPPET_LENGTH].str.strip()
    )

    _VALID_POSITIVE = {"true", "1", "yes"}
    _VALID_NEGATIVE = {"false", "0", "no"}
    _VALID_ALL = _VALID_POSITIVE | _VALID_NEGATIVE

    raw_labels = df["is_lotte_related"].astype(str).str.strip().str.lower()
    invalid_mask = ~raw_labels.isin(_VALID_ALL)
    if invalid_mask.any():
        print(f"  WARNING: dropping {invalid_mask.sum()} rows with unrecognised is_lotte_related values: "
              f"{raw_labels[invalid_mask].unique().tolist()}")
        df = df[~invalid_mask].reset_index(drop=True)
        raw_labels = raw_labels[~invalid_mask].reset_index(drop=True)

    df["_raw_label"] = raw_labels
    conflicting_titles = (
        df.groupby("title")["_raw_label"]
        .nunique()
        .loc[lambda counts: counts > 1]
        .index
    )
    if len(conflicting_titles) > 0:
        print(f"  WARNING: dropping {len(conflicting_titles)} titles with conflicting labels "
              f"(same title, different is_lotte_related across CSVs)")
        df = df[~df["title"].isin(conflicting_titles)].reset_index(drop=True)

    df = df.drop_duplicates(subset=["title"]).reset_index(drop=True)

    labels = df["_raw_label"].map(lambda v: 1.0 if v in _VALID_POSITIVE else 0.0).tolist()

    positives = int(sum(labels))
    negatives = len(labels) - positives
    print(f"\nTotal: {len(labels)} rows")
    print(f"  is_lotte_related=True  {positives:>5}")
    print(f"  is_lotte_related=False {negatives:>5}")

    return df["title"].tolist(), df["description_snippet"].tolist(), labels


def find_recall_first_threshold(
    y_true: np.ndarray,
    probs: np.ndarray,
    recall_target: float = RECALL_TARGET,
) -> float:
    """Find the lowest threshold that achieves recall >= recall_target."""
    precision_arr, recall_arr, thresholds = precision_recall_curve(y_true, probs)
    # precision_recall_curve returns arrays sorted by descending threshold
    # Find thresholds where recall >= target
    valid = [(float(t), float(r), float(p))
             for t, r, p in zip(thresholds, recall_arr[:-1], precision_arr[:-1])
             if r >= recall_target]
    if not valid:
        # Fallback: pick threshold with best recall
        best_idx = int(np.argmax(recall_arr[:-1]))
        t = float(thresholds[best_idx])
        print(f"  WARNING: recall target {recall_target} not achievable; using t={t:.2f}")
        return t
    # Among valid thresholds, pick the one with highest precision
    best = max(valid, key=lambda x: x[2])
    print(f"  Threshold candidates meeting recall>={recall_target}: {len(valid)}")
    print(f"  Selected: t={best[0]:.2f}  recall={best[1]:.4f}  precision={best[2]:.4f}")
    return best[0]


def evaluate_threshold(
    y_true: np.ndarray,
    probs: np.ndarray,
    threshold: float,
) -> tuple[float, float]:
    from sklearn.metrics import precision_score, recall_score

    preds = (probs >= threshold).astype(int)
    recall = recall_score(y_true, preds, zero_division=0)
    precision = precision_score(y_true, preds, zero_division=0)
    return recall, precision


def train(
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    epochs: int = DEFAULT_LOTTE_RELATED_EPOCHS,
    lr: float = DEFAULT_LOTTE_RELATED_LR,
    batch_size: int = DEFAULT_LOTTE_RELATED_BATCH_SIZE,
    warmup_ratio: float = DEFAULT_TRAIN_WARMUP_RATIO,
    seed: int = DEFAULT_TRAIN_SEED,
):
    out_dir = output_dir or LOTTE_RELATED_MODEL_DIR
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    titles, snippets, labels = load_data(data_dir)

    # Stratified split
    tr_t, va_t, tr_s, va_s, tr_l, va_l = train_test_split(
        titles, snippets, labels,
        test_size=DEFAULT_VALIDATION_SPLIT,
        random_state=seed,
        stratify=labels,
    )
    print(f"\nTrain: {len(tr_t)} rows  Validation: {len(va_t)} rows")

    tokenizer = AutoTokenizer.from_pretrained(PRETRAINED)
    model = AutoModelForSequenceClassification.from_pretrained(
        PRETRAINED,
        num_labels=1,
    ).to(device)

    pin = device.type == "cuda"
    num_workers = 2 if device.type == "cuda" else 0
    train_ds = BinaryDataset(tr_t, tr_s, tr_l, tokenizer)
    val_ds = BinaryDataset(va_t, va_s, va_l, tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=pin)
    val_loader = DataLoader(val_ds, batch_size=DEFAULT_EVAL_BATCH_SIZE, num_workers=num_workers, pin_memory=pin)

    # Class imbalance weight
    positives = sum(tr_l)
    negatives = len(tr_l) - positives
    pos_weight = torch.tensor([negatives / max(positives, 1)], dtype=torch.float).clamp(0.5, 5.0).to(device)
    print(f"\nPos weight: {pos_weight.item():.3f}")
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * warmup_ratio),
        num_training_steps=total_steps,
    )

    best_recall = 0.0
    best_precision = 0.0
    best_epoch = 0
    best_threshold = DEFAULT_THRESHOLD

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            labels_batch = batch.pop("labels").unsqueeze(1).to(device)
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(**batch).logits
            loss = loss_fn(logits, labels_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += loss.item()

        # Validation
        model.eval()
        all_probs: list[float] = []
        all_true: list[int] = []
        with torch.no_grad():
            for batch in val_loader:
                labels_batch = batch.pop("labels").to(device)
                batch = {k: v.to(device) for k, v in batch.items()}
                logits = model(**batch).logits[:, 0]
                probs = torch.sigmoid(logits).cpu().tolist()
                all_probs.extend(probs)
                all_true.extend(labels_batch.cpu().int().tolist())

        probs_arr = np.array(all_probs)
        true_arr = np.array(all_true)
        epoch_threshold = find_recall_first_threshold(true_arr, probs_arr, RECALL_TARGET)
        recall, precision = evaluate_threshold(true_arr, probs_arr, epoch_threshold)
        avg_loss = total_loss / len(train_loader)
        print(
            f"Epoch {epoch}/{epochs}  loss={avg_loss:.4f}  "
            f"recall={recall:.4f}  precision={precision:.4f}  (t={epoch_threshold:.4f})"
        )

        is_better = False
        if best_epoch == 0:
            is_better = True
        elif recall >= RECALL_TARGET:
            if best_recall < RECALL_TARGET:
                is_better = True
            elif precision > best_precision or (precision == best_precision and recall > best_recall):
                is_better = True
        elif best_recall < RECALL_TARGET and recall > best_recall:
            is_better = True

        if is_better:
            best_recall = recall
            best_precision = precision
            best_epoch = epoch
            best_threshold = epoch_threshold
            _save(model, tokenizer, out_dir, best_threshold)
            print("  Best checkpoint updated and saved")

    print(f"\nTraining complete — best recall: {best_recall:.4f} at epoch {best_epoch}")
    print(f"Best precision: {best_precision:.4f}  Best threshold: {best_threshold:.4f}")

    if best_epoch == 0:
        raise RuntimeError("Training finished without selecting a checkpoint.")

    return best_recall


def _save(model, tokenizer, out_dir: Path, threshold: float):
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    threshold_path = out_dir / "threshold.json"
    with threshold_path.open("w", encoding="utf-8") as f:
        json.dump({"threshold": round(threshold, 4)}, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Train is_lotte_related binary classifier")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="Directory containing labeled_titles.csv and labeled_players.csv")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory for model artifacts")
    parser.add_argument("--epochs", type=int, default=DEFAULT_LOTTE_RELATED_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_LOTTE_RELATED_LR)
    parser.add_argument("--batch", type=int, default=DEFAULT_LOTTE_RELATED_BATCH_SIZE)
    args = parser.parse_args()

    train(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch,
    )


if __name__ == "__main__":
    main()
