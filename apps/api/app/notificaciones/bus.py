"""Difusión SSE en proceso. Seguro entre hilos; cada suscriptor es una cola asyncio."""
import asyncio
import json
import threading
import uuid
from dataclasses import dataclass


@dataclass
class _Sub:
    user_id: uuid.UUID
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue


class Hub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: list[_Sub] = []

    def subscribe(self, user_id: uuid.UUID) -> _Sub:
        sub = _Sub(user_id, asyncio.get_running_loop(), asyncio.Queue())
        with self._lock:
            self._subs.append(sub)
        return sub

    def count(self, user_id: uuid.UUID) -> int:
        with self._lock:
            return sum(1 for s in self._subs if s.user_id == user_id)

    def unsubscribe(self, sub: _Sub) -> None:
        with self._lock:
            if sub in self._subs:
                self._subs.remove(sub)

    def publish(self, event: str, data: dict, user_ids: list[uuid.UUID] | None = None) -> None:
        msg = (event, json.dumps(data, default=str))
        with self._lock:
            targets = [s for s in self._subs if user_ids is None or s.user_id in user_ids]
        for s in targets:
            try:
                s.loop.call_soon_threadsafe(s.queue.put_nowait, msg)
            except RuntimeError:
                pass  # bucle cerrado


hub = Hub()
