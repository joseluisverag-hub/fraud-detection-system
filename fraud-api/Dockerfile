# ─────────────────────────────────────────────
# Multi-stage build para linux/amd64
# Stage 1: instala dependencias en imagen temporal
# Stage 2: copia solo lo necesario → imagen final liviana
# ─────────────────────────────────────────────

FROM --platform=linux/amd64 python:3.11-slim AS builder

WORKDIR /build

# Copiar e instalar dependencias en directorio aparte
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────
# Stage 2: imagen de producción
# ─────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.11-slim

# Instalar curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar dependencias desde el builder
COPY --from=builder /install /usr/local

# Copiar código fuente
COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
