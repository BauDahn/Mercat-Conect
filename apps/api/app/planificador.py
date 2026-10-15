"""Planificador interno (demo): caducidades, cierre y donación, pagos retrasados, temperatura, outbox."""
import logging
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.donaciones.service import close_offers
from app.eventos import analytics
from app.eventos.publisher import publish_pending
from app.pagos.service import deliver_due
from app.pedidos.lifecycle import sweep
from app.reloj import get_clock
from app.taquillas.service import check_temperatures

log = logging.getLogger("mercat.planificador")
_run_lock = threading.Lock()


def run_due(db: Session, now: datetime, force_analytics: bool = False) -> dict:
    """Una pasada. Todas las decisiones usan `now` (hora del Clock)."""
    with _run_lock:
        out = {}
        for name, fn in (("pagos", deliver_due), ("pedidos", sweep), ("temperatura", check_temperatures),
                         ("cierre", close_offers), ("outbox", publish_pending)):
            try:
                out[name] = fn(db, now)
            except Exception:  # noqa: BLE001
                db.rollback()
                log.exception("fallo en %s", name)
        out["analitica"] = analytics.maybe_refresh(db, now, force_analytics)
        return out


class Scheduler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="planificador")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        interval = get_settings().SCHEDULER_INTERVAL_SECONDS
        while not self._stop.wait(interval):
            try:
                with SessionLocal() as db:
                    run_due(db, get_clock().now())
            except Exception:  # noqa: BLE001
                log.exception("tick fallido")
