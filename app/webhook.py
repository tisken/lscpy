from __future__ import annotations
import httpx
from app.settings_store import get_section


async def send_webhook(analyses: list[dict], channel: str = "") -> dict:
    """Envía resumen de errores a webhook configurado (Slack o genérico)."""
    cfg = get_section("webhook")
    url = cfg.get("url", "")
    if not url:
        raise ValueError("Webhook URL not configured")

    wh_type = cfg.get("type", "slack")
    text = _build_text(analyses)

    if wh_type == "slack":
        payload = {"text": text}
        if channel or cfg.get("channel"):
            payload["channel"] = channel or cfg["channel"]
    else:
        payload = {"text": text, "analyses_count": len(analyses)}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()

    return {"status": "sent", "type": wh_type}


def _build_text(analyses: list[dict]) -> str:
    lines = [f"🔍 *LSC Error Report* — {len(analyses)} errores analizados\n"]
    for a in analyses[:10]:
        err = a.get("error", {})
        llm = a.get("llm_result", {})
        snippet = a.get("snippet")
        link = f" <{snippet['bb_url']}|código>" if snippet else ""
        analysis_preview = (llm.get("analysis", ""))[:150].replace("\n", " ")
        lines.append(
            f"• *{err.get('exception_class', '?')}* ({err.get('count', '?')}x) — {err.get('logger', '')}{link}\n"
            f"  _{analysis_preview}_"
        )
    if len(analyses) > 10:
        lines.append(f"\n... y {len(analyses) - 10} más")
    return "\n".join(lines)
