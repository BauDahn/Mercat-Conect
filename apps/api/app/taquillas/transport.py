"""LockerTransport: dominio <-> taquilla. Demo: InProcessSimulator (sin red)."""
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.config import get_settings
from app.taquillas.codes import code_hash


@dataclass
class DeviceEvent:
    kind: str  # door_closed | pickup | temp | alarm
    compartment_id: uuid.UUID
    locker_id: uuid.UUID
    slot: int
    at: datetime
    data: dict = field(default_factory=dict)


@dataclass
class CodeEntry:
    code_hash: bytes
    valid_from: datetime
    valid_until: datetime
    used: bool = False


@dataclass
class CompState:
    locker_id: uuid.UUID
    slot: int
    zone: str
    door: str = "CLOSED"
    celsius: float = 3.0
    above_since: datetime | None = None
    entries: list[CodeEntry] = field(default_factory=list)


class LockerTransport(ABC):
    @abstractmethod
    def set_handler(self, handler: Callable[[DeviceEvent], None]) -> None: ...

    @abstractmethod
    def register(self, compartment_id: uuid.UUID, locker_id: uuid.UUID, slot: int, zone: str) -> None: ...

    @abstractmethod
    def open_compartment(self, compartment_id: uuid.UUID) -> None: ...

    @abstractmethod
    def push_codes(self, compartment_id: uuid.UUID, entries: list[CodeEntry]) -> None: ...

    @abstractmethod
    def remove_codes(self, compartment_id: uuid.UUID) -> None: ...

    @abstractmethod
    def close_door(self, compartment_id: uuid.UUID, now: datetime, emit: bool = True) -> "CompState": ...

    @abstractmethod
    def enter_code(self, compartment_id: uuid.UUID, code: str, now: datetime) -> bool: ...

    @abstractmethod
    def set_temperature(self, compartment_id: uuid.UUID, celsius: float, now: datetime) -> "CompState": ...

    @abstractmethod
    def set_online(self, locker_id: uuid.UUID, online: bool) -> None: ...

    @abstractmethod
    def is_offline(self, locker_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def state(self, compartment_id: uuid.UUID) -> "CompState | None": ...

    @abstractmethod
    def states(self) -> list[tuple[uuid.UUID, "CompState"]]: ...

    @abstractmethod
    def reset(self) -> None: ...


class InProcessSimulator(LockerTransport):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._comps: dict[uuid.UUID, CompState] = {}
        self._offline: set[uuid.UUID] = set()
        self._queue: list[DeviceEvent] = []
        self._handler: Callable[[DeviceEvent], None] | None = None

    def set_handler(self, handler):
        self._handler = handler

    def reset(self) -> None:
        with self._lock:
            self._comps.clear()
            self._offline.clear()
            self._queue.clear()

    def register(self, compartment_id, locker_id, slot, zone):
        with self._lock:
            if compartment_id not in self._comps:
                self._comps[compartment_id] = CompState(
                    locker_id, slot, zone, celsius=3.0 if zone == "REFRIGERATED" else 20.0)

    def state(self, compartment_id) -> CompState | None:
        with self._lock:
            return self._comps.get(compartment_id)

    def states(self):
        with self._lock:
            return list(self._comps.items())

    def is_offline(self, locker_id) -> bool:
        return locker_id in self._offline

    def open_compartment(self, compartment_id):
        with self._lock:
            self._comps[compartment_id].door = "OPEN"

    def push_codes(self, compartment_id, entries):
        with self._lock:
            self._comps[compartment_id].entries = list(entries)

    def remove_codes(self, compartment_id):
        with self._lock:
            if compartment_id in self._comps:
                self._comps[compartment_id].entries = []

    # --- acciones del "dispositivo" (las dispara el simulador web) ---
    def _emit(self, ev: DeviceEvent) -> None:
        with self._lock:
            if ev.locker_id in self._offline:
                self._queue.append(ev)
                return
        if self._handler:
            self._handler(ev)

    def close_door(self, compartment_id, now, emit: bool = True) -> CompState:
        with self._lock:
            st = self._comps[compartment_id]
            st.door = "CLOSED"
            ev = DeviceEvent("door_closed", compartment_id, st.locker_id, st.slot, now, {"celsius": st.celsius})
        if emit:
            self._emit(ev)
        return st

    def enter_code(self, compartment_id, code: str, now) -> bool:
        """Comprueba hash y ventana en local (funciona sin red)."""
        with self._lock:
            st = self._comps[compartment_id]
            h = code_hash(compartment_id, code)
            for e in st.entries:
                if not e.used and e.code_hash == h and e.valid_from <= now <= e.valid_until:
                    e.used = True
                    st.door = "OPEN"
                    ev = DeviceEvent("pickup", compartment_id, st.locker_id, st.slot, now, {})
                    break
            else:
                return False
        self._emit(ev)
        return True

    def set_temperature(self, compartment_id, celsius: float, now) -> CompState:
        with self._lock:
            st = self._comps[compartment_id]
            st.celsius = celsius
            ev = DeviceEvent("temp", compartment_id, st.locker_id, st.slot, now, {"celsius": celsius})
        self._emit(ev)
        return st

    def set_online(self, locker_id, online: bool) -> None:
        with self._lock:
            if online:
                self._offline.discard(locker_id)
                pending = [e for e in self._queue if e.locker_id == locker_id]
                self._queue = [e for e in self._queue if e.locker_id != locker_id]
            else:
                self._offline.add(locker_id)
                pending = []
        for ev in pending:
            if self._handler:
                self._handler(ev)


_sim: InProcessSimulator | None = None


def get_transport() -> InProcessSimulator:
    global _sim
    if _sim is None:
        name = get_settings().LOCKER_TRANSPORT
        if name not in ("inprocess", "sim"):
            raise RuntimeError(f"LockerTransport '{name}' no implementado")
        _sim = InProcessSimulator()
    return _sim
