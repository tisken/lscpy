from typing import Optional

from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import setup_logging
from app.config import get_settings
from app.auth import ensure_default_user, authenticate, change_password, create_token, verify_token
from app.settings_store import (
    get_all, get_section, update_section,
    list_datasources, get_datasource, save_datasource, delete_datasource,
)
from app.es_client import get_top_errors, get_error_detail, test_connection
from app.bitbucket_client import parse_stack_frames, fetch_source_snippet
from app.llm_analyzer import analyze_error
from app.mail_sender import send_jira_email, build_report_html
from app.analysis_cache import get_stats as cache_stats
from app.scheduler import (
    start_scheduler, stop_scheduler, trigger_now,
    get_cron_config, get_cron_status, update_cron_config,
)

log = logging.getLogger("lsc.app")

_PUBLIC_PATHS = {"/login", "/api/auth/login", "/api/auth/change-password", "/api/health"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)
        token = request.cookies.get("lsc_token")
        auth_header = request.headers.get("authorization", "")
        if not token and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            return RedirectResponse("/login")
        user = verify_token(token)
        if not user:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)
            return RedirectResponse("/login")
        if user["must_change"] and path not in ("/api/auth/change-password", "/login"):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Password change required"}, status_code=403)
            return RedirectResponse("/login")
        request.state.user = user
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log.info("LSC starting up")
    ensure_default_user()
    s = get_settings()
    update_cron_config({
        "enabled": s.cron_enabled,
        "interval_minutes": s.cron_interval_minutes,
        "hours": s.cron_hours,
        "size": s.cron_size,
        "step_search": s.cron_step_search,
        "step_analyze": s.cron_step_analyze,
        "step_send": s.cron_step_send,
    })
    start_scheduler()
    log.info("LSC ready")
    yield
    stop_scheduler()
    log.info("LSC shutdown")


app = FastAPI(title="Log Source Checker", version="0.7.0", lifespan=lifespan)
app.add_middleware(AuthMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# --- Health ---

@app.get("/api/health")
async def api_health():
    datasources = list_datasources()
    ds_status = {}
    for ds in datasources:
        ds_status[ds["id"]] = test_connection(ds["id"])
    llm_cfg = get_section("llm")
    smtp_cfg = get_section("smtp")
    return {
        "status": "ok", "version": app.version,
        "datasources": ds_status,
        "llm_provider": llm_cfg.get("provider", "unknown"),
        "smtp_configured": bool(smtp_cfg.get("host")),
        "cache": cache_stats(),
    }


# --- Auth ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
async def api_login(req: LoginRequest):
    user = authenticate(req.username, req.password)
    if not user:
        log.warning("Failed login attempt for user: %s", req.username)
        raise HTTPException(401, "Credenciales incorrectas")
    log.info("User logged in: %s", req.username)
    token = create_token(user["username"], user["must_change"])
    return {"token": token, "username": user["username"], "must_change": user["must_change"]}


class ChangePasswordRequest(BaseModel):
    new_password: str


@app.post("/api/auth/change-password")
async def api_change_password(req: ChangePasswordRequest, request: Request):
    token = request.cookies.get("lsc_token")
    auth_header = request.headers.get("authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    user = verify_token(token) if token else None
    if not user:
        raise HTTPException(401, "Not authenticated")
    if not change_password(user["username"], req.new_password):
        raise HTTPException(400, "Contraseña inválida (mín. 6 caracteres)")
    log.info("Password changed for user: %s", user["username"])
    new_token = create_token(user["username"], must_change=False)
    return {"token": new_token, "username": user["username"]}


@app.post("/api/auth/logout")
async def api_logout():
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie("lsc_token")
    return resp


# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# --- Settings ---

@app.get("/api/settings")
async def api_get_settings():
    return get_all()

@app.get("/api/settings/{section}")
async def api_get_section(section: str):
    return get_section(section)

@app.post("/api/settings/{section}")
async def api_update_section(section: str, payload: dict):
    log.info("Settings updated: section=%s", section)
    return update_section(section, payload)


# --- Datasources ---

@app.get("/api/datasources")
async def api_list_datasources():
    return list_datasources()

@app.post("/api/datasources")
async def api_create_datasource(payload: dict):
    ds_id = payload.pop("id", None) or str(uuid.uuid4())[:8]
    log.info("Datasource created: %s", ds_id)
    return save_datasource(ds_id, payload)

@app.put("/api/datasources/{ds_id}")
async def api_update_datasource(ds_id: str, payload: dict):
    if not get_datasource(ds_id):
        raise HTTPException(404, "Datasource not found")
    return save_datasource(ds_id, payload)

@app.delete("/api/datasources/{ds_id}")
async def api_delete_datasource(ds_id: str):
    if not delete_datasource(ds_id):
        raise HTTPException(404, "Datasource not found")
    log.info("Datasource deleted: %s", ds_id)
    return {"status": "deleted"}

@app.get("/api/datasources/{ds_id}/test")
async def api_test_datasource(ds_id: str):
    return test_connection(ds_id)


# --- Errors (logger como alias de logger_filter) ---

@app.get("/api/errors")
async def api_errors(
    ds: str, hours: int = 24, size: int = 50,
    message: str = "",
    logger: str = Query("", alias="logger"),
    exception: str = "",
):
    if not ds:
        raise HTTPException(400, "Missing datasource id")
    return get_top_errors(ds_id=ds, hours=hours, size=size, message=message, logger=logger, exception=exception)

@app.get("/api/errors/{exception_class}/{logger_name}")
async def api_error_detail(exception_class: str, logger_name: str, ds: str, hours: int = 24):
    return get_error_detail(ds, hours, exception_class, logger_name)


# --- Analyze ---

@app.post("/api/analyze")
async def api_analyze(payload: dict):
    error = payload.get("error")
    if not error:
        raise HTTPException(400, "Missing error data")
    frames = parse_stack_frames(error.get("stack_trace", ""))
    snippet = None
    for frame in frames:
        snippet = await fetch_source_snippet(frame["source_path"], frame["line"])
        if snippet:
            break
    llm_result = await analyze_error(error, snippet)
    return {"error": error, "snippet": snippet, "llm_result": llm_result, "frames": frames}

class BulkAnalyzeRequest(BaseModel):
    datasource_id: str
    hours: int = 24
    size: int = 10

@app.post("/api/analyze/bulk")
async def api_analyze_bulk(req: BulkAnalyzeRequest):
    errors = get_top_errors(ds_id=req.datasource_id, hours=req.hours, size=req.size)
    results = []
    for error in errors:
        frames = parse_stack_frames(error.get("stack_trace", ""))
        snippet = None
        for frame in frames:
            snippet = await fetch_source_snippet(frame["source_path"], frame["line"])
            if snippet:
                break
        llm_result = await analyze_error(error, snippet)
        results.append({"error": error, "snippet": snippet, "llm_result": llm_result, "frames": frames})
    return results


# --- Jira ---

class JiraRequest(BaseModel):
    subject: str
    analyses: list[dict]
    to: Optional[str] = None

@app.post("/api/send-jira")
async def api_send_jira(req: JiraRequest):
    html = build_report_html(req.analyses)
    try:
        send_jira_email(req.subject, html, req.to)
        log.info("Jira email sent: %s", req.subject)
    except Exception as e:
        log.error("Jira email failed: %s", e)
        raise HTTPException(500, str(e))
    return {"status": "sent"}


# --- Cron ---

@app.get("/api/cron/config")
async def api_cron_config():
    return get_cron_config()

@app.post("/api/cron/config")
async def api_cron_update(payload: dict):
    log.info("Cron config updated")
    return update_cron_config(payload)

@app.get("/api/cron/status")
async def api_cron_status():
    return get_cron_status()

@app.post("/api/cron/trigger")
async def api_cron_trigger():
    log.info("Cron manually triggered")
    return await trigger_now()
