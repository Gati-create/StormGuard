"""Simulation endpoints: the hero POST /api/simulate, reset, and event list."""
from fastapi import APIRouter, HTTPException, Request

from backend import config
from backend.engines import analytics_engine
from backend.models import SimulateRequest
from backend.routers import deps
from backend.services import simulation

router = APIRouter(tags=["simulation"])


@router.post("/simulate")
def simulate(body: SimulateRequest, request: Request):
    scenario = None
    if body.scenario_key:
        scenario = config.SCENARIOS.get(body.scenario_key)
        if scenario is None:
            raise HTTPException(status_code=400,
                                detail="Unknown scenario_key %s" % body.scenario_key)
    zone_id = body.zone_id or (scenario["zone_id"] if scenario else config.JUDGE_EVENT["zone_id"])
    deps.zone_or_404(zone_id)

    weather = dict(scenario["weather"]) if scenario else {}
    if body.weather:
        weather.update({k: v for k, v in body.weather.model_dump().items() if v is not None})
    data_source = "USER INPUT" if body.weather is not None else "SIMULATED"
    overrides = body.overrides.model_dump() if body.overrides else {}

    with deps.write_locked(request) as conn:
        result = simulation.run_pipeline(
            conn, zone_id=zone_id, weather=weather,
            scenario_key=body.scenario_key,
            label=scenario["label"] if scenario else None,
            data_source=data_source, overrides=overrides)
        conn.commit()
    request.app.state.last_event_id = result["event_id"]
    request.app.state.last_simulation = {
        "event_id": result["event_id"],
        "totals": result["totals"],
        "assessment": result["assessment"],
    }
    return result


@router.post("/simulation/reset")
def simulation_reset(request: Request):
    with deps.write_locked(request) as conn:
        cards = simulation.reset_demo(conn)
        conn.commit()
    request.app.state.last_event_id = None
    request.app.state.last_simulation = None
    return {"status": "reset", "cards": cards}


@router.get("/events")
def list_events(request: Request):
    conn = deps.get_conn(request)
    rows = conn.execute(
        "SELECT e.*, "
        " (SELECT COUNT(*) FROM claims c WHERE c.event_id = e.event_id) AS affected,"
        " (SELECT COALESCE(SUM(p.amount), 0) FROM payouts p WHERE p.event_id = e.event_id) AS paid"
        " FROM weather_events e ORDER BY e.created_at DESC, e.event_id DESC"
    ).fetchall()
    events = [{
        "event_id": r["event_id"],
        "event_type": r["event_type"],
        "label": analytics_engine.event_label(r["event_type"], r["scenario_key"]),
        "zone_name": _zone_name(r["zone_id"]),
        "rainfall_mm": r["rainfall_mm"],
        "created_at": r["created_at"],
        "totals": {"affected_riders": int(r["affected"]), "payout_total": round(float(r["paid"]), 2)},
    } for r in rows]
    return {"events": events}


def _zone_name(zone_id):
    for z in config.ZONES:
        if z["id"] == zone_id:
            return z["name"]
    return zone_id
