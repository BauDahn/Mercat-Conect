"""Acciones posteriores al commit (SSE, correo, transporte de taquillas)."""
import logging
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session

log = logging.getLogger("mercat.hooks")


def after_commit(db: Session, fn: Callable[[], None]) -> None:
    db.info.setdefault("post_commit", []).append(fn)


@event.listens_for(Session, "after_commit")
def _run_post_commit(session: Session) -> None:
    for fn in session.info.pop("post_commit", []):
        try:
            fn()
        except Exception:  # noqa: BLE001 - un fallo de aviso nunca rompe la transacción ya confirmada
            log.exception("post-commit hook failed")


@event.listens_for(Session, "after_rollback")
def _drop_post_commit(session: Session) -> None:
    session.info.pop("post_commit", None)
