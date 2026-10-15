"""Consultas de capacidad y reserva de compartimentos (solo base de datos)."""
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

SIZE_RANK = "CASE c.size WHEN 'S' THEN 1 WHEN 'M' THEN 2 ELSE 3 END"
ORDER_ZONE = """(CASE WHEN EXISTS (SELECT 1 FROM order_items oi JOIN offers f ON f.id = oi.offer_id
   JOIN products p ON p.id = f.product_id WHERE oi.order_id = o.id AND p.food_class = 'REFRIGERATED')
   THEN 'REFRIGERATED' ELSE 'AMBIENT' END)"""


def free_slots_map(db: Session) -> dict[tuple[uuid.UUID, str], int]:
    """{(market_id, zone): compartimentos libres no comprometidos por pedidos HELD/PAID}."""
    free = {(r[0], r[1]): r[2] for r in db.execute(text(
        "SELECT l.market_id, c.zone, count(*) FROM compartments c JOIN lockers l ON l.id=c.locker_id "
        "WHERE c.status='FREE' GROUP BY 1,2"))}
    committed = {(r[0], r[1]): r[2] for r in db.execute(text(
        f"SELECT s.market_id, {ORDER_ZONE} AS zone, count(*) FROM orders o JOIN stalls s ON s.id=o.stall_id "
        "WHERE o.status IN ('HELD','PAID') GROUP BY 1,2"))}
    return {k: max(0, v - committed.get(k, 0)) for k, v in free.items()}


def locker_free_slots(db: Session, market_id: uuid.UUID, zone: str) -> int:
    return free_slots_map(db).get((market_id, zone), 0)


def required_size(total_grams: int | None) -> int:
    if total_grams is None:
        return 2
    return 1 if total_grams <= 2000 else 2 if total_grams <= 6000 else 3


def reserve_compartment(db: Session, market_id: uuid.UUID, zone: str, need_rank: int) -> uuid.UUID | None:
    row = db.execute(text(f"""
        UPDATE compartments SET status='RESERVED' WHERE id = (
          SELECT c.id FROM compartments c JOIN lockers l ON l.id=c.locker_id
          WHERE l.market_id=:m AND c.zone=:z AND c.status='FREE' AND {SIZE_RANK} >= :need
          ORDER BY {SIZE_RANK}, l.device_id, c.slot LIMIT 1 FOR UPDATE OF c SKIP LOCKED)
        RETURNING id"""), {"m": market_id, "z": zone, "need": need_rank}).first()
    return row[0] if row else None


def release_compartment(db: Session, order_id: uuid.UUID, now: datetime) -> uuid.UUID | None:
    """Libera el compartimento del pedido (salvo si está fuera de servicio) y devuelve su id."""
    row = db.execute(text("SELECT compartment_id FROM deposits WHERE order_id=:o"), {"o": order_id}).first()
    if not row:
        return None
    db.execute(text("UPDATE compartments SET status='FREE' WHERE id=:c AND status IN ('RESERVED','OCCUPIED')"),
               {"c": row[0]})
    return row[0]
