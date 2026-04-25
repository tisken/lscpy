import hashlib
import re

_STRIP_NUMBERS_RE = re.compile(r":\d+\)")
_STRIP_LAMBDA_RE = re.compile(r"\$\$Lambda\$\d+/\d+")
_STRIP_GENERATED_RE = re.compile(r"\$\d+")


def compute_fingerprint(exception_class: str, stack_trace: str) -> str:
    """Genera un hash estable del error normalizando el stacktrace.

    Normaliza:
    - Quita números de línea (cambian con cada deploy)
    - Quita lambdas generadas
    - Quita clases internas anónimas ($1, $2...)
    - Solo usa los primeros 5 frames del stack (el core del error)
    """
    normalized = stack_trace or ""
    normalized = _STRIP_NUMBERS_RE.sub(":0)", normalized)
    normalized = _STRIP_LAMBDA_RE.sub("$$Lambda", normalized)
    normalized = _STRIP_GENERATED_RE.sub("", normalized)

    # Extraer solo los primeros 5 frames "at ..."
    frames = [line.strip() for line in normalized.splitlines() if line.strip().startswith("at ")]
    core = "\n".join(frames[:5])

    raw = f"{exception_class}|{core}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
