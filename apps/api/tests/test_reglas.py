from hypothesis import given, strategies as st

from app.reglas.engine import Signals, UserFacts, evaluate
from app.reglas.profiles import PROFILES

OK = UserFacts("ACTIVE", True, 1.0, 20)


def sig(**kw):
    base = dict(stock_ratio=1.0, demand_velocity=0.0, minutes_to_close=120, time_band="media_manana",
                locker_free_slots=5, local_minutes=700)
    base.update(kw)
    return Signals(**base)


P = PROFILES["EQUILIBRADO"]


def test_base():
    d = evaluate(OK, 2, sig(), P)
    assert d.allowed and d.points_cost == 4 and d.rules_applied == []


def test_pico_demanda_sube_coste_y_baja_maximo():
    d = evaluate(OK, 2, sig(demand_velocity=0.6), P)
    assert d.allowed and d.points_cost == 8 and d.rules_applied == ["pico-de-demanda"]
    d = evaluate(OK, 3, sig(demand_velocity=0.6), P)
    assert not d.allowed and d.denial == "exceeds_max"


def test_cierre_con_sobrante_baja_coste():
    d = evaluate(OK, 4, sig(minutes_to_close=20, stock_ratio=0.5), P)
    assert d.allowed and d.points_cost == 4 and d.rules_applied == ["cierre-con-sobrante"]


def test_denegaciones():
    assert evaluate(UserFacts("PENDING", False, 1, 20), 1, sig(), P).denial == "account_not_verified"
    assert evaluate(UserFacts("ACTIVE", True, 1, 1), 1, sig(), P).denial == "no_points"
    pol = {"base": {"points_per_unit": 1, "max_units_per_user": 3, "min_reputation": 0.6}}
    assert evaluate(UserFacts("ACTIVE", True, 0.5, 20), 1, sig(), pol).denial == "insufficient_reputation"
    assert evaluate(UserFacts("ACTIVE", True, 1, 20, units_already=3), 1, sig(), P).denial == "exceeds_max"


def test_barandillas_siempre_ganan():
    pol = {"base": {"points_per_unit": 5, "max_units_per_user": 9}}
    d = evaluate(OK, 1, sig(), pol, {"max_points_per_unit": 2, "max_units_per_user": 3})
    assert d.points_cost == 2 and d.params["max"] == 3
    assert "guardrail:max_points_per_unit" in d.rules_applied


def test_time_between_y_ultima_regla_gana():
    pol = {"base": {"points_per_unit": 2, "max_units_per_user": 3}, "rules": [
        {"id": "a", "when": {"time_between": ["12:30", "13:00"]}, "then": {"min_reputation": 0.9}},
        {"id": "b", "when": {"stock_ratio_gte": 0.1}, "then": {"max_units_per_user": 5}},
        {"id": "c", "when": {"stock_ratio_gte": 0.1}, "then": {"max_units_per_user": 1}}]}
    d = evaluate(UserFacts("ACTIVE", True, 0.8, 20), 1, sig(local_minutes=12 * 60 + 40), pol)
    assert d.denial == "insufficient_reputation" and d.params["max"] == 1


@given(qty=st.integers(1, 10), pts=st.integers(0, 40), vel=st.floats(0, 3), rep=st.floats(0, 1))
def test_nunca_gasta_mas_que_el_saldo(qty, pts, vel, rep):
    d = evaluate(UserFacts("ACTIVE", True, rep, pts), qty, sig(demand_velocity=vel), P)
    if d.allowed:
        assert d.points_cost <= pts
    assert d.max_units >= 0
