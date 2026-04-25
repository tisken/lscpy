import json
import httpx
import boto3
from app.config import get_settings

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
    s = get_settings()
    user_msg = _build_user_prompt(error, snippet)
    if s.llm_provider == "bedrock":
        return await _call_bedrock(user_msg)
    return await _call_ollama(user_msg)


async def _call_bedrock(user_msg: str) -> dict:
    s = get_settings()
    client = boto3.client("bedrock-runtime", region_name=s.aws_region)
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
        }
    )
    resp = client.invoke_model(modelId=s.bedrock_model_id, body=body)
    result = json.loads(resp["body"].read())
    return {"analysis": result["content"][0]["text"], "model": s.bedrock_model_id}


async def _call_ollama(user_msg: str) -> dict:
    s = get_settings()
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{s.ollama_base_url}/api/chat",
            json={
                "model": s.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return {"analysis": data["message"]["content"], "model": s.ollama_model}
