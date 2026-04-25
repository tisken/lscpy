import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.settings_store import get_section


def send_jira_email(subject: str, body_html: str, to: str | None = None) -> bool:
    cfg = get_section("smtp")
    dest = to or cfg.get("jira_email", "")
    host = cfg.get("host", "")
    if not dest or not host:
        raise ValueError("SMTP or Jira email not configured")

    port = cfg.get("port", 587)
    user = cfg.get("user", "")
    password = cfg.get("password", "")
    project_key = cfg.get("jira_project_key", "PROJ")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{project_key}] {subject}"
    msg["From"] = user
    msg["To"] = dest
    msg.attach(MIMEText(body_html, "html"))

    if cfg.get("use_ssl", False):
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx) as server:
            if user and password:
                server.login(user, password)
            server.sendmail(user, [dest], msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            if cfg.get("use_tls", True):
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(user, [dest], msg.as_string())
    return True


def build_report_html(analyses: list[dict]) -> str:
    rows = ""
    for a in analyses:
        error = a.get("error", {})
        snippet = a.get("snippet")
        llm = a.get("llm_result", {})
        bb_link = f'<a href="{snippet["bb_url"]}">Ver código</a>' if snippet else "N/A"
        rows += f"""<tr>
            <td>{error.get('exception_class','')}</td>
            <td>{error.get('count','')}</td>
            <td>{error.get('logger','')}</td>
            <td>{bb_link}</td>
            <td><pre>{llm.get('analysis','')[:500]}</pre></td>
        </tr>"""

    return f"""<html><body>
    <h2>Error Analysis Report</h2>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
    <tr><th>Exception</th><th>Count</th><th>Logger</th><th>Source</th><th>Analysis</th></tr>
    {rows}
    </table></body></html>"""
