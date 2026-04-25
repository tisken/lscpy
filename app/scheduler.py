from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

from app.es_client import get_top_errors
from app.bitbucket_client import parse_stack_frames, fetch_source_snippet
from app.llm_analyzer import analyze_error
from app.mail_sender import send_jira_email, build_report_html
from app.config import get_settings

logger = logging.getLogger("lsc.scheduler")


@dataclass
class CronConfig:
    enabled: bool = False
    interval_minutes: int = 60
    datasource_id: str = ""
    hours: int = 24
    size: int = 20
    message: str = ""
    logger_filter: str = ""
    exception: str = ""
    step_search: bool = True
    step_analyze: bool = True
    step_send: bool = False


@dataclass
class CronStatus:
    running: bool = False
    last_run: str | None = None
    last_errors_found: int = 0
    last_analyzed: int = 0
    last_sent: bool = False
    last_error: str | None = None
    history: list[dict] = field(default_factory=list)


_config = CronConfig()
_status = CronStatus()
_task: asyncio.Task | None = None
_MAX_HISTORY = 50


def get_cron_config() -> dict:
    return asdict(_config)


def get_cron_status() -> dict:
    return asdict(_status)


def update_cron_config(data: dict) -> dict:
    global _config
    for k, v in data.items():
        if hasattr(_config, k):
            setattr(_config, k, v)
    return asdict(_config)


async def _run_cycle():
    global _status
    _status.running = True
    _status.last_error = None
    _status.last_run = datetime.now(timezone.utc).isoformat()
    run_record = {"timestamp": _status.last_run, "steps": []}

    try:
        if not _config.datasource_id:
            raise ValueError("No datasource configured for cron")

        errors = []
        results = []

        if _config.step_search:
            errors = get_top_errors(
                ds_id=_config.datasource_id,
                hours=_config.hours, size=_config.size,
                message=_config.message, logger=_config.logger_filter,
                exception=_config.exception,
            )
            _status.last_errors_found = len(errors)
            run_record["steps"].append(f"search: {len(errors)} errores")
            logger.info("Cron search: %d error groups found", len(errors))

        if _config.step_analyze and errors:
            for error in errors:
                frames = parse_stack_frames(error.get("stack_trace", ""))
                snippet = None
                for frame in frames:
                    snippet = await fetch_source_snippet(frame["source_path"], frame["line"])
                    if snippet:
                        break
                llm_result = await analyze_error(error, snippet)
                results.append({"error": error, "snippet": snippet, "llm_result": llm_result})
            _status.last_analyzed = len(results)
            run_record["steps"].append(f"analyze: {len(results)} analizados")
            logger.info("Cron analyze: %d errors analyzed", len(results))

        _status.last_sent = False
        if _config.step_send and results:
            html = build_report_html(results)
            subject = f"[LSC Auto] {len(results)} errores - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
            send_jira_email(subject, html)
            _status.last_sent = True
            run_record["steps"].append("send: ok")
            logger.info("Cron send: email sent to Jira")

    except Exception as e:
        _status.last_error = str(e)
        run_record["steps"].append(f"error: {e}")
        logger.exception("Cron cycle failed")
    finally:
        _status.running = False
        _status.history.insert(0, run_record)
        _status.history = _status.history[:_MAX_HISTORY]


async def _cron_loop():
    while True:
        if _config.enabled:
            await _run_cycle()
        await asyncio.sleep(_config.interval_minutes * 60)


def start_scheduler():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_cron_loop())
        logger.info("Scheduler started")


def stop_scheduler():
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
        logger.info("Scheduler stopped")


async def trigger_now():
    if _status.running:
        return {"status": "already_running"}
    await _run_cycle()
    return get_cron_status()
