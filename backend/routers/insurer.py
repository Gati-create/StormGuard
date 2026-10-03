"""Insurer / risk-manager dashboard."""
from fastapi import APIRouter, Request

from backend import config
from backend.engines import analytics_engine, pricing_engine
from backend.routers import deps
from backend.services import mock_apis

router = APIRouter(prefix="/insurer", tags=["insurer"])


@router.get("/dashboard")
def insurer_dashboard(request: Request):
    conn = deps.get_conn(request)
    cards = analytics_engine.fleet_cards(conn)
    ledger = analytics_engine.current_ledger(conn) or {}
    premium = cards["premium_collected"]

    # Capital exposure = sum over active policies of P(event) x max single-event
    # payout — the probability-weighted worst-case weekly draw.
    cap_rows = conn.execute(
        "SELECT p.plan, w.home_zone_id AS z, COUNT(*) AS n"
        " FROM policies p JOIN workers w ON w.worker_id = p.worker_id"
        " WHERE p.status = 'ACTIVE' GROUP BY p.plan, w.home_zone_id"
    ).fetchall()
    zones = {z["id"]: z for z in config.ZONES}
    capital = 0.0
    for r in cap_rows:
        prob = pricing_engine.weekly_event_probability(zones[r["z"]])
        capital += prob * config.COVERAGE_LEVELS[r["plan"]]["max_payout_per_event"] * r["n"]

    riders = cards["riders_protected"]
    forecast = mock_apis.forecast_7d(riders, config.VIABILITY["avg_payout"])

    return {
        "cards": {
            "portfolio_size": riders,
            "premium": premium,
            "claims": cards["claims_paid"],
            "loss_ratio": cards["loss_ratio"],
            "risk_reserve": round(premium * config.VIABILITY["risk_reserve_rate"], 2),
            "expected_loss": round(ledger.get("expected_claims", 0.0), 2),
            "capital_exposure": round(capital, 2),
            "fraud_rate": config.FRAUD["base_suspicious_rate"],
        },
        "forecast_7d": forecast["forecast"],
        "charts": analytics_engine.all_charts(conn),
        "data_source": forecast["data_source"],
    }
