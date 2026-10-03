"""Pricing endpoints: plan comparison + single quote."""
from fastapi import APIRouter, HTTPException, Request

from backend import config
from backend.engines import pricing_engine
from backend.models import QuoteRequest
from backend.routers import deps

router = APIRouter(prefix="/pricing", tags=["pricing"])

_EXPLAIN = ("Premium = Expected Loss + Operating Cost + Fraud Reserve + Risk Margin. "
            "Expected loss = weekly event probability × expected payout.")


@router.get("/plans")
def plans(request: Request, zone_id: str = "Z-MK", weekly_income: float = 4200.0,
          weekly_hours: float = 42.0):
    if weekly_income <= 0 or weekly_hours <= 0:
        raise HTTPException(status_code=400, detail="weekly_income and weekly_hours must be positive")
    zone = deps.zone_or_404(zone_id)
    avg_hourly = weekly_income / weekly_hours
    return {
        "plans": [pricing_engine.price(avg_hourly, zone, plan)
                  for plan in config.COVERAGE_LEVELS],
        "inputs": {
            "zone_id": zone_id,
            "weekly_income": weekly_income,
            "weekly_hours": weekly_hours,
            "season": config.DEMO["season"],
        },
        "explain": _EXPLAIN,
    }


@router.post("/quote")
def quote(body: QuoteRequest, request: Request):
    zone = deps.zone_or_404(body.zone_id)
    if body.plan not in config.COVERAGE_LEVELS:
        raise HTTPException(status_code=400, detail="Unknown plan %s" % body.plan)
    avg_hourly = body.weekly_income / body.weekly_hours
    result = pricing_engine.price(avg_hourly, zone, body.plan,
                                  subsidy_share=body.subsidy_share)
    result["why"] = pricing_engine.why(result, zone, body.weekly_income, body.weekly_hours)
    result["inputs"] = {
        "zone_id": body.zone_id,
        "weekly_income": body.weekly_income,
        "weekly_hours": body.weekly_hours,
        "season": config.DEMO["season"],
    }
    return result
