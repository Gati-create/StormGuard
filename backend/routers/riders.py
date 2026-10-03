"""Rider dashboard (demo rider = config DEMO.demo_rider_id)."""
import random
from datetime import date, timedelta

from fastapi import APIRouter, Request

from backend import config
from backend.engines import analytics_engine
from backend.routers import deps

router = APIRouter(prefix="/riders", tags=["riders"])


@router.get("/{worker_id}/dashboard")
def rider_dashboard(worker_id: str, request: Request):
    conn = deps.get_conn(request)
    worker = deps.worker_or_404(conn, worker_id)
    zone = deps.zone_or_404(worker["home_zone_id"])
    week_start = analytics_engine.current_week_start()

    policy = conn.execute(
        "SELECT * FROM policies WHERE worker_id = ? AND week_start = ?",
        (worker_id, week_start)).fetchone()
    plan_row = conn.execute(
        "SELECT * FROM weekly_plans WHERE worker_id = ? AND week_start = ?",
        (worker_id, week_start)).fetchone()
    plan = policy["plan"] if policy else "STANDARD"
    coverage_factor = policy["coverage_factor"] if policy else 0.0
    worker_contribution = round(plan_row["worker_contribution"], 2) if plan_row else 0.0

    a, _w = analytics_engine.ambient_assessment(zone)
    # Prefer the latest event assessment for the rider's zone when one exists.
    row = conn.execute(
        "SELECT risk_score, risk_level FROM risk_assessments WHERE zone_id = ?"
        " ORDER BY created_at DESC, assessment_id DESC LIMIT 1", (zone["id"],)).fetchone()
    current_zone_risk = {
        "risk_score": row["risk_score"] if row else a["risk_score"],
        "risk_level": row["risk_level"] if row else a["risk_level"],
    }

    latest = conn.execute(
        "SELECT c.*, e.event_type, e.scenario_key FROM claims c"
        " JOIN weather_events e ON e.event_id = c.event_id"
        " WHERE c.worker_id = ? AND c.eligible = 1"
        " ORDER BY c.created_at DESC, c.claim_id DESC LIMIT 1", (worker_id,)).fetchone()
    latest_event = None
    if latest:
        payout = latest["payout_amount"] if latest["status"] == "PAID" else 0.0
        latest_event = {
            "label": analytics_engine.event_label(latest["event_type"], latest["scenario_key"]),
            "estimated_income_loss": latest["income_loss"],
            "protection_payout": payout,
            "status": latest["status"],
            "payment_label": ("HK$%g credited to FPS — DEMO / SIMULATED" % payout)
                             if payout else "No payout due",
        }

    payouts = conn.execute(
        "SELECT p.payout_id, p.amount, p.created_at, e.event_type, e.scenario_key"
        " FROM payouts p JOIN weather_events e ON e.event_id = p.event_id"
        " WHERE p.worker_id = ? ORDER BY p.created_at DESC, p.payout_id DESC LIMIT 5",
        (worker_id,)).fetchall()
    recent_payouts = [{
        "payout_id": p["payout_id"],
        "amount": p["amount"],
        "created_at": p["created_at"],
        "event_label": analytics_engine.event_label(p["event_type"], p["scenario_key"]),
    } for p in payouts]

    coverage_history = _coverage_history(worker_contribution)

    return {
        "worker": {
            "worker_id": worker["worker_id"],
            "name": worker["name"],
            "zone_name": zone["name"],
            "fps_handle": worker["fps_handle"],
        },
        "weekly_income": worker["weekly_income"],
        "protected_income": round(worker["weekly_income"] * coverage_factor, 2),
        "worker_contribution": worker_contribution,
        "plan": plan,
        "coverage_status": policy["status"] if policy else "NONE",
        "current_zone_risk": current_zone_risk,
        "latest_event": latest_event,
        "recent_payouts": recent_payouts,
        "coverage_history": coverage_history,
    }


def _coverage_history(current_premium, weeks=8):
    rng = random.Random("coverage-history")
    start = date.fromisoformat(analytics_engine.current_week_start())
    out = []
    for k in range(weeks - 1, -1, -1):
        ws = (start - timedelta(weeks=k)).isoformat()
        premium = current_premium if k == 0 else round(current_premium * rng.uniform(0.9, 1.1), 2)
        out.append({"week_start": ws, "premium": premium, "paid": True})
    return out
