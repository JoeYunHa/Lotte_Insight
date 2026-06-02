# Stage 1: Install Python dependencies (build tools included)
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# torch CPU-only as a dedicated layer (~700MB, changes rarely)
# Must be installed before transformers to prevent CUDA variant from being pulled
RUN pip install --no-cache-dir --user \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

# HuggingFace transformers for KoELECTRA inference
RUN pip install --no-cache-dir --user transformers

# All remaining application dependencies
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Runtime image (no build tools → smaller final image)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/root/.local/bin:$PATH

COPY --from=builder /root/.local /root/.local

# Playwright system deps + Chromium browser (required for KBO crawler)
RUN playwright install chromium --with-deps

WORKDIR /app
COPY . .

# 빌드 시 모델을 이미지에 포함 — API 서버와 크론 잡이 동일 이미지를 공유하므로
# 런타임 다운로드 없이 모든 서비스에서 모델을 사용할 수 있다.
ARG HF_TOKEN
RUN HF_TOKEN=${HF_TOKEN} python scripts/download_models.py

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
