"""
Upload fine-tuned models to HuggingFace Hub.

Models uploaded:
  - lotte_related_koelectra   → <username>/lotte-related-koelectra
  - stance_koelectra          → <username>/lotte-stance-koelectra
  - player_stance_koelectra   → <username>/lotte-player-stance-koelectra

Usage:
    python push_to_hub.py --username <hf-username> [--private] [--model all|lotte_related|stance|player_stance]
"""

import argparse
from pathlib import Path

from huggingface_hub import HfApi

MODELS_DIR = Path(__file__).parent / "models"

MODEL_REGISTRY: dict[str, tuple[str, str]] = {
    "lotte_related":  ("lotte_related_model",       "lotte-related-koelectra"),
    "stance":         ("stance_koelectra",           "lotte-stance-koelectra"),
    "player_stance":  ("player_stance_koelectra",    "lotte-player-stance-koelectra"),
}


def push(username: str, private: bool, model_key: str) -> None:
    api = HfApi()

    targets = (
        list(MODEL_REGISTRY.items())
        if model_key == "all"
        else [(model_key, MODEL_REGISTRY[model_key])]
    )

    for key, (dir_name, repo_suffix) in targets:
        local_dir = MODELS_DIR / dir_name
        if not local_dir.exists():
            print(f"[SKIP] {key}: directory not found ({local_dir})")
            continue

        repo_id = f"{username}/{repo_suffix}"

        try:
            api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)
            print(f"[REPO] {repo_id} ready")
        except Exception as e:
            print(f"[ERROR] Repo create failed ({repo_id}): {e}")
            continue

        print(f"[UPLOAD] {key}: {local_dir} → {repo_id}")
        api.upload_folder(folder_path=str(local_dir), repo_id=repo_id, repo_type="model")
        print(f"[DONE]  https://huggingface.co/{repo_id}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True, help="HuggingFace username")
    parser.add_argument("--private", action="store_true", help="Make repos private")
    parser.add_argument(
        "--model",
        default="all",
        choices=["all"] + list(MODEL_REGISTRY.keys()),
        help="Which model to upload (default: all)",
    )
    args = parser.parse_args()
    push(args.username, args.private, args.model)
