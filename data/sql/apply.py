"""Aplicador de las capas SQL del almacen (raw/staging/core/marts/open_data).

Uso:
    uv run --project apps/api python data/sql/apply.py [apply|refresh|quality]

Funciones reutilizables (las usa data/seed/run.py y puede usarlas el backend):
    apply_layers(conn, clock_now, ...)  crea/recrea las capas y la vista marts.quality_failures
    refresh(conn, clock_now=None)       ingesta outbox -> raw (idempotente) y refresca las vistas
    run_quality(conn)                   devuelve [(test, detail), ...]; vacio = todo bien
Ninguna funcion lee la hora del sistema: el reloj es el de la demo (core.meta.clock_now).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent
QUALITY_FILE = SQL_DIR / "quality" / "quality_tests.sql"
DEFAULTS = {"open_data_min_cell": "5", "freshness_minutes": "120", "commission_rate": "0.05"}


def _layer_files() -> list[Path]:
    return sorted(p for p in SQL_DIR.glob("[0-9][0-9]_*.sql"))


def set_meta(conn, **values) -> None:
    for k, v in values.items():
        conn.execute(
            "INSERT INTO core.meta (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (k, str(v)),
        )


def apply_layers(conn, clock_now: datetime, *, open_data_min_cell: int | None = None,
                 freshness_minutes: int | None = None, commission_rate: float | None = None) -> None:
    """Recrea staging/core/marts/open_data (raw se conserva) y deja los parametros en core.meta."""
    params = dict(DEFAULTS)
    env_min = os.environ.get("OPEN_DATA_MIN_CELL")
    if env_min:
        params["open_data_min_cell"] = env_min
    if open_data_min_cell is not None:
        params["open_data_min_cell"] = str(open_data_min_cell)
    if freshness_minutes is not None:
        params["freshness_minutes"] = str(freshness_minutes)
    if commission_rate is not None:
        params["commission_rate"] = str(commission_rate)
    for i, path in enumerate(_layer_files()):
        conn.execute(path.read_text(encoding="utf-8"))
        if i == 0:  # 00_schemas.sql crea core.meta: se rellena antes de las vistas materializadas
            set_meta(conn, clock_now=clock_now.isoformat(), **params)
    body = QUALITY_FILE.read_text(encoding="utf-8").strip().rstrip(";")
    conn.execute("CREATE VIEW marts.quality_failures AS\n" + body)


def refresh(conn, clock_now: datetime | None = None) -> None:
    if clock_now is not None:
        set_meta(conn, clock_now=clock_now.isoformat())
    conn.execute((SQL_DIR / "refresh.sql").read_text(encoding="utf-8"))


def run_quality(conn) -> list[tuple[str, str]]:
    return [(r[0], r[1]) for r in conn.execute("SELECT test, detail FROM marts.quality_failures ORDER BY 1, 2")]


def _main(argv: list[str]) -> int:
    import psycopg

    cmd = argv[1] if len(argv) > 1 else "apply"
    url = os.environ.get("DATABASE_URL", "postgresql+psycopg://mercat:mercat@localhost:5432/mercat")
    url = url.replace("postgresql+psycopg://", "postgresql://")
    start = os.environ.get("DEMO_CLOCK_START", "2026-10-16T12:00:00+02:00")
    clock = datetime.fromisoformat(start)
    with psycopg.connect(url) as conn:
        if cmd == "apply":
            apply_layers(conn, clock)
            refresh(conn)
        elif cmd == "refresh":
            refresh(conn)
        elif cmd != "quality":
            print("uso: apply.py [apply|refresh|quality]")
            return 2
        failures = run_quality(conn)
        for t, d in failures:
            print(f"FALLO {t}: {d}")
        return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
