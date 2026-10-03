"""Payout engine: formula, caps, weekly limit, min payout, overlap determinism."""
import pytest

from backend import config
from backend.engines import payout_engine

DEMO = config.DEMO["demo_rider_id"]
STANDARD = {"plan": "STANDARD", **config.COVERAGE_LEVELS["STANDARD"]}


def _worker(worker_id="W-000042", avg_hourly=100.0):
    return {"worker_id": worker_id, "avg_hourly_income": avg_hourly}


def test_demo_rider_canonical_payout():
    calc = payout_engine.compute_payout(_worker(DEMO), STANDARD, duration_h=4.0)
    assert calc["overlap"] == config.DISRUPTION["demo_rider_overlap"] == 1.0
    assert calc["affected_hours"] == 6.2            # min(4 x 1.55 x 1.0, 9)
    assert calc["income_loss"] == 620.0             # 100 x 6.2
    assert calc["payout_amount"] == 496.0           # x 0.80


def test_max_payout_per_event_cap():
    rich = _worker(avg_hourly=1000.0)
    calc = payout_engine.compute_payout(rich, STANDARD, duration_h=9.0)
    assert calc["payout_amount"] == STANDARD["max_payout_per_event"]


def test_weekly_coverage_limit_partial():
    calc = payout_engine.compute_payout(_worker(DEMO), STANDARD, duration_h=4.0,
                                        weekly_paid=STANDARD["weekly_coverage_limit"] - 100.0)
    assert calc["payout_amount"] == 100.0
    assert calc["note"] == "WEEKLY_COVERAGE_LIMIT_REACHED"


def test_weekly_coverage_limit_exhausted():
    calc = payout_engine.compute_payout(_worker(DEMO), STANDARD, duration_h=4.0,
                                        weekly_paid=STANDARD["weekly_coverage_limit"])
    assert calc["payout_amount"] == 0.0
    assert calc["note"] == "WEEKLY_COVERAGE_LIMIT_REACHED"


def test_min_payout_floor():
    poor = _worker("W-000043", avg_hourly=30.0)
    calc = payout_engine.compute_payout(poor, STANDARD, duration_h=0.5)
    assert calc["payout_amount"] == config.PAYOUT["min_payout"]


def test_overlap_deterministic_and_bounded():
    for wid in ("W-000101", "W-000202", "W-000303"):
        o1 = payout_engine.scheduled_overlap(wid)
        o2 = payout_engine.scheduled_overlap(wid)
        assert o1 == o2
        assert config.DISRUPTION["overlap_min"] <= o1 <= config.DISRUPTION["overlap_max"]


def test_idempotency_key_format():
    assert payout_engine.idempotency_key("W-1", "EV-1", "POL-1") == "W-1:EV-1:POL-1"
