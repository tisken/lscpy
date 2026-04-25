from __future__ import annotations
import json
from pathlib import Path

_FILE = Path("settings.json")
_cache: dict | None = None

_DEFAULTS = {
    "datasources": {},
    "llm": {
        "provider": "bedrock",
        "bedrock": {
            "region": "eu-west-1",
            "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "llama3:8b",
        },
    },
    "bitbucket": {
        "workspace": "",
        "repo": "",
        "branch": "main",
        "user": "",
        "app_password": "",
    },
    "smtp": {
        "host": "",
        "port": 587,
        "user": "",
        "password": "",
        "use_tls": True,
        "use_ssl": False,
        "jira_email": "",
        "jira_project_key": "PROJ",
    },
}


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if _FILE.exists():
        _cache = json.loads(_FILE.read_text())
    else:
        _cache = json.loads(json.dumps(_DEFAULTS))
        _save()
    # Asegurar que todas las secciones existen
    for k, v in _DEFAULTS.items():
        if k not in _cache:
            _cache[k] = json.loads(json.dumps(v))
    return _cache


def _save():
    _FILE.write_text(json.dumps(_cache, indent=2))


# --- Getters genéricos ---

def get_section(section: str) -> dict:
    return _load().get(section, {})


def update_section(section: str, data: dict) -> dict:
    store = _load()
    if section not in store:
        store[section] = {}
    store[section].update(data)
    _save()
    return store[section]


def get_all() -> dict:
    return _load()


# --- Datasources helpers ---

def list_datasources() -> list[dict]:
    ds = _load().get("datasources", {})
    return [{"id": k, **v} for k, v in ds.items()]


def get_datasource(ds_id: str) -> dict | None:
    ds = _load().get("datasources", {})
    if ds_id not in ds:
        return None
    return {"id": ds_id, **ds[ds_id]}


def save_datasource(ds_id: str, data: dict) -> dict:
    store = _load()
    ds = store.setdefault("datasources", {})
    ds[ds_id] = {
        "name": data.get("name", ds_id),
        "host": data.get("host", "https://localhost"),
        "port": data.get("port", 9200),
        "user": data.get("user", "elastic"),
        "password": data.get("password", ""),
        "index": data.get("index", "app-logs-*"),
        "use_ssl": data.get("use_ssl", True),
        "verify_certs": data.get("verify_certs", False),
        "ca_cert_path": data.get("ca_cert_path", ""),
    }
    _save()
    return {"id": ds_id, **ds[ds_id]}


def delete_datasource(ds_id: str) -> bool:
    store = _load()
    ds = store.get("datasources", {})
    if ds_id not in ds:
        return False
    del ds[ds_id]
    _save()
    return True
