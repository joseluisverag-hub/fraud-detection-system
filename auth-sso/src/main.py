"""
auth-sso: Servicio de autenticación SSO para el sistema de detección de fraude.

Responsabilidades:
  1. POST /token  — recibe client_id y client_secret, devuelve un JWT firmado
  2. GET  /verify — valida un JWT entrante y retorna sus claims
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Header
from jose import jwt, JWTError
from pydantic import BaseModel


# ── Clientes pre-registrados (simulan un directorio SSO) ────────────────────
# En producción esto vendría de una base de datos o de Azure AD / Okta
CLIENTES_REGISTRADOS: dict[str, dict] = {
    "tienda-online": {
        "client_secret": "secret123",
        "name": "TechStore Chile",
    },
    "app-movil": {
        "client_secret": "mobile456",
        "name": "TechStore App",
    },
    "pos-system": {
        "client_secret": "pos789",
        "name": "TechStore POS",
    },
}

# Algoritmo de firma para los JWT
ALGORITMO = "HS256"

# Duración del token antes de expirar
TOKEN_EXPIRACION_HORAS = 1


def _leer_jwt_secret() -> str:
    """
    Lee el JWT secret desde Docker Secrets.
    Si el archivo no existe (entorno local), usa la variable de entorno JWT_SECRET.
    """
    ruta_secret = "/run/secrets/jwt_secret"
    if os.path.exists(ruta_secret):
        with open(ruta_secret) as archivo:
            return archivo.read().strip()
    # Fallback solo para desarrollo local — no usar en producción
    return os.getenv("JWT_SECRET", "dev-secret-inseguro-cambiar-en-produccion")


# Cargar el secret al iniciar el servicio
JWT_SECRET = _leer_jwt_secret()


# ── Modelos de datos ─────────────────────────────────────────────────────────

class SolicitudToken(BaseModel):
    """Credenciales del cliente para solicitar un JWT."""
    client_id: str
    client_secret: str


class RespuestaToken(BaseModel):
    """JWT devuelto al cliente tras autenticación exitosa."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_EXPIRACION_HORAS * 3600  # en segundos
    client_name: str


# ── Aplicación FastAPI ───────────────────────────────────────────────────────

app = FastAPI(
    title="Auth SSO — TechStore",
    description="Servicio de autenticación SSO que emite y valida JWT para los sistemas TechStore",
    version="1.0.0",
)


@app.get("/health", tags=["Sistema"])
async def health():
    """Healthcheck para Docker Compose."""
    return {"status": "ok", "servicio": "auth-sso", "version": "1.0.0"}


@app.post("/token", response_model=RespuestaToken, tags=["Autenticación"])
async def obtener_token(solicitud: SolicitudToken):
    """
    Valida las credenciales del cliente y devuelve un JWT firmado.

    Flujo:
      - Verifica que client_id exista en el registro
      - Compara client_secret con el almacenado
      - Genera JWT con expiración de 1 hora y lo retorna
    """
    # Buscar el cliente en el registro pre-cargado
    cliente = CLIENTES_REGISTRADOS.get(solicitud.client_id)

    # Validar credenciales — usar mismo mensaje para evitar enumeración de usuarios
    if not cliente or cliente["client_secret"] != solicitud.client_secret:
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas: client_id o client_secret incorrecto",
        )

    # Construir el payload del JWT con los claims estándar
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": solicitud.client_id,                            # Subject: identidad del cliente
        "name": cliente["name"],                               # Nombre legible del cliente
        "iat": ahora,                                          # Issued at: momento de emisión
        "exp": ahora + timedelta(hours=TOKEN_EXPIRACION_HORAS),  # Expiration: 1 hora
    }

    # Firmar el token con el secret cargado desde Docker Secrets
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITMO)

    return RespuestaToken(
        access_token=token,
        client_name=cliente["name"],
    )


@app.get("/verify", tags=["Autenticación"])
async def verificar_token(
    authorization: str = Header(..., description="JWT en formato: Bearer <token>")
):
    """
    Valida un JWT y retorna sus claims si es válido.

    Cabecera requerida:
      Authorization: Bearer <token>

    Retorna error 401 si el token es inválido, expirado o malformado.
    """
    # Verificar que el header tenga el formato correcto
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Formato de autorización inválido. Use: Authorization: Bearer <token>",
        )

    # Extraer el token del header (remover prefijo "Bearer ")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        # Decodificar y verificar firma + expiración automáticamente
        claims = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITMO])

        return {
            "valido": True,
            "client_id": claims.get("sub"),
            "client_name": claims.get("name"),
            "emitido_en": claims.get("iat"),
            "expira_en": claims.get("exp"),
        }

    except JWTError as error:
        raise HTTPException(
            status_code=401,
            detail=f"Token inválido o expirado: {str(error)}",
        )
