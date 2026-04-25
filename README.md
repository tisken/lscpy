# Log Source Checker (LSC)

Analiza errores de producción desde Elasticsearch, localiza el código fuente en Bitbucket y sugiere fixes usando LLM.

## Requisitos

- Python 3.11+
- Elasticsearch 8.x
- Bitbucket Cloud (con App Password)
- **Opción A**: AWS credentials para Bedrock (Claude)
- **Opción B**: Ollama corriendo localmente con `llama3:8b`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus credenciales
```

## Ejecutar

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abrir http://localhost:8000

## Uso

1. Configura las horas y cantidad de errores a buscar
2. Click en **Buscar errores** para consultar Elasticsearch
3. Click en **Analizar** en un error individual o selecciona varios y usa **Analizar seleccionados**
4. Revisa el análisis del LLM con el código fuente de Bitbucket
5. Envía a Jira con el botón de email

## LLM Providers

Cambia `LLM_PROVIDER` en `.env`:

- `bedrock` → Amazon Bedrock (Claude 3.5 Sonnet). Requiere AWS credentials configuradas.
- `ollama` → Modelo local. Instala [Ollama](https://ollama.ai) y ejecuta `ollama pull llama3:8b`.

## Campos de Elasticsearch esperados

La app busca estos campos en tus logs:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `level` | keyword | Nivel del log (ERROR) |
| `@timestamp` | date | Timestamp del evento |
| `message` | text | Mensaje del error |
| `exception.class` | keyword | Clase de la excepción Java |
| `exception.stacktrace` o `stack_trace` | text | Stacktrace completo |
| `logger_name` | keyword | Logger Java (ej: com.app.MyService) |

> Si tus campos tienen nombres diferentes, ajusta las queries en `app/es_client.py`.
