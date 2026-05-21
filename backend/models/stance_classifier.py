"""
Lotte stance classifier (negative / neutral / positive).

Only called for articles where is_lotte_related=True.
Falls back to None (not neutral) when the model is unavailable.
"""

import json
import logging
from pathlib import Path

from core.config import settings
from models.runtime import LazyArtifactsLoader, ModelArtifacts

logger = logging.getLogger(__name__)

_DEFAULT_STANCE_LABELS = ["negative", "neutral", "positive"]
_NOT_APPLICABLE = {"label": None, "confidence": 0.0, "source": "not_applicable"}
_MODEL_ERROR = {"label": None, "confidence": 0.0, "source": "model_error"}


def _load_stance_artifacts(model_dir: Path) -> ModelArtifacts:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(device)
    model.eval()
    labels = _DEFAULT_STANCE_LABELS
    config_path = model_dir / "stance_config.json"
    if config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            config = json.load(f)
        labels = list(config.get("labels") or labels)
    elif getattr(model.config, "id2label", None):
        labels = [model.config.id2label[idx] for idx in sorted(model.config.id2label)]
    logger.info("Loaded stance classifier from %s", model_dir)
    return ModelArtifacts(model=model, tokenizer=tokenizer, device=device, extras={"labels": labels})


_runtime = LazyArtifactsLoader(
    current_file=__file__,
    env_var="STANCE_MODEL_DIR",
    deployed_dir_name="stance_koelectra",
    training_dir_name="stance_koelectra",
    required_file="config.json",
    loader=_load_stance_artifacts,
    missing_log="Stance classifier model not found; returning null.",
    error_log="Failed to load stance classifier (%s); returning null.",
)


def classify_stance(title: str, description_snippet: str = "") -> dict:
    """
    Returns {label, confidence, source} for the given article.
    label is None (not 'neutral') when the model is unavailable.
    Only call this for is_lotte_related=True articles.
    """
    artifacts = _runtime.get()
    if artifacts is None:
        return dict(_NOT_APPLICABLE)

    try:
        import torch

        labels = artifacts.extras.get("labels") or _DEFAULT_STANCE_LABELS
        snippet = (description_snippet or "")[: settings.article_description_snippet_length].strip()
        enc = artifacts.tokenizer(
            title,
            snippet,
            truncation="only_second",
            padding="max_length",
            max_length=128,
            return_tensors="pt",
        )
        enc = {k: v.to(artifacts.device) for k, v in enc.items()}

        with torch.no_grad():
            logits = artifacts.model(**enc).logits[0]
            probs = torch.softmax(logits, dim=-1).cpu().tolist()

        best_idx = int(max(range(len(probs)), key=lambda i: probs[i]))
        return {
            "label": labels[best_idx],
            "confidence": round(probs[best_idx], 4),
            "source": "koelectra",
        }
    except Exception as exc:
        logger.error("Stance classification failed: %s", exc)
        return dict(_MODEL_ERROR)
