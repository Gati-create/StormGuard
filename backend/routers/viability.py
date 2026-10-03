"""Business viability simulator (weekly P&L, sensitivity shocks, stress presets)."""
import math
import random

from fastapi import APIRouter, Request

from backend import config
from backend.models import SensitivityRequest, ViabilityRequest

router = APIRouter(prefix="/viability", tags=["viability"])

_INPUT_KEYS = ("riders", "avg_weekly_income", "avg_gross_premium",
               "platform_subsidy_share", "weekly_event_probability", "avg_payout",
               "operating_cost_rate", "fraud_loss_rate")


def _defaults():
    v = config.VIABILITY
    return {k: v[k] for k in _INPUT_KEYS}


def compute(inputs):
    v = config.VIABILITY
    riders = inputs["riders"]
    premium_revenue = riders * inputs["avg_gross_premium"]
    expected_claims = riders * inputs["weekly_event_probability"] * inputs["avg_payout"]
    operating_cost = premium_revenue * inputs["operating_cost_rate"]
    fraud_losses = expected_claims * inputs["fraud_loss_rate"]
    risk_reserve = premium_revenue * v["risk_reserve_rate"]
    gross_contribution = (premium_revenue - expected_claims - operating_cost
                          - fraud_losses - risk_reserve - v["fixed_weekly_cost"])
    loss_ratio = expected_claims / premium_revenue if premium_revenue else 0.0

    per_rider = (inputs["avg_gross_premium"]
                 - inputs["weekly_event_probability"] * inputs["avg_payout"]
                 - inputs["avg_gross_premium"] * (inputs["operating_cost_rate"] + v["risk_reserve_rate"])
                 - inputs["weekly_event_probability"] * inputs["avg_payout"] * inputs["fraud_loss_rate"])
    break_even = math.ceil(v["fixed_weekly_cost"] / per_rider) if per_rider > 0 else None

    wpy = v["weeks_per_year"]
    return {
        "weekly": {
            "premium_revenue": round(premium_revenue, 2),
            "expected_claims": round(expected_claims, 2),
            "operating_cost": round(operating_cost, 2),
            "fraud_losses": round(fraud_losses, 2),
            "risk_reserve": round(risk_reserve, 2),
            "fixed_weekly_cost": round(v["fixed_weekly_cost"], 2),
            "gross_contribution": round(gross_contribution, 2),
            "loss_ratio": round(loss_ratio, 4),
        },
        "annual": {
            "premium_revenue": round(premium_revenue * wpy, 2),
            "expected_claims": round(expected_claims * wpy, 2),
            "operating_cost": round(operating_cost * wpy, 2),
            "fraud_losses": round(fraud_losses * wpy, 2),
            "risk_reserve": round(risk_reserve * wpy, 2),
            "contribution": round(gross_contribution * wpy, 2),
        },
        "break_even_riders": break_even,
        "inputs": inputs,
        "explain": {
            "premium_revenue": "riders × avg_gross_premium",
            "expected_claims": "riders × weekly_event_probability × avg_payout",
            "operating_cost": "premium_revenue × operating_cost_rate",
            "fraud_losses": "expected_claims × fraud_loss_rate",
            "risk_reserve": "premium_revenue × risk_reserve_rate",
            "gross_contribution": "premium_revenue − expected_claims − operating_cost "
                                  "− fraud_losses − risk_reserve − fixed_weekly_cost",
            "break_even_riders": "ceil(fixed_weekly_cost ÷ per-rider contribution)",
        },
    }


@router.post("")
def viability(body: ViabilityRequest, request: Request):
    inputs = _defaults()
    provided = {k: v for k, v in body.model_dump().items() if v is not None}
    inputs.update(provided)
    return compute(inputs)


@router.post("/sensitivity")
def sensitivity(body: SensitivityRequest, request: Request):
    inputs = _defaults()
    if body.base:
        inputs.update({k: v for k, v in body.base.items() if k in inputs and v is not None})
    results = []
    for shock in body.shocks:
        if shock.key not in inputs:
            continue
        shocked = dict(inputs)
        shocked[shock.key] = round(shocked[shock.key] * shock.mult, 6)
        r = compute(shocked)
        results.append({
            "label": shock.label or "%s ×%g" % (shock.key, shock.mult),
            "loss_ratio": r["weekly"]["loss_ratio"],
            "annual_contribution": r["annual"]["contribution"],
            "break_even_riders": r["break_even_riders"],
        })
    return {"results": results}


@router.get("/stress")
def stress(request: Request):
    v = config.VIABILITY
    scenarios = []
    for name, sc in config.STRESS_SCENARIOS.items():
        rng = random.Random("stress:%s" % name)
        premium_revenue = v["riders"] * v["avg_gross_premium"]
        prob = v["weekly_event_probability"] * sc["event_frequency_mult"]
        payout = v["avg_payout"] * sc["severity_mult"]
        expected_claims = v["riders"] * prob * payout
        simulated_claims = expected_claims * rng.uniform(0.92, 1.12)
        operating_cost = premium_revenue * v["operating_cost_rate"]
        fraud_loss = expected_claims * v["fraud_loss_rate"]
        reserve = premium_revenue * v["risk_reserve_rate"]
        contribution = (premium_revenue - expected_claims - operating_cost
                        - fraud_loss - reserve - v["fixed_weekly_cost"])
        scenarios.append({
            "name": name,
            "premium_revenue": round(premium_revenue, 2),
            "expected_claims": round(expected_claims, 2),
            "simulated_claims": round(simulated_claims, 2),
            "loss_ratio": round(expected_claims / premium_revenue, 4) if premium_revenue else 0.0,
            "simulated_loss_ratio": round(simulated_claims / premium_revenue, 4) if premium_revenue else 0.0,
            "operating_cost": round(operating_cost, 2),
            "fraud_loss": round(fraud_loss, 2),
            "reserve_requirement": round(reserve, 2),
            "contribution_margin": round(contribution, 2),
        })
    return {"scenarios": scenarios}
