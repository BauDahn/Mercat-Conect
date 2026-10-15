"""Seed determinista de la demo: vacia y recarga datos, genera el historial de 4 semanas, escribe los
eventos en domain_events, crea las capas raw/staging/core/marts, refresca y ejecuta la calidad.

    uv run --project apps/api python data/seed/run.py [--hash] [--no-quality]

Variables: DATABASE_URL, DEMO_SEED (42), DEMO_CLOCK_START, PERSON_HASH_KEY, OPEN_DATA_MIN_CELL (5).
Salida con codigo != 0 si alguna prueba de calidad devuelve filas.
El backend puede usar:  from data.seed.run import reset;  reset()
(con la raiz del repositorio en sys.path).
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import psycopg  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from data.seed import generate as gen  # noqa: E402
from data.sql import apply as layers  # noqa: E402

DEFAULT_URL = "postgresql+psycopg://mercat:mercat@localhost:5432/mercat"
DEFAULT_CLOCK = "2026-10-16T12:00:00+02:00"
DEFAULT_KEY = "dev-only-change-me-too"


def _load_dotenv() -> None:
    f = REPO / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def _url(url: str | None) -> str:
    return (url or os.environ.get("DATABASE_URL") or DEFAULT_URL).replace("postgresql+psycopg://", "postgresql://")


def _clock(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value or os.environ.get("DEMO_CLOCK_START") or DEFAULT_CLOCK)
    return dt.replace(tzinfo=gen.TZ) if dt.tzinfo is None else dt


def _hasher():
    ph = PasswordHasher()
    return lambda password, salt: ph.hash(password, salt=salt)


def _truncate(conn) -> None:
    conn.execute("TRUNCATE " + ", ".join(gen.LOAD_ORDER + ["sessions", "push_subscriptions", "deliveries"])
                 + " RESTART IDENTITY CASCADE")
    if conn.execute("SELECT to_regclass('raw.events')").fetchone()[0]:
        conn.execute("TRUNCATE raw.events")


def _load(conn, ds) -> None:
    for table in gen.LOAD_ORDER:
        cols = gen.COLUMNS[table]
        wrap = [i for i, c in enumerate(cols) if (table, c) in gen.JSONB_COLUMNS]
        with conn.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
            for row in ds.tables[table]:
                if wrap:
                    row = tuple(Jsonb(v) if i in wrap else v for i, v in enumerate(row))
                cp.write_row(row)


def reset(database_url: str | None = None, seed: int | None = None, clock_start: str | datetime | None = None,
          *, quality: bool = True, person_hash_key: str | None = None) -> dict:
    """Vacia y recarga los datos de demo (idempotente). Devuelve resumen y fallos de calidad."""
    _load_dotenv()
    seed = int(seed if seed is not None else os.environ.get("DEMO_SEED", 42))
    clock = _clock(clock_start)
    key = person_hash_key or os.environ.get("PERSON_HASH_KEY") or DEFAULT_KEY
    ds = gen.generate(seed, clock, key, _hasher())
    with psycopg.connect(_url(database_url)) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        _truncate(conn)
        _load(conn, ds)
        layers.apply_layers(conn, clock.astimezone(gen.UTC))
        layers.refresh(conn)
        conn.commit()
        failures = layers.run_quality(conn) if quality else []
    return {"seed": seed, "clock_start": clock.isoformat(), "rows": ds.stats, "failures": failures}


def table_hashes(database_url: str | None = None) -> dict[str, str]:
    """md5 por tabla (public + raw.events + vistas materializadas): comprueba el determinismo."""
    out: dict[str, str] = {}
    with psycopg.connect(_url(database_url)) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        rels = [f"public.{r[0]}" for r in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version' ORDER BY 1")]
        rels += ["raw.events"]
        rels += [f"{r[0]}.{r[1]}" for r in conn.execute(
            "SELECT schemaname, matviewname FROM pg_matviews ORDER BY 1, 2")]
        for rel in rels:
            out[rel] = conn.execute(
                f"SELECT md5(coalesce(string_agg(t::text, E'\\n' ORDER BY t::text), '')) FROM {rel} t").fetchone()[0]
    return out


def main(argv: list[str]) -> int:
    res = reset(quality="--no-quality" not in argv)
    print(f"seed={res['seed']} clock={res['clock_start']}")
    print(", ".join(f"{t}={n}" for t, n in res["rows"].items()))
    if "--hash" in argv:
        hs = table_hashes()
        for k, v in hs.items():
            print(f"{v}  {k}")
        print("TOTAL", hashlib.md5("".join(hs.values()).encode()).hexdigest())
    for test, detail in res["failures"]:
        print(f"FALLO calidad {test}: {detail}")
    print("calidad: " + ("FALLA" if res["failures"] else "OK"))
    return 1 if res["failures"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
