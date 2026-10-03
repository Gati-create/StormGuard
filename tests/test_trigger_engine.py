"""Trigger engine: thresholds, boundary values, multi-trigger events."""
from backend import config
from backend.engines import trigger_engine


def _evals(**over):
    w = dict(config.SCENARIOS["NORMAL_DAY"]["weather"])
    w.update(over)
    return trigger_engine.evaluate(w)


def _fired(evals):
    return {e["trigger_type"] for e in evals if e["fired"]}


def test_boundary_below_threshold():
    assert "HEAVY_RAIN" not in _fired(_evals(rainfall_mm=64.4))


def test_boundary_at_threshold():
    assert "HEAVY_RAIN" in _fired(_evals(rainfall_mm=64.5))


def test_any_semantics():
    # EXTREME_RAIN_FLOOD is an OR rule: rain >= 90 OR flood_probability >= 0.75.
    assert "EXTREME_RAIN_FLOOD" in _fired(_evals(rainfall_mm=91.0, flood_probability=0.1))
    assert "EXTREME_RAIN_FLOOD" in _fired(_evals(rainfall_mm=10.0, flood_probability=0.8))
    assert "EXTREME_RAIN_FLOOD" not in _fired(_evals(rainfall_mm=80.0, flood_probability=0.5))


def test_black_swan_multi_trigger():
    fired = _fired(_evals(**config.SCENARIOS["BLACK_SWAN"]["weather"]))
    for expected in ("EXTREME_RAIN_FLOOD", "CYCLONE", "ZONE_CLOSURE", "PLATFORM_OUTAGE"):
        assert expected in fired


def test_normal_day_fires_nothing():
    assert _fired(_evals()) == set()


def test_platform_outage_comparator():
    assert "PLATFORM_OUTAGE" in _fired(_evals(platform_availability_pct=84.9))
    assert "PLATFORM_OUTAGE" not in _fired(_evals(platform_availability_pct=85.0))
