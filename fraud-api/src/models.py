"""
Modelos Pydantic para la API de detección de fraude.
Define los contratos de entrada y salida del sistema.
"""

from pydantic import BaseModel, Field
from typing import List
from enum import Enum


class TipoTransaccion(str, Enum):
    """Tipos de transacciones bancarias en Chile."""
    debito = "débito"
    credito = "crédito"
    transferencia = "transferencia"


class CanalTransaccion(str, Enum):
    """Canales de origen de la transacción."""
    app = "app"
    web = "web"
    presencial = "presencial"
    cajero = "cajero"


class Transaccion(BaseModel):
    """
    Representa una transacción financiera chilena.
    Es el modelo de entrada del webhook.
    """
    id: str = Field(..., description="Identificador único de la transacción")
    rut_cliente: str = Field(..., description="RUT del cliente en formato XX.XXX.XXX-X")
    comercio: str = Field(..., description="Nombre del comercio o beneficiario")
    monto_clp: int = Field(..., gt=0, description="Monto en pesos chilenos (CLP)")
    tipo: TipoTransaccion = Field(..., description="Tipo de transacción")
    region: str = Field(..., description="Región de Chile donde se realizó")
    hora: str = Field(..., description="Hora en formato HH:MM")
    canal: CanalTransaccion = Field(..., description="Canal utilizado")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "TXN-001",
                "rut_cliente": "12.345.678-9",
                "comercio": "Jumbo Las Condes",
                "monto_clp": 45000,
                "tipo": "débito",
                "region": "Región Metropolitana",
                "hora": "14:30",
                "canal": "presencial",
            }
        }
    }


class ResultadoAnalisis(BaseModel):
    """Resultado del análisis de riesgo devuelto por fraud-analyzer."""
    risk_score: int = Field(..., ge=0, le=100, description="Puntuación de riesgo 0-100")
    risk_level: str = Field(..., description="Nivel: LOW, MEDIUM, HIGH, CRITICAL")
    risk_factors: List[str] = Field(..., description="Factores de riesgo detectados")
    recommendation: str = Field(..., description="Acción: APPROVE, REVIEW, BLOCK")
    explanation: str = Field(..., description="Explicación en español")


class RespuestaFraude(BaseModel):
    """Respuesta completa del sistema de detección de fraude."""
    transaccion_id: str
    analisis: ResultadoAnalisis
    alerta_enviada: bool = Field(..., description="True si se notificó por riesgo HIGH/CRITICAL")
    timestamp: str = Field(..., description="ISO 8601 UTC")
