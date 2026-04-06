"""
fraud-api: Punto de entrada del sistema de detección de fraude.

Responsabilidades:
  1. Recibir webhooks con transacciones (de clientes o de n8n)
  2. Enviar la transacción a fraud-analyzer para obtener el score de riesgo
  3. Si el riesgo es HIGH o CRITICAL, notificar a fraud-notifier
  4. Devolver el resultado completo al cliente
"""

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import httpx
import os

from .models import Transaccion, RespuestaFraude, ResultadoAnalisis

# URLs de los microservicios internos (configuradas vía variables de entorno)
ANALYZER_URL = os.getenv("ANALYZER_URL", "http://fraud-analyzer:8001")
NOTIFIER_URL = os.getenv("NOTIFIER_URL", "http://fraud-notifier:8002")

# Niveles de riesgo que disparan una notificación automática
NIVELES_ALERTA = {"HIGH", "CRITICAL"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida del cliente HTTP (abre/cierra la conexión)."""
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="Fraud Detection API",
    description="Coordina el análisis de fraude para transacciones financieras chilenas",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Sistema"])
async def health():
    """Healthcheck para Docker Compose."""
    return {"status": "ok", "servicio": "fraud-api", "version": "1.0.0"}


@app.post("/analizar", response_model=RespuestaFraude, tags=["Fraude"])
async def analizar_transaccion(transaccion: Transaccion):
    """
    Analiza una transacción financiera y retorna el resultado de riesgo.

    Flujo:
      - Llama a fraud-analyzer → obtiene risk_score y recommendation
      - Si riesgo >= HIGH → llama a fraud-notifier
      - Retorna resultado consolidado
    """
    client: httpx.AsyncClient = app.state.http_client

    # ── Paso 1: análisis de riesgo ──────────────────────────────────────────
    try:
        resp = await client.post(
            f"{ANALYZER_URL}/analizar",
            json=transaccion.model_dump(),
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"fraud-analyzer respondió con error {e.response.status_code}",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo conectar con fraud-analyzer: {str(e)}",
        )

    analisis = ResultadoAnalisis(**resp.json())

    # ── Paso 2: notificar si el riesgo es alto ──────────────────────────────
    alerta_enviada = False

    if analisis.risk_level in NIVELES_ALERTA:
        try:
            payload_alerta = {
                "transaccion": transaccion.model_dump(),
                "analisis": analisis.model_dump(),
            }
            resp_notif = await client.post(
                f"{NOTIFIER_URL}/notificar",
                json=payload_alerta,
            )
            resp_notif.raise_for_status()
            alerta_enviada = True
        except httpx.HTTPError:
            # La falla del notificador no bloquea la respuesta al cliente
            pass

    return RespuestaFraude(
        transaccion_id=transaccion.id,
        analisis=analisis,
        alerta_enviada=alerta_enviada,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/webhook/n8n", response_model=RespuestaFraude, tags=["Webhooks"])
async def webhook_n8n(transaccion: Transaccion):
    """
    Endpoint compatible con nodos HTTP Request de n8n.
    Reutiliza la misma lógica que /analizar.
    """
    return await analizar_transaccion(transaccion)
