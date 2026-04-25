import json
from pathlib import Path
from datetime import datetime, timezone

_FILE = Path("analysis_cache.json")
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if _FILE.exists():
        _cache = json.loads(_FILE.read_text())
    else:
        _cache = {}
    return _cache


def _save():
    _FILE.write_text(json.dumps(_cache, indent=2))


def get_cached(fingerprint: str) -> dict | None:
    entry = _load().get(fingerprint)
    if entry:
        # Actualizar last_seen y hit_count
        entry["last_seen"] = datetime.now(timezone.utc).isoformat()
        entry["hit_count"] = entry.get("hit_count", 1) + 1
        _save()
    return entry


def store(fingerprint: str, analysis: dict, error_summary: dict):
    cache = _load()
    now = datetime.now(timezone.utc).isoformat()
    is_new = fingerprint not in cache
    cache[fingerprint] = {
        "analysis": analysis,
        "error_summary": {
            "exception_class": error_summary.get("exception_class", ""),
            "logger": error_summary.get("logger", ""),
            "message": error_summary.get("message", "")[:200],
        },
        "first_seen": cache.get(fingerprint, {}).get("first_seen", now),
        "last_seen": now,
        "hit_count": 1 if is_new else cache.get(fingerprint, {}).get("hit_count", 0) + 1,
        "is_new": is_new,
    }
    _save()
    return cache[fingerprint]


def get_error_status(fingerprint: str) -> dict:
    """Devuelve si el error es nuevo, recurrente, y cuándo se vio por primera vez."""
    entry = _load().get(fingerprint)
    if not entry:
        return {"status": "new", "first_seen": None, "last_seen": None, "hit_count": 0}
    return {
        "status": "recurrent",
        "first_seen": entry.get("first_seen"),
        "last_seen": entry.get("last_seen"),
        "hit_count": entry.get("hit_count", 1),
    }


def get_stats() -> dict:
    cache = _load()
    return {
        "total_fingerprints": len(cache),
        "total_hits": sum(e.get("hit_count", 0) for e in cache.values()),
    }
