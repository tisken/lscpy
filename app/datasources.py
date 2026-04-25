import json
import uuid
from pathlib import Path
from app.config import get_settings

_cache: dict[str, dict] | None = None


def _file_path() -> Path:
    return Path(get_settings().datasources_file)


def _load() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    p = _file_path()
    if p.exists():
        _cache = json.loads(p.read_text())
    else:
        _cache = {}
    return _cache


def _save():
    _file_path().write_text(json.dumps(_cache, indent=2))


def list_datasources() -> list[dict]:
    ds = _load()
    return [{"id": k, **v} for k, v in ds.items()]


def get_datasource(ds_id: str) -> dict | None:
    ds = _load()
    if ds_id not in ds:
        return None
    return {"id": ds_id, **ds[ds_id]}


def create_datasource(data: dict) -> dict:
    ds = _load()
    ds_id = data.pop("id", None) or str(uuid.uuid4())[:8]
    ds[ds_id] = {
        "name": data.get("name", ds_id),
        "host": data.get("host", "https://localhost:9200"),
        "user": data.get("user", "elastic"),
        "password": data.get("password", ""),
        "index": data.get("index", "app-logs-*"),
        "ca_cert_path": data.get("ca_cert_path", ""),
    }
    _save()
    return {"id": ds_id, **ds[ds_id]}


def update_datasource(ds_id: str, data: dict) -> dict | None:
    ds = _load()
    if ds_id not in ds:
        return None
    for k in ("name", "host", "user", "password", "index", "ca_cert_path"):
        if k in data:
            ds[ds_id][k] = data[k]
    _save()
    return {"id": ds_id, **ds[ds_id]}


def delete_datasource(ds_id: str) -> bool:
    ds = _load()
    if ds_id not in ds:
        return False
    del ds[ds_id]
    _save()
    return True
