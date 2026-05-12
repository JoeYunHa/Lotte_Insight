"""
Upload fine-tuned models to HuggingFace Hub.

Usage:
    python push_to_hub.py --username <hf-username> [--private]
"""

import argparse
from pathlib import Path

from huggingface_hub import HfApi

CLASSIFIER_DIR = Path(__file__).parent / "models" / "classifier_koelectra"
SUMMARIZER_DIR = Path(__file__).parent / "models" / "summarizer_kobart"


def push(username: str, private: bool) -> None:
    api = HfApi()

    classifier_repo = f"{username}/lotte-classifier-koelectra"
    summarizer_repo = f"{username}/lotte-summarizer-kobart"

    for repo_id in [classifier_repo, summarizer_repo]:
        try:
            api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)
            print(f"Repo ready: {repo_id}")
        except Exception as e:
            print(f"Repo create failed ({repo_id}): {e}")

    print(f"\nUploading classifier ({CLASSIFIER_DIR}) → {classifier_repo}")
    api.upload_folder(
        folder_path=str(CLASSIFIER_DIR),
        repo_id=classifier_repo,
        repo_type="model",
    )
    print("Classifier upload done.")

    print(f"\nUploading summarizer ({SUMMARIZER_DIR}) → {summarizer_repo}")
    api.upload_folder(
        folder_path=str(SUMMARIZER_DIR),
        repo_id=summarizer_repo,
        repo_type="model",
    )
    print("Summarizer upload done.")

    print(f"\nDone.\n  Classifier: https://huggingface.co/{classifier_repo}")
    print(f"  Summarizer: https://huggingface.co/{summarizer_repo}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True, help="HuggingFace username")
    parser.add_argument("--private", action="store_true", help="Make repos private")
    args = parser.parse_args()
    push(args.username, args.private)
