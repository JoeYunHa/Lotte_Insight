"""
뉴스 기사 분류기.

fine-tuned KoELECTRA 모델이 MODEL_DIR에 있으면 로드하여 추론한다.
모델이 없으면 keyword 규칙 기반 폴백으로 동작한다.

MODEL_DIR 탐색 순서:
  1. 환경변수 CLASSIFIER_MODEL_DIR
  2. backend/models/classifier_koelectra/  (배포 시 위치)
  3. training/models/classifier_koelectra/ (로컬 학습 결과)
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 경로 ─────────────────────────────────────────────────────────────────────

_THIS_DIR = Path(__file__).parent
_BACKEND_DIR = _THIS_DIR.parent
_REPO_ROOT = _BACKEND_DIR.parent

_CANDIDATE_DIRS = [
    os.environ.get("CLASSIFIER_MODEL_DIR", ""),
    str(_THIS_DIR / "classifier_koelectra"),
    str(_REPO_ROOT / "training" / "models" / "classifier_koelectra"),
]


def _find_model_dir() -> Path | None:
    for d in _CANDIDATE_DIRS:
        if d and (Path(d) / "label_encoder.json").exists():
            return Path(d)
    return None


# ── 모델 로드 (lazy, 프로세스당 1회) ─────────────────────────────────────────

_model = None
_tokenizer = None
_le_classes: list[str] = []
_device = None
_model_loaded = False


def _load_model():
    global _model, _tokenizer, _le_classes, _device, _model_loaded
    if _model_loaded:
        return

    model_dir = _find_model_dir()
    if model_dir is None:
        logger.warning("KoELECTRA 모델 없음 — keyword 폴백 사용")
        _model_loaded = True
        return

    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        _model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(_device)
        _model.eval()

        with open(model_dir / "label_encoder.json", encoding="utf-8") as f:
            _le_classes = json.load(f)

        logger.info(f"분류 모델 로드 완료: {model_dir}  labels={_le_classes}")
    except Exception as e:
        logger.error(f"모델 로드 실패 ({e}) — keyword 폴백 사용")
        _model = None

    _model_loaded = True


# ── keyword 폴백 ──────────────────────────────────────────────────────────────

_LABEL_RULES: list[tuple[str, list[str]]] = [
    ("INJURY_ROSTER", [
        "부상", "재활", "엔트리", "말소", "콜업", "등록", "입원", "수술",
        "회복", "통증", "골절", "인대", "1군 말소", "2군", "부상자 명단",
    ]),
    ("TRANSACTION_CONTRACT", [
        "영입", "방출", "트레이드", "계약", "FA", "자유계약", "이적",
        "연봉", "다년계약", "입단", "웨이버",
    ]),
    ("MATCH_RELATED", [
        "경기", "승리", "패배", "무승부", "선발", "불펜", "타선",
        "홈런", "안타", "삼진", "볼넷", "실점", "득점", "역전",
        "완투", "완봉", "세이브", "블론", "vs",
    ]),
    ("PERFORMANCE_ANALYSIS", [
        "타율", "OPS", "ERA", "기록", "분석", "성적", "지표", "순위",
        "WAR", "wRC", "WHIP", "피홈런", "출루율", "장타율",
    ]),
    ("INTERVIEW", [
        "인터뷰", "말했다", "밝혔다", "강조했다", "설명했다",
        "감독", "코치", "발언", "소감", "각오",
    ]),
    ("PLAYER_RELATED", [
        "선수", "활약", "복귀", "합류", "화제", "주목",
    ]),
    ("CLUB_OPERATION", [
        "구단", "구장", "팬", "이벤트", "행사", "사직구장",
        "홈경기", "관중", "입장권",
    ]),
]


def _keyword_classify(text: str) -> dict:
    for label, keywords in _LABEL_RULES:
        if any(kw in text for kw in keywords):
            return {"label": label, "confidence": 0.6, "secondary_labels": []}
    return {"label": "ETC", "confidence": 0.5, "secondary_labels": []}


def _build_auxiliary_text(description_snippet: str, event_summary: str = "") -> str:
    parts: list[str] = []

    snippet = description_snippet[:120].strip()
    if snippet:
        parts.append(snippet)

    summary = event_summary.strip()
    if summary:
        parts.append(f"요약: {summary}")

    return " [요약정보] ".join(parts)


# ── public API ────────────────────────────────────────────────────────────────

def classify(title: str, description_snippet: str = "", event_summary: str = "") -> dict:
    """
    Returns:
        {"label": str, "confidence": float, "secondary_labels": list[str]}
    """
    _load_model()

    auxiliary_text = _build_auxiliary_text(description_snippet, event_summary)
    text = (title + " " + auxiliary_text).strip()

    if _model is None or _tokenizer is None:
        return _keyword_classify(text)

    try:
        import torch

        enc = _tokenizer(
            title,
            auxiliary_text,
            truncation="only_second",
            padding="max_length",
            max_length=256,
            return_tensors="pt",
        )
        enc = {k: v.to(_device) for k, v in enc.items()}

        _SIGMOID_THRESHOLD = 0.3

        with torch.no_grad():
            logits = _model(**enc).logits[0]
            probs = torch.sigmoid(logits).cpu().numpy()

        active = sorted(
            [(i, float(p)) for i, p in enumerate(probs) if p >= _SIGMOID_THRESHOLD],
            key=lambda x: x[1],
            reverse=True,
        )

        if not active:
            label = "ETC"
            top_idx = _le_classes.index("ETC") if "ETC" in _le_classes else int(probs.argmax())
            top_conf = float(probs[top_idx])
            secondary: list[str] = []
        else:
            top_idx, top_conf = active[0]
            label = _le_classes[top_idx]

            # ETC cleanup: prefer non-ETC when other labels are active
            if label == "ETC":
                non_etc = [(i, p) for i, p in active if _le_classes[i] != "ETC"]
                if non_etc:
                    top_idx, top_conf = non_etc[0]
                    label = _le_classes[top_idx]

            secondary = [_le_classes[i] for i, _ in active if i != top_idx]

        return {"label": label, "confidence": round(top_conf, 4), "secondary_labels": secondary}

    except Exception as e:
        logger.error(f"모델 추론 실패 ({e}) — keyword 폴백")
        return _keyword_classify(text)
