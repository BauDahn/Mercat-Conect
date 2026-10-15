from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.errors import ApiError
from app.identidad.service import session_user
from app.reloj import get_clock


def current_user_optional(mc_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User | None:
    return session_user(db, mc_session, get_clock().now())


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise ApiError("unauthorized")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise ApiError("forbidden")
        return user
    return dep
