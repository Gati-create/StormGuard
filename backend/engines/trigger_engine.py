"""Parametric trigger evaluation against config.TRIGGERS.

Pure function of the (possibly zone-attenuated) weather signal; persistence is
handled by the simulation pipeline so every evaluation — fired or not — lands
in the triggers table.
"""
from backend import config


def _compare(value, op, threshold):
    if value is None:
        return False
    if op == ">=":
        return value >= threshold
    if op == ">":
        return value > threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    if op == "==":
        return bool(value) == bool(threshold)
    raise ValueError("unsupported trigger operator %r" % op)


def evaluate(weather):
    """Evaluate every trigger rule; returns the full evaluation list (fired
    and not-fired), each with threshold_desc and observed_value."""
    evaluations = []
    for ttype, tdef in config.TRIGGERS.items():
        checks = []
        descs = []
        observed = []
        for param, (op, threshold) in tdef["params"].items():
            value = weather.get(param)
            if param == "zone_closure":
                value = bool(value)
            checks.append(_compare(value, op, threshold))
            descs.append("%s %s %s" % (param, op, threshold))
            observed.append("%s=%s" % (param, value))
        fired = any(checks) if tdef.get("any") else all(checks)
        evaluations.append({
            "trigger_type": ttype,
            "label": tdef["label"],
            "fired": bool(fired),
            "threshold_desc": (" OR " if tdef.get("any") else " AND ").join(descs),
            "observed_value": ", ".join(observed),
        })
    return evaluations


def fired_types(evaluations):
    return [e["trigger_type"] for e in evaluations if e["fired"]]


# Severity order used to name an event after its most significant trigger.
_EVENT_TYPE_PRIORITY = [
    "EXTREME_RAIN_FLOOD", "CYCLONE", "EXTREME_HEAT", "SEVERE_AQI",
    "HEAVY_RAIN", "ZONE_CLOSURE", "PLATFORM_OUTAGE",
]


def event_type_for(evaluations):
    fired = set(fired_types(evaluations))
    for ttype in _EVENT_TYPE_PRIORITY:
        if ttype in fired:
            return ttype
    return "NONE"
