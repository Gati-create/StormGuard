"""Fraud engine: additive scoring, bands, hold action, bulk simulation."""
from backend import config
from backend.engines import fraud_engine


def test_signal_sum_and_hold():
    r = fraud_engine.score_claim(["gps_mismatch", "unusual_claim_frequency",
                                  "event_zone_mismatch"])
    assert r["fraud_score"] == 84          # 34 + 22 + 28
    assert r["risk_band"] == "HIGH"
    assert r["action"] == "HOLD_FOR_REVIEW"
    assert len(r["signals"]) == 3


def test_score_capped_at_100():
    r = fraud_engine.score_claim(["impossible_travel", "duplicate_payout_attempt",
                                  "gps_mismatch", "duplicate_event"])
    assert r["fraud_score"] == 100         # 40+45+34+30 = 149 -> capped


def test_band_thresholds():
    f = config.FRAUD
    assert fraud_engine.band_for(0) == "LOW"
    assert fraud_engine.band_for(f["medium_threshold"] - 1) == "LOW"
    assert fraud_engine.band_for(f["medium_threshold"]) == "MEDIUM"
    assert fraud_engine.band_for(f["hold_threshold"] - 1) == "MEDIUM"
    assert fraud_engine.band_for(f["hold_threshold"]) == "HIGH"
    assert fraud_engine.action_for(f["hold_threshold"]) == "HOLD_FOR_REVIEW"
    assert fraud_engine.action_for(f["hold_threshold"] - 1) == "AUTO_APPROVE"


def test_bulk_scoring_calibration():
    claim_ids = ["CL-%06d" % i for i in range(1, 3101)]
    results = fraud_engine.bulk_scores(claim_ids, "EV-TEST-001")
    held = [r for r in results.values() if r["action"] == "HOLD_FOR_REVIEW"]
    expected = round(config.FRAUD["base_suspicious_rate"] * len(claim_ids))
    assert len(held) == expected
    for r in held:
        assert 60 <= r["fraud_score"] <= 92
        assert 2 <= len(r["signals"]) <= 4
    noise = [r["fraud_score"] for r in results.values() if r["action"] == "AUTO_APPROVE"]
    assert all(0 <= s <= 25 for s in noise)


def test_bulk_deterministic():
    ids = ["CL-%06d" % i for i in range(1, 501)]
    assert fraud_engine.bulk_scores(ids, "EV-X") == fraud_engine.bulk_scores(ids, "EV-X")
