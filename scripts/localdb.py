#!/usr/bin/env python3
"""PostgreSQL embebido para la demo sin Docker (paquete PyPI `pgserver`).

Uso (desde la raíz del repo):
    uv run --python 3.12 --with pgserver scripts/localdb.py start   # arranca e imprime DATABASE_URL
    uv run --python 3.12 --with pgserver scripts/localdb.py stop    # para el servidor
    uv run --python 3.12 --with pgserver scripts/localdb.py status

- Datos: .demo/pgdata (se crea en el primer arranque).
- Escucha solo en TCP 127.0.0.1:${DB_PORT:-5433}.
- Usuario y base de datos: mercat / mercat (solo demo, auth trust en localhost).
- `start` es idempotente: si ya corre en ese puerto, solo imprime la URL.
- stdout: solo la DATABASE_URL (en `start`). Lo demás va a stderr y a .demo/postgres.log.
"""

import os
import subprocess
import sys
from pathlib import Path

import pgserver

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / ".demo"
DATA = DEMO / "pgdata"
LOG = DEMO / "postgres.log"
BIN = Path(pgserver.__file__).resolve().parent / "pginstall" / "bin"
HOST = "127.0.0.1"
DB_USER = "mercat"
DB_NAME = "mercat"
DEFAULT_PORT = "5433"


def log(msg: str) -> None:
    print(f"[localdb] {msg}", file=sys.stderr)


def port() -> int:
    raw = os.environ.get("DB_PORT") or DEFAULT_PORT
    try:
        return int(raw)
    except ValueError:
        sys.exit(f"[localdb] DB_PORT no es un número: {raw!r}")


def url(p: int) -> str:
    return f"postgresql+psycopg://{DB_USER}:{DB_USER}@{HOST}:{p}/{DB_NAME}"


def pg(tool: str, *args: str) -> subprocess.CompletedProcess:
    # La salida de las herramientas de PostgreSQL se captura para no ensuciar stdout.
    return subprocess.run([str(BIN / tool), *args], capture_output=True, text=True)


def running_port() -> int | None:
    """Puerto del servidor en marcha con este PGDATA, o None si no corre."""
    if pg("pg_ctl", "status", "-D", str(DATA)).returncode != 0:
        return None
    lines = (DATA / "postmaster.pid").read_text().splitlines()
    return int(lines[3])


def psql(p: int, sql: str) -> str:
    result = subprocess.run(
        [
            str(BIN / "psql"), "-X", "-h", HOST, "-p", str(p), "-U", DB_USER,
            "-d", "postgres", "-tA", "-c", sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def start() -> int:
    p = port()
    DEMO.mkdir(exist_ok=True)

    current = running_port()
    if current is not None:
        if current != p:
            log(f"ya corre en el puerto {current}, pero DB_PORT={p}. Ejecuta 'stop' primero.")
            return 1
        log(f"ya estaba en marcha en {HOST}:{p}")
    else:
        if not (DATA / "PG_VERSION").exists():
            log("creando el clúster en .demo/pgdata")
            init = pg(
                "initdb", "-D", str(DATA), "-U", DB_USER, "--auth=trust",
                "-E", "UTF8", "--locale=C",
            )
            if init.returncode != 0:
                log(f"initdb falló; mira {LOG}")
                return 1
        options = f"-p {p} -h {HOST} -k {DEMO}"
        started = pg(
            "pg_ctl", "start", "-D", str(DATA), "-l", str(LOG), "-w", "-t", "60",
            "-o", options,
        )
        if started.returncode != 0:
            log(f"no pude arrancar en {HOST}:{p} (¿puerto ocupado?). Mira {LOG}")
            return 1
        log(f"arrancado en {HOST}:{p}")

    exists = psql(p, f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
    if exists != "1":
        psql(p, f"CREATE DATABASE {DB_NAME}")
        log(f"base de datos '{DB_NAME}' creada")

    print(url(p))
    return 0


def stop() -> int:
    if running_port() is None:
        log("no estaba en marcha")
        return 0
    result = pg("pg_ctl", "stop", "-D", str(DATA), "-m", "fast", "-w", "-t", "60")
    if result.returncode != 0:
        log(f"no pude parar el servidor; mira {LOG}")
        return 1
    log("parado")
    return 0


def status() -> int:
    current = running_port()
    if current is None:
        print("parado")
        return 1
    print(f"en marcha: {url(current)}")
    return 0


def main() -> int:
    commands = {"start": start, "stop": stop, "status": status}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print(f"uso: {sys.argv[0]} [start|stop|status]", file=sys.stderr)
        return 2
    return commands[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
