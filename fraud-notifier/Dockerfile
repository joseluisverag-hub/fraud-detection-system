# ─────────────────────────────────────────────
# Multi-stage build para linux/amd64
# Servicio liviano: solo FastAPI + uvicorn
# ─────────────────────────────────────────────

FROM --platform=linux/amd64 python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────
# Stage 2: imagen de producción
# ─────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src/ ./src/

EXPOSE 8002

CMD ["uvicorn", "src.notifier:app", "--host", "0.0.0.0", "--port", "8002"]
