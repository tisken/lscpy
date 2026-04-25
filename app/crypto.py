from __future__ import annotations
from pathlib import Path
from cryptography.fernet import Fernet

_KEY_FILE = Path(".secret_key")
_PREFIX = "enc:"
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet:
        return _fernet
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
    _fernet = Fernet(key)
    return _fernet


def encrypt(value: str) -> str:
    if not value or value.startswith(_PREFIX):
        return value
    return _PREFIX + _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    if not value or not value.startswith(_PREFIX):
        return value
    try:
        return _get_fernet().decrypt(value[len(_PREFIX):].encode()).decode()
    except Exception:
        return value
