from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.deps import current_user
from app.identidad import service
from app.reloj import get_clock

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)
    lang: str = Field(default="es", pattern="^(es|va)$")


class LoginRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str


def _cookie(resp: Response, token: str) -> None:
    resp.set_cookie("mc_session", token, httponly=True, samesite="lax", path="/",
                    secure=get_settings().COOKIE_SECURE, max_age=get_settings().SESSION_TTL_HOURS * 3600)


@router.post("/auth/register", status_code=201)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    user, token = service.register(db, get_clock().now(), body.email, body.password, body.display_name, body.lang)
    _cookie(response, token)
    return service.user_out(db, user)


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user, token = service.login(db, get_clock().now(), body.email, body.password,
                                request.client.host if request.client else "")
    _cookie(response, token)
    return service.user_out(db, user)


@router.post("/auth/logout", status_code=204)
def logout(mc_session: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    service.logout(db, mc_session)
    resp = Response(status_code=204)
    resp.delete_cookie("mc_session", path="/")
    return resp


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.user_out(db, user)


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.delete_account(db, user)
    resp = Response(status_code=204)
    resp.delete_cookie("mc_session", path="/")
    return resp


@router.get("/identity/age/start")
def age_start(user: User = Depends(current_user)):
    return service.age_start(user, get_clock().now())


@router.get("/identity/age/callback")
def age_callback(state: str, token: str, kind: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = service.age_callback(db, get_clock().now(), user, state, token, kind)
    return service.user_out(db, u)
