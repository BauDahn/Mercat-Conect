import hashlib
import hmac
import json
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.config import get_settings


@dataclass
class ChargeSession:
    provider_ref: str
    checkout_url: str | None


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_charge(self, order_id: uuid.UUID, amount_cents: int) -> ChargeSession: ...

    @abstractmethod
    def refund(self, provider_ref: str, amount_cents: int) -> bool: ...

    @abstractmethod
    def verify_webhook(self, raw: bytes, signature: str) -> bool: ...


class FakePaymentProvider(PaymentProvider):
    """Demo: emite el webhook firmado como lo haría una pasarela real."""
    name = "fake"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.delayed: list[tuple[datetime, str]] = []
        self.refunded: list[str] = []

    @staticmethod
    def _key() -> bytes:
        return get_settings().SECRET_KEY.encode()

    def create_charge(self, order_id, amount_cents):
        ref = f"fake_{uuid.uuid4().hex}"
        return ChargeSession(ref, f"/demo/pago?ref={ref}")

    def refund(self, provider_ref, amount_cents):
        self.refunded.append(provider_ref)
        return True

    def sign(self, raw: bytes) -> str:
        return hmac.new(self._key(), raw, hashlib.sha256).hexdigest()

    def verify_webhook(self, raw, signature):
        return hmac.compare_digest(self.sign(raw), signature or "")

    def make_webhook(self, provider_ref: str, status: str, amount_cents: int | None = None) -> tuple[bytes, str]:
        body = {"provider_ref": provider_ref, "status": status}
        if amount_cents is not None:
            body["amount_cents"] = amount_cents
        raw = json.dumps(body).encode()
        return raw, self.sign(raw)

    def schedule(self, due: datetime, provider_ref: str) -> None:
        with self._lock:
            self.delayed.append((due, provider_ref))

    def pop_due(self, now: datetime) -> list[str]:
        with self._lock:
            due = [r for d, r in self.delayed if d <= now]
            self.delayed = [(d, r) for d, r in self.delayed if d > now]
            return due


_providers: dict[str, PaymentProvider] = {}


def get_provider(name: str | None = None) -> PaymentProvider:
    name = name or get_settings().PAYMENT_PROVIDER
    if name != "fake":
        raise RuntimeError(f"PaymentProvider '{name}' no implementado")
    if name not in _providers:
        _providers[name] = FakePaymentProvider()
    return _providers[name]
