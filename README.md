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
- **Export CSV y PDF**
- **Health check**: GET /api/health
- **Logging estructurado**

## Requisitos

- Python 3.9+
- Elasticsearch 8.x
- Bitbucket Cloud (con App Password)
- **Opción A**: AWS credentials para Bedrock (Claude)
- **Opción B**: Ollama corriendo localmente con `llama3:8b`

### Dependencias del sistema (para export PDF)

```bash
# Ubuntu / Debian
sudo apt install -y libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libcairo2

# Amazon Linux / RHEL / Fedora
sudo yum install -y pango gdk-pixbuf2 cairo

# macOS
brew install pango
```

> Si no necesitas export PDF, la app funciona sin estas dependencias. El PDF se genera bajo demanda.

## Setup

### Opción A: Local

```bash
git clone https://github.com/tisken/lscpy.git
cd lscpy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # opcional, solo para defaults del cron
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Opción B: Docker

```bash
git clone https://github.com/tisken/lscpy.git
cd lscpy
docker compose up -d
```

### Opción C: Docker build manual

```bash
docker build -t lsc .
docker run -p 8000:8000 -v $(pwd)/settings.json:/app/settings.json lsc
```

## Primer acceso

1. Abrir http://localhost:8000
2. Login: `admin` / `admin`
3. Se pide cambiar la contraseña en el primer acceso
4. Ir a **Configuración** → añadir al menos un datasource (Elasticsearch)

## Uso

1. **Configuración** → añade datasources, configura LLM, Bitbucket y SMTP/Webhook
2. **Errores** → selecciona datasource, configura filtros, busca errores
3. Analiza errores individuales o en bulk con el LLM
4. Envía a Jira por email, Slack por webhook, o exporta CSV/PDF
5. **Cron** → activa el análisis automático por pasos

## Configuración

Toda la configuración se gestiona desde la UI (pestaña **Configuración**) y se persiste en `settings.json`. No hace falta editar ficheros manualmente.

### Datasources (Elasticsearch)

Cada datasource tiene:

| Campo | Descripción |
|-------|-------------|
| Host | Hostname del cluster ES (sin esquema) |
| Puerto | Puerto (default: 9200) |
| Usuario / Contraseña | Credenciales de acceso |
| Índice | Patrón de índice (ej: `app-logs-*`) |
| SSL | Usar HTTPS |
| Verificar certificado | Validar cert SSL |
| CA cert path | Ruta al certificado CA (opcional) |

#### Mapeo de campos

Si tus logs usan nombres de campos diferentes a los defaults, puedes configurar el mapeo por datasource:

| Campo lógico | Default | Descripción |
|--------------|---------|-------------|
| `level` | `level` | Nivel del log |
| `timestamp` | `@timestamp` | Timestamp del evento |
| `message` | `message` | Mensaje del error |
| `exception_class` | `exception.class.keyword` | Clase de la excepción |
| `stack_trace` | `stack_trace` | Stacktrace (campo principal) |
| `stack_trace_alt` | `exception.stacktrace` | Stacktrace (campo alternativo) |
| `logger` | `logger_name.keyword` | Logger Java |

### LLM

| Provider | Configuración |
|----------|--------------|
| **Amazon Bedrock** | Region AWS + Model ID (ej: `anthropic.claude-3-5-sonnet-20241022-v2:0`). Requiere AWS credentials configuradas (`~/.aws/credentials` o variables de entorno). |
| **Ollama** | Base URL (ej: `http://localhost:11434`) + modelo (ej: `llama3:8b`). Instalar [Ollama](https://ollama.ai) y ejecutar `ollama pull llama3:8b`. |

### Bitbucket Cloud

- Workspace + uno o más repositorios con su branch
- Usuario + App Password ([crear aquí](https://bitbucket.org/account/settings/app-passwords/))
- Soporta multi-repo: el stacktrace se busca en cada repo hasta encontrar el fichero

### SMTP / Jira

- Host, puerto, usuario, contraseña
- STARTTLS o SSL directo
- Email destino de Jira + clave de proyecto

### Webhook / Slack

- URL del webhook (Slack incoming webhook o endpoint genérico)
- Tipo: `slack` o `generic`
- Canal opcional

## Roles

| Rol | Puede hacer |
|-----|------------|
| `admin` | Todo: config, datasources, cron, gestión de usuarios, análisis |
| `viewer` | Ver errores, analizar, exportar CSV/PDF |

## Cron automático

El cron ejecuta un ciclo con 3 pasos activables independientemente:

1. **Buscar** → consulta ES y obtiene los top errores
2. **Analizar** → pasa cada error por Bitbucket + LLM
3. **Enviar** → manda el informe por email a Jira

Se configura desde la pestaña **Cron**: intervalo, datasource, filtros, y qué pasos activar.

## Estructura del proyecto

```
lscpy/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, endpoints, middleware auth
│   ├── config.py             # Settings desde .env (solo cron defaults)
│   ├── settings_store.py     # Config persistente en settings.json (cifrada)
│   ├── auth.py               # Usuarios, JWT, bcrypt, roles
│   ├── crypto.py             # Cifrado Fernet para passwords
│   ├── es_client.py          # Queries a Elasticsearch
│   ├── bitbucket_client.py   # API Bitbucket Cloud (multi-repo)
│   ├── llm_analyzer.py       # Bedrock + Ollama con caché y rate limit
│   ├── fingerprint.py        # Hash normalizado de stacktraces
│   ├── analysis_cache.py     # Caché persistente de análisis LLM
│   ├── mail_sender.py        # Envío email SMTP (Jira)
│   ├── webhook.py            # Notificaciones Slack/webhook
│   ├── pdf_report.py         # Generación de informes PDF
│   ├── scheduler.py          # Cron con pasos configurables
│   ├── logging_config.py     # Logging estructurado
│   └── templates/
│       ├── index.html        # UI principal (pestañas: Errores, Config, Cron)
│       └── login.html        # Login + cambio de contraseña
├── .env.example              # Variables de entorno (solo cron defaults)
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### Ficheros generados (en .gitignore)

| Fichero | Descripción |
|---------|-------------|
| `settings.json` | Configuración (datasources, LLM, BB, SMTP, webhook) |
| `users.json` | Usuarios y passwords (bcrypt) |
| `analysis_cache.json` | Caché de análisis LLM por fingerprint |
| `.secret_key` | Clave Fernet para cifrar passwords en settings.json |
| `.env` | Variables de entorno opcionales |

## API Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/health` | — | Health check |
| POST | `/api/auth/login` | — | Login |
| POST | `/api/auth/change-password` | ✓ | Cambiar contraseña |
| POST | `/api/auth/logout` | ✓ | Logout |
| GET | `/api/datasources` | ✓ | Listar datasources |
| POST | `/api/datasources` | ✓ | Crear datasource |
| PUT | `/api/datasources/{id}` | ✓ | Actualizar datasource |
| DELETE | `/api/datasources/{id}` | ✓ | Eliminar datasource |
| GET | `/api/datasources/{id}/test` | ✓ | Test conexión ES |
| GET | `/api/errors?ds=ID&hours=24` | ✓ | Buscar errores |
| POST | `/api/analyze` | ✓ | Analizar un error |
| POST | `/api/analyze/bulk` | ✓ | Analizar en bulk |
| POST | `/api/send-jira` | ✓ | Enviar email a Jira |
| POST | `/api/send-webhook` | ✓ | Enviar a Slack/webhook |
| POST | `/api/export-pdf` | ✓ | Exportar informe PDF |
| GET | `/api/settings` | admin | Config completa |
| GET/POST | `/api/settings/{section}` | admin | Config por sección |
| GET/POST | `/api/cron/config` | ✓/admin | Config cron |
| GET | `/api/cron/status` | ✓ | Estado del cron |
| POST | `/api/cron/trigger` | admin | Ejecutar cron manualmente |
| GET | `/api/users` | admin | Listar usuarios |
| POST | `/api/users` | admin | Crear usuario |
| DELETE | `/api/users/{username}` | admin | Eliminar usuario |
