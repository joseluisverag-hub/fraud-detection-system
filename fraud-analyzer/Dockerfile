# ─────────────────────────────────────────────
# Multi-stage build para linux/amd64
# Stage 1: instala dependencias (langchain, langchain-openai)
# Stage 2: imagen final sin caché de pip
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

EXPOSE 8001

CMD ["uvicorn", "src.analyzer:app", "--host", "0.0.0.0", "--port", "8001"]
