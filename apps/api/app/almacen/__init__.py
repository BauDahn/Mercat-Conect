"""FileStore: almacén de archivos subidos. Demo: disco local; producción: S3 (misma interfaz)."""
import re
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings

NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
MEDIA = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def detect_image(data: bytes) -> str | None:
    """Valida la cabecera real del archivo (no el nombre ni el Content-Type)."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


class FileStore(ABC):
    @abstractmethod
    def save(self, data: bytes, ext: str) -> str:
        """Guarda con nombre aleatorio y devuelve el nombre."""

    @abstractmethod
    def path(self, name: str) -> Path | None: ...

    @abstractmethod
    def delete(self, name: str) -> None: ...


class LocalFileStore(FileStore):
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, data, ext):
        self.root.mkdir(parents=True, exist_ok=True)
        name = f"{secrets.token_hex(16)}.{ext}"
        (self.root / name).write_bytes(data)
        return name

    def path(self, name):
        if not NAME_RE.match(name):
            return None
        p = self.root / name
        return p if p.is_file() else None

    def delete(self, name):
        p = self.path(name)
        if p:
            p.unlink(missing_ok=True)


def get_store() -> FileStore:
    s = get_settings()
    root = Path(s.UPLOAD_DIR) if s.UPLOAD_DIR else Path(__file__).resolve().parents[4] / ".demo" / "uploads"
    return LocalFileStore(root)
