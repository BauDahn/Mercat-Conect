import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.almacen import MEDIA, get_store
from sqlalchemy.orm import Session

from app.catalogo import service
from app.db.models import User
from app.db.session import get_db
from app.deps import current_user_optional
from app.errors import ApiError
from app.eventos.outbox import emit
from app.identidad.security import pseudo_id
from app.identidad.service import is_age_verified
from app.reglas import service as reglas
from app.reloj import get_clock
from app.taquillas.capacity import free_slots_map

router = APIRouter()


@router.get("/uploads/{file}")
def get_upload(file: str):
    path = get_store().path(file)
    if path is None:
        raise ApiError("not_found")
    return FileResponse(path, media_type=MEDIA[file.rsplit(".", 1)[1]], headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=31536000, immutable"})
SORTS = {"closing_soon", "price_asc", "price_desc", "newest", "distance"}


@router.get("/offers")
def list_offers(market: uuid.UUID | None = None, category: str | None = None, sort: str = "closing_soon",
                q: str | None = None, user: User | None = Depends(current_user_optional),
                db: Session = Depends(get_db)):
    if sort not in SORTS:
        raise ApiError("validation_failed", field="sort")
    return {"items": service.list_offers(db, get_clock().now(), market, category, sort, q, user)}


@router.get("/offers/{id}")
def get_offer(id: uuid.UUID, qty: int = Query(default=1, ge=1), user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)):
    now = get_clock().now()
    row = service.load_offer(db, id)
    if row is None or (row[0].status == "DRAFT" and not (user and row[1].owner_user_id == user.id)):
        raise ApiError("not_found")
    o, s, p, m = row
    out = service.offer_out(o, s, p, m, free_slots_map(db))
    out["decision"] = None
    out["policy_profile"] = service.policy_profile(db, o.id)
    if user is not None:
        verified = is_age_verified(db, user.id)
        out["decision"] = reglas.decide(db, user, verified, o, s, p, m, qty, now).to_api()
    emit(db, now, "app.offer_viewed", o.id, {"user_pseudo_id": pseudo_id(user.id) if user else None,
                                              "offer_id": str(o.id)})
    db.commit()
    return out
