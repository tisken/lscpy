# Log Source Checker (LSC)

Analiza errores de producción desde Elasticsearch, localiza el código fuente en Bitbucket y sugiere fixes usando LLM.

## Features

- **Multi-datasource**: Múltiples clusters Elasticsearch con config independiente
- **Mapeo de campos configurable**: Adapta los nombres de campos ES a tu esquema
- **Fingerprint + deduplicación**: Agrupa errores idénticos por hash del stacktrace
- **Caché de análisis LLM**: No re-analiza errores ya vistos
- **Rate limiting LLM**: Semáforo de concurrencia + delay entre llamadas
- **Detección nuevo vs recurrente**: Marca errores como NUEVO o recurrente con first_seen
- **Tendencia/sparkline**: Mini gráfico de tendencia por error
- **Multi-repo Bitbucket**: Busca código fuente en múltiples repositorios
- **Dual LLM**: Amazon Bedrock (Claude) + Ollama (Llama 3)
- **Cron automático**: Pasos activables (buscar/analizar/enviar) con intervalo configurable
- **Auth con roles**: admin (todo) y viewer (solo lectura), JWT + bcrypt
- **Cambio de contraseña obligatorio** en primer login
- **Cifrado de passwords**: Fernet en settings.json
- **Notificaciones**: Email (Jira), Webhook/Slack
- **Export CSV**
- **Health check**: GET /api/health
- **Logging estructurado**

## Requisitos

- Python 3.9+
- Elasticsearch 8.x
- Bitbucket Cloud (con App Password)
- **Opción A**: AWS credentials para Bedrock (Claude)
- **Opción B**: Ollama corriendo localmente con `llama3:8b`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abrir http://localhost:8000 — Login: `admin` / `admin` (se pide cambiar en primer acceso)

## Uso

1. Ve a **Configuración** → añade un datasource (Elasticsearch)
2. Configura LLM (Bedrock u Ollama), Bitbucket y SMTP/Webhook
3. En **Errores** → selecciona datasource, configura filtros, busca errores
4. Analiza errores individuales o en bulk
5. Envía a Jira por email, Slack por webhook, o exporta CSV
6. En **Cron** → activa el análisis automático por pasos

## Roles

| Rol | Puede hacer |
|-----|------------|
| `admin` | Todo: config, datasources, cron, usuarios, análisis |
| `viewer` | Ver errores, analizar, exportar CSV |

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Health check (público) |
| POST | `/api/auth/login` | Login |
| GET | `/api/datasources` | Listar datasources |
| GET | `/api/errors?ds=ID&hours=24` | Buscar errores |
| POST | `/api/analyze` | Analizar un error |
| POST | `/api/send-jira` | Enviar a Jira |
| POST | `/api/send-webhook` | Enviar a Slack/webhook |
| GET | `/api/settings` | Config completa (admin) |
| GET/POST | `/api/cron/config` | Config cron |
| POST | `/api/cron/trigger` | Ejecutar cron manualmente |
| GET/POST/DELETE | `/api/users` | Gestión usuarios (admin) |
