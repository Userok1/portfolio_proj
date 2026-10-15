"""Серверные сессии в памяти процесса (по решению пользователя).
Cookie хранит только случайный sid; сами JWT живут в этом dict и в браузер не уходят.
Минус: сессии слетают при рестарте контейнера — для MVP приемлемо.
"""
import secrets
import time
from dataclasses import dataclass, field

from .config import settings

COOKIE = "vbm_sid"


@dataclass
class Session:
    access: str
    refresh: str
    email: str
    created: float = field(default_factory=time.time)


_store: dict[str, Session] = {}


def create(access: str, refresh: str, email: str) -> str:
    sid = secrets.token_urlsafe(32)
    _store[sid] = Session(access=access, refresh=refresh, email=email)
    return sid


def get(sid: str | None) -> Session | None:
    if not sid or sid not in _store:
        return None
    s = _store[sid]
    if time.time() - s.created > settings.SESSION_TTL_H * 3600:
        _store.pop(sid, None)
        return None
    return s


def drop(sid: str | None) -> None:
    if sid:
        _store.pop(sid, None)
