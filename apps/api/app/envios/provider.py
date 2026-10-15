"""Interfaz DeliveryProvider (§15). Solo el contrato y una implementación simulada; sin endpoints."""
import hashlib
import hmac
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config import get_settings


@dataclass
class Quote:
    price_cents: int
    eta: datetime
    cold_chain_ok: bool


class DeliveryProvider(ABC):
    @abstractmethod
    def quote(self, origin_locker_id: uuid.UUID, destination: str, window_start: datetime,
              refrigerated: bool) -> Quote: ...

    @abstractmethod
    def create(self, order_id: uuid.UUID, origin_locker_id: uuid.UUID, destination: str) -> str: ...

    @abstractmethod
    def cancel(self, delivery_id: str) -> None: ...

    @abstractmethod
    def status(self, delivery_id: str) -> str: ...

    @abstractmethod
    def verify_webhook(self, raw: bytes, signature: str) -> bool: ...


class FakeDeliveryProvider(DeliveryProvider):
    MAX_TRIP_MINUTES = 45  # cadena de frío (§15)

    def __init__(self) -> None:
        self._status: dict[str, str] = {}

    def quote(self, origin_locker_id, destination, window_start, refrigerated):
        trip = 30
        return Quote(price_cents=390, eta=window_start + timedelta(minutes=trip),
                     cold_chain_ok=(not refrigerated) or trip <= self.MAX_TRIP_MINUTES)

    def create(self, order_id, origin_locker_id, destination):
        ref = f"fakedel_{uuid.uuid4().hex[:12]}"
        self._status[ref] = "REQUESTED"
        return ref

    def cancel(self, delivery_id):
        self._status[delivery_id] = "CANCELLED"

    def status(self, delivery_id):
        return self._status.get(delivery_id, "UNKNOWN")

    def verify_webhook(self, raw, signature):
        key = get_settings().SECRET_KEY.encode()
        return hmac.compare_digest(hmac.new(key, raw, hashlib.sha256).hexdigest(), signature or "")


def get_delivery_provider() -> DeliveryProvider:
    return FakeDeliveryProvider()
