import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import get_settings


@dataclass
class AgeResult:
    stable_id: str
    adult: bool
    method: str
    provider_ref: str | None = None


class AgeVerifier(ABC):
    @abstractmethod
    def start_url(self, state: str) -> str: ...

    @abstractmethod
    def verify(self, token: str, kind: str | None = None) -> AgeResult:
        """Lanza ValueError si el resultado no es válido."""


class FakeAgeVerifier(AgeVerifier):
    """Demo. token = DNI inventado (identificador estable); kind = 'adult' | 'minor'."""

    def start_url(self, state: str) -> str:
        return f"/demo/verificador?state={state}"

    def verify(self, token: str, kind: str | None = None) -> AgeResult:
        kind = kind or "adult"
        if kind not in ("adult", "minor") or not token.strip():
            raise ValueError("token inválido")
        return AgeResult(stable_id=token.strip(), adult=kind == "adult", method="demo", provider_ref="fake")


def get_age_verifier() -> AgeVerifier:
    name = get_settings().AGE_VERIFIER
    if name == "fake":
        return FakeAgeVerifier()
    raise RuntimeError(f"AgeVerifier '{name}' no implementado")


_ = base64
