from __future__ import annotations
from weasyprint import HTML


def build_pdf_html(analyses: list[dict]) -> str:
    """Genera HTML optimizado para PDF con estilos inline."""
    rows = ""
    for i, a in enumerate(analyses, 1):
        error = a.get("error", {})
        snippet = a.get("snippet")
        llm = a.get("llm_result", {})
        bb_link = f'<a href="{snippet["bb_url"]}">{snippet["path"]}:{snippet["line"]}</a>' if snippet else "N/A"
        analysis_text = (llm.get("analysis", "") or "")[:800].replace("<", "&lt;").replace(">", "&gt;")
        snippet_text = ""
        if snippet:
            snippet_text = f'<pre style="background:#f5f5f5;padding:8px;font-size:9px;border:1px solid #ddd;border-radius:4px;overflow:hidden">{snippet["snippet"][:600]}</pre>'

        rows += f"""<tr style="page-break-inside:avoid">
            <td style="padding:6px;border:1px solid #ddd;font-size:10px;text-align:center">{i}</td>
            <td style="padding:6px;border:1px solid #ddd;font-size:10px;font-family:monospace">{error.get('exception_class','')}</td>
            <td style="padding:6px;border:1px solid #ddd;font-size:10px;text-align:center">{error.get('count','')}</td>
            <td style="padding:6px;border:1px solid #ddd;font-size:10px">{error.get('logger','')}</td>
            <td style="padding:6px;border:1px solid #ddd;font-size:10px">{bb_link}</td>
        </tr>
        <tr style="page-break-inside:avoid">
            <td colspan="5" style="padding:8px;border:1px solid #ddd;font-size:9px">
                {snippet_text}
                <div style="margin-top:4px;white-space:pre-wrap;font-size:9px;line-height:1.4">{analysis_text}</div>
            </td>
        </tr>"""

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11px; color: #333; margin: 20px; }}
  h1 {{ font-size: 18px; color: #1e293b; margin-bottom: 4px; }}
  .meta {{ font-size: 10px; color: #666; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1e293b; color: #fff; padding: 8px; font-size: 10px; text-align: left; }}
  a {{ color: #3b82f6; }}
</style></head><body>
<h1>🔍 Log Source Checker — Error Report</h1>
<div class="meta">Generado: {now} | Errores: {len(analyses)}</div>
<table>
<tr><th>#</th><th>Exception</th><th>Count</th><th>Logger</th><th>Source</th></tr>
{rows}
</table></body></html>"""


def generate_pdf(analyses: list[dict]) -> bytes:
    """Genera PDF en bytes a partir de la lista de análisis."""
    html_content = build_pdf_html(analyses)
    return HTML(string=html_content).write_pdf()
