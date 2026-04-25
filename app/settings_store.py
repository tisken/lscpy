from __future__ import annotations
import json
from pathlib import Path
from app.crypto import encrypt, decrypt

_FILE = Path("settings.json")
_cache: dict | None = None

# Campos que contienen passwords y deben cifrarse
_SECRET_FIELDS = {
    "datasources": ["password"],
    "bitbucket": ["app_password"],
    "smtp": ["password"],
}

_DEFAULTS = {
    "datasources": {},
    "llm": {
        "provider": "bedrock",
        "bedrock": {"region": "eu-west-1", "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0"},
        "ollama": {"base_url": "http://localhost:11434", "model": "llama3:8b"},
    },
    "bitbucket": {"workspace": "", "repo": "", "branch": "main", "user": "", "app_password": ""},
    "smtp": {"host": "", "port": 587, "user": "", "password": "", "use_tls": True, "use_ssl": False, "jira_email": "", "jira_project_key": "PROJ"},
}


def _encrypt_secrets(section: str, data: dict) -> dict:
    """Cifra los campos sensibles de una sección."""
    fields = _SECRET_FIELDS.get(section, [])
    for f in fields:
        if f in data and data[f]:
            data[f] = encrypt(data[f])
    return data


def _decrypt_secrets(section: str, data: dict) -> dict:
    """Descifra los campos sensibles de una sección."""
    fields = _SECRET_FIELDS.get(section, [])
    out = dict(data)
    for f in fields:
        if f in out and out[f]:
            out[f] = decrypt(out[f])
    return out


def _decrypt_datasources(ds_dict: dict) -> dict:
    """Descifra passwords de todos los datasources."""
    return {k: _decrypt_secrets("datasources", v) for k, v in ds_dict.items()}


def _load_raw() -> dict:
    """Carga el JSON sin descifrar."""
    global _cache
    if _cache is not None:
        return _cache
    if _FILE.exists():
        _cache = json.loads(_FILE.read_text())
    else:
        _cache = json.loads(json.dumps(_DEFAULTS))
        _save()
    for k, v in _DEFAULTS.items():
        if k not in _cache:
            _cache[k] = json.loads(json.dumps(v))
    return _cache


def _save():
    _FILE.write_text(json.dumps(_cache, indent=2))


# --- Getters (descifran al devolver) ---

def get_section(section: str) -> dict:
    raw = _load_raw().get(section, {})
    return _decrypt_secrets(section, raw)


def update_section(section: str, data: dict) -> dict:
    store = _load_raw()
    if section not in store:
        store[section] = {}
    encrypted = _encrypt_secrets(section, dict(data))
    store[section].update(encrypted)
    _save()
    return _decrypt_secrets(section, store[section])


def get_all() -> dict:
    raw = _load_raw()
    out = {}
    for k, v in raw.items():
        if k == "datasources":
            out[k] = _decrypt_datasources(v)
        else:
            out[k] = _decrypt_secrets(k, v) if isinstance(v, dict) else v
    return out


# --- Datasources ---

def list_datasources() -> list[dict]:
    ds = _load_raw().get("datasources", {})
    return [{"id": k, **_decrypt_secrets("datasources", v)} for k, v in ds.items()]


def get_datasource(ds_id: str) -> dict | None:
    ds = _load_raw().get("datasources", {})
    if ds_id not in ds:
        return None
    return {"id": ds_id, **_decrypt_secrets("datasources", ds[ds_id])}


def save_datasource(ds_id: str, data: dict) -> dict:
    store = _load_raw()
    ds = store.setdefault("datasources", {})
    entry = {
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
    ds[ds_id] = _encrypt_secrets("datasources", entry)
    _save()
    return {"id": ds_id, **_decrypt_secrets("datasources", ds[ds_id])}


def delete_datasource(ds_id: str) -> bool:
    store = _load_raw()
    ds = store.get("datasources", {})
    if ds_id not in ds:
        return False
    del ds[ds_id]
    _save()
    return True
