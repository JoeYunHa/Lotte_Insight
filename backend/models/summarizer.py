"""
KoBART 기사 요약기.

fine-tuned KoBART 모델이 MODEL_DIR에 있으면 로드하여 추론한다.
모델이 없으면 빈 결과를 반환하고 파이프라인은 정상 진행된다.

MODEL_DIR 탐색 순서:
  1. 환경변수 SUMMARIZER_MODEL_DIR
  2. backend/models/summarizer_kobart/  (배포 시 위치)
  3. training/models/summarizer_kobart/ (로컬 학습 결과)
"""

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_THIS_DIR = Path(__file__).parent
_BACKEND_DIR = _THIS_DIR.parent
_REPO_ROOT = _BACKEND_DIR.parent

_CANDIDATE_DIRS = [
    os.environ.get("SUMMARIZER_MODEL_DIR", ""),
    str(_THIS_DIR / "summarizer_kobart"),
    str(_REPO_ROOT / "training" / "models" / "summarizer_kobart"),
]

_ARTICLE_SNIPPET_LENGTH = 300
_MAX_SOURCE_LEN = 384
_MAX_TARGET_LEN = 256
_NUM_BEAMS = 6
_LENGTH_PENALTY = 1.2
_NO_REPEAT_NGRAM = 3

_model = None
_tokenizer = None
_device = None
_model_loaded = False


def _find_model_dir() -> Path | None:
    for d in _CANDIDATE_DIRS:
        if d and (Path(d) / "config.json").exists():
            return Path(d)
    return None


def _load_model():
    global _model, _tokenizer, _device, _model_loaded
    if _model_loaded:
        return

    model_dir = _find_model_dir()
    if model_dir is None:
        logger.warning("KoBART 요약 모델 없음 — event_summary 생성 건너뜀")
        _model_loaded = True
        return

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        _model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir)).to(_device)
        _model.eval()
        logger.info("KoBART 요약 모델 로드 완료: %s", model_dir)
    except Exception as exc:
        logger.error("KoBART 모델 로드 실패 (%s) — 요약 건너뜀", exc)
        _model = None

    _model_loaded = True


# ── JSON 파싱 헬퍼 ──────────────────────────────────────────────────────────

def _regex_extract(text: str) -> dict:
    result: dict = {}
    m = re.search(r'"event_summary"\s*:\s*"([^"]+)"', text)
    if m:
        result["event_summary"] = m.group(1)
    m = re.search(r'"lotte_stance"\s*:\s*"([^"]+)"', text)
    if m:
        result["lotte_stance"] = m.group(1)
    players = re.findall(r'"key_players"\s*:\s*\[([^\]]*)\]', text)
    if players:
        names = re.findall(r'"([^"]+)"', players[0])
        result["key_players"] = [n for n in names if n != "nan"]
    return result


def _extract_first_json(text: str) -> dict | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return _regex_extract(candidate)
    return None


# ── Stopping criteria ─────────────────────────────────────────────────────

def _make_stopping_criteria():
    try:
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        class _JsonClosedStopping(StoppingCriteria):
            def __init__(self, tok):
                self._tok = tok

            def __call__(self, input_ids: "torch.LongTensor", scores: "torch.FloatTensor", **kwargs) -> bool:
                text = self._tok.decode(input_ids[0], skip_special_tokens=True)
                depth = 0
                started = False
                for ch in text:
                    if ch == "{":
                        depth += 1
                        started = True
                    elif ch == "}":
                        depth -= 1
                return started and depth <= 0

        return StoppingCriteriaList([_JsonClosedStopping(_tokenizer)])
    except Exception:
        return None


# ── 입력 텍스트 생성 ───────────────────────────────────────────────────────

def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _build_source_text(
    title: str,
    description_snippet: str,
    primary_label: str,
    published_at: str,
    game_context: str,
) -> str:
    parts = ["뉴스 요약:"]
    parts.append(f"title: {_clean_html(title.strip())}")
    desc = _clean_html((description_snippet or "").strip())
    if desc:
        parts.append(f"description: {desc[:_ARTICLE_SNIPPET_LENGTH]}")
    if published_at:
        parts.append(f"published_at: {published_at.strip()}")
    if primary_label:
        parts.append(f"topic_label: {primary_label.strip()}")
    if game_context:
        parts.append(f"game_context: {game_context.strip()}")
    return "\n".join(parts)


# ── public API ────────────────────────────────────────────────────────────

def summarize(
    title: str,
    description_snippet: str = "",
    primary_label: str = "",
    published_at: str = "",
    game_context: str = "",
) -> dict:
    """
    Returns:
        {"event_summary": str, "lotte_stance": str, "key_players": list[str]}
        모델 없거나 실패 시 빈 값으로 반환한다.
    """
    _load_model()

    if _model is None or _tokenizer is None:
        return {"event_summary": "", "lotte_stance": "", "key_players": []}

    source = _build_source_text(title, description_snippet, primary_label, published_at, game_context)

    try:
        import torch

        inputs = _tokenizer(
            source,
            max_length=_MAX_SOURCE_LEN,
            truncation=True,
            return_tensors="pt",
        ).to(_device)

        stopping = _make_stopping_criteria()
        gen_kwargs: dict = {
            "max_new_tokens": _MAX_TARGET_LEN,
            "num_beams": _NUM_BEAMS,
            "length_penalty": _LENGTH_PENALTY,
            "no_repeat_ngram_size": _NO_REPEAT_NGRAM,
            "early_stopping": True,
        }
        if stopping is not None:
            gen_kwargs["stopping_criteria"] = stopping

        with torch.no_grad():
            output_ids = _model.generate(**inputs, **gen_kwargs)

        raw = _tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        parsed = _extract_first_json(raw) or {}

        key_players = parsed.get("key_players") or []
        if isinstance(key_players, str):
            key_players = [p.strip() for p in key_players.split(";") if p.strip()]

        return {
            "event_summary": parsed.get("event_summary", ""),
            "lotte_stance": parsed.get("lotte_stance", ""),
            "key_players": [p for p in key_players if p and p != "nan"],
        }

    except Exception as exc:
        logger.error("KoBART 요약 추론 실패 (%s)", exc)
        return {"event_summary": "", "lotte_stance": "", "key_players": []}
