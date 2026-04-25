from __future__ import annotations
import asyncio
import json
import logging
import httpx
import boto3
from app.settings_store import get_section
from app.analysis_cache import get_cached, store as cache_store

logger = logging.getLogger("lsc.llm")

_semaphore = asyncio.Semaphore(3)  # Max 3 llamadas LLM concurrentes
_DELAY_BETWEEN_CALLS = 0.5  # segundos entre llamadas

_SYSTEM_PROMPT = """You are a senior Java developer analyzing production errors.
Given an error log with stacktrace and the relevant source code snippet, provide:
1. **Root Cause**: What is causing this error (1-2 sentences).
2. **Fix Suggestion**: Concrete code change to fix it, with a short code snippet if applicable.
3. **Severity**: CRITICAL / HIGH / MEDIUM / LOW based on production impact.
4. **Category**: e.g. NullPointer, ResourceLeak, ConcurrencyBug, ConfigError, ExternalDependency, etc.
Be concise and actionable. Answer in the same language the user message is written in."""


def _build_user_prompt(error: dict, snippet: dict | None) -> str:
    parts = [
        f"**Exception**: {error.get('exception_class', 'unknown')}",
        f"**Logger**: {error.get('logger', '')}",
        f"**Message**: {error.get('message', '')}",
        f"**Occurrences (last window)**: {error.get('count', '?')}",
        f"\n**Stack Trace**:\n```\n{error.get('stack_trace', 'N/A')}\n```",
    ]
    if snippet:
        parts.append(
            f"\n**Source Code** ({snippet['path']} around line {snippet['line']}):\n"
            f"```java\n{snippet['snippet']}\n```\n"
            f"Bitbucket link: {snippet['bb_url']}"
        )
    return "\n".join(parts)


async def analyze_error(error: dict, snippet: dict | None) -> dict:
    fingerprint = error.get("fingerprint", "")

    # Comprobar caché
    if fingerprint:
        cached = get_cached(fingerprint)
        if cached:
            logger.info("Cache hit for fingerprint %s", fingerprint)
            result = cached["analysis"]
            result["cached"] = True
            return result

    # Rate limiting: semáforo + delay
    async with _semaphore:
        await asyncio.sleep(_DELAY_BETWEEN_CALLS)
        llm_cfg = get_section("llm")
        user_msg = _build_user_prompt(error, snippet)
        try:
            if llm_cfg.get("provider", "bedrock") == "bedrock":
                result = await _call_bedrock(user_msg, llm_cfg.get("bedrock", {}))
            else:
                result = await _call_ollama(user_msg, llm_cfg.get("ollama", {}))
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            result = {"analysis": f"Error calling LLM: {e}", "model": "error"}

    # Guardar en caché
    if fingerprint and "error" not in result.get("model", ""):
        cache_store(fingerprint, result, error)

    result["cached"] = False
    return result


async def _call_bedrock(user_msg: str, cfg: dict) -> dict:
    region = cfg.get("region", "eu-west-1")
    model_id = cfg.get("model_id", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    client = boto3.client("bedrock-runtime", region_name=region)
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": _SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    })
    resp = client.invoke_model(modelId=model_id, body=body)
    result = json.loads(resp["body"].read())
    return {"analysis": result["content"][0]["text"], "model": model_id}


async def _call_ollama(user_msg: str, cfg: dict) -> dict:
    base_url = cfg.get("base_url", "http://localhost:11434")
    model = cfg.get("model", "llama3:8b")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"analysis": data["message"]["content"], "model": model}
