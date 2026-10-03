"""Pricing engine: breakdown arithmetic, plan ordering, canonical calibration."""
import pytest

from backend import config
from backend.engines import pricing_engine

ZONE = next(z for z in config.ZONES if z["id"] == "Z-MK")
AVG_HOURLY = 3360.0 / 42.0  # 80


def test_breakdown_sums_to_gross():
    for plan in config.COVERAGE_LEVELS:
        r = pricing_engine.price(AVG_HOURLY, ZONE, plan)
        b = r["breakdown"]
        assert b["expected_loss"] + b["operating_cost"] + b["fraud_reserve"] + b["risk_margin"] \
            == pytest.approx(r["gross_premium"], abs=0.011)


def test_worker_plus_platform_equals_gross():
    r = pricing_engine.price(AVG_HOURLY, ZONE, "STANDARD")
    assert r["worker_contribution"] + r["platform_subsidy"] == pytest.approx(r["gross_premium"], abs=0.011)


def test_worker_never_above_affordability_cap():
    cap = config.PRICING["worker_affordability_cap"]
    for plan in config.COVERAGE_LEVELS:
        r = pricing_engine.price(250.0, ZONE, plan)  # high earner, worst case
        assert r["worker_contribution"] <= cap


def test_plan_ordering():
    gross = {p: pricing_engine.price(AVG_HOURLY, ZONE, p)["gross_premium"]
             for p in config.COVERAGE_LEVELS}
    assert gross["PLUS"] > gross["STANDARD"] > gross["BASIC"]


def test_canonical_standard_koramangala():
    r = pricing_engine.price(AVG_HOURLY, ZONE, "STANDARD")
    assert 180 <= r["gross_premium"] <= 290
    assert r["worker_contribution"] == 43.75


def test_zone_risk_scales_probability():
    low = next(z for z in config.ZONES if z["id"] == "Z-TP")
    assert pricing_engine.weekly_event_probability(ZONE) > pricing_engine.weekly_event_probability(low)


def test_expected_payout_capped_at_plan_max():
    r = pricing_engine.price(400.0, ZONE, "BASIC")  # 400/h -> raw > 700 cap
    assert r["expected_payout_given_event"] <= config.COVERAGE_LEVELS["BASIC"]["max_payout_per_event"]
