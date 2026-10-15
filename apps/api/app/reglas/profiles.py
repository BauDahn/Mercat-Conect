"""Políticas por perfil (sección 10.2)."""
import copy

PROFILES: dict[str, dict] = {
    "LIBRE": {
        "version": 1,
        "base": {"points_per_unit": 1, "max_units_per_user": 6},
        "rules": [{"id": "agotamiento-rapido", "when": {"demand_velocity_gte": 1.0},
                   "then": {"points_per_unit_mult": 2.0, "max_units_per_user": 3}}],
        "bounds": {"points_per_unit": [0, 6], "max_units_per_user": [1, 10]},
    },
    "EQUILIBRADO": {
        "version": 1,
        "base": {"points_per_unit": 2, "max_units_per_user": 3},
        "rules": [
            {"id": "pico-de-demanda", "when": {"demand_velocity_gte": 0.5},
             "then": {"points_per_unit_mult": 2.0, "max_units_per_user": 2}},
            {"id": "cierre-con-sobrante", "when": {"minutes_to_close_lte": 30, "stock_ratio_gte": 0.4},
             "then": {"points_per_unit_mult": 0.5, "max_units_per_user": 6}},
        ],
        "bounds": {"points_per_unit": [0, 6], "max_units_per_user": [1, 10]},
    },
    "ESTRICTO": {
        "version": 1,
        "base": {"points_per_unit": 4, "max_units_per_user": 2},
        "rules": [{"id": "cierre-con-sobrante", "when": {"minutes_to_close_lte": 20, "stock_ratio_gte": 0.5},
                   "then": {"points_per_unit_mult": 0.5, "max_units_per_user": 3}}],
        "bounds": {"points_per_unit": [1, 6], "max_units_per_user": [1, 4]},
    },
}


def policy_for(profile: str, custom: dict | None = None) -> dict:
    if profile == "PERSONALIZADO":
        if not custom:
            raise ValueError("PERSONALIZADO exige policy")
        return custom
    return copy.deepcopy(PROFILES.get(profile, PROFILES["EQUILIBRADO"]))
