import hashlib
import hmac
import secrets
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

_ph = PasswordHasher()
_DUMMY = _ph.hash("dummy-password-for-timing")


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(hashed: str | None, pw: str) -> bool:
    try:
        _ph.verify(hashed or _DUMMY, pw)
        return hashed is not None
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def person_hash(stable_id: str) -> bytes:
    """HMAC-SHA256(clave, identificador estable); nunca se guarda el documento."""
    return hmac.new(get_settings().PERSON_HASH_KEY.encode(), stable_id.strip().upper().encode(), hashlib.sha256).digest()


def pseudo_id(user_id: uuid.UUID) -> str:
    """Identificador derivado para analítica: ni id de cuenta ni person_hash."""
    return hmac.new(get_settings().SECRET_KEY.encode(), b"pseudo:" + user_id.bytes, hashlib.sha256).hexdigest()[:16]


def sign(payload: str) -> str:
    return hmac.new(get_settings().SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
