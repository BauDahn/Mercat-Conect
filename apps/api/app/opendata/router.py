import csv
import io
import re

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.errors import ApiError
from app.reglas import service as reglas

router = APIRouter()
COUNT_COLS = ("n_orders", "orders", "order_count")


@router.get("/open-data/{name}.csv")
def open_data(name: str, db: Session = Depends(get_db)):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ApiError("not_found")
    if not db.execute(text("SELECT 1 FROM information_schema.schemata WHERE schema_name='marts'")).first():
        raise ApiError("conflict", "errors.open_data_unavailable", status=503)
    if db.execute(text("SELECT to_regclass(:n)"), {"n": f"marts.open_data_{name}"}).scalar() is None:
        raise ApiError("not_found")
    res = db.execute(text(f'SELECT * FROM marts."open_data_{name}"'))
    cols = list(res.keys())
    threshold = reglas.get_guardrails(db)["min_open_data_cell"]
    cnt = next((c for c in cols if c in COUNT_COLS), None)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for row in res:
        if cnt is not None and row._mapping[cnt] is not None and row._mapping[cnt] < threshold:
            continue  # celda pequeña suprimida (privacidad)
        w.writerow(row)
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8")
