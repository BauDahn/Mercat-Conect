import threading
from collections import defaultdict, deque

from app.reloj import wall_seconds

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def hit(key: str, limit: int, window_s: float) -> bool:
    """Registra un intento; False si se supera el límite en la ventana."""
    now = wall_seconds()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def clear(prefix: str | None = None) -> None:
    with _lock:
        for k in [k for k in _hits if prefix is None or k.startswith(prefix)]:
            del _hits[k]
