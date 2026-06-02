"""
Player-level stance classifier (negative / neutral / positive).

Classifies the stance of an article toward a specific named player.
Input: title + player_name + description_snippet.
Falls back to None (not neutral) when the model is unavailable.
"""

import json
import logging
from pathlib import Path

from core.config import settings
from models.runtime import LazyArtifactsLoader, ModelArtifacts, infer_batch, infer_single

logger = logging.getLogger(__name__)

_DEFAULT_LABELS = ["negative", "neutral", "positive"]
_NOT_APPLICABLE = {"label": None, "confidence": 0.0, "source": "not_applicable"}
_MODEL_ERROR = {"label": None, "confidence": 0.0, "source": "model_error"}


def _load_artifacts(model_dir: Path) -> ModelArtifacts:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(device)
    model.eval()
    labels = _DEFAULT_LABELS
    config_path = model_dir / "player_stance_config.json"
    if config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            config = json.load(f)
        labels = list(config.get("labels") or labels)
    elif getattr(model.config, "id2label", None):
        labels = [model.config.id2label[idx] for idx in sorted(model.config.id2label)]
    logger.info("Loaded player stance classifier from %s", model_dir)
    return ModelArtifacts(model=model, tokenizer=tokenizer, device=device, extras={"labels": labels})


_runtime = LazyArtifactsLoader(
    current_file=__file__,
    env_var="PLAYER_STANCE_CLASSIFIER_MODEL_DIR",
    deployed_dir_name="player_stance_koelectra",
    training_dir_name="player_stance_koelectra",
    required_file="config.json",
    loader=_load_artifacts,
    missing_log="Player stance classifier model not found; returning null.",
    error_log="Failed to load player stance classifier (%s); returning null.",
)


def _build_player_snippet(player_name: str, description_snippet: str, event_summary: str = "") -> str:
    snippet = (description_snippet or "")[: settings.article_description_snippet_length].strip()
    summary = (event_summary or "").strip()
    parts = [p for p in [player_name, snippet, summary] if p]
    return " ".join(parts)


def classify_player_stance(
    title: str,
    description_snippet: str = "",
    player_name: str = "",
    event_summary: str = "",
) -> dict:
    """
    Returns {label, confidence, source} for the given article and player.
    label is None (not 'neutral') when the model is unavailable.
    """
    artifacts = _runtime.get()
    if artifacts is None:
        return dict(_NOT_APPLICABLE)

    try:
        labels = artifacts.extras.get("labels") or _DEFAULT_LABELS
        player_snippet = _build_player_snippet(player_name, description_snippet, event_summary)
        return infer_single(artifacts, title, player_snippet, labels)
    except Exception as exc:
        logger.error("Player stance classification failed: %s", exc)
        return dict(_MODEL_ERROR)


_CHUNK_SIZE = 32


def classify_player_stance_batch(articles: list[dict]) -> list[dict]:
    """
    articles: list of {"title": str, "description_snippet": str, "player_name": str}
    Returns list of {label, confidence, source} in the same order.
    """
    if not articles:
        return []

    artifacts = _runtime.get()
    if artifacts is None:
        return [dict(_NOT_APPLICABLE) for _ in articles]

    labels = artifacts.extras.get("labels") or _DEFAULT_LABELS
    pairs = [
        (
            a["title"],
            _build_player_snippet(
                a.get("player_name", ""),
                a.get("description_snippet", ""),
                a.get("event_summary", ""),
            ),
        )
        for a in articles
    ]
    return infer_batch(
        artifacts,
        pairs,
        labels,
        chunk_size=_CHUNK_SIZE,
        error_log_prefix="Player stance batch inference failed",
        module_logger=logger,
    )
