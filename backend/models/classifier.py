"""
News article classifier.

The classifier uses only `title + description_snippet` so inference matches
the documented training contract.
"""

import json
import logging
from pathlib import Path

from core.config import settings
from models.runtime import LazyArtifactsLoader, ModelArtifacts

logger = logging.getLogger(__name__)


def _load_classifier_artifacts(model_dir: Path) -> ModelArtifacts:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(device)
    model.eval()

    with open(model_dir / "label_encoder.json", encoding="utf-8") as file:
        label_classes = json.load(file)

    thresholds_path = model_dir / "label_thresholds.json"
    if thresholds_path.exists():
        with open(thresholds_path, encoding="utf-8") as file:
            label_thresholds: dict[str, float] = json.load(file)
    else:
        label_thresholds = {}

    logger.info("Loaded classifier model from %s", model_dir)
    return ModelArtifacts(
        model=model,
        tokenizer=tokenizer,
        device=device,
        extras={"label_classes": label_classes, "label_thresholds": label_thresholds},
    )


_runtime = LazyArtifactsLoader(
    current_file=__file__,
    env_var="CLASSIFIER_MODEL_DIR",
    deployed_dir_name="classifier_koelectra",
    training_dir_name="classifier_koelectra",
    required_file="label_encoder.json",
    loader=_load_classifier_artifacts,
    missing_log="Classifier model not found; using keyword fallback.",
    error_log="Failed to load classifier model (%s); using keyword fallback.",
)

_LABEL_RULES: list[tuple[str, list[str]]] = [
    ("INJURY_ROSTER", [
        "부상", "재활", "엔트리", "말소", "콜업", "등록", "입원", "수술",
        "회복", "복귀", "골절", "허리", "1군 말소", "2군", "부상자 명단",
    ]),
    ("TRANSACTION_CONTRACT", [
        "영입", "방출", "트레이드", "계약", "FA", "자유계약", "이적",
        "연봉", "재계약", "입단", "웨이버",
    ]),
    ("MATCH_RELATED", [
        "경기", "승리", "패배", "무승부", "역전패", "부진", "타선",
        "홈런", "안타", "삼진", "볼넷", "득점", "실점", "연전",
        "선발", "투수", "세이브", "블론", "vs",
    ]),
    ("PERFORMANCE_ANALYSIS", [
        "타율", "OPS", "ERA", "기록", "분석", "성적", "지표", "순위",
        "WAR", "wRC", "WHIP", "홈런왕", "출루율", "장타율",
    ]),
    ("INTERVIEW", [
        "인터뷰", "말했다", "밝혔다", "강조했다", "설명했다",
        "감독", "코치", "발언", "소감", "각오",
    ]),
    ("CLUB_OPERATION", [
        "구단", "구장", "행사", "이벤트", "팬서비스", "사직구장",
        "원정길", "관중", "입장권",
    ]),
]


def _keyword_classify(text: str) -> dict:
    for label, keywords in _LABEL_RULES:
        if any(keyword in text for keyword in keywords):
            return {"label": label, "confidence": 0.6, "secondary_labels": []}
    return {"label": "ETC", "confidence": 0.5, "secondary_labels": []}


def _build_auxiliary_text(description_snippet: str) -> str:
    return description_snippet[: settings.article_description_snippet_length].strip()


def classify(title: str, description_snippet: str = "") -> dict:
    """
    Returns:
        {"label": str, "confidence": float, "secondary_labels": list[str]}
    """
    runtime = _runtime.get()
    auxiliary_text = _build_auxiliary_text(description_snippet)
    text = (title + " " + auxiliary_text).strip()

    if runtime is None or runtime.model is None or runtime.tokenizer is None:
        return _keyword_classify(text)

    try:
        import torch

        encoded = runtime.tokenizer(
            title,
            auxiliary_text,
            truncation="only_second",
            padding="max_length",
            max_length=128,
            return_tensors="pt",
        )
        encoded = {key: value.to(runtime.device) for key, value in encoded.items()}

        with torch.no_grad():
            logits = runtime.model(**encoded).logits[0]
            probs = torch.sigmoid(logits).cpu().numpy()

        label_classes: list[str] = runtime.extras["label_classes"]
        label_thresholds: dict[str, float] = runtime.extras.get("label_thresholds", {})
        active = sorted(
            [
                (index, float(prob))
                for index, prob in enumerate(probs)
                if prob >= label_thresholds.get(label_classes[index], 0.5)
            ],
            key=lambda item: item[1],
            reverse=True,
        )

        if not active:
            top_index = (
                label_classes.index("ETC")
                if "ETC" in label_classes
                else int(probs.argmax())
            )
            label = "ETC"
            confidence = float(probs[top_index])
            secondary_labels: list[str] = []
        else:
            top_index, confidence = active[0]
            label = label_classes[top_index]
            if label == "ETC":
                non_etc = [(index, prob) for index, prob in active if label_classes[index] != "ETC"]
                if non_etc:
                    top_index, confidence = non_etc[0]
                    label = label_classes[top_index]
            secondary_labels = [label_classes[index] for index, _ in active if index != top_index]

        return {
            "label": label,
            "confidence": round(confidence, 4),
            "secondary_labels": secondary_labels,
        }
    except Exception as exc:
        logger.error("Classifier inference failed (%s); using keyword fallback.", exc)
        return _keyword_classify(text)
