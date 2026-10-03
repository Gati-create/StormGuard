"""Deterministic additive demo risk model.

Factor points = weight x min(value / normalizer, cap); contextual factors are
additionally scaled by the event activation level (0-1). All weights and
thresholds come from backend.config — see config.RISK_MODEL for the formula
documentation.
"""
from typing import Dict, List, Optional

from backend import config

# Model semantics documented in config.RISK_MODEL: the heat factor value is
# "degC above 33", i.e. 33 degC is the zero-point (HKO Very Hot Weather Warning threshold) of heat stress.
HEAT_ZERO_C = 33.0

# Event-hazard -> which zone propensity drives zone_history / attenuation.
HAZARD_PROPENSITY = {
    "rain": "flood_propensity",
    "flood": "flood_propensity",
    "wind": "flood_propensity",
    "cyclone": "flood_propensity",
    "heat": "heat_propensity",
    "aqi": "aqi_propensity",
    "outage": None,   # operational events: zone_history uses base_risk
    "closure": None,
    "ambient": None,
}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def activation_level(weather):
    """clamp(max over trigger params of value/threshold, 0, 1).

    Heat uses the same value semantics as the risk factor (degC above 33);
    zone_closure forces full activation.
    """
    t = config.TRIGGERS
    if weather.get("zone_closure"):
        return 1.0
    heat_threshold = t["EXTREME_HEAT"]["params"]["temperature_c"][1]
    ratios = [
        weather["rainfall_mm"] / t["HEAVY_RAIN"]["params"]["rainfall_mm"][1],
        weather["rainfall_mm"] / t["EXTREME_RAIN_FLOOD"]["params"]["rainfall_mm"][1],
        weather["flood_probability"] / t["EXTREME_RAIN_FLOOD"]["params"]["flood_probability"][1],
        max(0.0, weather["temperature_c"] - HEAT_ZERO_C) / (heat_threshold - HEAT_ZERO_C),
        weather["aqi"] / t["SEVERE_AQI"]["params"]["aqi"][1],
        weather["wind_speed_kmh"] / t["CYCLONE"]["params"]["wind_speed_kmh"][1],
        weather["cyclone_probability"] / t["CYCLONE"]["params"]["cyclone_probability"][1],
    ]
    return clamp(max(ratios), 0.0, 1.0)


def risk_level_for(score):
    for min_score, level in config.RISK_MODEL["levels"]:
        if score >= min_score:
            return level
    return config.RISK_MODEL["levels"][-1][1]


def assess(weather, zone, worker_exposure_ratio=None, hazard="ambient",
           data_completeness=1.0, conflicting_sources=False):
    """Score one zone under one (possibly attenuated) weather signal.

    worker_exposure_ratio overrides the zone-average income-at-risk ratio when
    scoring for a specific rider.
    """
    rm = config.RISK_MODEL
    d = config.DISRUPTION
    activation = activation_level(weather)
    duration_h = float(weather.get("duration_h") or 1.0)

    disruption_hours = min(duration_h * d["hours_multiplier"], d["max_disruption_hours"])
    # Zone-average rider (gross, overlap = 1) per the pricing conventions.
    avg_hourly = config.WORKER_PROFILE["weekly_income_mean"] / config.WORKER_PROFILE["weekly_hours_mean"]
    income_loss = round(avg_hourly * disruption_hours, 2)
    if worker_exposure_ratio is None:
        worker_exposure_ratio = clamp(income_loss / config.WORKER_PROFILE["weekly_income_mean"], 0.0, 1.0)

    propensity_key = HAZARD_PROPENSITY.get(hazard)
    zone_history_value = zone["base_risk"] if propensity_key is None else zone[propensity_key]

    values = {
        "rainfall": weather["rainfall_mm"],
        "flood_probability": weather["flood_probability"],
        "zone_history": zone_history_value,
        "traffic": zone["traffic_index"],
        "heat": max(0.0, weather["temperature_c"] - HEAT_ZERO_C),
        "aqi": weather["aqi"],
        "wind": weather["wind_speed_kmh"],
        "time_exposure": duration_h,
        "worker_exposure": worker_exposure_ratio,
    }

    factors = []
    total = 0.0
    for name, fdef in rm["factors"].items():
        pts = fdef["weight"] * min(values[name] / fdef["normalizer"], fdef["cap"])
        if fdef["contextual"]:
            pts *= activation
        pts = round(pts, 2)
        factors.append({"key": name, "label": fdef["label"], "points": pts})
        total += pts

    score = int(clamp(round(total), 0, 100))
    level = risk_level_for(score)
    expected_payout = round(income_loss * config.COVERAGE_LEVELS["STANDARD"]["coverage_factor"], 2)
    confidence = clamp(
        rm["confidence_base"] + 0.05 * data_completeness - (0.08 if conflicting_sources else 0.0),
        0.0, 1.0,
    )

    return {
        "zone_id": zone["id"],
        "risk_score": score,
        "risk_level": level,
        "expected_disruption_hours": round(disruption_hours, 2),
        "expected_income_loss": income_loss,
        "expected_payout": expected_payout,
        "confidence_score": round(confidence, 2),
        "risk_factors": [{"label": f["label"], "points": f["points"]} for f in factors],
        "explanation": _explain(factors, weather, values, activation),
        "model_version": rm["version"],
        "activation": round(activation, 4),
    }


def _factor_phrase(key, weather, zone_value):
    t = config.TRIGGERS
    if key == "rainfall":
        thr = t["HEAVY_RAIN"]["params"]["rainfall_mm"][1]
        verb = "exceeded" if weather["rainfall_mm"] >= thr else "is approaching"
        return "rainfall (%gmm) %s the zone's disruption threshold (%gmm)" % (
            weather["rainfall_mm"], verb, thr)
    if key == "flood_probability":
        return "flood probability is elevated (%g%%)" % (weather["flood_probability"] * 100.0)
    if key == "heat":
        thr = t["EXTREME_HEAT"]["params"]["temperature_c"][1]
        verb = "crossed" if weather["temperature_c"] >= thr else "is approaching"
        return "temperature (%g°C) %s the extreme-heat threshold (%g°C)" % (
            weather["temperature_c"], verb, thr)
    if key == "aqi":
        thr = t["SEVERE_AQI"]["params"]["aqi"][1]
        verb = "breached" if weather["aqi"] >= thr else "is nearing"
        return "air quality (AQI %g) %s the severe threshold (%g)" % (weather["aqi"], verb, thr)
    if key == "wind":
        thr = t["CYCLONE"]["params"]["wind_speed_kmh"][1]
        verb = "reached" if weather["wind_speed_kmh"] >= thr else "is building toward"
        return "wind speeds (%g km/h) %s typhoon thresholds (%g km/h)" % (
            weather["wind_speed_kmh"], verb, thr)
    if key == "zone_history":
        return "the zone's high historical disruption propensity (%g)" % zone_value
    if key == "traffic":
        return "severe traffic congestion (index %g)" % zone_value
    if key == "time_exposure":
        return "a long disruption window (%gh)" % (weather.get("duration_h") or 1.0)
    if key == "worker_exposure":
        return "a large share of weekly income at risk"
    return key


def _explain(factors, weather, values, activation):
    ranked = sorted([f for f in factors if f["points"] > 0], key=lambda f: f["points"], reverse=True)
    if not ranked or activation < 0.5:
        return (
            "The risk remains low: weather parameters are at %g%% of the parametric "
            "trigger thresholds, so no disruption trigger is close to breaching."
            % round(activation * 100.0)
        )
    phrases = [_factor_phrase(f["key"], weather, values.get(f["key"])) for f in ranked[:2]]
    if len(phrases) == 1:
        return "The risk increased primarily because %s." % phrases[0]
    return "The risk increased primarily because %s and %s." % (phrases[0], phrases[1])
