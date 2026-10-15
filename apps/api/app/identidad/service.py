import base64
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import ratelimit
from app.config import get_settings
from app.db.models import Session as SessionRow
from app.db.models import User, UserIdentity
from app.errors import ApiError
from app.eventos.outbox import emit
from app.identidad import security as sec
from app.identidad.verifier import get_age_verifier


def delete_account(db: Session, user: User) -> None:
    """§18.2: anonimiza los datos personales; los pedidos quedan sin identificar a la persona."""
    from app.db.models import Notification, Order, PushSubscription, Subscription
    active = db.scalar(select(Order.id).where(Order.user_id == user.id, Order.status.in_(
        ("HELD", "PAID", "PREPARING", "IN_LOCKER"))).limit(1))
    if active is not None:
        raise ApiError("conflict", "errors.orders_in_progress")
    for model in (SessionRow, UserIdentity, PushSubscription, Subscription, Notification):
        db.execute(delete(model).where(model.user_id == user.id))
    user.email, user.display_name = f"deleted-{user.id}@anon.invalid", "Cuenta eliminada"
    user.password_hash, user.telegram_chat_id, user.status = None, None, "DELETED"
    db.commit()


def is_age_verified(db: Session, user_id: uuid.UUID) -> bool:
    return db.get(UserIdentity, user_id) is not None


def user_out(db: Session, u: User) -> dict:
    return {"id": str(u.id), "email": u.email, "display_name": u.display_name, "role": u.role,
            "lang": u.lang, "status": u.status, "age_verified": is_age_verified(db, u.id),
            "reputation": float(u.reputation)}


def create_session(db: Session, now: datetime, user_id: uuid.UUID) -> str:
    token = sec.new_token()
    db.add(SessionRow(user_id=user_id, token_hash=sec.hash_token(token), created_at=now,
                      expires_at=now + timedelta(hours=get_settings().SESSION_TTL_HOURS)))
    return token


def register(db: Session, now: datetime, email: str, password: str, display_name: str, lang: str):
    email = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ApiError("email_taken")
    user = User(id=uuid.uuid4(), email=email, password_hash=sec.hash_password(password),
                display_name=display_name.strip(), role="NEIGHBOR", lang=lang, status="PENDING", created_at=now)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError("email_taken") from None
    token = create_session(db, now, user.id)
    db.commit()
    return user, token


def login(db: Session, now: datetime, email: str, password: str, ip: str):
    email = email.strip().lower()
    key = f"login:{email}"
    if not ratelimit.hit(key, 10, 300):
        raise ApiError("rate_limited")
    user = db.scalar(select(User).where(User.email == email))
    ok = sec.verify_password(user.password_hash if user else None, password)
    if not ok or user is None or user.status in ("DELETED", "SUSPENDED"):
        raise ApiError("invalid_credentials")
    ratelimit.clear(key)
    token = create_session(db, now, user.id)
    db.commit()
    return user, token


def logout(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(SessionRow).where(SessionRow.token_hash == sec.hash_token(token)))
        db.commit()


def session_user(db: Session, token: str | None, now: datetime) -> User | None:
    if not token:
        return None
    row = db.scalar(select(SessionRow).where(SessionRow.token_hash == sec.hash_token(token)))
    if row is None or row.expires_at <= now:
        return None
    user = db.get(User, row.user_id)
    if user is None or user.status in ("DELETED", "SUSPENDED"):
        return None
    return user


def _state(user_id: uuid.UUID, exp: int) -> str:
    payload = f"{user_id}|{exp}"
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=") + "." + sec.sign("age|" + payload)


def _check_state(state: str, user_id: uuid.UUID, now: datetime) -> None:
    try:
        b, sig = state.split(".", 1)
        payload = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        uid, exp = payload.split("|")
        valid = sec.sign("age|" + payload) == sig and uid == str(user_id) and int(exp) > now.timestamp()
    except Exception:  # noqa: BLE001
        valid = False
    if not valid:
        raise ApiError("unauthorized")


def age_start(user: User, now: datetime) -> dict:
    state = _state(user.id, int(now.timestamp()) + 900)
    return {"redirect_url": get_age_verifier().start_url(state), "state": state}


def age_callback(db: Session, now: datetime, user: User, state: str, token: str, kind: str | None = None) -> User:
    _check_state(state, user.id, now)
    try:
        res = get_age_verifier().verify(token, kind)
    except ValueError:
        raise ApiError("unauthorized") from None
    if not res.adult:
        raise ApiError("age_not_verified")
    ph = sec.person_hash(res.stable_id)
    existing = db.scalar(select(UserIdentity).where(UserIdentity.person_hash == ph))
    mine = db.get(UserIdentity, user.id)
    if existing is not None:
        if existing.user_id == user.id:
            return user
        raise ApiError("person_already_registered", recover=True)
    if mine is not None:
        raise ApiError("conflict")
    db.add(UserIdentity(user_id=user.id, person_hash=ph, age_verified_at=now, age_method=res.method,
                        provider_ref=res.provider_ref))
    if user.status == "PENDING":
        user.status = "ACTIVE"
    emit(db, now, "user.verified", user.id, {"user_pseudo_id": sec.pseudo_id(user.id), "method": res.method})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError("person_already_registered", recover=True) from None
    return user
