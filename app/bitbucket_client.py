import re
import httpx
from app.config import get_settings

_JAVA_STACK_RE = re.compile(
    r"at\s+([\w$.]+)\.([\w<>]+)\(([\w]+\.java):(\d+)\)"
)

BB_API = "https://api.bitbucket.org/2.0"


def parse_stack_frames(stack_trace: str) -> list[dict]:
    """Extrae frames del stacktrace Java: clase, método, fichero, línea."""
    frames = []
    for m in _JAVA_STACK_RE.finditer(stack_trace or ""):
        full_class = m.group(1)
        pkg_path = full_class.replace(".", "/")
        frames.append(
            {
                "class": full_class,
                "method": m.group(2),
                "file": m.group(3),
                "line": int(m.group(4)),
                "source_path": f"{pkg_path.rsplit('/', 1)[0]}/{m.group(3)}"
                if "/" in pkg_path
                else m.group(3),
            }
        )
    return frames


async def fetch_source_snippet(file_path: str, line: int, context: int = 10) -> dict | None:
    """Descarga un fragmento de código fuente de Bitbucket Cloud."""
    s = get_settings()
    if not s.bitbucket_workspace or not s.bitbucket_app_password:
        return None

    search_url = f"{BB_API}/repositories/{s.bitbucket_workspace}/{s.bitbucket_repo}/src/{s.bitbucket_branch}"

    async with httpx.AsyncClient(
        auth=(s.bitbucket_user, s.bitbucket_app_password), timeout=15
    ) as client:
        # Buscar el fichero en el repo
        resp = await client.get(f"{search_url}/{file_path}")
        if resp.status_code != 200:
            # Intentar búsqueda por nombre de fichero
            search_resp = await client.get(
                f"{BB_API}/repositories/{s.bitbucket_workspace}/{s.bitbucket_repo}/src/{s.bitbucket_branch}/",
                params={"q": f'path ~ "{file_path.split("/")[-1]}"', "max_depth": 20},
            )
            if search_resp.status_code != 200:
                return None
            values = search_resp.json().get("values", [])
            match = next((v for v in values if v["path"].endswith(file_path)), None)
            if not match:
                return None
            resp = await client.get(f"{search_url}/{match['path']}")
            if resp.status_code != 200:
                return None
            file_path = match["path"]

        lines = resp.text.splitlines()
        start = max(0, line - context - 1)
        end = min(len(lines), line + context)
        snippet_lines = lines[start:end]

        return {
            "path": file_path,
            "line": line,
            "start_line": start + 1,
            "snippet": "\n".join(
                f"{'>>>' if i + start + 1 == line else '   '} {i + start + 1:4d} | {l}"
                for i, l in enumerate(snippet_lines)
            ),
            "bb_url": f"https://bitbucket.org/{s.bitbucket_workspace}/{s.bitbucket_repo}/src/{s.bitbucket_branch}/{file_path}#lines-{line}",
        }
