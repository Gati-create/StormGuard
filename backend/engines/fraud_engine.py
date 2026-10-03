"""Additive anomaly scoring for claims. Anything at or above the hold
threshold goes to a human — the engine never auto-accuses or auto-rejects."""
import random

from backend import config

SIGNAL_LABELS = {
    "gps_mismatch": "GPS mismatch",
    "impossible_travel": "Impossible travel",
    "duplicate_event": "Duplicate event claim",
    "duplicate_payout_attempt": "Duplicate payout attempt",
    "unusual_claim_frequency": "Unusual claim frequency",
    "event_zone_mismatch": "Event-zone mismatch",
    "new_account_high_claim": "New account, high claim",
    "historical_behaviour_flag": "Historical behaviour flag",
}

SIGNAL_DETAILS = {
    "gps_mismatch": "Worker GPS 12.4km outside affected zone during event window",
    "impossible_travel": "Location jump of 180km within 10 minutes",
    "duplicate_event": "Multiple claims filed for the same event window",
    "duplicate_payout_attempt": "Repeated payout request for an already-settled claim",
    "unusual_claim_frequency": "4 claims in 7 days vs fleet baseline of 0.3",
    "event_zone_mismatch": "Registered home zone outside the triggered zone set",
    "new_account_high_claim": "Account tenure 2 weeks with a maximum-value claim",
    "historical_behaviour_flag": "Prior flagged claims in the last 30 days",
}

# Pre-computed signal bundles whose totals land inside the 60-92 band used by
# bulk simulation (2-4 signals each, per demo calibration).
_BULK_COMBOS = [
    ("gps_mismatch", "event_zone_mismatch"),                                    # 62
    ("gps_mismatch", "unusual_claim_frequency", "event_zone_mismatch"),         # 84
    ("impossible_travel", "event_zone_mismatch"),                               # 68
    ("gps_mismatch", "duplicate_event"),                                        # 64
    ("impossible_travel", "unusual_claim_frequency", "event_zone_mismatch"),    # 90
    ("gps_mismatch", "unusual_claim_frequency", "new_account_high_claim"),      # 71
    ("duplicate_event", "gps_mismatch", "unusual_claim_frequency"),             # 86
    ("impossible_travel", "new_account_high_claim", "historical_behaviour_flag"),  # 73
    ("event_zone_mismatch", "unusual_claim_frequency",
     "new_account_high_claim", "historical_behaviour_flag"),                    # 83
]

SIMULATED_FRAUD_SIGNALS = ("gps_mismatch", "unusual_claim_frequency", "event_zone_mismatch")  # 84


def band_for(score):
    f = config.FRAUD
    if score >= f["hold_threshold"]:
        return "HIGH"
    if score >= f["medium_threshold"]:
        return "MEDIUM"
    return "LOW"


def action_for(score):
    return "HOLD_FOR_REVIEW" if score >= config.FRAUD["hold_threshold"] else "AUTO_APPROVE"


def score_claim(signal_keys):
    """score = sum of signal points capped at 100; band and action derived."""
    signals = []
    total = 0
    for key in signal_keys:
        points = config.FRAUD["signals"][key]
        total += points
        signals.append({
            "signal": SIGNAL_LABELS[key],
            "points": points,
            "detail": SIGNAL_DETAILS[key],
        })
    score = min(100, total)
    return {
        "fraud_score": score,
        "risk_band": band_for(score),
        "signals": signals,
        "action": action_for(score),
    }


def bulk_scores(claim_ids, event_id):
    """Deterministic bulk scoring: ~base_suspicious_rate of claims are flagged
    (score 60-92 -> HOLD_FOR_REVIEW); the rest get a benign noise score 0-25.
    Seeded by event_id so re-runs of the same event are reproducible."""
    rng = random.Random("fraud-bulk:%s" % event_id)
    ordered = sorted(claim_ids)
    n = len(ordered)
    k = int(round(config.FRAUD["base_suspicious_rate"] * n))
    flagged = set(rng.sample(ordered, k)) if k else set()
    results = {}
    for cid in ordered:
        if cid in flagged:
            combo = _BULK_COMBOS[rng.randrange(len(_BULK_COMBOS))]
            results[cid] = score_claim(combo)
        else:
            noise = rng.randint(0, 25)
            results[cid] = {
                "fraud_score": noise,
                "risk_band": band_for(noise),
                "signals": [],
                "action": action_for(noise),
            }
    return results
