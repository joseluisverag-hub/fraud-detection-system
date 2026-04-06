"""
fraud-analyzer: Microservicio de análisis de riesgo con LangChain + GPT-4o.

Lee la API key desde Docker Secrets (/run/secrets/openai_key) con fallback
a variable de entorno OPENAI_API_KEY para desarrollo local.
"""

from fastapi import FastAPI, HTTPException
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import List
import json
import os

from .prompts import SYSTEM_PROMPT, HUMAN_PROMPT


# ── Lectura segura de secretos ───────────────────────────────────────────────

def leer_secreto(nombre: str) -> str:
    """
    Lee un secreto desde Docker Secrets.
    En Docker, los secretos se montan como archivos en /run/secrets/.
    Compatible con Azure Key Vault en producción (mismo nombre de secreto).
    """
    ruta = f"/run/secrets/{nombre}"
    if os.path.exists(ruta):
        with open(ruta) as f:
            return f.read().strip()
    # Fallback para desarrollo local (sin Docker)
    return os.getenv("OPENAI_API_KEY", "")


# ── Inicialización del modelo ────────────────────────────────────────────────

api_key = leer_secreto("openai_key")

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1,      # Baja temperatura → respuestas consistentes y deterministas
    api_key=api_key,
    model_kwargs={"response_format": {"type": "json_object"}},  # Forzar JSON puro
)


# ── Modelos Pydantic ─────────────────────────────────────────────────────────

class Transaccion(BaseModel):
    """Datos de entrada de la transacción a analizar."""
    id: str
    rut_cliente: str
    comercio: str
    monto_clp: int
    tipo: str
    region: str
    hora: str
    canal: str


class ResultadoAnalisis(BaseModel):
    """Respuesta estructurada del análisis de fraude."""
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str
    risk_factors: List[str]
    recommendation: str
    explanation: str


# ── Aplicación FastAPI ───────────────────────────────────────────────────────

app = FastAPI(
    title="Fraud Analyzer",
    description="Análisis de riesgo de fraude usando LangChain + GPT-4o",
    version="1.0.0",
)


@app.get("/health", tags=["Sistema"])
async def health():
    """Healthcheck para Docker Compose."""
    return {"status": "ok", "servicio": "fraud-analyzer", "modelo": "gpt-4o"}


@app.post("/analizar", response_model=ResultadoAnalisis, tags=["Análisis"])
async def analizar(transaccion: Transaccion):
    """
    Analiza una transacción con GPT-4o vía LangChain.

    Flujo:
      1. Construye el prompt con los datos de la transacción
      2. Invoca GPT-4o en modo JSON (response_format: json_object)
      3. Parsea y valida la respuesta con Pydantic
    """
    # Formatear el prompt humano con los datos de la transacción
    mensaje_humano = HUMAN_PROMPT.format(
        id=transaccion.id,
        rut_cliente=transaccion.rut_cliente,
        comercio=transaccion.comercio,
        monto_clp=transaccion.monto_clp,
        tipo=transaccion.tipo,
        region=transaccion.region,
        hora=transaccion.hora,
        canal=transaccion.canal,
    )

    mensajes = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=mensaje_humano),
    ]

    # Invocar el modelo de forma asíncrona
    try:
        respuesta = await llm.ainvoke(mensajes)
        datos = json.loads(respuesta.content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"El LLM no devolvió JSON válido: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Error al invocar GPT-4o: {str(e)}",
        )

    # Validar y devolver el resultado
    try:
        return ResultadoAnalisis(**datos)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"La respuesta del LLM no cumple el esquema esperado: {str(e)}",
        )
