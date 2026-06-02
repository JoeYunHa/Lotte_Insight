"""빌드 시 1회 실행 — HuggingFace Hub에서 모델 다운로드 (Railway Nixpacks build step)"""
import os
from huggingface_hub import snapshot_download

HF_TOKEN = os.environ.get("HF_TOKEN")

MODELS = {
    "JoeYunHa/lotte-classifier-koelectra":    os.environ.get("CLASSIFIER_MODEL_DIR",        "/app/models/classifier_koelectra"),
    "JoeYunHa/lotte-related-koelectra":       os.environ.get("LOTTE_RELATED_MODEL_DIR",     "/app/models/lotte_related_koelectra"),
    "JoeYunHa/lotte-stance-koelectra":        os.environ.get("STANCE_CLASSIFIER_MODEL_DIR", "/app/models/stance_koelectra"),
    "JoeYunHa/lotte-player-stance-koelectra": os.environ.get("PLAYER_STANCE_CLASSIFIER_MODEL_DIR", "/app/models/player_stance_koelectra"),
}

for repo_id, local_dir in MODELS.items():
    print(f"Downloading {repo_id} → {local_dir}")
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        token=HF_TOKEN,
    )
    print(f"  Done: {local_dir}")
