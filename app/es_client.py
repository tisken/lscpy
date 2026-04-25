from __future__ import annotations
from elasticsearch import Elasticsearch
from app.settings_store import get_datasource
from app.fingerprint import compute_fingerprint
from app.analysis_cache import get_error_status

_DEFAULT_FIELDS = {
    "level": "level",
    "timestamp": "@timestamp",
    "message": "message",
    "exception_class": "exception.class.keyword",
    "stack_trace": "stack_trace",
    "stack_trace_alt": "exception.stacktrace",
    "logger": "logger_name.keyword",
}


def _get_fields(ds: dict) -> dict:
    fm = ds.get("field_mapping", {})
    return {k: fm.get(k, v) for k, v in _DEFAULT_FIELDS.items()}


def _get_client(ds_id: str) -> tuple[Elasticsearch, dict]:
    ds = get_datasource(ds_id)
    if not ds:
        raise ValueError(f"Datasource '{ds_id}' not found")

    scheme = "https" if ds.get("use_ssl", True) else "http"
    host = ds["host"].replace("https://", "").replace("http://", "").rstrip("/")
    port = ds.get("port", 9200)
    url = f"{scheme}://{host}:{port}"

    kwargs: dict = {
        "hosts": [url],
        "basic_auth": (ds["user"], ds["password"]),
        "request_timeout": 30,
        "verify_certs": ds.get("verify_certs", False),
    }
    if ds.get("ca_cert_path"):
        kwargs["ca_certs"] = ds["ca_cert_path"]
    return Elasticsearch(**kwargs), ds


def _build_filters(f: dict, hours: int, message: str = "", logger: str = "", exception: str = "") -> list[dict]:
    filters: list[dict] = [
        {"term": {f["level"]: {"value": "ERROR"}}},
        {"range": {f["timestamp"]: {"gte": f"now-{hours}h"}}},
    ]
    if message:
        filters.append({"match_phrase": {f["message"]: message}})
    if logger:
        filters.append({"wildcard": {f["logger"]: f"*{logger}*"}})
    if exception:
        filters.append({"wildcard": {f["exception_class"]: f"*{exception}*"}})
    return filters


def _extract_stack(hit: dict, f: dict) -> str:
    """Extrae stacktrace del hit usando campo principal o alternativo."""
    # Navegar campos con punto (ej: exception.stacktrace)
    def _get_nested(d, path):
        for part in path.split("."):
            if isinstance(d, dict):
                d = d.get(part, "")
            else:
                return ""
        return d or ""

    st = _get_nested(hit, f["stack_trace"])
    if not st:
        st = _get_nested(hit, f["stack_trace_alt"])
    return st


def get_top_errors(
    ds_id: str, hours: int = 24, size: int = 50,
    message: str = "", logger: str = "", exception: str = "",
) -> list[dict]:
    es, ds = _get_client(ds_id)
    f = _get_fields(ds)
    query = {
        "size": 0,
        "query": {"bool": {"must": _build_filters(f, hours, message, logger, exception)}},
        "aggs": {
            "error_groups": {
                "multi_terms": {
                    "terms": [
                        {"field": f["exception_class"], "missing": "unknown"},
                        {"field": f["logger"], "missing": "unknown"},
                    ],
                    "size": size,
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "sample": {
                        "top_hits": {
                            "size": 1,
                            "sort": [{f["timestamp"]: "desc"}],
                        }
                    }
                },
            }
        },
    }
    resp = es.search(index=ds["index"], body=query)
    results = []
    for bucket in resp["aggregations"]["error_groups"]["buckets"]:
        hit = bucket["sample"]["hits"]["hits"][0]["_source"]
        exc_class = bucket["key"][0]
        stack = _extract_stack(hit, f)
        fp = compute_fingerprint(exc_class, stack)
        status = get_error_status(fp)

        # Extraer message con navegación de campos anidados
        msg = hit
        for part in f["message"].split("."):
            msg = msg.get(part, "") if isinstance(msg, dict) else ""

        results.append({
            "count": bucket["doc_count"],
            "exception_class": exc_class,
            "logger": bucket["key"][1],
            "message": msg if isinstance(msg, str) else str(msg),
            "stack_trace": stack,
            "timestamp": hit.get(f["timestamp"].lstrip("@"), hit.get(f["timestamp"], "")),
            "fingerprint": fp,
            "status": status["status"],
            "first_seen": status["first_seen"],
            "hit_count": status["hit_count"],
        })
    return results


def get_error_detail(ds_id: str, hours: int, exception_class: str, logger: str, max_samples: int = 5) -> list[dict]:
    es, ds = _get_client(ds_id)
    f = _get_fields(ds)
    filters = _build_filters(f, hours)
    filters.append({"term": {f["exception_class"]: exception_class}})
    filters.append({"term": {f["logger"]: logger}})
    query = {
        "size": max_samples,
        "query": {"bool": {"must": filters}},
        "sort": [{f["timestamp"]: "desc"}],
    }
    resp = es.search(index=ds["index"], body=query)
    return [h["_source"] for h in resp["hits"]["hits"]]


def test_connection(ds_id: str) -> dict:
    try:
        es, ds = _get_client(ds_id)
        info = es.info()
        return {"ok": True, "cluster": info["cluster_name"], "version": info["version"]["number"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
