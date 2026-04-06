"""
fraud-notifier: Microservicio de alertas de fraude.

Recibe alertas desde fraud-api cuando una transacción es HIGH o CRITICAL.
En producción conectaría con: email, Slack, SMS, sistema core bancario, SIEM.
En este portafolio: log estructurado + registro en memoria + endpoint de consulta.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timezone
import json


app = FastAPI(
    title="Fraud Notifier",
    description="Gestión y envío de alertas de fraude financiero",
    version="1.0.0",
)

# Registro en memoria de las alertas de esta sesión
# En producción: Redis, PostgreSQL o sistema de colas (SQS, Azure Service Bus)
_alertas: List[Dict[str, Any]] = []


# ── Modelos ──────────────────────────────────────────────────────────────────

class PayloadAlerta(BaseModel):
    """Estructura que recibe desde fraud-api."""
    transaccion: Dict[str, Any]
    analisis: Dict[str, Any]


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Sistema"])
async def health():
    """Healthcheck para Docker Compose."""
    return {
        "status": "ok",
        "servicio": "fraud-notifier",
        "alertas_registradas": len(_alertas),
    }


@app.post("/notificar", tags=["Alertas"])
async def notificar(payload: PayloadAlerta):
    """
    Procesa una alerta de fraude y la distribuye por los canales configurados.

    Canales activos en este entorno:
      - Log estructurado (stdout → Docker logs)
      - Registro interno en memoria

    Canales disponibles en producción (configurables vía env vars):
      - Email (SendGrid / SES)
      - Slack Webhook
      - SMS (Twilio)
      - Core bancario (REST interno)
      - SIEM (Splunk / Azure Sentinel)
    """
    nivel = payload.analisis.get("risk_level", "UNKNOWN")
    transaccion_id = payload.transaccion.get("id", "N/A")

    # Construir registro de alerta
    alerta = {
        "alerta_id": f"ALT-{len(_alertas) + 1:05d}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transaccion_id": transaccion_id,
        "rut_cliente": payload.transaccion.get("rut_cliente"),
        "comercio": payload.transaccion.get("comercio"),
        "monto_clp": payload.transaccion.get("monto_clp"),
        "region": payload.transaccion.get("region"),
        "hora": payload.transaccion.get("hora"),
        "canal": payload.transaccion.get("canal"),
        "risk_level": nivel,
        "risk_score": payload.analisis.get("risk_score"),
        "risk_factors": payload.analisis.get("risk_factors", []),
        "recommendation": payload.analisis.get("recommendation"),
        "explanation": payload.analisis.get("explanation"),
    }

    # Persistir en registro interno
    _alertas.append(alerta)

    # ── Log estructurado por nivel de criticidad ──────────────────────────
    prefijo = {
        "CRITICAL": "🚨 [CRÍTICO]",
        "HIGH":     "⚠️  [ALTO]",
    }.get(nivel, "[ALERTA]")

    print(f"{prefijo} {json.dumps(alerta, ensure_ascii=False)}", flush=True)

    # Acciones diferenciadas según criticidad
    if nivel == "CRITICAL":
        # En producción: bloqueo inmediato + notificación al equipo de fraude
        print(
            f"  → Transacción {transaccion_id} BLOQUEADA. "
            f"Notificando equipo de fraude.",
            flush=True,
        )
    elif nivel == "HIGH":
        # En producción: poner en cola de revisión manual
        print(
            f"  → Transacción {transaccion_id} encolada para REVISIÓN MANUAL.",
            flush=True,
        )

    return {
        "alerta_id": alerta["alerta_id"],
        "procesada": True,
        "canales_notificados": ["log_estructurado", "registro_interno"],
        "timestamp": alerta["timestamp"],
    }


@app.get("/alertas", tags=["Alertas"])
async def listar_alertas(limit: int = 50):
    """
    Retorna las últimas alertas registradas en esta sesión.
    Útil para monitoreo y debugging desde n8n o herramientas externas.
    """
    ultimas = _alertas[-limit:] if len(_alertas) > limit else _alertas
    return {
        "total_sesion": len(_alertas),
        "mostrando": len(ultimas),
        "alertas": list(reversed(ultimas)),  # Más recientes primero
    }
