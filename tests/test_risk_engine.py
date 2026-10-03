"""Risk engine: monotonicity, calibration bands, determinism."""
from backend import config
from backend.engines import risk_engine

ZONE = next(z for z in config.ZONES if z["id"] == "Z-MK")


def _weather(**over):
    w = dict(config.SCENARIOS["NORMAL_DAY"]["weather"])
    w.update(over)
    return w


def test_monotonic_in_rainfall():
    scores = [risk_engine.assess(_weather(rainfall_mm=r, flood_probability=f), ZONE,
                                 hazard="rain")["risk_score"]
              for r, f in [(5, 0.1), (30, 0.3), (64.5, 0.5), (95, 0.82), (160, 0.95)]]
    assert scores == sorted(scores)
    assert scores[-1] > scores[0]


def test_extreme_flood_band():
    a = risk_engine.assess(config.SCENARIOS["EXTREME_FLOOD"]["weather"], ZONE, hazard="rain")
    assert 85 <= a["risk_score"] <= 95
    assert a["risk_level"] in ("HIGH", "SEVERE")
    assert a["expected_disruption_hours"] == 6.2       # min(4h x 1.55, 9)
    assert a["expected_income_loss"] == 531.43        # 85.71/h fleet avg x 6.2h
    assert a["expected_payout"] == 425.14          # x 0.80 STANDARD coverage


def test_normal_day_is_low():
    a = risk_engine.assess(config.SCENARIOS["NORMAL_DAY"]["weather"], ZONE, hazard="ambient")
    assert a["risk_score"] < 25
    assert a["risk_level"] == "LOW"


def test_determinism():
    w = config.SCENARIOS["EXTREME_FLOOD"]["weather"]
    a1 = risk_engine.assess(w, ZONE, hazard="rain")
    a2 = risk_engine.assess(w, ZONE, hazard="rain")
    assert a1 == a2


def test_explanation_names_top_factors():
    a = risk_engine.assess(config.SCENARIOS["EXTREME_FLOOD"]["weather"], ZONE, hazard="rain")
    assert "rainfall" in a["explanation"]
    assert "64.5" in a["explanation"]


def test_zone_closure_full_activation():
    w = _weather(zone_closure=True)
    assert risk_engine.activation_level(w) == 1.0
