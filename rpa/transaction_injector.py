"""
RPA — Inyector de transacciones financieras chilenas.

Simula clientes reales de un e-commerce enviando transacciones al sistema
de detección de fraude a través del webhook de n8n.

Modos de uso:
  python rpa/transaction_injector.py              # modo normal (30 s)
  python rpa/transaction_injector.py --turbo      # modo demo   (5 s)
  python rpa/transaction_injector.py --count 50   # envía 50 y termina
  python rpa/transaction_injector.py --turbo --count 20
"""

import argparse
import logging
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# Añadir el directorio del script al path para importar config
sys.path.insert(0, str(Path(__file__).parent))

import config


# ═══════════════════════════════════════════════════════════════════════════════
# DATOS DE DOMINIO — Comercios, regiones y perfiles de clientes chilenos
# ═══════════════════════════════════════════════════════════════════════════════

COMERCIOS_NORMALES = [
    "Falabella",
    "Ripley",
    "Lider Quilicura",
    "Paris Mall",
    "SMU Unimarc",
    "Shell Pudahuel",
    "Copec Ruta 68",
    "McDonald's Providencia",
    "Subway Las Condes",
    "Farmacia Cruz Verde",
    "Farmacia Ahumada",
    "Starbucks Kennedy",
    "Jumbo Apumanque",
    "Easy Pudahuel",
    "Sodimac Maipú",
    "Petrobras Maipú",
    "Tottus La Florida",
    "Santa Isabel Ñuñoa",
    "Entel Centro",
    "Cornershop",
]

COMERCIOS_SOSPECHOSOS = [
    "CryptoExchange XY",
    "Casino Online 777",
    "Transfer Rápido SA",
    "Tienda Sin Registro",
    "PaymentAnon Ltd",
    "BitTrade Chile",
    "WireTransfer Global",
    "Exchange Oscuro",
    "FastCash Anónimo",
    "BetOnline CL",
]

REGIONES_CHILE = [
    "Región Metropolitana",
    "Valparaíso",
    "Biobío",
    "La Araucanía",
    "Los Lagos",
    "O'Higgins",
    "Maule",
    "Antofagasta",
    "Tarapacá",
    "Atacama",
    "Coquimbo",
    "Los Ríos",
    "Arica y Parinacota",
    "Aysén",
    "Magallanes",
]

TIPOS = ["débito", "crédito", "transferencia"]

# Distribución de canales para transacciones normales
# (presencial 60%, app 30%, web 10%)
CANALES_PESOS = [
    ("presencial", 60),
    ("app",        30),
    ("web",        10),
]

# 10 perfiles de clientes ficticios con historial coherente
PERFILES_CLIENTES = [
    {
        "nombre":          "María González",
        "rut":             "12.345.678-9",
        "region":          "Región Metropolitana",
        "gasto_min":       5_000,
        "gasto_max":       80_000,
        "canal_preferido": "presencial",
    },
    {
        "nombre":          "Carlos Muñoz",
        "rut":             "15.234.567-K",
        "region":          "Valparaíso",
        "gasto_min":       10_000,
        "gasto_max":       150_000,
        "canal_preferido": "app",
    },
    {
        "nombre":          "Ana Martínez",
        "rut":             "9.876.543-2",
        "region":          "Biobío",
        "gasto_min":       3_000,
        "gasto_max":       60_000,
        "canal_preferido": "presencial",
    },
    {
        "nombre":          "Luis Herrera",
        "rut":             "17.654.321-5",
        "region":          "Región Metropolitana",
        "gasto_min":       20_000,
        "gasto_max":       500_000,
        "canal_preferido": "web",
    },
    {
        "nombre":          "Camila Rojas",
        "rut":             "13.579.246-8",
        "region":          "La Araucanía",
        "gasto_min":       5_000,
        "gasto_max":       45_000,
        "canal_preferido": "app",
    },
    {
        "nombre":          "Diego Fernández",
        "rut":             "11.222.333-4",
        "region":          "Coquimbo",
        "gasto_min":       8_000,
        "gasto_max":       120_000,
        "canal_preferido": "presencial",
    },
    {
        "nombre":          "Valentina López",
        "rut":             "16.789.012-3",
        "region":          "Maule",
        "gasto_min":       4_000,
        "gasto_max":       55_000,
        "canal_preferido": "presencial",
    },
    {
        "nombre":          "Sebastián Castro",
        "rut":             "14.111.222-6",
        "region":          "Antofagasta",
        "gasto_min":       15_000,
        "gasto_max":       200_000,
        "canal_preferido": "app",
    },
    {
        "nombre":          "Javiera Silva",
        "rut":             "10.999.888-7",
        "region":          "Los Lagos",
        "gasto_min":       6_000,
        "gasto_max":       70_000,
        "canal_preferido": "presencial",
    },
    {
        "nombre":          "Matías Torres",
        "rut":             "18.333.444-1",
        "region":          "Región Metropolitana",
        "gasto_min":       25_000,
        "gasto_max":       300_000,
        "canal_preferido": "web",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

def configurar_logging() -> logging.Logger:
    """
    Configura logger con salida a consola y archivo simultáneamente.
    El archivo se crea en rpa/logs/transactions.log.
    """
    # Crear directorio de logs si no existe
    Path(config.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("inyector")
    logger.setLevel(logging.DEBUG)

    # Formato para el archivo (con timestamp completo)
    fmt_archivo = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo
    fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt_archivo)

    # Handler de consola (sin formato — lo gestionamos manualmente para íconos)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


log = configurar_logging()


# ═══════════════════════════════════════════════════════════════════════════════
# SESIÓN SSO — Gestión automática de tokens JWT
# ═══════════════════════════════════════════════════════════════════════════════

class SesionSSO:
    """
    Gestiona la autenticación contra auth-sso.
    - Rota entre los clientes SSO disponibles
    - Renueva el token automáticamente cuando está próximo a vencer
    """

    def __init__(self):
        self._indice_cliente = 0
        self._token: Optional[str] = None
        self._obtenido_en: float = 0.0

    @property
    def _cliente_actual(self) -> dict:
        """Devuelve las credenciales del cliente SSO en turno."""
        return config.CLIENTES_SSO[self._indice_cliente]

    def _rotar_cliente(self):
        """Avanza al siguiente cliente SSO en la rotación circular."""
        self._indice_cliente = (self._indice_cliente + 1) % len(config.CLIENTES_SSO)

    def _token_expirado(self) -> bool:
        """True si el token superó el umbral de renovación (55 minutos)."""
        return time.time() - self._obtenido_en > config.TOKEN_DURACION_SEGUNDOS

    def obtener_token(self) -> str:
        """
        Devuelve el token vigente.
        Si no existe o está por vencer, solicita uno nuevo a auth-sso.
        """
        if self._token is None or self._token_expirado():
            self._renovar()
        return self._token

    def _renovar(self):
        """
        Solicita un JWT fresco a auth-sso.
        Rota al siguiente cliente SSO después de cada renovación.
        """
        cliente = self._cliente_actual
        log.info(
            f"🔐 Renovando token SSO — cliente: {cliente['client_id']}"
        )

        try:
            # auth-sso espera JSON con client_id y client_secret (BaseModel Pydantic)
            respuesta = requests.post(
                config.AUTH_SSO_URL,
                json={
                    "client_id":     cliente["client_id"],
                    "client_secret": cliente["client_secret"],
                },
                timeout=10,
            )
            respuesta.raise_for_status()
            self._token = respuesta.json()["access_token"]
            self._obtenido_en = time.time()
            log.info(f"🔐 Token obtenido correctamente para '{cliente['client_id']}'")
        except requests.exceptions.ConnectionError:
            log.warning(
                f"⚠️  auth-sso no disponible en {config.AUTH_SSO_URL}. "
                "Continuando sin JWT (los requests fallarán con 401)."
            )
            self._token = "token-no-disponible"
            self._obtenido_en = time.time()
        except Exception as exc:
            log.error(f"❌ Error al obtener token SSO: {exc}")
            self._token = "token-error"
            self._obtenido_en = time.time()

        # Rotar cliente para la próxima renovación
        self._rotar_cliente()


# ═══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE TRANSACCIONES — 85% normales, 15% fraudulentas
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LoteTransacciones:
    """
    Resultado del generador: una o más transacciones con metadatos.
    Lista de más de 1 elemento → patrón de ráfaga (patrón 5).
    """
    transacciones: list[dict]
    es_fraude: bool
    patron: str          # "normal", "monto_inusual", "horario_nocturno", etc.
    cliente_nombre: str


class GeneradorTransacciones:
    """
    Genera transacciones financieras chilenas sintéticas con distribución
    85% normales / 15% fraudulentas y 5 patrones de fraude distintos.
    """

    # Peso relativo de cada patrón de fraude (suman 100)
    _PATRONES_FRAUDE = [
        ("monto_inusual",        25),
        ("horario_nocturno",     20),
        ("region_diferente",     20),
        ("comercio_desconocido", 20),
        ("rafaga",               15),
    ]

    def generar(self) -> LoteTransacciones:
        """
        Punto de entrada: decide si la transacción es normal o fraudulenta
        y delega la construcción al método correspondiente.
        """
        cliente = random.choice(PERFILES_CLIENTES)

        if random.random() < 0.85:
            # 85% — transacción dentro de parámetros normales
            return LoteTransacciones(
                transacciones=[self._construir_normal(cliente)],
                es_fraude=False,
                patron="normal",
                cliente_nombre=cliente["nombre"],
            )
        else:
            # 15% — transacción con patrón de fraude
            return self._construir_fraudulenta(cliente)

    # ── Transacción normal ────────────────────────────────────────────────────

    def _construir_normal(self, cliente: dict) -> dict:
        """Transacción coherente con el perfil habitual del cliente."""
        canales = [c for c, _ in CANALES_PESOS]
        pesos   = [p for _, p in CANALES_PESOS]

        return {
            "id":          self._nuevo_id(),
            "rut_cliente": cliente["rut"],
            "comercio":    random.choice(COMERCIOS_NORMALES),
            "monto_clp":   random.randint(cliente["gasto_min"], cliente["gasto_max"]),
            "tipo":        random.choice(TIPOS),
            "region":      cliente["region"],
            "hora":        self._hora_normal(),
            "canal":       random.choices(canales, weights=pesos, k=1)[0],
        }

    # ── Transacciones fraudulentas ────────────────────────────────────────────

    def _construir_fraudulenta(self, cliente: dict) -> LoteTransacciones:
        """Selecciona un patrón de fraude y delega la construcción."""
        patrones = [p for p, _ in self._PATRONES_FRAUDE]
        pesos    = [w for _, w in self._PATRONES_FRAUDE]
        patron   = random.choices(patrones, weights=pesos, k=1)[0]

        if patron == "monto_inusual":
            txn = self._construir_normal(cliente)
            txn["monto_clp"] = random.randint(2_000_000, 9_999_999)
            txn["id"] = self._nuevo_id()
            return LoteTransacciones([txn], True, patron, cliente["nombre"])

        elif patron == "horario_nocturno":
            txn = self._construir_normal(cliente)
            txn["hora"] = self._hora_nocturna()
            txn["id"] = self._nuevo_id()
            return LoteTransacciones([txn], True, patron, cliente["nombre"])

        elif patron == "region_diferente":
            # Seleccionar una región distinta a la habitual del cliente
            regiones_otras = [r for r in REGIONES_CHILE if r != cliente["region"]]
            txn = self._construir_normal(cliente)
            txn["region"] = random.choice(regiones_otras)
            txn["id"] = self._nuevo_id()
            return LoteTransacciones([txn], True, patron, cliente["nombre"])

        elif patron == "comercio_desconocido":
            txn = self._construir_normal(cliente)
            txn["comercio"] = random.choice(COMERCIOS_SOSPECHOSOS)
            txn["monto_clp"] = random.randint(500_000, 5_000_000)
            txn["canal"] = "web"
            txn["id"] = self._nuevo_id()
            return LoteTransacciones([txn], True, patron, cliente["nombre"])

        elif patron == "rafaga":
            # Patrón 5 — 3 transacciones del mismo RUT en menos de 2 minutos.
            # Las 3 se enviarán con 5–10 s de diferencia en el inyector.
            txns = []
            for _ in range(3):
                txn = self._construir_normal(cliente)
                txn["id"]      = self._nuevo_id()
                txn["monto_clp"] = random.randint(200_000, 800_000)
                # Hora idéntica para que parezcan simultáneas
                txn["hora"] = datetime.now().strftime("%H:%M")
                txns.append(txn)
            return LoteTransacciones(txns, True, patron, cliente["nombre"])

        # Fallback (no debería ocurrir)
        return LoteTransacciones(
            [self._construir_normal(cliente)], False, "normal", cliente["nombre"]
        )

    # ── Utilidades ────────────────────────────────────────────────────────────

    @staticmethod
    def _nuevo_id() -> str:
        """Genera un ID de transacción corto y único."""
        return f"TXN-{str(uuid.uuid4())[:6].upper()}"

    @staticmethod
    def _hora_normal() -> str:
        """Hora en horario comercial: 08:00–22:00."""
        return f"{random.randint(8, 21):02d}:{random.randint(0, 59):02d}"

    @staticmethod
    def _hora_nocturna() -> str:
        """Hora en franja nocturna de alto riesgo: 00:00–05:59."""
        return f"{random.randint(0, 5):02d}:{random.randint(0, 59):02d}"


# ═══════════════════════════════════════════════════════════════════════════════
# INYECTOR — Orquesta autenticación, generación y envío
# ═══════════════════════════════════════════════════════════════════════════════

class Inyector:
    """
    Orquesta el ciclo completo:
    1. Obtiene/renueva JWT desde auth-sso
    2. Genera la transacción (normal o fraudulenta)
    3. Envía al webhook de n8n
    4. Imprime el resultado en consola y escribe al log
    5. Muestra resumen cada 10 transacciones
    """

    _SEPARADOR = "─" * 60

    def __init__(self, intervalo: int):
        self._sso       = SesionSSO()
        self._generador = GeneradorTransacciones()
        self._intervalo = intervalo

        # Contadores de sesión
        self._total       = 0
        self._normales    = 0
        self._fraudulentas = 0

    # ── Envío HTTP ────────────────────────────────────────────────────────────

    def _enviar(self, transaccion: dict, token: str) -> bool:
        """
        Envía una transacción al webhook de n8n con el JWT en el header.
        Retorna True si el servidor respondió 2xx, False en cualquier otro caso.
        """
        try:
            respuesta = requests.post(
                config.N8N_WEBHOOK_URL,
                json=transaccion,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            return respuesta.ok
        except requests.exceptions.ConnectionError:
            log.warning(
                f"⚠️  n8n no disponible en {config.N8N_WEBHOOK_URL}. "
                "Verifica que los servicios estén corriendo."
            )
            return False
        except Exception as exc:
            log.error(f"❌ Error inesperado al enviar transacción: {exc}")
            return False

    # ── Logging visual ────────────────────────────────────────────────────────

    def _imprimir_transaccion(
        self,
        txn: dict,
        es_fraude: bool,
        patron: str,
        exito: bool,
    ):
        """Imprime la línea de log con ícono, datos y estado HTTP."""
        hora_actual = datetime.now().strftime("%H:%M:%S")
        icono       = "🚨" if es_fraude else "✅"
        etiqueta    = f"FRAUDE [{patron}]" if es_fraude else "NORMAL"
        estado_http = "→ OK" if exito else "→ ERROR"
        monto_fmt   = f"${txn['monto_clp']:,}".replace(",", ".")

        linea = (
            f"{icono} [{hora_actual}] {txn['id']} | "
            f"{txn['comercio'][:22]:<22} | "
            f"{monto_fmt:>15} | "
            f"{etiqueta:<25} | "
            f"{txn['region']:<25} | "
            f"{estado_http}"
        )
        log.info(linea)

    def _imprimir_resumen(self):
        """Muestra estadísticas acumuladas cada 10 transacciones."""
        tasa = (self._fraudulentas / self._total * 100) if self._total else 0
        log.info(self._SEPARADOR)
        log.info(
            f"📊 RESUMEN | Total: {self._total} | "
            f"Normales: {self._normales} | "
            f"Fraudulentas: {self._fraudulentas} | "
            f"Tasa: {tasa:.0f}%"
        )
        log.info(self._SEPARADOR)

    # ── Ciclo de procesamiento ────────────────────────────────────────────────

    def _procesar_lote(self, lote: LoteTransacciones):
        """
        Envía todas las transacciones del lote.
        Para el patrón de ráfaga (3 txns), añade un micro-delay entre ellas.
        """
        es_rafaga = len(lote.transacciones) > 1

        for i, txn in enumerate(lote.transacciones):
            token = self._sso.obtener_token()
            exito = self._enviar(txn, token)

            self._total += 1
            if lote.es_fraude:
                self._fraudulentas += 1
            else:
                self._normales += 1

            self._imprimir_transaccion(txn, lote.es_fraude, lote.patron, exito)

            # Mostrar resumen cada 10 transacciones
            if self._total % 10 == 0:
                self._imprimir_resumen()

            # Micro-delay entre transacciones de ráfaga (simula < 2 minutos)
            if es_rafaga and i < len(lote.transacciones) - 1:
                time.sleep(random.uniform(5, 10))

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def ejecutar(self, count: Optional[int] = None):
        """
        Bucle principal del inyector.

        Args:
            count: Si se especifica, detiene el script tras enviar ese número
                   de transacciones. Si es None, corre indefinidamente.
        """
        modo = f"TURBO ({self._intervalo}s)" if self._intervalo <= 5 else f"NORMAL ({self._intervalo}s)"
        limite = f"hasta {count} transacciones" if count else "indefinidamente"

        log.info(self._SEPARADOR)
        log.info(f"🚀 Inyector iniciado — Modo: {modo} | Corriendo {limite}")
        log.info(f"   Webhook: {config.N8N_WEBHOOK_URL}")
        log.info(f"   Auth SSO: {config.AUTH_SSO_URL}")
        log.info(self._SEPARADOR)

        # Obtener token inicial antes de empezar
        self._sso.obtener_token()

        try:
            while True:
                # Verificar límite de transacciones
                if count is not None and self._total >= count:
                    break

                # Generar y enviar
                lote = self._generador.generar()
                self._procesar_lote(lote)

                # Esperar el intervalo configurado
                # (excepto si ya llegamos al límite)
                if count is None or self._total < count:
                    time.sleep(self._intervalo)

        except KeyboardInterrupt:
            log.info("\n⛔ Inyector detenido por el usuario.")
        finally:
            # Resumen final siempre
            if self._total > 0:
                log.info(self._SEPARADOR)
                log.info("📋 SESIÓN FINALIZADA")
                self._imprimir_resumen()


# ═══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA — Parseo de argumentos CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parsear_argumentos() -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="RPA — Inyector de transacciones financieras chilenas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python rpa/transaction_injector.py                  # modo normal (30s)
  python rpa/transaction_injector.py --turbo          # modo demo (5s)
  python rpa/transaction_injector.py --count 50       # envía 50 y termina
  python rpa/transaction_injector.py --turbo --count 20
        """,
    )
    parser.add_argument(
        "--turbo",
        action="store_true",
        default=config.TURBO_MODE,
        help=f"Modo demo: {config.TURBO_INTERVAL}s entre transacciones (default: {config.INTERVAL_SECONDS}s)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        metavar="N",
        help="Detener tras enviar N transacciones (default: infinito)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parsear_argumentos()

    intervalo = config.TURBO_INTERVAL if args.turbo else config.INTERVAL_SECONDS

    inyector = Inyector(intervalo=intervalo)
    inyector.ejecutar(count=args.count)
