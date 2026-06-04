"""
lotte_related 모델 로컬 성능 평가 스크립트.

평가 데이터: labeled_titles.csv + labeled_players.csv (전체 dedup)
지표: precision / recall / F1 / accuracy @ saved threshold
추가: Colab smoke-test 케이스 + review_lotte_related.csv 리뷰 케이스
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models" / "lotte_related_model"
DATA_DIR = ROOT / "data"

LABELED_TITLES_CSV = DATA_DIR / "labeled_titles.csv"
LABELED_PLAYERS_CSV = DATA_DIR / "labeled_players.csv"
REVIEW_CSV = DATA_DIR / "review_lotte_related.csv"

MAX_LENGTH = 256
SNIPPET_LEN = 300
BATCH_SIZE = 32

VALID_POS = {"true", "1", "yes"}
VALID_NEG = {"false", "0", "no"}

# ── 모델 로드 ──────────────────────────────────────────────────────────────────
def load_model():
    if not (MODEL_DIR / "config.json").exists():
        print(f"[ERROR] 모델을 찾을 수 없습니다: {MODEL_DIR}")
        sys.exit(1)

    thresh_path = MODEL_DIR / "threshold.json"
    threshold = json.load(thresh_path.open(encoding="utf-8"))["threshold"] if thresh_path.exists() else 0.40
    print(f"모델 로드: {MODEL_DIR}")
    print(f"Threshold: {threshold}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR)).to(device)
    model.eval()
    print(f"Device: {device}\n")
    return model, tokenizer, device, threshold


# ── 데이터 로드 ────────────────────────────────────────────────────────────────
def load_data():
    frames = []
    for path in [LABELED_TITLES_CSV, LABELED_PLAYERS_CSV]:
        if not path.exists():
            print(f"  SKIP: {path.name} 없음")
            continue
        df = pd.read_csv(path, encoding="utf-8-sig")
        df = df.dropna(subset=["is_lotte_related"]).copy()
        frames.append(df)
        print(f"  {path.name}: {len(df)}행")

    df = pd.concat(frames, ignore_index=True)
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["description_snippet"] = (
        df["description_snippet"].fillna("").astype(str).str[:SNIPPET_LEN].str.strip()
    )

    raw = df["is_lotte_related"].astype(str).str.strip().str.lower()
    valid_mask = raw.isin(VALID_POS | VALID_NEG)
    df = df[valid_mask].reset_index(drop=True)
    raw = raw[valid_mask].reset_index(drop=True)

    # 충돌 제거
    conflicts = df.groupby("title")["is_lotte_related"].transform(
        lambda s: s.astype(str).str.lower().map(lambda v: "pos" if v in VALID_POS else "neg").nunique()
    )
    df = df[conflicts == 1].reset_index(drop=True)
    raw = raw[df.index] if len(raw) > len(df) else raw.iloc[: len(df)]

    dedup_cols = ["title", "source_name"] if "source_name" in df.columns else ["title"]
    df = df.drop_duplicates(subset=dedup_cols).reset_index(drop=True)

    labels = df["is_lotte_related"].astype(str).str.strip().str.lower().map(
        lambda v: 1 if v in VALID_POS else 0
    ).tolist()
    pos = sum(labels)
    print(f"  최종: {len(labels)}행  True={pos}  False={len(labels)-pos}\n")
    return df["title"].tolist(), df["description_snippet"].tolist(), labels


# ── 추론 ───────────────────────────────────────────────────────────────────────
def run_inference(model, tokenizer, device, titles, snippets):
    all_probs = []
    for start in range(0, len(titles), BATCH_SIZE):
        batch_t = titles[start : start + BATCH_SIZE]
        batch_s = snippets[start : start + BATCH_SIZE]
        enc = tokenizer(
            batch_t, batch_s,
            truncation="only_second", padding="max_length",
            max_length=MAX_LENGTH, return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            logits = model(**enc).logits[:, 0]
            probs = torch.sigmoid(logits).cpu().tolist()
        all_probs.extend(probs)
        print(f"\r  추론 중... {min(start+BATCH_SIZE, len(titles))}/{len(titles)}", end="")
    print()
    return all_probs


# ── 스모크 테스트 ──────────────────────────────────────────────────────────────
SMOKE_TRUE = [
    ("롯데 나균안, 시즌 5승…선발 로테이션 안정화", "나균안이 두산전 6이닝 2실점 호투로 시즌 5승을 달성했다."),
    ("롯데 전준우 햄스트링 부상, 2주 결장", "전준우가 1군 엔트리에서 말소됐다."),
    ("사직구장 개막전 팬 3만 명 몰려", "롯데 자이언츠 홈 개막전 이벤트 성황리에 마무리됐다."),
    ("롯데, 외국인 투수 교체 결정", "롯데가 부진한 외국인 투수를 방출하고 새 용병을 물색 중이다."),
    ("롯데 구단, 스프링캠프 일정 발표", "롯데 자이언츠가 2026 스프링캠프 일정을 공개했다."),
    ("자이언츠 타선, 최근 5경기 연속 5점 이상", "롯데 타선이 최근 5경기에서 안정적인 득점력을 보여주고 있다."),
]
SMOKE_FALSE = [
    ("롯데백화점, 봄 세일 시작", "롯데백화점이 봄 할인 행사를 시작했다."),
    ("롯데월드, 신규 어트랙션 공개", "롯데월드가 여름 신규 놀이기구를 선보였다."),
    ("삼성 라이온즈, KIA 잡고 선두 탈환", "KIA 타이거즈가 삼성에 패해 2위로 내려앉았다."),
    ("두산 베어스, FA 대어 영입 확정", "두산이 거액의 FA 계약을 체결했다."),
    ("롯데칠성음료 실적 개선…주가 반등", "롯데칠성음료가 2분기 깜짝 실적으로 주가가 상승세를 보이고 있다."),
]


def run_smoke_test(model, tokenizer, device, threshold):
    print("=" * 60)
    print("스모크 테스트 (정성 평가)")
    print("=" * 60)

    def predict(title, snippet=""):
        enc = tokenizer(
            title, snippet[:SNIPPET_LEN],
            truncation="only_second", padding="max_length",
            max_length=MAX_LENGTH, return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            prob = float(torch.sigmoid(model(**enc).logits[0, 0]))
        return prob >= threshold, round(prob, 4)

    ok = 0
    total = len(SMOKE_TRUE) + len(SMOKE_FALSE)

    print(f"\n[True여야 할 케이스] (threshold={threshold})")
    for title, snippet in SMOKE_TRUE:
        related, prob = predict(title, snippet)
        mark = "O" if related else "X"
        ok += int(related)
        print(f"  {mark} prob={prob:.4f}  {title}")

    print(f"\n[False여야 할 케이스]")
    for title, snippet in SMOKE_FALSE:
        related, prob = predict(title, snippet)
        mark = "O" if not related else "X"
        ok += int(not related)
        print(f"  {mark} prob={prob:.4f}  {title}")

    print(f"\n스모크 결과: {ok}/{total} 통과\n")


# ── review_lotte_related.csv 케이스 ───────────────────────────────────────────
def run_review_eval(model, tokenizer, device, threshold):
    if not REVIEW_CSV.exists():
        return
    df = pd.read_csv(REVIEW_CSV, encoding="utf-8-sig")
    if "original_value" not in df.columns or "gpt_value" not in df.columns:
        return

    print("=" * 60)
    print("리뷰 케이스 평가 (GPT 교정 기준)")
    print("=" * 60)

    # corrected_value 우선, 없으면 gpt_value
    def get_label(row):
        for col in ["corrected_value", "gpt_value", "original_value"]:
            v = str(row.get(col, "")).strip().lower()
            if v in VALID_POS:
                return 1
            if v in VALID_NEG:
                return 0
        return None

    rows = []
    for _, row in df.iterrows():
        label = get_label(row)
        if label is None:
            continue
        rows.append({
            "title": str(row.get("title", "")).strip(),
            "snippet": str(row.get("description_snippet", ""))[:SNIPPET_LEN].strip(),
            "label": label,
        })

    if not rows:
        print("  유효한 데이터 없음\n")
        return

    ok = 0
    for r in rows:
        enc = tokenizer(
            r["title"], r["snippet"],
            truncation="only_second", padding="max_length",
            max_length=MAX_LENGTH, return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            prob = float(torch.sigmoid(model(**enc).logits[0, 0]))
        pred = int(prob >= threshold)
        correct = pred == r["label"]
        ok += int(correct)
        mark = "O" if correct else "X"
        expected = "True" if r["label"] == 1 else "False"
        print(f"  {mark} prob={prob:.4f}  [{expected}]  {r['title'][:60]}")

    print(f"\n리뷰 케이스 결과: {ok}/{len(rows)} 정확\n")


# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("lotte_related 모델 성능 평가")
    print("=" * 60)
    print()

    model, tokenizer, device, threshold = load_model()

    # 1. 스모크 테스트
    run_smoke_test(model, tokenizer, device, threshold)

    # 2. review_lotte_related 케이스
    run_review_eval(model, tokenizer, device, threshold)

    # 3. 전체 데이터셋 정량 평가
    print("=" * 60)
    print("정량 평가 (labeled_titles + labeled_players)")
    print("=" * 60)
    print()
    titles, snippets, labels = load_data()

    probs = run_inference(model, tokenizer, device, titles, snippets)
    probs_arr = np.array(probs)
    labels_arr = np.array(labels)

    preds = (probs_arr >= threshold).astype(int)

    print(f"\n[Saved Threshold: {threshold}]")
    print(classification_report(labels_arr, preds, target_names=["False", "True"], digits=4))

    cm = confusion_matrix(labels_arr, preds)
    print(f"Confusion Matrix:\n  TN={cm[0,0]}  FP={cm[0,1]}\n  FN={cm[1,0]}  TP={cm[1,1]}")

    try:
        auc = roc_auc_score(labels_arr, probs_arr)
        print(f"\nROC-AUC: {auc:.4f}")
    except Exception:
        pass

    # 최적 threshold 탐색
    print("\n[Threshold 탐색 — recall ≥ 0.97 기준 최대 precision]")
    precision_arr, recall_arr, thresholds = precision_recall_curve(labels_arr, probs_arr)
    valid = [
        (float(t), float(r), float(p))
        for t, r, p in zip(thresholds, recall_arr[:-1], precision_arr[:-1])
        if r >= 0.97
    ]
    if valid:
        best_t, best_r, best_p = max(valid, key=lambda x: x[2])
        print(f"  최적 threshold={best_t:.4f}  recall={best_r:.4f}  precision={best_p:.4f}")
        if abs(best_t - threshold) > 0.01:
            print(f"  → 저장된 threshold({threshold})와 차이 있음: 재조정 고려")
    else:
        best_idx = int(np.argmax(recall_arr[:-1]))
        print(f"  recall 0.97 달성 불가 — 최고 recall={recall_arr[best_idx]:.4f} @ t={thresholds[best_idx]:.4f}")

    # 오분류 샘플
    errors = [(titles[i], snippets[i], labels[i], probs[i]) for i in range(len(titles)) if preds[i] != labels[i]]
    if errors:
        fn = [(t, s, p) for t, s, l, p in errors if l == 1]
        fp = [(t, s, p) for t, s, l, p in errors if l == 0]
        print(f"\n[오분류 {len(errors)}건: FP={len(fp)}  FN={len(fn)}]")
        if fn:
            print("  FN (놓친 롯데 기사) 상위 5:")
            for t, s, p in sorted(fn, key=lambda x: x[2])[:5]:
                print(f"    prob={p:.4f}  {t[:70]}")
        if fp:
            print("  FP (잘못 분류된 비롯데 기사) 상위 5:")
            for t, s, p in sorted(fp, key=lambda x: -x[2])[:5]:
                print(f"    prob={p:.4f}  {t[:70]}")

    print("\n평가 완료.")


if __name__ == "__main__":
    main()
