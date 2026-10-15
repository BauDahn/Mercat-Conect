"""Interfaz Notifier con InAppNotifier (bandeja + SSE) y EmailNotifier (SMTP con respaldo en log)."""
import logging
import smtplib
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.hooks import after_commit
from app.db.models import Notification, User
from app.notificaciones.bus import hub

log = logging.getLogger("mercat.notif")
_mail_lock = threading.Lock()


class Notifier(ABC):
    channel: str

    @abstractmethod
    def send(self, db: Session, now: datetime, user: User, kind: str, payload: dict) -> None: ...


class InAppNotifier(Notifier):
    channel = "in_app"

    def send(self, db, now, user, kind, payload):
        n = Notification(user_id=user.id, kind=kind, payload=payload, created_at=now)
        db.add(n)
        db.flush()
        data = {"id": n.id, "kind": kind, "payload": payload, "created_at": now.isoformat()}
        after_commit(db, lambda: hub.publish("notification.created", data, [user.id]))


def mail_log_path() -> Path:
    s = get_settings()
    if s.MAIL_LOG_PATH:
        return Path(s.MAIL_LOG_PATH)
    return Path(__file__).resolve().parents[4] / ".demo" / "mail.log"


def deliver_email(to: str, subject: str, body: str, link: str | None, attempts: int = 2) -> bool:
    """SMTP con un reintento; si no hay buzón, deja el correo legible en .demo/mail.log."""
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.SMTP_FROM, to, subject
    msg.set_content(body + (f"\n\n{link}" if link else ""))
    for _ in range(attempts):
        try:
            with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=2) as smtp:
                smtp.send_message(msg)
            return True
        except Exception:  # noqa: BLE001
            continue
    try:
        p = mail_log_path()
        with _mail_lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(f"--- para: {to}\nasunto: {subject}\nenlace: {link or '-'}\n{body}\n\n")
    except Exception:  # noqa: BLE001
        log.warning("no se pudo escribir mail.log", exc_info=True)
    return False


class EmailNotifier(Notifier):
    channel = "email"

    def send(self, db, now, user, kind, payload):
        subject = payload.get("subject") or f"Mercat-Conect: {kind}"
        body = payload.get("message") or subject
        link = payload.get("link")
        to = user.email
        after_commit(db, lambda: threading.Thread(
            target=deliver_email, args=(to, subject, body, link), daemon=True).start())


def get_notifiers() -> list[Notifier]:
    out: list[Notifier] = []
    for n in get_settings().notifiers_list:
        if n == "inapp":
            out.append(InAppNotifier())
        elif n == "email":
            out.append(EmailNotifier())
    return out
