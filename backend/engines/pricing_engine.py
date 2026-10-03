"""Weekly premium construction.

gross = ExpectedLoss + OperatingCost + FraudReserve + RiskMargin
ExpectedLoss(rider-week) = P(paid disruption event in week) x E[payout | event]
P(event) = base_weekly_event_probability x (zone.base_risk / fleet_avg) x seasonality
"""
from typing import Optional

from backend import config

FLEET_AVG_BASE_RISK = sum(z["base_risk"] for z in config.ZONES) / len(config.ZONES)


def zone_by_id(zone_id):
    for z in config.ZONES:
        if z["id"] == zone_id:
            return z
    return None


def weekly_event_probability(zone, season=None):
    season = season or config.DEMO["season"]
    p = config.PRICING
    return (p["base_weekly_event_probability"]
            * (zone["base_risk"] / FLEET_AVG_BASE_RISK)
            * config.SEASONALITY[season])


def expected_payout_given_event(avg_hourly, plan):
    pl = config.COVERAGE_LEVELS[plan]
    raw = (avg_hourly
           * config.PRICING["typical_event_duration_h"]
           * config.DISRUPTION["hours_multiplier"]
           * pl["coverage_factor"]
           * config.DISRUPTION["overlap_mean"])
    return min(raw, pl["max_payout_per_event"])


def price(avg_hourly, zone, plan, subsidy_share=None, season=None):
    p = config.PRICING
    pl = config.COVERAGE_LEVELS[plan]
    prob = weekly_event_probability(zone, season)
    ep = expected_payout_given_event(avg_hourly, plan)
    expected_loss = round(prob * ep, 2)
    operating_cost = round(p["operating_cost_per_week"], 2)
    fraud_reserve = round(p["fraud_reserve_rate"] * expected_loss, 2)
    risk_margin = round(p["risk_margin_rate"] * expected_loss, 2)
    gross = round(expected_loss + operating_cost + fraud_reserve + risk_margin, 2)
    share = p["subsidy_share"] if subsidy_share is None else subsidy_share
    worker = round(min(gross * (1.0 - share), p["worker_affordability_cap"]), 2)
    platform = round(gross - worker, 2)
    return {
        "plan": plan,
        "coverage_factor": pl["coverage_factor"],
        "weekly_event_probability": round(prob, 4),
        "expected_payout_given_event": round(ep, 2),
        "gross_premium": gross,
        "breakdown": {
            "expected_loss": expected_loss,
            "operating_cost": operating_cost,
            "fraud_reserve": fraud_reserve,
            "risk_margin": risk_margin,
        },
        "platform_subsidy": platform,
        "worker_contribution": worker,
        "subsidy_share": share,
        "max_payout_per_event": pl["max_payout_per_event"],
        "weekly_coverage_limit": pl["weekly_coverage_limit"],
    }


def why(result, zone, weekly_income, weekly_hours, season=None):
    b = result["breakdown"]
    share = result.get("subsidy_share", config.PRICING["subsidy_share"])
    return (
        "Expected loss HK$%g/week = %.1f%% weekly event probability (%s, %s season, "
        "zone base risk %g vs fleet avg %g) × HK$%g expected payout per event "
        "(HK$%g/h × %gh × %g disruption multiplier × %g coverage × %g mean schedule overlap). "
        "Add HK$%g operating cost + HK$%g fraud reserve + HK$%g risk margin → gross HK$%g. "
        "The platform subsidises %g%%, so the rider pays HK$%g (capped at HK$%g/week) "
        "and the platform contributes HK$%g."
        % (
            b["expected_loss"], result["weekly_event_probability"] * 100.0,
            zone["name"], season or config.DEMO["season"],
            zone["base_risk"], round(FLEET_AVG_BASE_RISK, 3),
            result["expected_payout_given_event"],
            round(weekly_income / weekly_hours, 2), config.PRICING["typical_event_duration_h"],
            config.DISRUPTION["hours_multiplier"], result["coverage_factor"],
            config.DISRUPTION["overlap_mean"],
            b["operating_cost"], b["fraud_reserve"], b["risk_margin"], result["gross_premium"],
            share * 100.0, result["worker_contribution"],
            config.PRICING["worker_affordability_cap"], result["platform_subsidy"],
        )
    )
