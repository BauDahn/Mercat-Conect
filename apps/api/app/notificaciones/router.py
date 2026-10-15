import asyncio
import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Notification, PushSubscription, User
from app.db.session import get_db
from app.config import get_settings
from app.deps import current_user
from app.errors import ApiError
from app.notificaciones.bus import hub
from app.reglas import service as reglas
from app.reloj import get_clock

router = APIRouter()


@router.get("/notifications")
def list_notifications(unread: bool | None = None, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(q.order_by(Notification.id.desc()).limit(200)).all()
    return {"items": [{"id": n.id, "kind": n.kind, "payload": n.payload,
                       "read_at": n.read_at.isoformat() if n.read_at else None,
                       "created_at": n.created_at.isoformat()} for n in rows]}


class PushBody(BaseModel):
    endpoint: str
    keys: dict[str, str]


@router.post("/push/subscribe", status_code=204)
def push_subscribe(body: PushBody, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    if row:
        row.user_id, row.keys = user.id, body.keys
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, keys=body.keys))
    db.commit()
    return Response(status_code=204)


@router.get("/me/points")
def my_points(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return reglas.points_state(db, user.id, get_clock().now())


@router.get("/stream")
async def stream(request: Request, user: User = Depends(current_user)):
    if hub.count(user.id) >= get_settings().SSE_MAX_PER_USER:
        raise ApiError("rate_limited", reason="too_many_streams")
    sub = hub.subscribe(user.id)

    async def gen():
        try:
            yield "retry: 3000\n: connected\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event, data = await asyncio.wait_for(sub.queue.get(), timeout=15)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"event: {event}\ndata: {data}\n\n"
        finally:
            hub.unsubscribe(sub)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


_ = json
