# Dockerfile
FROM python:3.12-slim

# ── 시스템 의존성 ─────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    # Playwright Chromium 의존성
    libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# ── 작업 디렉토리 ─────────────────────────────────────────────
WORKDIR /app

# ── Python 패키지 설치 ────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright Chromium 설치 ──────────────────────────────────
RUN playwright install chromium

# ── 소스 복사 ─────────────────────────────────────────────────
COPY . .

# ── 실행 ─────────────────────────────────────────────────────
CMD ["python", "scheduler.py"]
