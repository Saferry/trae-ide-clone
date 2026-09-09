FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 系统依赖（Bubblewrap、git、build-essential）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    bubblewrap \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/ ./src/
COPY pyproject.toml .

# 数据目录
RUN mkdir -p /app/data /app/data/chroma /app/workspace
ENV PYTHONPATH=/app/src

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()" || exit 1

CMD ["uvicorn", "trae_server.main:app", "--host", "0.0.0.0", "--port", "8080"]