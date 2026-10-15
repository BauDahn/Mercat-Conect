import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Order, Payout, Stall, User
from app.db.session import get_db
from app.deps import current_user, require_roles
from app.errors import ApiError
from app.pagos import service
from app.reloj import get_clock

router = APIRouter()


class PayBody(BaseModel):
    simulate: str | None = None


@router.post("/orders/{id}/pay")
def pay(id: uuid.UUID, body: PayBody | None = None, user: User = Depends(current_user),
        db: Session = Depends(get_db)):
    order = db.get(Order, id)
    if order is None or order.user_id != user.id:
        raise ApiError("not_found")
    sim = body.simulate if body else None
    if sim not in (None, "success", "failure", "delay"):
        raise ApiError("validation_failed", field="simulate")
    return service.pay_order(db, get_clock().now(), order, sim)


@router.post("/payments/webhook/{provider}")
async def webhook(provider: str, request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    sig = request.headers.get("X-Signature", "")
    from starlette.concurrency import run_in_threadpool
    await run_in_threadpool(service.process_webhook, db, get_clock().now(), provider, raw, sig)
    return {"status": "ok"}


@router.get("/producer/payouts")
def payouts(user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Payout).join(Stall, Stall.id == Payout.stall_id)
                      .where(Stall.owner_user_id == user.id).order_by(Payout.period_from.desc())).all()
    return {"items": [{
        "id": str(p.id), "stall_id": str(p.stall_id), "period_from": p.period_from.date().isoformat(),
        "period_to": p.period_to.date().isoformat(), "gross_cents": p.gross_cents,
        "commission_cents": p.commission_cents, "amount_cents": p.amount_cents, "status": p.status,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None} for p in rows]}
