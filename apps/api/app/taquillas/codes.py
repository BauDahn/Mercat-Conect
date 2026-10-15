import hashlib
import hmac
import uuid

from app.config import get_settings


def pickup_code(order_id: uuid.UUID) -> str:
    """Código de 6 dígitos derivable del pedido: no se guarda en claro, solo su hash."""
    d = hmac.new(get_settings().SECRET_KEY.encode(), b"pickup:" + order_id.bytes, hashlib.sha256).digest()
    return f"{int.from_bytes(d[:8], 'big') % 1_000_000:06d}"


def code_hash(compartment_id: uuid.UUID, code: str) -> bytes:
    return hashlib.sha256(f"{compartment_id}:{code}".encode()).digest()
