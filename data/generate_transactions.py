"""
Generador de transacciones financieras chilenas sintéticas.

Produce 100 transacciones realistas:
  - 85 normales  (patrones habituales de consumo)
  - 15 sospechosas (uno o más factores de riesgo)

Salida:
  - transactions_labeled.json  → con campo es_fraude y notas (para evaluación)
  - transactions_api.json      → solo campos del API (para pruebas reales)
"""

import random
import json
import uuid
from pathlib import Path


# ── Datos chilenos realistas ─────────────────────────────────────────────────

COMERCIOS_NORMALES = [
    "Jumbo Las Condes", "Lider Quilicura", "Falabella Parque Arauco",
    "Ripley Portal La Dehesa", "Paris Mall Plaza Norte",
    "Farmacia Cruz Verde", "Farmacia Ahumada", "Farmacia Salcobrand",
    "Copec Ruta 68", "Shell Pudahuel", "Petrobras Maipú",
    "McDonald's Providencia", "Starbucks Las Condes", "Burger King Centro",
    "Mercado Libre", "Rappi Chile", "Uber Chile", "Cornershop",
    "Entel", "Claro Chile", "VTR", "Movistar Chile",
    "Metro Santiago", "Bip! Recarga", "Transbank Pago",
    "Easy Pudahuel", "Sodimac Homecenter", "Unimarc Ñuñoa",
    "Santa Isabel Recoleta", "Tottus Maipú",
]

COMERCIOS_SOSPECHOSOS = [
    "CryptoExchange XY", "Casino Online 777", "Transfer Rápido SA",
    "Tienda Sin Nombre", "PaymentAnon Ltd", "BitTrade Chile",
    "WireTransfer Global", "Exchange Oscuro", "FastCash Anónimo",
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
CANALES = ["app", "web", "presencial", "cajero"]

# Región habitual del cliente de prueba
REGION_BASE = "Región Metropolitana"


# ── Funciones auxiliares ─────────────────────────────────────────────────────

def generar_rut() -> str:
    """Genera un RUT chileno ficticio con formato XX.XXX.XXX-X."""
    numero = random.randint(5_000_000, 25_000_000)
    s = str(numero)
    dv = random.choice("0123456789K")
    return f"{s[:2]}.{s[2:5]}.{s[5:]}-{dv}"


def hora_normal() -> str:
    """Hora comercial: 08:00–23:59."""
    return f"{random.randint(8, 23):02d}:{random.randint(0, 59):02d}"


def hora_sospechosa() -> str:
    """Horario nocturno de alto riesgo: 00:00–04:59."""
    return f"{random.randint(0, 4):02d}:{random.randint(0, 59):02d}"


def monto_normal() -> int:
    """Monto habitual chileno: $1.000–$499.999 CLP."""
    return random.randint(1_000, 499_999)


def monto_sospechoso() -> int:
    """Monto inusualmente alto: $1.500.000–$10.000.000 CLP."""
    return random.randint(1_500_000, 10_000_000)


# ── Generadores de transacciones ─────────────────────────────────────────────

def transaccion_normal() -> dict:
    """Crea una transacción con patrón completamente normal."""
    return {
        "id": str(uuid.uuid4())[:8].upper(),
        "rut_cliente": generar_rut(),
        "comercio": random.choice(COMERCIOS_NORMALES),
        "monto_clp": monto_normal(),
        "tipo": random.choice(TIPOS),
        "region": REGION_BASE,
        "hora": hora_normal(),
        "canal": random.choice(CANALES),
        # Metadatos de evaluación (no se envían al API)
        "es_fraude": False,
        "notas": "Transacción dentro de parámetros normales",
    }


def transaccion_sospechosa() -> dict:
    """
    Crea una transacción con 1 a 3 factores de riesgo combinados.
    Factores posibles: monto_alto, horario_nocturno, region_distinta,
                       canal_inusual, comercio_sospechoso.
    """
    # Seleccionar factores de riesgo aleatorios
    factores = random.sample(
        ["monto_alto", "horario_nocturno", "region_distinta",
         "canal_inusual", "comercio_sospechoso"],
        k=random.randint(1, 3),
    )

    regiones_otras = [r for r in REGIONES_CHILE if r != REGION_BASE]

    return {
        "id": str(uuid.uuid4())[:8].upper(),
        "rut_cliente": generar_rut(),
        "comercio": (
            random.choice(COMERCIOS_SOSPECHOSOS)
            if "comercio_sospechoso" in factores
            else random.choice(COMERCIOS_NORMALES)
        ),
        "monto_clp": (
            monto_sospechoso()
            if "monto_alto" in factores
            else monto_normal()
        ),
        "tipo": (
            "transferencia"
            if "canal_inusual" in factores
            else random.choice(TIPOS)
        ),
        "region": (
            random.choice(regiones_otras)
            if "region_distinta" in factores
            else REGION_BASE
        ),
        "hora": (
            hora_sospechosa()
            if "horario_nocturno" in factores
            else hora_normal()
        ),
        "canal": (
            "web"
            if "canal_inusual" in factores
            else random.choice(CANALES)
        ),
        # Metadatos de evaluación
        "es_fraude": True,
        "notas": f"Sospechosa — factores: {', '.join(factores)}",
    }


# ── Función principal ────────────────────────────────────────────────────────

def generar_dataset(n_total: int = 100) -> list:
    """
    Genera el dataset completo con la distribución indicada:
      85% normales, 15% sospechosas.
    """
    n_sospechosas = int(n_total * 0.15)  # 15 transacciones sospechosas
    n_normales = n_total - n_sospechosas  # 85 transacciones normales

    dataset = (
        [transaccion_normal() for _ in range(n_normales)] +
        [transaccion_sospechosa() for _ in range(n_sospechosas)]
    )

    random.shuffle(dataset)
    return dataset


if __name__ == "__main__":
    random.seed(42)  # Semilla fija para reproducibilidad

    transacciones = generar_dataset(100)
    output_dir = Path(__file__).parent

    # ── Archivo 1: con etiquetas (para evaluación del modelo) ────────────────
    labeled_path = output_dir / "transactions_labeled.json"
    with open(labeled_path, "w", encoding="utf-8") as f:
        json.dump(transacciones, f, ensure_ascii=False, indent=2)

    # ── Archivo 2: sin etiquetas (para pruebas reales del API) ───────────────
    campos_api = ["id", "rut_cliente", "comercio", "monto_clp",
                  "tipo", "region", "hora", "canal"]
    transacciones_api = [{k: t[k] for k in campos_api} for t in transacciones]

    api_path = output_dir / "transactions_api.json"
    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(transacciones_api, f, ensure_ascii=False, indent=2)

    # ── Estadísticas ──────────────────────────────────────────────────────────
    n_fraude = sum(1 for t in transacciones if t["es_fraude"])
    n_normal = len(transacciones) - n_fraude

    print(f"\nDataset generado: {len(transacciones)} transacciones")
    print(f"  Normales:     {n_normal:3d} ({n_normal/len(transacciones)*100:.0f}%)")
    print(f"  Sospechosas:  {n_fraude:3d} ({n_fraude/len(transacciones)*100:.0f}%)")
    print(f"\nArchivos creados:")
    print(f"  {labeled_path}  ← con etiquetas (evaluación)")
    print(f"  {api_path}       ← sin etiquetas (pruebas API)")

    # Mostrar 3 ejemplos de cada tipo
    normales = [t for t in transacciones if not t["es_fraude"]][:3]
    sospechosas = [t for t in transacciones if t["es_fraude"]][:3]

    print("\nEjemplos normales:")
    for t in normales:
        print(f"  [{t['id']}] ${t['monto_clp']:,} CLP | {t['comercio']} | {t['hora']} | {t['region']}")

    print("\nEjemplos sospechosos:")
    for t in sospechosas:
        print(f"  [{t['id']}] ${t['monto_clp']:,} CLP | {t['comercio']} | {t['hora']} | {t['notas']}")
