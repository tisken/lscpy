from elasticsearch import Elasticsearch
from app.datasources import get_datasource


def _get_client(ds_id: str) -> tuple[Elasticsearch, dict]:
    ds = get_datasource(ds_id)
    if not ds:
        raise ValueError(f"Datasource '{ds_id}' not found")
    kwargs: dict = {
        "hosts": [ds["host"]],
        "basic_auth": (ds["user"], ds["password"]),
        "request_timeout": 30,
    }
    if ds.get("ca_cert_path"):
        kwargs["ca_certs"] = ds["ca_cert_path"]
    else:
        kwargs["verify_certs"] = False
    return Elasticsearch(**kwargs), ds


def _build_filters(hours: int, message: str = "", logger: str = "", exception: str = "") -> list[dict]:
    filters: list[dict] = [
        {"term": {"level": {"value": "ERROR"}}},
        {"range": {"@timestamp": {"gte": f"now-{hours}h"}}},
    ]
    if message:
        filters.append({"match_phrase": {"message": message}})
    if logger:
        filters.append({"wildcard": {"logger_name.keyword": f"*{logger}*"}})
    if exception:
        filters.append({"wildcard": {"exception.class.keyword": f"*{exception}*"}})
    return filters


def get_top_errors(
    ds_id: str, hours: int = 24, size: int = 50,
    message: str = "", logger: str = "", exception: str = "",
) -> list[dict]:
    es, ds = _get_client(ds_id)
    query = {
        "size": 0,
        "query": {"bool": {"must": _build_filters(hours, message, logger, exception)}},
        "aggs": {
            "error_groups": {
                "multi_terms": {
                    "terms": [
                        {"field": "exception.class.keyword", "missing": "unknown"},
                        {"field": "logger_name.keyword", "missing": "unknown"},
                    ],
                    "size": size,
                    "order": {"_count": "desc"},
                },
                "aggs": {
                    "sample": {
                        "top_hits": {
                            "size": 1,
                            "_source": [
                                "message", "exception", "stack_trace",
                                "logger_name", "@timestamp", "level",
                            ],
                            "sort": [{"@timestamp": "desc"}],
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
        results.append({
            "count": bucket["doc_count"],
            "exception_class": bucket["key"][0],
            "logger": bucket["key"][1],
            "message": hit.get("message", ""),
            "stack_trace": hit.get("stack_trace", hit.get("exception", {}).get("stacktrace", "")),
            "timestamp": hit.get("@timestamp", ""),
        })
    return results


def get_error_detail(ds_id: str, hours: int, exception_class: str, logger: str, max_samples: int = 5) -> list[dict]:
    es, ds = _get_client(ds_id)
    filters = _build_filters(hours)
    filters.append({"term": {"exception.class.keyword": exception_class}})
    filters.append({"term": {"logger_name.keyword": logger}})
    query = {
        "size": max_samples,
        "query": {"bool": {"must": filters}},
        "sort": [{"@timestamp": "desc"}],
    }
    resp = es.search(index=ds["index"], body=query)
    return [h["_source"] for h in resp["hits"]["hits"]]


def test_connection(ds_id: str) -> dict:
    """Testea la conexión a un datasource y devuelve info del cluster."""
    try:
        es, ds = _get_client(ds_id)
        info = es.info()
        return {"ok": True, "cluster": info["cluster_name"], "version": info["version"]["number"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
