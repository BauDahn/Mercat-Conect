"""Arranque: `python -m app`. En demo escucha solo en 127.0.0.1 (salvo BIND_HOST explícito, p. ej. Docker)."""
import os

import uvicorn

from app.config import get_settings


def bind_host() -> str:
    s = get_settings()
    return s.BIND_HOST or ("127.0.0.1" if s.DEMO_MODE else "0.0.0.0")  # noqa: S104


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=bind_host(), port=int(os.environ.get("PORT", "8000")))
