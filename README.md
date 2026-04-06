# 🚨 Fraud Detection System — Banca Chile

Sistema de detección de fraude en tiempo real para transacciones financieras chilenas. Arquitectura de microservicios con Docker, orquestación visual con n8n, análisis AI con GPT-4o y alertas automáticas por Slack y email.

## 🏗️ Arquitectura
┌─────────────────────────────────────────────────────────────┐
│                    MICROSERVICIOS                           │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ fraud-api   │  │fraud-analyzer│  │  fraud-notifier   │  │
│  │ FastAPI     │  │ LangChain    │  │  Alertas          │  │
│  │ :8000       │  │ GPT-4o       │  │  Email/Slack      │  │
│  └──────┬──────┘  └──────┬───────┘  └───────────────────┘  │
│         │                │                                  │
└─────────┼────────────────┼──────────────────────────────────┘
│                │
┌─────────▼────────────────▼──────────────────────────────────┐
│                      n8n :5678                              │
│                                                             │
│  Webhook → HTTP Request → IF → Code → Slack + Email        │
│                              └──────→ Log                   │
└─────────────────────────────────────────────────────────────┘
FLUJO:
[1] Transacción llega al Webhook de n8n
[2] n8n llama a fraud-api:8000/analizar
[3] fraud-analyzer analiza con GPT-4o
[4] IF risk_level = CRITICAL/HIGH → Slack + Email
[5] IF risk_level = LOW/MEDIUM → solo log
## 🛠️ Tech Stack

| Componente | Tecnología |
|---|---|
| Orquestación | n8n |
| API Gateway | FastAPI |
| Análisis AI | LangChain + GPT-4o |
| Alertas | Slack Webhook + SendGrid |
| Containerización | Docker Compose |
| Secretos | Docker Secrets |
| Arquitectura | Microservicios |

## 📦 Microservicios

| Servicio | Puerto | Responsabilidad |
|---|---|---|
| fraud-api | 8000 | Recibe transacciones, coordina análisis |
| fraud-analyzer | interno | Analiza riesgo con GPT-4o |
| fraud-notifier | interno | Envía alertas |
| n8n | 5678 | Orquestación visual del pipeline |

## 🔐 Gestión de Secretos
Local/Dev     → Docker Secrets
CI/CD         → GitHub Secrets
Producción    → Azure Key Vault
Compatible con Azure Key Vault sin cambios de código — el secreto se monta en el mismo path `/run/secrets/openai_key`.

## 🚀 Instalación
```bash
git clone https://github.com/joseluisverag-hub/fraud-detection-system
cd fraud-detection-system
echo "sk-tu-openai-key" > secrets/openai_key.txt
docker compose up --build
```

Abrir n8n en `http://localhost:5678` e importar `n8n/workflow.json`.

## 🧪 Prueba rápida
```bash
# Transacción sospechosa (CRITICAL)
curl -X POST http://localhost:5678/webhook-test/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "id": "TXN-001",
    "rut_cliente": "12.345.678-9",
    "comercio": "Comercio Desconocido",
    "monto_clp": 8500000,
    "tipo": "crédito",
    "region": "Magallanes",
    "hora": "02:30",
    "canal": "web"
  }'

# Transacción normal (LOW)
curl -X POST http://localhost:5678/webhook-test/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "id": "TXN-002",
    "rut_cliente": "12.345.678-9",
    "comercio": "Supermercado Lider",
    "monto_clp": 45000,
    "tipo": "débito",
    "region": "Metropolitana",
    "hora": "12:30",
    "canal": "presencial"
  }'
```

## 💼 Casos de uso empresariales

- Bancos: monitoreo de transacciones en tiempo real
- Fintech: detección de fraude en pagos digitales
- Retail financiero: protección de tarjetas de crédito
- PSP: monitoreo de transacciones de adquirencia

## 👤 Autor
José Luis Vera — IT Operations Senior & AI Engineer
[GitHub](https://github.com/joseluisverag-hub)
