"""
KoBART-backed article summarizer.
"""

import json
import logging
import re
from pathlib import Path

from models.runtime import LazyArtifactsLoader, ModelArtifacts
from services.article_utils import clean_html

logger = logging.getLogger(__name__)

_ARTICLE_SNIPPET_LENGTH = 300
_MAX_SOURCE_LEN = 384
_MAX_TARGET_LEN = 256
_NUM_BEAMS = 6
_LENGTH_PENALTY = 1.2
_NO_REPEAT_NGRAM = 3


def _empty_summary() -> dict:
    return {"event_summary": "", "lotte_stance": "", "key_players": []}


def _load_summarizer_artifacts(model_dir: Path) -> ModelArtifacts:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir)).to(device)
    model.eval()
    logger.info("Loaded summarizer model from %s", model_dir)
    return ModelArtifacts(model=model, tokenizer=tokenizer, device=device)


_runtime = LazyArtifactsLoader(
    current_file=__file__,
    env_var="SUMMARIZER_MODEL_DIR",
    deployed_dir_name="summarizer_kobart",
    training_dir_name="summarizer_kobart",
    required_file="config.json",
    loader=_load_summarizer_artifacts,
    missing_log="Summarizer model not found; skipping event summary generation.",
    error_log="Failed to load summarizer model (%s); skipping event summary generation.",
)


def _regex_extract(text: str) -> dict:
    result: dict = {}
    match = re.search(r'"event_summary"\s*:\s*"([^"]+)"', text)
    if match:
        result["event_summary"] = match.group(1)
    match = re.search(r'"lotte_stance"\s*:\s*"([^"]+)"', text)
    if match:
        result["lotte_stance"] = match.group(1)
    players = re.findall(r'"key_players"\s*:\s*\[([^\]]*)\]', text)
    if players:
        names = re.findall(r'"([^"]+)"', players[0])
        result["key_players"] = [name for name in names if name != "nan"]
    return result


def _extract_first_json(text: str) -> dict | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for index, char in enumerate(text[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : index + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return _regex_extract(candidate)
    return None


def _make_stopping_criteria():
    try:
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        runtime = _runtime.get()
        if runtime is None or runtime.tokenizer is None:
            return None

        class _JsonClosedStopping(StoppingCriteria):
            def __init__(self, tokenizer):
                self._tokenizer = tokenizer

            def __call__(
                self,
                input_ids: "torch.LongTensor",
                scores: "torch.FloatTensor",
                **kwargs,
            ) -> bool:
                text = self._tokenizer.decode(input_ids[0], skip_special_tokens=True)
                depth = 0
                started = False
                for char in text:
                    if char == "{":
                        depth += 1
                        started = True
                    elif char == "}":
                        depth -= 1
                return started and depth <= 0

        return StoppingCriteriaList([_JsonClosedStopping(runtime.tokenizer)])
    except Exception:
        return None


def _build_source_text(
    title: str,
    description_snippet: str,
    primary_label: str,
    published_at: str,
    game_context: str,
) -> str:
    parts = ["news summary:"]
    parts.append(f"title: {clean_html(title.strip())}")
    description = clean_html((description_snippet or "").strip())
    if description:
        parts.append(f"description: {description[:_ARTICLE_SNIPPET_LENGTH]}")
    if published_at:
        parts.append(f"published_at: {published_at.strip()}")
    if primary_label:
        parts.append(f"topic_label: {primary_label.strip()}")
    if game_context:
        parts.append(f"game_context: {game_context.strip()}")
    return "\n".join(parts)


def summarize(
    title: str,
    description_snippet: str = "",
    primary_label: str = "",
    published_at: str = "",
    game_context: str = "",
) -> dict:
    runtime = _runtime.get()
    if runtime is None or runtime.model is None or runtime.tokenizer is None:
        return _empty_summary()

    source = _build_source_text(
        title,
        description_snippet,
        primary_label,
        published_at,
        game_context,
    )

    try:
        import torch

        inputs = runtime.tokenizer(
            source,
            max_length=_MAX_SOURCE_LEN,
            truncation=True,
            return_tensors="pt",
        ).to(runtime.device)

        generation_kwargs: dict = {
            "max_new_tokens": _MAX_TARGET_LEN,
            "num_beams": _NUM_BEAMS,
            "length_penalty": _LENGTH_PENALTY,
            "no_repeat_ngram_size": _NO_REPEAT_NGRAM,
            "early_stopping": True,
        }
        stopping = _make_stopping_criteria()
        if stopping is not None:
            generation_kwargs["stopping_criteria"] = stopping

        with torch.no_grad():
            output_ids = runtime.model.generate(**inputs, **generation_kwargs)

        raw = runtime.tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        parsed = _extract_first_json(raw) or {}

        key_players = parsed.get("key_players") or []
        if isinstance(key_players, str):
            key_players = [player.strip() for player in key_players.split(";") if player.strip()]

        return {
            "event_summary": parsed.get("event_summary", ""),
            "lotte_stance": parsed.get("lotte_stance", ""),
            "key_players": [player for player in key_players if player and player != "nan"],
        }
    except Exception as exc:
        logger.error("Summarizer inference failed (%s)", exc)
        return _empty_summary()
