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
from models.runtime import LazyArtifactsLoader, ModelArtifacts

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


def _build_player_snippet(player_name: str, description_snippet: str) -> str:
    snippet = (description_snippet or "")[: settings.article_description_snippet_length].strip()
    if player_name:
        return f"{player_name} {snippet}".strip()
    return snippet


def classify_player_stance(
    title: str,
    description_snippet: str = "",
    player_name: str = "",
) -> dict:
    """
    Returns {label, confidence, source} for the given article and player.
    label is None (not 'neutral') when the model is unavailable.
    """
    artifacts = _runtime.get()
    if artifacts is None:
        return dict(_NOT_APPLICABLE)

    try:
        import torch

        labels = artifacts.extras.get("labels") or _DEFAULT_LABELS
        player_snippet = _build_player_snippet(player_name, description_snippet)
        enc = artifacts.tokenizer(
            title,
            player_snippet,
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

    import torch

    labels = artifacts.extras.get("labels") or _DEFAULT_LABELS
    results: list[dict] = [dict(_MODEL_ERROR)] * len(articles)

    for start in range(0, len(articles), _CHUNK_SIZE):
        end = start + _CHUNK_SIZE
        chunk = articles[start:end]
        titles = [a["title"] for a in chunk]
        player_snippets = [
            _build_player_snippet(a.get("player_name", ""), a.get("description_snippet", ""))
            for a in chunk
        ]
        try:
            enc = artifacts.tokenizer(
                titles,
                player_snippets,
                truncation="only_second",
                padding=True,
                max_length=128,
                return_tensors="pt",
            )
            enc = {k: v.to(artifacts.device) for k, v in enc.items()}

            with torch.no_grad():
                logits = artifacts.model(**enc).logits
                probs_batch = torch.softmax(logits, dim=-1).cpu().tolist()

            for i, probs in enumerate(probs_batch):
                best_idx = int(max(range(len(probs)), key=lambda j: probs[j]))
                results[start + i] = {
                    "label": labels[best_idx],
                    "confidence": round(probs[best_idx], 4),
                    "source": "koelectra",
                }
        except Exception as exc:
            logger.error(
                "Player stance batch inference failed for chunk [%d:%d] (%s); returning model_error.",
                start, end, exc,
            )

    return results
