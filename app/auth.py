from __future__ import annotations
import json
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

_USERS_FILE = Path("users.json")
_SECRET_KEY = secrets.token_hex(32)
_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 12
_DEFAULT_USER = "admin"
_DEFAULT_PASSWORD = "admin"

ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"


def _load_users() -> dict:
    if _USERS_FILE.exists():
        return json.loads(_USERS_FILE.read_text())
    return {}


def _save_users(users: dict):
    _USERS_FILE.write_text(json.dumps(users, indent=2))


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def ensure_default_user():
    users = _load_users()
    if not users:
        users[_DEFAULT_USER] = {
            "password": _hash_password(_DEFAULT_PASSWORD),
            "role": ROLE_ADMIN,
            "must_change": True,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        _save_users(users)


def authenticate(username: str, password: str) -> dict | None:
    users = _load_users()
    user = users.get(username)
    if not user or not _verify_password(password, user["password"]):
        return None
    return {
        "username": username,
        "role": user.get("role", ROLE_VIEWER),
        "must_change": user.get("must_change", False),
    }


def change_password(username: str, new_password: str) -> bool:
    if len(new_password) < 6:
        return False
    users = _load_users()
    if username not in users:
        return False
    users[username]["password"] = _hash_password(new_password)
    users[username]["must_change"] = False
    _save_users(users)
    return True


def list_users() -> list[dict]:
    users = _load_users()
    return [{"username": k, "role": v.get("role", ROLE_VIEWER), "created": v.get("created", "")} for k, v in users.items()]


def create_user(username: str, password: str, role: str = ROLE_VIEWER) -> bool:
    users = _load_users()
    if username in users:
        return False
    users[username] = {
        "password": _hash_password(password),
        "role": role if role in (ROLE_ADMIN, ROLE_VIEWER) else ROLE_VIEWER,
        "must_change": True,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    _save_users(users)
    return True


def delete_user(username: str) -> bool:
    users = _load_users()
    if username not in users or username == _DEFAULT_USER:
        return False
    del users[username]
    _save_users(users)
    return True


def create_token(username: str, must_change: bool = False, role: str = ROLE_VIEWER) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": username, "role": role, "must_change": must_change, "exp": expire},
        _SECRET_KEY, algorithm=_ALGORITHM,
    )


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        return {
            "username": payload["sub"],
            "role": payload.get("role", ROLE_VIEWER),
            "must_change": payload.get("must_change", False),
        }
    except Exception:
        return None
