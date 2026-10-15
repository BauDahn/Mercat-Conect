"""Motor de reglas PURO (sección 10.4-10.5): sin base de datos ni reloj."""
import math
from dataclasses import dataclass, field

DEFAULT_GUARDRAILS = {
    "max_points_per_unit": 30,
    "max_units_per_user": 10,
    "max_price_ratio": None,
    "weekly_allowance": 100,
    "min_open_data_cell": 5,
}
SIGNAL_NAMES = {"stock_ratio", "demand_velocity", "minutes_to_close", "locker_free_slots",
                "user_points_left", "user_reputation", "time_band"}
OPS = ("gte", "lte", "gt", "lt", "eq")
THEN_KEYS = {"points_per_unit", "points_per_unit_mult", "max_units_per_user", "min_reputation"}
BOUND_KEYS = {"points_per_unit", "max_units_per_user", "min_reputation"}


@dataclass(frozen=True)
class Signals:
    stock_ratio: float
    demand_velocity: float
    minutes_to_close: float
    time_band: str
    locker_free_slots: int
    local_minutes: int  # minutos desde medianoche, hora de Madrid
    saving_cents: int = 0  # precio habitual - precio de oferta (>= 0)


@dataclass(frozen=True)
class UserFacts:
    status: str
    age_verified: bool
    reputation: float
    points_left: int
    units_already: int = 0


@dataclass
class Decision:
    allowed: bool
    points_cost: int = 0
    max_units: int = 0
    reasons: list[str] = field(default_factory=list)
    rules_applied: list[str] = field(default_factory=list)
    denial: str | None = None  # código ApiError
    params: dict = field(default_factory=dict)

    def to_api(self) -> dict:
        return {"allowed": self.allowed, "points_cost": self.points_cost, "max_units": self.max_units,
                "reasons": self.reasons, "rules_applied": self.rules_applied}


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _matches(when: dict, sig: Signals, user: UserFacts) -> bool:
    vals = {"stock_ratio": sig.stock_ratio, "demand_velocity": sig.demand_velocity,
            "minutes_to_close": sig.minutes_to_close, "locker_free_slots": sig.locker_free_slots,
            "user_points_left": user.points_left, "user_reputation": user.reputation,
            "time_band": sig.time_band}
    for key, target in when.items():
        if key == "time_between":
            a, b = _hhmm(target[0]), _hhmm(target[1])
            t = sig.local_minutes
            if not (a <= t < b if a <= b else (t >= a or t < b)):
                return False
            continue
        name, _, op = key.rpartition("_")
        if name not in vals or op not in OPS:
            return False
        v = vals[name]
        if op == "gte" and not v >= target:
            return False
        if op == "lte" and not v <= target:
            return False
        if op == "gt" and not v > target:
            return False
        if op == "lt" and not v < target:
            return False
        if op == "eq" and not v == target:
            return False
    return True


def validate_policy(policy: dict) -> list[str]:
    errs: list[str] = []
    base = policy.get("base")
    if not isinstance(base, dict):
        return ["base requerido"]
    ppu = base.get("points_per_unit")
    mx = base.get("max_units_per_user")
    ppe = base.get("points_per_euro")
    if ppe is not None and (not isinstance(ppe, (int, float)) or ppe < 0):
        errs.append("base.points_per_euro inválido")
    if ppe is None and (not isinstance(ppu, (int, float)) or ppu < 0):
        errs.append("base.points_per_unit inválido")
    if not isinstance(mx, int) or mx < 1:
        errs.append("base.max_units_per_user inválido")
    for r in policy.get("rules", []) or []:
        rid = r.get("id")
        if not rid:
            errs.append("regla sin id")
        for k in r.get("when", {}):
            if k == "time_between":
                continue
            name, _, op = k.rpartition("_")
            if name not in SIGNAL_NAMES or op not in OPS:
                errs.append(f"{rid}: condición desconocida {k}")
        for k in r.get("then", {}):
            if k not in THEN_KEYS:
                errs.append(f"{rid}: efecto desconocido {k}")
    for k, v in (policy.get("bounds") or {}).items():
        if k not in BOUND_KEYS or not isinstance(v, list) or len(v) != 2 or v[0] > v[1]:
            errs.append(f"bounds.{k} inválido")
    return errs


def resolve_params(user: UserFacts, sig: Signals, policy: dict, guardrails: dict | None = None):
    """Pasos 1-4 de la sección 10.4. Devuelve (ppu, max_units, min_rep, reglas_aplicadas)."""
    g = {**DEFAULT_GUARDRAILS, **(guardrails or {})}
    base = policy["base"]
    if base.get("points_per_euro") is not None:
        # coste base = max(1, round(ahorro_en_euros x K)); el descuento aprovechado cuesta más puntos
        ppu = float(max(1, math.floor(max(0, sig.saving_cents) / 100 * float(base["points_per_euro"]) + 0.5)))
    else:
        ppu = float(base["points_per_unit"])
    anchor = ppu
    max_units = int(base["max_units_per_user"])
    min_rep = float(base.get("min_reputation", 0))
    applied: list[str] = []
    for rule in policy.get("rules", []) or []:
        if _matches(rule.get("when", {}), sig, user):
            then = rule.get("then", {})
            if "points_per_unit" in then:
                ppu = anchor = float(then["points_per_unit"])
            if "points_per_unit_mult" in then:
                ppu = anchor * float(then["points_per_unit_mult"])
            if "max_units_per_user" in then:
                max_units = int(then["max_units_per_user"])
            if "min_reputation" in then:
                min_rep = float(then["min_reputation"])
            applied.append(rule["id"])
    b = policy.get("bounds") or {}
    if "points_per_unit" in b:
        lo, hi = b["points_per_unit"]
        n = min(max(ppu, lo), hi)
        if n != ppu:
            applied.append("bounds:points_per_unit")
        ppu = n
    if "max_units_per_user" in b:
        lo, hi = b["max_units_per_user"]
        n = min(max(max_units, lo), hi)
        if n != max_units:
            applied.append("bounds:max_units_per_user")
        max_units = n
    if "min_reputation" in b:
        lo, hi = b["min_reputation"]
        min_rep = min(max(min_rep, lo), hi)
    if g["max_points_per_unit"] is not None and ppu > g["max_points_per_unit"]:
        ppu = float(g["max_points_per_unit"])
        applied.append("guardrail:max_points_per_unit")
    if g["max_units_per_user"] is not None and max_units > g["max_units_per_user"]:
        max_units = int(g["max_units_per_user"])
        applied.append("guardrail:max_units_per_user")
    return ppu, max_units, min_rep, applied


def evaluate(user: UserFacts, qty: int, sig: Signals, policy: dict, guardrails: dict | None = None) -> Decision:
    if user.status != "ACTIVE" or not user.age_verified:
        return Decision(False, reasons=["errors.account_not_verified"], denial="account_not_verified")
    ppu, max_units, min_rep, applied = resolve_params(user, sig, policy, guardrails)
    remaining = max(0, max_units - user.units_already)
    affordable = remaining if ppu <= 0 else min(remaining, int(math.floor(user.points_left / ppu + 1e-9)))
    cost = math.ceil(round(qty * ppu, 6))
    d = Decision(True, points_cost=cost, max_units=max(0, affordable), rules_applied=applied,
                 params={"max": max_units, "remaining": remaining, "points_per_unit": ppu})
    if qty > remaining:
        d.allowed, d.denial = False, "exceeds_max"
    elif user.reputation < min_rep:
        d.allowed, d.denial = False, "insufficient_reputation"
        d.params["min_reputation"] = min_rep
    elif cost > user.points_left:
        d.allowed, d.denial = False, "no_points"
        d.params["points_left"] = user.points_left
    if not d.allowed:
        d.reasons = [f"errors.{d.denial}"]
    return d
