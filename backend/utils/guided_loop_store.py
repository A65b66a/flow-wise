from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass
class _Entry:
    value: dict[str, Any]
    expires_at: float


class GuidedLoopStore:
    """
    Minimal in-memory session store with TTL.
    This keeps the guided-loop feature working without adding Redis as a dependency.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._lock = RLock()
        self._data: dict[str, _Entry] = {}

    def _now(self) -> float:
        return time.time()

    def _gc(self) -> None:
        now = self._now()
        dead = [k for k, e in self._data.items() if e.expires_at <= now]
        for k in dead:
            self._data.pop(k, None)

    def new_session_id(self) -> str:
        return str(uuid.uuid4())

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._gc()
            entry = self._data.get(session_id)
            if not entry:
                return None
            return entry.value

    def set(self, session_id: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._gc()
            self._data[session_id] = _Entry(value=value, expires_at=self._now() + self._ttl)

