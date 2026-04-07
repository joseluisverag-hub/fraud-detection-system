"""
Configuración central del RPA de inyección de transacciones.
Modifica este archivo para ajustar URLs, credenciales e intervalos.
"""

# ── URLs de los servicios ────────────────────────────────────────────────────

# Webhook de n8n que recibe cada transacción
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/transaction"

# Endpoint de autenticación SSO
AUTH_SSO_URL = "http://localhost:8001/token"

# ── Clientes SSO disponibles ─────────────────────────────────────────────────
# El script rota entre estos sistemas para simular distintos puntos
# de venta que envían transacciones al pipeline de fraude.
CLIENTES_SSO = [
    {"client_id": "tienda-online", "client_secret": "secret123"},
    {"client_id": "app-movil",     "client_secret": "mobile456"},
    {"client_id": "pos-system",    "client_secret": "pos789"},
]

# ── Timing ───────────────────────────────────────────────────────────────────
INTERVAL_SECONDS = 30   # Intervalo normal entre transacciones (segundos)
TURBO_INTERVAL   = 5    # Intervalo en modo demo/turbo (segundos)
TURBO_MODE       = False

# ── Renovación de token ──────────────────────────────────────────────────────
# auth-sso emite tokens con vencimiento de 1 hora (3600 s).
# Renovamos a los 55 minutos para evitar expiración en mitad de una llamada.
TOKEN_DURACION_SEGUNDOS = 3300

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_FILE = "rpa/logs/transactions.log"
