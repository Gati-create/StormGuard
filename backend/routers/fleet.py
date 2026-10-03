"""Fleet / B2B dashboard endpoints."""
import json

from fastapi import APIRouter, Request

from backend import config
from backend.engines import analytics_engine
from backend.routers import deps

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/dashboard")
def fleet_dashboard(request: Request):
    conn = deps.get_conn(request)
    cards = analytics_engine.fleet_cards(conn)
    ledger = analytics_engine.current_ledger(conn) or {}
    plan_rows = conn.execute(
        "SELECT plan, COUNT(*) AS n FROM policies WHERE status = 'ACTIVE' GROUP BY plan"
    ).fetchall()
    exposure_by_plan = {plan: 0 for plan in config.COVERAGE_LEVELS}
    for r in plan_rows:
        exposure_by_plan[r["plan"]] = int(r["n"])
    expected = ledger.get("expected_claims", 0.0)
    actual = ledger.get("actual_claims", 0.0)
    return {
        "cards": cards,
        "week_label": "Season to date (%d weeks, simulated)" % config.DEMO["ledger_weeks"],
        "map_zones": analytics_engine.zone_summaries(conn),
        "exposure_by_plan": exposure_by_plan,
        "projected_next_week_liability": round(expected, 2),
        "financials": {
            "platform_subsidy": round(ledger.get("platform_subsidy", 0.0), 2),
            "worker_contribution": round(ledger.get("worker_contribution", 0.0), 2),
            "expected_claims": round(expected, 2),
            "actual_claims": round(actual, 2),
            "net_risk_exposure": round(expected - actual, 2),
        },
    }


@router.get("/zones")
def fleet_zones(request: Request):
    conn = deps.get_conn(request)
    return {"zones": analytics_engine.zone_summaries(conn)}


@router.get("/zones/{zone_id}")
def fleet_zone_detail(zone_id: str, request: Request):
    conn = deps.get_conn(request)
    deps.zone_or_404(zone_id)
    summary = next(z for z in analytics_engine.zone_summaries(conn) if z["zone_id"] == zone_id)

    row = conn.execute(
        "SELECT risk_factors FROM risk_assessments WHERE zone_id = ?"
        " ORDER BY created_at DESC, assessment_id DESC LIMIT 1", (zone_id,)).fetchone()
    if row:
        factors = json.loads(row["risk_factors"])
    else:
        a, _w = analytics_engine.ambient_assessment(deps.zone_or_404(zone_id))
        factors = a["risk_factors"]
    top = sorted(factors, key=lambda f: f["points"], reverse=True)[:3]

    events = conn.execute(
        "SELECT DISTINCT e.event_id, e.event_type, e.scenario_key, e.created_at"
        " FROM weather_events e"
        " LEFT JOIN triggers t ON t.event_id = e.event_id AND t.zone_id = ?"
        " WHERE e.zone_id = ? OR t.fired = 1"
        " ORDER BY e.created_at DESC LIMIT 5", (zone_id, zone_id),
    ).fetchall()
    recent = [{
        "event_id": e["event_id"],
        "label": analytics_engine.event_label(e["event_type"], e["scenario_key"]),
        "created_at": e["created_at"],
    } for e in events]

    return dict(summary, top_risk_factors=top, recent_events=recent)
