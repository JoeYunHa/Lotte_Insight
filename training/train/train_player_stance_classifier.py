"""
Train KoELECTRA 3-class classifier for player_stance.

Labels: negative / neutral / positive
Only uses labeled_players.csv rows where player_stance is not null.
Input: title (seq-A) + query_player + description_snippet (seq-B)
— including the player name lets the model attribute stance to the specific player.

Usage (local):
    python train_player_stance_classifier.py

Usage (Colab/Kaggle):
    python train_player_stance_classifier.py \\
        --data-dir /kaggle/input/<dataset>/ \\
        --output-dir /kaggle/working/player_stance_koelectra/
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from settings import (
    ARTICLE_SNIPPET_LENGTH,
    DATA_DIR,
    DEFAULT_CLASSIFIER_MAX_LENGTH,
    DEFAULT_EVAL_BATCH_SIZE,
    DEFAULT_PLAYER_STANCE_BATCH_SIZE,
    DEFAULT_PLAYER_STANCE_EPOCHS,
    DEFAULT_PLAYER_STANCE_LR,
    DEFAULT_PLAYER_STANCE_PRETRAINED,
    DEFAULT_TRAIN_SEED,
    DEFAULT_TRAIN_WARMUP_RATIO,
    DEFAULT_VALIDATION_SPLIT,
    LABELED_PLAYERS_CSV,
    PLAYER_STANCE_LABELS,
    PLAYER_STANCE_MODEL_DIR,
)

PRETRAINED = DEFAULT_PLAYER_STANCE_PRETRAINED
LABEL2ID = {label: i for i, label in enumerate(PLAYER_STANCE_LABELS)}
ID2LABEL = {i: label for i, label in enumerate(PLAYER_STANCE_LABELS)}
NUM_LABELS = len(PLAYER_STANCE_LABELS)


class PlayerStanceDataset(Dataset):
    def __init__(
        self,
        titles: list[str],
        player_snippets: list[str],
        labels: list[int],
        tokenizer,
        max_len: int = DEFAULT_CLASSIFIER_MAX_LENGTH,
    ):
        # seq-A: title  |  seq-B: query_player + " " + description_snippet
        self.encodings = tokenizer(
            titles,
            player_snippets,
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
    path = (data_dir or DATA_DIR) / LABELED_PLAYERS_CSV.name
    if not path.exists():
        raise FileNotFoundError(f"labeled_players.csv not found: {path}")

    df = pd.read_csv(path, encoding="utf-8-sig")

    required_cols = {"title", "player_stance", "query_player"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"labeled_players.csv missing columns: {missing}")

    before = len(df)
    df = df.dropna(subset=["player_stance"])
    df = df[df["player_stance"].isin(PLAYER_STANCE_LABELS)]
    print(f"Loaded: {path.name} ({len(df)} rows, dropped {before - len(df)})")

    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["query_player"] = df["query_player"].fillna("").astype(str).str.strip()
    df["description_snippet"] = (
        df["description_snippet"].fillna("").astype(str)
        .str[:ARTICLE_SNIPPET_LENGTH].str.strip()
    )
    # seq-B: player name (anchor) + description snippet. event_summary is
    # excluded because it is GPT-generated and unavailable at inference time.
    df["player_snippet"] = (
        df["query_player"] + " " + df["description_snippet"]
    ).str.strip()

    # Drop titles with conflicting player_stance labels (same title+player, different label)
    df["_label_id"] = df["player_stance"].map(LABEL2ID)
    conflict_key = df["title"] + "|||" + df["query_player"]
    conflicting = (
        df.assign(_key=conflict_key)
        .groupby("_key")["_label_id"].nunique()
        .loc[lambda c: c > 1].index
    )
    if len(conflicting) > 0:
        print(f"  WARNING: dropping {len(conflicting)} (title+player) pairs with conflicting labels")
        mask = (conflict_key).isin(conflicting)
        df = df[~mask].reset_index(drop=True)

    df = df.drop_duplicates(subset=["title", "query_player"]).reset_index(drop=True)

    labels = df["player_stance"].map(LABEL2ID).tolist()
    print(f"\nTotal: {len(labels)} rows")
    for label in PLAYER_STANCE_LABELS:
        count = labels.count(LABEL2ID[label])
        print(f"  {label:>10}: {count:>5}")

    return df["title"].tolist(), df["player_snippet"].tolist(), labels


def compute_class_weights(labels: list[int]) -> torch.Tensor:
    counts = np.bincount(labels, minlength=NUM_LABELS).astype(float)
    if np.any(counts == 0):
        missing = [PLAYER_STANCE_LABELS[i] for i, c in enumerate(counts) if c == 0]
        raise ValueError(f"Training split is missing player_stance classes: {missing}")
    total = counts.sum()
    weights = total / (NUM_LABELS * counts)
    weights = np.clip(weights, 0.3, 5.0)
    print(f"\nClass weights: {dict(zip(PLAYER_STANCE_LABELS, weights.round(3).tolist()))}")
    return torch.tensor(weights, dtype=torch.float)


def train(
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    epochs: int = DEFAULT_PLAYER_STANCE_EPOCHS,
    lr: float = DEFAULT_PLAYER_STANCE_LR,
    batch_size: int = DEFAULT_PLAYER_STANCE_BATCH_SIZE,
    pretrained: str = PRETRAINED,
    max_length: int = DEFAULT_CLASSIFIER_MAX_LENGTH,
    warmup_ratio: float = DEFAULT_TRAIN_WARMUP_RATIO,
    seed: int = DEFAULT_TRAIN_SEED,
):
    from sklearn.metrics import classification_report, f1_score
    from sklearn.model_selection import train_test_split
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        get_linear_schedule_with_warmup,
    )

    out_dir = output_dir or PLAYER_STANCE_MODEL_DIR
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")

    titles, player_snippets, labels = load_data(data_dir)

    tr_t, va_t, tr_ps, va_ps, tr_l, va_l = train_test_split(
        titles, player_snippets, labels,
        test_size=DEFAULT_VALIDATION_SPLIT,
        random_state=seed,
        stratify=labels,
    )
    print(f"\nTrain: {len(tr_t)} rows  Validation: {len(va_t)} rows")

    tokenizer = AutoTokenizer.from_pretrained(pretrained)
    model = AutoModelForSequenceClassification.from_pretrained(
        pretrained,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    ).to(device)

    pin = device.type == "cuda"
    num_workers = 2 if device.type == "cuda" else 0
    train_ds = PlayerStanceDataset(tr_t, tr_ps, tr_l, tokenizer, max_len=max_length)
    val_ds = PlayerStanceDataset(va_t, va_ps, va_l, tokenizer, max_len=max_length)
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
    print(classification_report(all_true, all_preds, target_names=PLAYER_STANCE_LABELS, zero_division=0))

    return best_macro_f1


def _save(model, tokenizer, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    config_path = out_dir / "player_stance_config.json"
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(
            {"labels": PLAYER_STANCE_LABELS, "label2id": LABEL2ID, "id2label": ID2LABEL},
            f, indent=2, ensure_ascii=False,
        )


def main():
    parser = argparse.ArgumentParser(description="Train player_stance 3-class KoELECTRA classifier")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="Directory containing labeled_players.csv")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory for model artifacts")
    parser.add_argument("--epochs", type=int, default=DEFAULT_PLAYER_STANCE_EPOCHS)
    parser.add_argument("--lr", type=float, default=DEFAULT_PLAYER_STANCE_LR)
    parser.add_argument("--batch", type=int, default=DEFAULT_PLAYER_STANCE_BATCH_SIZE)
    parser.add_argument("--pretrained", default=PRETRAINED,
                        help="Base model name, e.g. klue/roberta-large")
    parser.add_argument("--max-length", type=int, default=DEFAULT_CLASSIFIER_MAX_LENGTH)
    args = parser.parse_args()

    train(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch,
        pretrained=args.pretrained,
        max_length=args.max_length,
    )


if __name__ == "__main__":
    main()
