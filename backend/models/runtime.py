from dataclasses import dataclass, field
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_KOELECTRA_MAX_LEN = 128


def infer_single(
    artifacts: "ModelArtifacts",
    text_a: str,
    text_b: str,
    labels: list[str],
) -> dict:
    """Run single-item sequence classification and return {label, confidence, source}."""
    import torch

    enc = artifacts.tokenizer(
        text_a,
        text_b,
        truncation="only_second",
        padding="max_length",
        max_length=_KOELECTRA_MAX_LEN,
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


def infer_batch(
    artifacts: "ModelArtifacts",
    text_pairs: list[tuple[str, str]],
    labels: list[str],
    *,
    chunk_size: int,
    error_log_prefix: str,
    module_logger: logging.Logger,
) -> list[dict]:
    """Run batched sequence classification. Returns [{label, confidence, source}] in input order.

    On chunk-level failure falls back to model_error entries for that chunk.
    """
    import torch

    results: list[dict] = [{"label": None, "confidence": 0.0, "source": "model_error"} for _ in text_pairs]

    for start in range(0, len(text_pairs), chunk_size):
        end = start + chunk_size
        chunk = text_pairs[start:end]
        texts_a = [p[0] for p in chunk]
        texts_b = [p[1] for p in chunk]
        try:
            enc = artifacts.tokenizer(
                texts_a,
                texts_b,
                truncation="only_second",
                padding=True,
                max_length=_KOELECTRA_MAX_LEN,
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
        except Exception:
            module_logger.exception(
                "%s chunk [%d:%d]; returning model_error.",
                error_log_prefix,
                start,
                end,
            )

    return results


@dataclass
class ModelArtifacts:
    model: Any = None
    tokenizer: Any = None
    device: Any = None
    extras: dict[str, Any] = field(default_factory=dict)


class LazyArtifactsLoader:
    def __init__(
        self,
        *,
        current_file: str,
        env_var: str,
        deployed_dir_name: str,
        training_dir_name: str,
        required_file: str,
        loader: Callable[[Path], ModelArtifacts],
        missing_log: str,
        error_log: str,
    ) -> None:
        this_dir = Path(current_file).resolve().parent
        repo_root = this_dir.parent.parent
        self._env_var = env_var
        self._static_dirs = [
            str(this_dir / deployed_dir_name),
            str(repo_root / "training" / "models" / training_dir_name),
        ]
        self._required_file = required_file
        self._loader = loader
        self._missing_log = missing_log
        self._error_log = error_log
        self._loaded = False
        self._artifacts: ModelArtifacts | None = None
        self._lock = threading.Lock()

    def _find_model_dir(self) -> Path | None:
        candidates = [os.environ.get(self._env_var, "")] + self._static_dirs
        for candidate_dir in candidates:
            if candidate_dir and (Path(candidate_dir) / self._required_file).exists():
                return Path(candidate_dir)
        return None

    def get(self) -> ModelArtifacts | None:
        # Fast path without locking
        if self._loaded:
            return self._artifacts

        with self._lock:
            # Double-checked locking
            if self._loaded:
                return self._artifacts

            model_dir = self._find_model_dir()
            if model_dir is None:
                logger.warning(self._missing_log)
                self._loaded = True
                return None

            try:
                self._artifacts = self._loader(model_dir)
            except Exception as exc:
                logger.error(self._error_log, exc)
                self._artifacts = None
            self._loaded = True
            return self._artifacts
