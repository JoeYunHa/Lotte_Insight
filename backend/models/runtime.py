from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


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
        self._candidate_dirs = [
            os.environ.get(env_var, ""),
            str(this_dir / deployed_dir_name),
            str(repo_root / "training" / "models" / training_dir_name),
        ]
        self._required_file = required_file
        self._loader = loader
        self._missing_log = missing_log
        self._error_log = error_log
        self._loaded = False
        self._artifacts: ModelArtifacts | None = None

    def _find_model_dir(self) -> Path | None:
        for candidate_dir in self._candidate_dirs:
            if candidate_dir and (Path(candidate_dir) / self._required_file).exists():
                return Path(candidate_dir)
        return None

    def get(self) -> ModelArtifacts | None:
        if self._loaded:
            return self._artifacts

        model_dir = self._find_model_dir()
        self._loaded = True
        if model_dir is None:
            logger.warning(self._missing_log)
            return None

        try:
            self._artifacts = self._loader(model_dir)
        except Exception as exc:
            logger.error(self._error_log, exc)
            self._artifacts = None
        return self._artifacts
