"""Reloj inyectable. ÚNICO lugar autorizado a leer la hora del sistema."""
import threading
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings

MADRID = ZoneInfo("Europe/Madrid")


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)


class DemoClock(Clock):
    """Reloj offset: corre en tiempo real (1 s = 1 s) desde su hora de inicio; se puede saltar y pausar."""

    def __init__(self, start: datetime, paused: bool = False) -> None:
        self._lock = threading.Lock()
        self._start = start
        self._base = start               # hora virtual en el anclaje
        self._anchor = time.monotonic()  # instante real del anclaje
        self._paused = paused

    def _now(self) -> datetime:
        if self._paused:
            return self._base
        return self._base + timedelta(seconds=time.monotonic() - self._anchor)

    def _rebase(self, value: datetime) -> None:
        self._base, self._anchor = value, time.monotonic()

    @property
    def paused(self) -> bool:
        return self._paused

    def now(self) -> datetime:
        with self._lock:
            return self._now()

    def set(self, value: datetime) -> datetime:
        with self._lock:
            self._rebase(value if value.tzinfo else value.replace(tzinfo=MADRID))
            return self._base

    def advance(self, seconds: int) -> datetime:
        with self._lock:
            self._rebase(self._now() + timedelta(seconds=seconds))
            return self._base

    def pause(self) -> None:
        with self._lock:
            self._rebase(self._now())
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._rebase(self._base)
            self._paused = False

    def reset(self) -> datetime:
        with self._lock:
            self._paused = False
        return self.set(self._start)


def wall_seconds() -> float:
    """Tiempo monótono solo para limitadores de tasa (no es lógica de negocio)."""
    return time.monotonic()


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=MADRID)


_clock: Clock | None = None


def get_clock() -> Clock:
    global _clock
    if _clock is None:
        s = get_settings()
        _clock = DemoClock(parse_dt(s.DEMO_CLOCK_START)) if s.DEMO_MODE else SystemClock()
    return _clock


def set_clock(clock: Clock | None) -> None:
    global _clock
    _clock = clock


def local(dt: datetime) -> datetime:
    return dt.astimezone(MADRID)


def week_key(dt: datetime) -> str:
    y, w, _ = local(dt).isocalendar()
    return f"{y}-W{w:02d}"


def next_week_start(dt: datetime) -> datetime:
    d = local(dt)
    monday = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday + timedelta(days=7)


def day_start(dt: datetime) -> datetime:
    return local(dt).replace(hour=0, minute=0, second=0, microsecond=0)
