"""
fraud-api: Punto de entrada del sistema de detección de fraude.

Responsabilidades:
  1. Recibir webhooks con transacciones (de clientes o de n8n)
  2. Validar el JWT del cliente contra auth-sso antes de procesar
  3. Enviar la transacción a fraud-analyzer para obtener el score de riesgo
  4. Si el riesgo es HIGH o CRITICAL, notificar a fraud-notifier
  5. Devolver el resultado completo al cliente
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .models import ResultadoAnalisis, RespuestaFraude, Transaccion

# URLs de los microservicios internos (configuradas vía variables de entorno)
ANALYZER_URL = os.getenv("ANALYZER_URL", "http://fraud-analyzer:8001")
NOTIFIER_URL = os.getenv("NOTIFIER_URL", "http://fraud-notifier:8002")

# Niveles de riesgo que disparan una notificación automática
NIVELES_ALERTA = {"HIGH", "CRITICAL"}

# ── Configuración de JWT ─────────────────────────────────────────────────────
ALGORITMO = "HS256"


def _leer_jwt_secret() -> str:
    """
    Lee el JWT secret desde Docker Secrets.
    Mismo secret que usa auth-sso para firmar los tokens.
    """
    ruta_secret = "/run/secrets/jwt_secret"
    if os.path.exists(ruta_secret):
        with open(ruta_secret) as archivo:
            return archivo.read().strip()
    # Fallback para desarrollo local
    return os.getenv("JWT_SECRET", "dev-secret-inseguro-cambiar-en-produccion")


JWT_SECRET = _leer_jwt_secret()

# Esquema de seguridad Bearer para documentación automática en Swagger
_bearer_scheme = HTTPBearer()


def validar_jwt(
    credenciales: HTTPAuthorizationCredentials = Security(_bearer_scheme),
) -> dict:
    """
    Dependencia de FastAPI que valida el JWT en cada request protegido.

    - Extrae el token del header Authorization: Bearer <token>
    - Verifica firma y expiración usando el mismo secret que auth-sso
    - Retorna los claims si el token es válido
    - Lanza 401 si el token es inválido, expirado o ausente
    """
    try:
        claims = jwt.decode(
            credenciales.credentials,
            JWT_SECRET,
            algorithms=[ALGORITMO],
        )
        return claims
    except JWTError as error:
        raise HTTPException(
            status_code=401,
            detail=f"Token JWT inválido o expirado: {str(error)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


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


async def _ejecutar_analisis(transaccion: Transaccion, client: httpx.AsyncClient) -> RespuestaFraude:
    """
    Lógica central de análisis: llama a fraud-analyzer y fraud-notifier.
    Separada del endpoint para poder reutilizarse sin acoplar la dependencia JWT.
    """
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


@app.post("/analizar", response_model=RespuestaFraude, tags=["Fraude"])
async def analizar_transaccion(
    transaccion: Transaccion,
    _claims: dict = Depends(validar_jwt),  # Requiere JWT válido emitido por auth-sso
):
    """
    Analiza una transacción financiera y retorna el resultado de riesgo.

    Requiere header: Authorization: Bearer <token>
    Obtener token previamente en POST http://auth-sso:8001/token

    Flujo:
      - Valida JWT (firma + expiración)
      - Llama a fraud-analyzer → obtiene risk_score y recommendation
      - Si riesgo >= HIGH → llama a fraud-notifier
      - Retorna resultado consolidado
    """
    return await _ejecutar_analisis(transaccion, app.state.http_client)


@app.post("/webhook/n8n", response_model=RespuestaFraude, tags=["Webhooks"])
async def webhook_n8n(
    transaccion: Transaccion,
    _claims: dict = Depends(validar_jwt),  # n8n también debe autenticarse con JWT
):
    """
    Endpoint compatible con nodos HTTP Request de n8n.
    Requiere el mismo JWT que /analizar (configurar en el nodo HTTP de n8n).
    """
    return await _ejecutar_analisis(transaccion, app.state.http_client)
