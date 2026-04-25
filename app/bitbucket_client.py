from __future__ import annotations
import re
import httpx
from app.settings_store import get_section

_JAVA_STACK_RE = re.compile(
    r"at\s+([\w$.]+)\.([\w<>]+)\(([\w]+\.java):(\d+)\)"
)

BB_API = "https://api.bitbucket.org/2.0"


def parse_stack_frames(stack_trace: str) -> list[dict]:
    frames = []
    for m in _JAVA_STACK_RE.finditer(stack_trace or ""):
        full_class = m.group(1)
        pkg_path = full_class.replace(".", "/")
        frames.append({
            "class": full_class,
            "method": m.group(2),
            "file": m.group(3),
            "line": int(m.group(4)),
            "source_path": f"{pkg_path.rsplit('/', 1)[0]}/{m.group(3)}"
            if "/" in pkg_path else m.group(3),
        })
    return frames


def _get_repos() -> list[dict]:
    """Devuelve lista de repos. Soporta formato legacy (un repo) y nuevo (lista)."""
    bb = get_section("bitbucket")
    workspace = bb.get("workspace", "")
    user = bb.get("user", "")
    app_password = bb.get("app_password", "")
    if not workspace or not app_password:
        return []

    repos = bb.get("repos", [])
    if repos:
        return [{"workspace": workspace, "user": user, "app_password": app_password, **r} for r in repos]

    # Legacy: campo "repo" único
    repo = bb.get("repo", "")
    if not repo:
        return []
    return [{"workspace": workspace, "repo": repo, "branch": bb.get("branch", "main"), "user": user, "app_password": app_password}]


async def _try_fetch_from_repo(client: httpx.AsyncClient, repo_cfg: dict, file_path: str, line: int, context: int) -> dict | None:
    workspace = repo_cfg["workspace"]
    repo = repo_cfg["repo"]
    branch = repo_cfg.get("branch", "main")
    base = f"{BB_API}/repositories/{workspace}/{repo}/src/{branch}"

    resp = await client.get(f"{base}/{file_path}")
    if resp.status_code != 200:
        # Buscar por nombre de fichero
        search_resp = await client.get(
            f"{base}/",
            params={"q": f'path ~ "{file_path.split("/")[-1]}"', "max_depth": 20},
        )
        if search_resp.status_code != 200:
            return None
        values = search_resp.json().get("values", [])
        match = next((v for v in values if v["path"].endswith(file_path)), None)
        if not match:
            return None
        resp = await client.get(f"{base}/{match['path']}")
        if resp.status_code != 200:
            return None
        file_path = match["path"]

    lines = resp.text.splitlines()
    start = max(0, line - context - 1)
    end = min(len(lines), line + context)

    return {
        "path": file_path,
        "repo": repo,
        "line": line,
        "start_line": start + 1,
        "snippet": "\n".join(
            f"{'>>>' if i + start + 1 == line else '   '} {i + start + 1:4d} | {l}"
            for i, l in enumerate(lines[start:end])
        ),
        "bb_url": f"https://bitbucket.org/{workspace}/{repo}/src/{branch}/{file_path}#lines-{line}",
    }


async def fetch_source_snippet(file_path: str, line: int, context: int = 10) -> dict | None:
    repos = _get_repos()
    if not repos:
        return None

    async with httpx.AsyncClient(
        auth=(repos[0]["user"], repos[0]["app_password"]), timeout=15
    ) as client:
        for repo_cfg in repos:
            result = await _try_fetch_from_repo(client, repo_cfg, file_path, line, context)
            if result:
                return result
    return None
