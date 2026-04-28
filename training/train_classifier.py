"""
KoELECTRA-small fine-tuning — 롯데 자이언츠 뉴스 분류 모델.

입력: 제목(segment A) + description_snippet(segment B) — 두 세그먼트 분리 입력
출력: 8-class 분류

핵심 설계 결정:
  - tokenizer(title, description) 형태로 두 세그먼트를 분리하여
    [CLS] title [SEP] description [SEP] 구조로 인코딩
  - 클래스 불균형(최대 8.8배) 대응: CrossEntropyLoss(weight=inverse_freq)
  - 학습률 warmup 10% + linear decay
  - best val macro-F1 기준 체크포인트 저장

사용:
    cd lotte-insight
    pip install -r training/requirements.txt
    python training/train_classifier.py
    python training/train_classifier.py --epochs 10 --lr 5e-5
    python training/train_classifier.py --eval-only
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
from sklearn.preprocessing import LabelEncoder
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

# ── 경로 ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
_DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models" / "classifier_koelectra"

PRETRAINED = "monologg/koelectra-small-v3-discriminator"

VALID_LABELS = [
    "INJURY_ROSTER",
    "TRANSACTION_CONTRACT",
    "MATCH_RELATED",
    "PERFORMANCE_ANALYSIS",
    "INTERVIEW",
    "PLAYER_RELATED",
    "CLUB_OPERATION",
    "ETC",
]

# ── 데이터셋 ──────────────────────────────────────────────────────────────────

class ArticleDataset(Dataset):
    """
    두 세그먼트 입력: tokenizer(title, description)
    → [CLS] title [SEP] description [SEP]
    token_type_ids: 0 for title tokens, 1 for description tokens
    """

    def __init__(
        self,
        titles: list[str],
        descriptions: list[str],
        labels: list[int],
        tokenizer,
        max_len: int = 128,
    ):
        self.encodings = tokenizer(
            titles,
            descriptions,
            truncation="only_second",   # description만 잘라냄
            padding="max_length",
            max_length=max_len,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def load_data() -> tuple[list[str], list[str], list[str]]:
    """
    labeled_titles.csv (팀 파이프라인)과 labeled_players.csv (선수 파이프라인)를
    모두 로드하여 합친다. 둘 다 없으면 오류.
    """
    csv_files = [
        _DATA_DIR / "labeled_titles.csv",
        _DATA_DIR / "labeled_players.csv",
    ]
    frames = []
    for p in csv_files:
        if not p.exists():
            print(f"  건너뜀: {p.name} 없음")
            continue
        df = pd.read_csv(p, encoding="utf-8-sig")
        if p.name == "labeled_players.csv":
            before = len(df)
            df = df[df["is_lotte_related"].astype(str).str.lower() == "true"]
            print(f"  로드: {p.name}  ({len(df)}건, is_lotte_related 필터 후 {before - len(df)}건 제외)")
        else:
            print(f"  로드: {p.name}  ({len(df)}건)")
        frames.append(df)

    if not frames:
        raise FileNotFoundError(f"학습 데이터 없음: {_DATA_DIR}")

    df = pd.concat(frames, ignore_index=True)
    df = df[df["primary_label"].isin(VALID_LABELS)].copy()
    df = df.drop_duplicates(subset=["title"]).reset_index(drop=True)
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["description_snippet"] = (
        df["description_snippet"].fillna("").astype(str).str[:120].str.strip()
    )

    titles = df["title"].tolist()
    descriptions = df["description_snippet"].tolist()
    labels = df["primary_label"].tolist()

    print(f"\n총 유효 데이터: {len(titles)}건 (중복 제거 후)")
    dist = pd.Series(labels).value_counts()
    for label in VALID_LABELS:
        print(f"  {label:<25} {dist.get(label, 0):>4}건")

    return titles, descriptions, labels


def compute_class_weights(labels: list[str], le: LabelEncoder) -> torch.Tensor:
    """역빈도 가중치: weight_i = total / (num_classes * count_i)"""
    encoded = le.transform(labels)
    counts = np.bincount(encoded, minlength=len(le.classes_)).astype(float)
    total = counts.sum()
    weights = total / (len(counts) * counts)
    weights = np.clip(weights, 0.5, 5.0)   # 극단값 제한
    print("\n클래스 가중치:")
    for i, cls in enumerate(le.classes_):
        print(f"  {cls:<25} {weights[i]:.3f}")
    return torch.tensor(weights, dtype=torch.float)


# ── 학습 ─────────────────────────────────────────────────────────────────────

def train(
    epochs: int = 5,
    lr: float = 5e-5,
    batch_size: int = 16,
    warmup_ratio: float = 0.1,
    seed: int = 42,
):
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n디바이스: {device}")

    titles, descriptions, raw_labels = load_data()

    le = LabelEncoder()
    le.fit(VALID_LABELS)
    int_labels = le.transform(raw_labels).tolist()

    tr_t, va_t, tr_d, va_d, tr_l, va_l = train_test_split(
        titles, descriptions, int_labels,
        test_size=0.15,
        random_state=seed,
        stratify=int_labels,
    )
    print(f"\n학습: {len(tr_t)}건  검증: {len(va_t)}건")

    tokenizer = AutoTokenizer.from_pretrained(PRETRAINED)
    model = AutoModelForSequenceClassification.from_pretrained(
        PRETRAINED, num_labels=len(le.classes_)
    ).to(device)

    train_ds = ArticleDataset(tr_t, tr_d, tr_l, tokenizer)
    val_ds   = ArticleDataset(va_t, va_d, va_l, tokenizer)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size)

    class_weights = compute_class_weights(raw_labels, le).to(device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = len(train_loader) * epochs
    warmup_steps = int(total_steps * warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    best_f1 = 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for batch in train_loader:
            labels_batch = batch.pop("labels").to(device)
            batch = {k: v.to(device) for k, v in batch.items()}
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
                batch = {k: v.to(device) for k, v in batch.items()}
                preds = model(**batch).logits.argmax(dim=-1).cpu().numpy()
                all_preds.extend(preds)
                all_true.extend(labels_batch.cpu().numpy())

        macro_f1 = f1_score(all_true, all_preds, average="macro", zero_division=0)
        print(f"Epoch {epoch}/{epochs}  loss={avg_loss:.4f}  val_macro_F1={macro_f1:.4f}")

        if macro_f1 > best_f1:
            best_f1 = macro_f1
            _save(model, tokenizer, le, MODEL_DIR)
            print(f"  → 최고 F1 갱신, 저장 완료")

    print(f"\n학습 완료 — 최고 val macro F1: {best_f1:.4f}")
    return best_f1


# ── 평가 ─────────────────────────────────────────────────────────────────────

def evaluate():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    titles, descriptions, raw_labels = load_data()
    tokenizer, model, le = _load(MODEL_DIR, device)

    int_labels = le.transform(raw_labels).tolist()
    ds = ArticleDataset(titles, descriptions, int_labels, tokenizer)
    loader = DataLoader(ds, batch_size=32)

    model.eval()
    all_preds, all_true = [], []
    with torch.no_grad():
        for batch in loader:
            batch.pop("labels")
            batch = {k: v.to(device) for k, v in batch.items()}
            all_preds.extend(model(**batch).logits.argmax(dim=-1).cpu().numpy())
    all_true = int_labels

    print("\n── Classification Report ─────────────────────────────────────")
    print(classification_report(all_true, all_preds, target_names=le.classes_, zero_division=0))


# ── 저장 / 로드 ───────────────────────────────────────────────────────────────

def _save(model, tokenizer, le: LabelEncoder, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    with open(out_dir / "label_encoder.json", "w", encoding="utf-8") as f:
        json.dump(le.classes_.tolist(), f, ensure_ascii=False)


def _load(model_dir: Path, device):
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    with open(model_dir / "label_encoder.json", encoding="utf-8") as f:
        classes = json.load(f)
    le = LabelEncoder()
    le.classes_ = np.array(classes)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(device)
    return tokenizer, model, le


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",    type=int,   default=5)
    parser.add_argument("--lr",        type=float, default=5e-5)
    parser.add_argument("--batch",     type=int,   default=16)
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args()

    if args.eval_only:
        evaluate()
    else:
        best_f1 = train(epochs=args.epochs, lr=args.lr, batch_size=args.batch)
        print("\n── 전체 데이터 최종 평가 ──")
        evaluate()
        if best_f1 < 0.70:
            print(f"\n[경고] macro F1 {best_f1:.4f} < 0.70 목표 미달")
            print("  → 권장: --epochs 10 --lr 5e-5 또는 데이터 추가")


if __name__ == "__main__":
    main()
