import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings


def send_jira_email(subject: str, body_html: str, to: str | None = None) -> bool:
    s = get_settings()
    dest = to or s.jira_email
    if not dest or not s.smtp_host:
        raise ValueError("SMTP or Jira email not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{s.jira_project_key}] {subject}"
    msg["From"] = s.smtp_user
    msg["To"] = dest
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
        server.starttls()
        server.login(s.smtp_user, s.smtp_password)
        server.sendmail(s.smtp_user, [dest], msg.as_string())
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
