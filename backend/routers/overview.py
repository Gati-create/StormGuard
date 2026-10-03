"""Central overview screen."""
from fastapi import APIRouter, Request

from backend import config
from backend.engines import analytics_engine
from backend.routers import deps

router = APIRouter(tags=["overview"])


def _event_stats(conn, event_id):
    """Exposure aggregates for one event (used by overview + protection)."""
    ev = conn.execute("SELECT * FROM weather_events WHERE event_id = ?", (event_id,)).fetchone()
    if ev is None:
        return None
    affected = conn.execute(
        "SELECT COUNT(*) AS n FROM claims WHERE event_id = ?", (event_id,)).fetchone()["n"]
    expo = conn.execute(
        "SELECT COALESCE(SUM(w.avg_hourly_income), 0) AS s FROM claims c"
        " JOIN workers w ON w.worker_id = c.worker_id WHERE c.event_id = ?",
        (event_id,)).fetchone()["s"]
    mult = config.DISRUPTION["hours_multiplier"]
    exposure = round(float(expo) * ev["duration_h"] * mult, 2)
    payout_total = round(float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM payouts WHERE event_id = ?",
        (event_id,)).fetchone()["s"]), 2)
    ticks = {
        "trigger": bool(conn.execute(
            "SELECT 1 FROM triggers WHERE event_id = ? AND fired = 1 LIMIT 1",
            (event_id,)).fetchone()),
        "eligibility": bool(conn.execute(
            "SELECT 1 FROM claims WHERE event_id = ? LIMIT 1", (event_id,)).fetchone()),
        "fraud": bool(conn.execute(
            "SELECT 1 FROM fraud_checks WHERE event_id = ? LIMIT 1", (event_id,)).fetchone()),
        "payout": bool(conn.execute(
            "SELECT 1 FROM payouts WHERE event_id = ? LIMIT 1", (event_id,)).fetchone()),
    }
    return {"event": dict(ev), "affected": int(affected), "exposure": exposure,
            "payout_total": payout_total, "ticks": ticks}


@router.get("/overview")
def overview(request: Request):
    conn = deps.get_conn(request)
    event_id = getattr(request.app.state, "last_event_id", None)
    stats = _event_stats(conn, event_id) if event_id else None

    cards = {
        "riders": analytics_engine._rider_count(conn),
        "exposed_riders": stats["affected"] if stats else 0,
        "exposure": stats["exposure"] if stats else 0,
        "payout_total": stats["payout_total"] if stats else 0,
        "portfolio_risk": analytics_engine.portfolio_risk(conn),
    }

    if stats:
        map_zones = analytics_engine.zone_summaries(conn, event_id=event_id)
        row = conn.execute(
            "SELECT * FROM risk_assessments WHERE event_id = ?"
            " ORDER BY risk_score DESC LIMIT 1", (event_id,)).fetchone()
        ai = _assessment_json(conn, row) if row else None
        ev = stats["event"]
        zone = next((z for z in config.ZONES if z["id"] == ev["zone_id"]), None)
        active_event = {
            "event_id": ev["event_id"],
            "label": analytics_engine.event_label(ev["event_type"], ev["scenario_key"]),
            "zone_name": zone["name"] if zone else ev["zone_id"],
            "rainfall_mm": ev["rainfall_mm"],
            "flood_probability": ev["flood_probability"],
            "event_type": ev["event_type"],
        }
        pipeline = stats["ticks"]
    else:
        map_zones = analytics_engine.zone_summaries(conn)
        ai = _worst_ambient_assessment()
        active_event = None
        pipeline = {"trigger": False, "eligibility": False, "fraud": False, "payout": False}

    return {
        "status": "SYSTEM OPERATIONAL",
        "cards": cards,
        "map_zones": map_zones,
        "ai_assessment": ai,
        "active_event": active_event,
        "pipeline": pipeline,
    }


def _assessment_json(conn, row):
    import json
    zone = next((z for z in config.ZONES if z["id"] == row["zone_id"]), None)
    return {
        "assessment_id": row["assessment_id"],
        "zone_id": row["zone_id"],
        "zone_name": zone["name"] if zone else row["zone_id"],
        "risk_score": row["risk_score"],
        "risk_level": row["risk_level"],
        "expected_disruption_hours": row["expected_disruption_hours"],
        "expected_income_loss": row["expected_income_loss"],
        "expected_payout": row["expected_payout"],
        "confidence_score": row["confidence_score"],
        "risk_factors": json.loads(row["risk_factors"]),
        "explanation": row["explanation"],
        "model_version": row["model_version"],
    }


def _worst_ambient_assessment():
    best = None
    for z in config.ZONES:
        a, _w = analytics_engine.ambient_assessment(z)
        if best is None or a["risk_score"] > best[0]["risk_score"]:
            best = (a, z)
    a, z = best
    return {
        "assessment_id": None,
        "zone_id": z["id"],
        "zone_name": z["name"],
        "risk_score": a["risk_score"],
        "risk_level": a["risk_level"],
        "expected_disruption_hours": a["expected_disruption_hours"],
        "expected_income_loss": a["expected_income_loss"],
        "expected_payout": a["expected_payout"],
        "confidence_score": a["confidence_score"],
        "risk_factors": a["risk_factors"],
        "explanation": a["explanation"],
        "model_version": a["model_version"],
    }
