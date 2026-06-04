"""
Hybrid is_lotte_related gate.

Detection order:
  1. Rule-based strong keywords → immediate True
  2. Rule-based weak keywords (only if no negative words match) → True
  3. Player name + unambiguous baseball context co-occurrence → True
  4. KoELECTRA binary classifier (threshold from threshold.json, fallback to config)
  5. Graceful degradation: if no model, rule-only (unmatched → False)
"""

import logging
from pathlib import Path

from core.config import settings
from models.runtime import CLASSIFIER_MAX_LEN, LazyArtifactsLoader, ModelArtifacts

logger = logging.getLogger(__name__)

# Unambiguous Lotte Giants phrases — immediate True regardless of negative words
_STRONG_KEYWORDS: tuple[str, ...] = (
    "롯데 자이언츠",
    "자이언츠",
    "롯데전",
    "자이언츠전",
    "사직구장",
    "사직야구장",
    "사직 원정",
    "부산 야구",
    "롯데 야구",
    "KBO 롯데",
    "롯데 선발",
    "롯데 타선",
    "롯데 불펜",
    "롯데 감독",
    "롯데 구단",
    "롯데 팬",
    "롯데 선수",
    "롯데 투수",
    "롯데 타자",
    "롯데 홈런",
    "롯데 안타",
    "롯데 승리",
    "롯데 패배",
    "롯데 FA",
    "롯데 트레이드",
    "롯데 외국인",
    "롯데 드래프트",
    "롯데 1군",
    "롯데 엔트리",
    "롯데 콜업",
)

# Single-token weak keywords — True only when no negative word is detected
_WEAK_KEYWORDS: tuple[str, ...] = (
    "롯데",
)

# Commercial / non-baseball Lotte entities that block weak keyword matching
_NEGATIVE_WORDS: frozenset[str] = frozenset({
    "롯데월드",
    "롯데백화점",
    "롯데마트",
    "롯데호텔",
    "롯데칠성",
    "롯데케미칼",
    "롯데면세점",
    "롯데카드",
    "롯데그룹",
    "롯데건설",
    "롯데쇼핑",
    "롯데렌터카",
    "롯데리아",
    "롯데제과",
    "롯데물산",
    "롯데지주",
    "롯데하이마트",
    "롯데시네마",
    "롯데타워",
    "잠실 롯데",  # 롯데타워/백화점 맥락
    "사직서",
    "사직동",
    "사직로",
})

# Unambiguously baseball terms for player name co-occurrence check
# Excludes "롯데" / "사직" to avoid pollution from commercial contexts
_UNAMBIGUOUS_BASEBALL: frozenset[str] = frozenset({
    "자이언츠",
    "야구",
    "선발",
    "타자",
    "투수",
    "불펜",
    "타선",
    "감독",
    "코치",
    "타율",
    "방어율",
    "홈런",
    "안타",
    "이닝",
    "KBO",
    "1군",
    "2군",
    "엔트리",
    "콜업",
    "FA",
    "트레이드",
    "등판",
    "마무리",
    "중간계투",
    "구원",
    "삼진",
    "볼넷",
    "도루",
    "사직구장",
    "사직야구장",
    "경기 결과",
    "선발 라인업",
    "선발 투수",
    "구원 투수",
})


def _get_player_names() -> list[str]:
    try:
        from services.player_catalog import list_player_names
        return list_player_names(active_only=False)
    except Exception as exc:
        logger.warning("Could not fetch player names for rule detector: %s", exc)
        return []


def rule_based_lotte_detector(text: str, player_names: list[str] | None = None) -> bool:
    """Returns True if text contains a strong Lotte Giants indicator.

    Evaluation order:
      1. Strong multi-word keywords → immediate True
      2. Negative word check → blocks weak-keyword and no-context-player matches
      3. Weak single keywords (if no negative) → True
      4. Player name + unambiguous baseball context (if no negative) → True
    """
    # Strong keywords always win
    for kw in _STRONG_KEYWORDS:
        if kw in text:
            return True

    has_negative = any(neg in text for neg in _NEGATIVE_WORDS)

    # Weak single keywords only when no commercial/non-baseball Lotte context
    if not has_negative:
        for kw in _WEAK_KEYWORDS:
            if kw in text:
                return True

    # Player name match requires unambiguous baseball co-occurrence
    names = player_names if player_names is not None else _get_player_names()
    if not has_negative:
        has_baseball = any(ctx in text for ctx in _UNAMBIGUOUS_BASEBALL)
        if has_baseball:
            for name in names:
                if name and len(name) >= 2 and name in text:
                    return True

    return False


def _load_lotte_related_artifacts(model_dir: Path) -> ModelArtifacts:
    import json
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(device)
    model.eval()

    threshold: float | None = None
    threshold_path = model_dir / "threshold.json"
    if threshold_path.exists():
        with threshold_path.open(encoding="utf-8") as f:
            threshold = json.load(f).get("threshold")
        logger.info("Loaded lotte_related threshold=%.4f from %s", threshold, threshold_path)

    logger.info("Loaded lotte_related classifier from %s", model_dir)
    return ModelArtifacts(model=model, tokenizer=tokenizer, device=device, extras={"threshold": threshold})


_runtime = LazyArtifactsLoader(
    current_file=__file__,
    env_var="LOTTE_RELATED_MODEL_DIR",
    deployed_dir_name="lotte_related_koelectra",
    training_dir_name="lotte_related_koelectra",
    required_file="config.json",
    loader=_load_lotte_related_artifacts,
    missing_log="lotte_related classifier not found; using rule-based detection only.",
    error_log="Failed to load lotte_related classifier (%s); using rule-based detection only.",
)

_INFER_CHUNK_SIZE = 32


def _get_threshold(runtime: ModelArtifacts) -> float:
    """Use threshold.json value when available, fall back to config."""
    saved = runtime.extras.get("threshold")
    if saved is not None:
        return float(saved)
    return settings.is_lotte_related_threshold


def detect_is_lotte_related_batch(articles: list[dict]) -> list[dict]:
    """Batch hybrid detection.

    Each dict must have 'title' and optionally 'description_snippet'.
    Returns list of {"is_lotte_related": bool, "confidence": float, "source": str}.
    """
    if not articles:
        return []

    player_names = _get_player_names()
    results: list[dict | None] = [None] * len(articles)
    rule_pending: list[int] = []

    for i, article in enumerate(articles):
        text = f"{article.get('title', '')} {article.get('description_snippet', '')}"
        if rule_based_lotte_detector(text, player_names):
            results[i] = {"is_lotte_related": True, "confidence": 1.0, "source": "rule"}
        else:
            rule_pending.append(i)

    if not rule_pending:
        return results  # type: ignore[return-value]

    runtime = _runtime.get()
    if runtime is None or runtime.model is None or runtime.tokenizer is None:
        for i in rule_pending:
            results[i] = {"is_lotte_related": False, "confidence": 0.0, "source": "rule_only"}
        return results  # type: ignore[return-value]

    import torch

    threshold = _get_threshold(runtime)
    snippet_len = settings.article_description_snippet_length

    for start in range(0, len(rule_pending), _INFER_CHUNK_SIZE):
        chunk_indices = rule_pending[start : start + _INFER_CHUNK_SIZE]
        titles = [articles[i].get("title", "") for i in chunk_indices]
        snippets = [
            articles[i].get("description_snippet", "")[:snippet_len].strip()
            for i in chunk_indices
        ]
        try:
            encoded = runtime.tokenizer(
                titles,
                snippets,
                truncation="only_second",
                padding="max_length",
                max_length=CLASSIFIER_MAX_LEN,
                return_tensors="pt",
            )
            encoded = {k: v.to(runtime.device) for k, v in encoded.items()}
            with torch.no_grad():
                logits = runtime.model(**encoded).logits[:, 0]
                probs = torch.sigmoid(logits).cpu().tolist()
            for idx, prob in zip(chunk_indices, probs):
                results[idx] = {
                    "is_lotte_related": prob >= threshold,
                    "confidence": round(prob, 4),
                    "source": "classifier",
                }
        except Exception:
            logger.exception(
                "lotte_related batch inference failed [%d:%d]",
                start, start + len(chunk_indices),
            )
            for idx in chunk_indices:
                results[idx] = {"is_lotte_related": False, "confidence": 0.0, "source": "classifier_error"}

    return results  # type: ignore[return-value]


def detect_is_lotte_related(article: dict) -> dict:
    """Single-article hybrid detection."""
    text = f"{article.get('title', '')} {article.get('description_snippet', '')}"
    player_names = _get_player_names()

    if rule_based_lotte_detector(text, player_names):
        return {"is_lotte_related": True, "confidence": 1.0, "source": "rule"}

    runtime = _runtime.get()
    if runtime is None or runtime.model is None or runtime.tokenizer is None:
        return {"is_lotte_related": False, "confidence": 0.0, "source": "rule_only"}

    try:
        import torch

        snippet_len = settings.article_description_snippet_length
        snippet = article.get("description_snippet", "")[:snippet_len].strip()
        encoded = runtime.tokenizer(
            article.get("title", ""),
            snippet,
            truncation="only_second",
            padding="max_length",
            max_length=CLASSIFIER_MAX_LEN,
            return_tensors="pt",
        )
        encoded = {k: v.to(runtime.device) for k, v in encoded.items()}
        with torch.no_grad():
            logit = runtime.model(**encoded).logits[0][0]
            prob = float(torch.sigmoid(logit).cpu())

        threshold = _get_threshold(runtime)
        return {
            "is_lotte_related": prob >= threshold,
            "confidence": round(prob, 4),
            "source": "classifier",
        }
    except Exception:
        logger.exception("lotte_related inference failed")
        return {"is_lotte_related": False, "confidence": 0.0, "source": "classifier_error"}
