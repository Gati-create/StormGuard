"""Judge mode: reset to the deterministic baseline and hand back the demo script."""
from fastapi import APIRouter, Request

from backend.routers import deps
from backend.services import audit as audit_mod
from backend.services import simulation

router = APIRouter(prefix="/judge", tags=["judge"])

_SCRIPT = [
    {"key": "NORMAL", "title": "Normal conditions", "action": "NONE",
     "narration": {"headline": "A normal delivery day in Hong Kong",
                   "body": "12,482 riders are covered this week. Zone risk is LOW; "
                           "premiums are collected, no triggers are close to firing."}},
    {"key": "EVENT", "title": "Extreme weather arrives", "action": "SIMULATE:EXTREME_FLOOD",
     "narration": {"headline": "95mm of rain hits Mong Kok in 4 hours",
                   "body": "A simulated HKO (Hong Kong Observatory) feed pushes an extreme-rain/flood signal "
                           "into the platform."}},
    {"key": "RISK", "title": "AI risk detection", "action": "NONE",
     "narration": {"headline": "The risk engine scores every zone",
                   "body": "Deterministic additive model: rainfall, flood probability "
                           "and zone history drive the score to SEVERE at the epicenter."}},
    {"key": "EXPOSURE", "title": "Rider exposure", "action": "NONE",
     "narration": {"headline": "Thousands of riders are exposed",
                   "body": "Workers whose home zone fired a trigger are matched with "
                           "their expected income loss."}},
    {"key": "TRIGGER", "title": "Parametric trigger", "action": "NONE",
     "narration": {"headline": "Objective thresholds breach",
                   "body": "Rainfall >= 64.5mm and flood probability >= 75% fire the "
                           "parametric triggers — no adjusters, no paperwork."}},
    {"key": "ELIGIBILITY", "title": "Worker eligibility", "action": "NONE",
     "narration": {"headline": "Active policies are matched",
                   "body": "Riders with an ACTIVE weekly policy become eligible; "
                           "expired policies are excluded with reasons."}},
    {"key": "FRAUD", "title": "Fraud check", "action": "NONE",
     "narration": {"headline": "Anomaly scoring in milliseconds",
                   "body": "Most claims auto-approve; suspicious ones are held for a "
                           "human risk manager — never auto-accused."}},
    {"key": "PAYOUT", "title": "Payout", "action": "NONE",
     "narration": {"headline": "Instant FPS payout (simulated)",
                   "body": "Approved claims pay out immediately with idempotency keys "
                           "guaranteeing no double payment."}},
    {"key": "FINANCE", "title": "Platform financial impact", "action": "NONE",
     "narration": {"headline": "The ledger updates live",
                   "body": "Claims are booked against collected premiums; watch the "
                           "loss ratio move."}},
    {"key": "VIABILITY", "title": "Business viability", "action": "NONE",
     "narration": {"headline": "The model is sustainable",
                   "body": "Premium = expected loss + costs + margin; stress tests show "
                           "the contribution margin under severe scenarios."}},
]


@router.post("/start")
def judge_start(request: Request):
    with deps.write_locked(request) as conn:
        cards = simulation.reset_demo(conn)
        audit_mod.audit(conn, "JUDGE_MODE_STARTED", "platform", simulation.PLATFORM_ID,
                        {"script_steps": len(_SCRIPT)})
        conn.commit()
    request.app.state.last_event_id = None
    request.app.state.last_simulation = None
    return {"status": "ready", "baseline_cards": cards, "script": _SCRIPT}
