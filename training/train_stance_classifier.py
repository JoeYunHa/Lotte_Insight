"""
Train KoELECTRA 3-class classifier for lotte_stance.

Labels: negative / neutral / positive
Only trains on rows where is_lotte_related=True and lotte_stance is not null.

Usage (local):
    python train_stance_classifier.py

Usage (Colab/Kaggle):
    python train_stance_classifier.py \\
        --data-dir /kaggle/input/<dataset>/ \\
        --output-dir /kaggle/working/stance_koelectra/
"""

import argparse
import json
from pathlib import Path

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

from settings import (
    ARTICLE_SNIPPET_LENGTH,
    DATA_DIR,
    DEFAULT_EVAL_BATCH_SIZE,
    DEFAULT_STANCE_BATCH_SIZE,
    DEFAULT_STANCE_EPOCHS,
    DEFAULT_STANCE_LR,
    DEFAULT_STANCE_PRETRAINED,
    DEFAULT_TRAIN_SEED,
    DEFAULT_TRAIN_WARMUP_RATIO,
    DEFAULT_VALIDATION_SPLIT,
    LABELED_PLAYERS_CSV,
    LABELED_TITLES_CSV,
    STANCE_LABELS,
    STANCE_MODEL_DIR,
)

PRETRAINED = DEFAULT_STANCE_PRETRAINED
LABEL2ID = {label: i for i, label in enumerate(STANCE_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(STANCE_LABELS)}
NUM_LABELS = len(STANCE_LABELS)


class StanceDataset(Dataset):
    def __init__(
        self,
        titles: list[str],
        snippets: list[str],
        labels: list[int],
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
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def load_data(data_dir: Path | None = None) -> tuple[list[str], list[str], list[int]]:
    base = data_dir or DATA_DIR

    def _read_valid(path: Path) -> pd.DataFrame | None:
        if not path.exists():
            print(f"  Skipped: {path.name} not found")
            return None
        df = pd.read_csv(path, encoding="utf-8-sig")
        if "lotte_stance" not in df.columns or "is_lotte_related" not in df.columns:
            print(f"  Skipped: {path.name} missing required columns")
            return None
        before = len(df)
        df = df[df["is_lotte_related"].astype(str).str.lower().isin({"true", "1", "yes"})].copy()
        df = df.dropna(subset=["lotte_stance"])
        df = df[df["lotte_stance"].isin(STANCE_LABELS)]
        df["title"] = df["title"].fillna("").astype(str).str.strip()
        df["description_snippet"] = (
            df["description_snippet"].fillna("").astype(str)
            .str[:ARTICLE_SNIPPET_LENGTH].str.strip()
        )
        print(f"  Loaded: {path.name} ({len(df)} rows, dropped {before - len(df)})")
        return df

    lt_df = _read_valid(base / LABELED_TITLES_CSV.name)
    lp_df = _read_valid(base / LABELED_PLAYERS_CSV.name)

    if lt_df is None and lp_df is None:
        raise FileNotFoundError(f"No valid stance data under: {base}")

    # Build priority lookup: labeled_titles.csv wins on conflict
    # Same article collected via team-keyword and player-keyword may get different GPT labels.
    # labeled_titles.csv (team-level perspective) is treated as the authoritative source.
    lt_priority: dict[str, str] = {}
    if lt_df is not None:
        lt_priority = dict(zip(lt_df["title"], lt_df["lotte_stance"]))

    if lp_df is not None and lt_priority:
        overridden = 0
        for idx in lp_df.index:
            title = lp_df.at[idx, "title"]
            if title in lt_priority and lp_df.at[idx, "lotte_stance"] != lt_priority[title]:
                lp_df.at[idx, "lotte_stance"] = lt_priority[title]
                overridden += 1
        if overridden:
            print(f"  Resolved {overridden} conflicts in labeled_players.csv "
                  f"using labeled_titles.csv label (team perspective wins)")

    frames = [df for df in [lt_df, lp_df] if df is not None]
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["title"]).reset_index(drop=True)

    labels = df["lotte_stance"].map(LABEL2ID).tolist()
    print(f"\nTotal: {len(labels)} rows")
    for label in STANCE_LABELS:
        count = labels.count(LABEL2ID[label])
        print(f"  {label:>10}: {count:>5}")

    return df["title"].tolist(), df["description_snippet"].tolist(), labels


def compute_class_weights(labels: list[int]) -> torch.Tensor:
    counts = np.bincount(labels, minlength=NUM_LABELS).astype(float)
    if np.any(counts == 0):
        missing = [STANCE_LABELS[i] for i, count in enumerate(counts) if count == 0]
        raise ValueError(f"Training split is missing stance classes: {missing}")
    total = counts.sum()
    weights = total / (NUM_LABELS * counts)
    weights = np.clip(weights, 0.3, 5.0)
    print(f"\nClass weights: {dict(zip(STANCE_LABELS, weights.round(3).tolist()))}")
    return torch.tensor(weights, dtype=torch.float)


def train(
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    epochs: int = DEFAULT_STANCE_EPOCHS,
    lr: float = DEFAULT_STANCE_LR,
    batch_size: int = DEFAULT_STANCE_BATCH_SIZE,
    warmup_ratio: float = DEFAULT_TRAIN_WARMUP_RATIO,
    seed: int = DEFAULT_TRAIN_SEED,
):
    out_dir = output_dir or STANCE_MODEL_DIR
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    titles, snippets, labels = load_data(data_dir)

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
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    ).to(device)

    pin = device.type == "cuda"
    num_workers = 2 if device.type == "cuda" else 0
    train_ds = StanceDataset(tr_t, tr_s, tr_l, tokenizer)
    val_ds = StanceDataset(va_t, va_s, va_l, tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=pin)
    val_loader = DataLoader(val_ds, batch_size=DEFAULT_EVAL_BATCH_SIZE, num_workers=num_workers, pin_memory=pin)

    class_weights = compute_class_weights(tr_l).to(device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * warmup_ratio),
        num_training_steps=total_steps,
    )

    best_macro_f1 = 0.0
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            labels_batch = batch.pop("labels").to(device)
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(**batch).logits
            loss = loss_fn(logits, labels_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += loss.item()

        model.eval()
        all_preds: list[int] = []
        all_true: list[int] = []
        with torch.no_grad():
            for batch in val_loader:
                labels_batch = batch.pop("labels")
                batch = {k: v.to(device) for k, v in batch.items()}
                logits = model(**batch).logits
                preds = logits.argmax(dim=-1).cpu().tolist()
                all_preds.extend(preds)
                all_true.extend(labels_batch.tolist())

        macro_f1 = f1_score(all_true, all_preds, average="macro", zero_division=0)
        avg_loss = total_loss / len(train_loader)
        print(f"Epoch {epoch}/{epochs}  loss={avg_loss:.4f}  macro_f1={macro_f1:.4f}")

        if best_epoch == 0 or macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            best_epoch = epoch
            _save(model, tokenizer, out_dir)
            print("  Best checkpoint saved")

    print(f"\nTraining complete — best macro_f1: {best_macro_f1:.4f} at epoch {best_epoch}")
    if best_epoch == 0:
        raise RuntimeError("Training finished without selecting a checkpoint.")

    # Final report on best checkpoint
    model = AutoModelForSequenceClassification.from_pretrained(str(out_dir)).to(device)
    model.eval()
    all_preds = []
    all_true = []
    with torch.no_grad():
        for batch in val_loader:
            labels_batch = batch.pop("labels")
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(**batch).logits
            preds = logits.argmax(dim=-1).cpu().tolist()
            all_preds.extend(preds)
            all_true.extend(labels_batch.tolist())

    print("\nClassification report (best checkpoint):")
    print(classification_report(all_true, all_preds, target_names=STANCE_LABELS, zero_division=0))

    return best_macro_f1


def _save(model, tokenizer, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    config_path = out_dir / "stance_config.json"
    with config_path.open("w", encoding="utf-8") as f:
        json.dump({"labels": STANCE_LABELS, "label2id": LABEL2ID, "id2label": ID2LABEL}, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Train lotte_stance 3-class KoELECTRA classifier")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="Directory containing labeled CSVs")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory for model artifacts")
    parser.add_argument("--epochs", type=int, default=DEFAULT_STANCE_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_STANCE_LR)
    parser.add_argument("--batch", type=int, default=DEFAULT_STANCE_BATCH_SIZE)
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
