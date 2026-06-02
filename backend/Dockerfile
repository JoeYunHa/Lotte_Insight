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
    PATH=/root/.local/bin:$PATH

COPY --from=builder /root/.local /root/.local

# Playwright system deps + Chromium browser (required for KBO crawler)
RUN playwright install chromium --with-deps

WORKDIR /app
COPY . .

EXPOSE 8000

# 기동 시 1회 모델 다운로드 후 서버 시작
CMD ["sh", "-c", "python scripts/download_models.py && uvicorn main:app --host 0.0.0.0 --port $PORT"]
