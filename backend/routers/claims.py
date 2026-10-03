"""Claims & fraud-review endpoints."""
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from backend import config
from backend.engines import analytics_engine, fraud_engine, payout_engine
from backend.models import ReviewRequest
from backend.routers import deps
from backend.services import audit as audit_mod
from backend.services import ids, simulation

router = APIRouter(prefix="/claims", tags=["claims"])

_DECISIONS = ("APPROVED", "REJECTED", "INVESTIGATING")


@router.get("")
def list_claims(request: Request, status: str = None, limit: int = 100):
    conn = deps.get_conn(request)
    limit = max(1, min(limit, 1000))
    sql = ("SELECT claim_id, worker_id, zone_id, payout_amount, status, created_at"
           " FROM claims")
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC, claim_id DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    if rows:
        marks = ",".join("?" for _ in rows)
        scores = {r["claim_id"]: r["fraud_score"] for r in conn.execute(
            "SELECT claim_id, fraud_score FROM fraud_checks WHERE claim_id IN (%s)" % marks,
            [r["claim_id"] for r in rows]).fetchall()}
        for r in rows:
            r["fraud_score"] = scores.get(r["claim_id"], 0)
    counts = {r["status"]: int(r["n"]) for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM claims GROUP BY status").fetchall()}
    return {"claims": rows, "counts": counts}


@router.get("/{claim_id}")
def claim_detail(claim_id: str, request: Request):
    conn = deps.get_conn(request)
    claim = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if claim is None:
        raise HTTPException(status_code=404, detail="Unknown claim %s" % claim_id)
    fc = conn.execute("SELECT * FROM fraud_checks WHERE claim_id = ?", (claim_id,)).fetchone()
    payout = conn.execute("SELECT * FROM payouts WHERE claim_id = ?", (claim_id,)).fetchone()
    trail = conn.execute(
        "SELECT audit_id, event_code, entity_type, entity_id, detail, created_at"
        " FROM audit_events WHERE entity_id = ? ORDER BY created_at", (claim_id,)).fetchall()
    out = dict(claim)
    out["fraud_check"] = _fraud_json(fc) if fc else None
    out["payout"] = dict(payout) if payout else None
    out["audit_trail"] = [dict(t) for t in trail]
    return out


@router.post("/simulate-fraud")
def simulate_fraud(request: Request):
    """Synthesize ONE suspicious claim against the latest event and run it
    through the fraud engine (GPS mismatch + unusual frequency + event-zone
    mismatch = 84 -> HOLD_FOR_REVIEW). A human always decides."""
    with deps.write_locked(request) as conn:
        ev = conn.execute(
            "SELECT * FROM weather_events ORDER BY created_at DESC, event_id DESC LIMIT 1"
        ).fetchone()
        if ev is None:
            # No event yet: create a small synthetic one to attach the claim to.
            result = simulation.run_pipeline(
                conn, zone_id=config.JUDGE_EVENT["zone_id"],
                weather=config.SCENARIOS["SEVERE_RAIN"]["weather"],
                scenario_key="SEVERE_RAIN",
                label=config.SCENARIOS["SEVERE_RAIN"]["label"])
            ev = conn.execute("SELECT * FROM weather_events WHERE event_id = ?",
                              (result["event_id"],)).fetchone()

        week_start = analytics_engine.current_week_start()
        # Deterministically pick a worker with no claim on this event yet.
        candidate = conn.execute(
            "SELECT w.worker_id, w.home_zone_id, p.policy_id FROM workers w"
            " JOIN policies p ON p.worker_id = w.worker_id AND p.week_start = ?"
            " WHERE w.worker_id NOT IN (SELECT worker_id FROM claims WHERE event_id = ?)"
            " ORDER BY w.worker_id LIMIT 1",
            (week_start, ev["event_id"])).fetchone()
        if candidate is None:
            raise HTTPException(status_code=409, detail="No worker available for a new claim")

        claim_id = ids.fmt("CL", ids.next_seq(conn, "claims"))
        key = payout_engine.idempotency_key(candidate["worker_id"], ev["event_id"],
                                            candidate["policy_id"])
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        # Reserve a plausible payout so a REJECTED review releases real funds.
        worker_row = conn.execute("SELECT * FROM workers WHERE worker_id = ?",
                                  (candidate["worker_id"],)).fetchone()
        policy_row = conn.execute("SELECT * FROM policies WHERE policy_id = ?",
                                  (candidate["policy_id"],)).fetchone()
        reserved = payout_engine.compute_payout(dict(worker_row), dict(policy_row),
                                                ev["duration_h"])
        conn.execute(
            "INSERT INTO claims (claim_id, event_id, worker_id, policy_id, zone_id,"
            " eligible, ineligibility_reason, affected_hours, income_loss, payout_amount,"
            " status, idempotency_key, created_at) VALUES (?,?,?,?,?,1,NULL,?,?,?,'HELD',?,?)",
            (claim_id, ev["event_id"], candidate["worker_id"], candidate["policy_id"],
             candidate["home_zone_id"], reserved["affected_hours"],
             reserved["income_loss"], reserved["payout_amount"], key, now),
        )
        scored = fraud_engine.score_claim(fraud_engine.SIMULATED_FRAUD_SIGNALS)
        conn.execute(
            "INSERT INTO fraud_checks (check_id, claim_id, worker_id, event_id, fraud_score,"
            " risk_band, signals, action, review_status, reviewed_by, reviewed_at, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL,?)",
            (ids.fmt("FC", ids.next_seq(conn, "fraud_checks")), claim_id,
             candidate["worker_id"], ev["event_id"], scored["fraud_score"],
             scored["risk_band"], json.dumps(scored["signals"]), scored["action"], now),
        )
        audit_mod.audit(conn, "FRAUD_HOLD", "claim", claim_id, {
            "fraud_score": scored["fraud_score"],
            "signals": [s["signal"] for s in scored["signals"]],
        })
        conn.commit()
    return {
        "claim_id": claim_id,
        "worker_id": candidate["worker_id"],
        "fraud_score": scored["fraud_score"],
        "risk_band": scored["risk_band"],
        "signals": scored["signals"],
        "action": scored["action"],
        "status": "HELD",
        "message": "Payout held. A risk manager must review before any payment.",
    }


@router.post("/{claim_id}/review")
def review_claim(claim_id: str, body: ReviewRequest, request: Request):
    if body.decision not in _DECISIONS:
        raise HTTPException(status_code=400,
                            detail="decision must be one of %s" % ", ".join(_DECISIONS))
    with deps.write_locked(request) as conn:
        claim = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        if claim is None:
            raise HTTPException(status_code=404, detail="Unknown claim %s" % claim_id)
        fc = conn.execute("SELECT * FROM fraud_checks WHERE claim_id = ?", (claim_id,)).fetchone()
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        audit_mod.audit(conn, "MANUAL_REVIEW", "claim", claim_id, {
            "decision": body.decision, "reviewer": body.reviewer,
        })
        conn.execute(
            "UPDATE fraud_checks SET review_status = ?, reviewed_by = ?, reviewed_at = ?"
            " WHERE claim_id = ?",
            (body.decision, body.reviewer, now, claim_id),
        )

        payout_row = None
        if body.decision == "APPROVED":
            if claim["status"] == "PAID":
                payout_row = conn.execute(
                    "SELECT * FROM payouts WHERE claim_id = ?", (claim_id,)).fetchone()
            else:
                if claim["status"] == "REJECTED":
                    raise HTTPException(status_code=409, detail="Claim was rejected; reopen before approving")
                policy = conn.execute("SELECT * FROM policies WHERE policy_id = ?",
                                      (claim["policy_id"],)).fetchone()
                week_paid = payout_engine.weekly_paid_totals(
                    conn, policy["week_start"]).get(claim["worker_id"], 0.0)
                calc = payout_engine.finalize_payout(
                    claim["income_loss"] if claim["income_loss"] > 0 else _default_loss(conn, claim),
                    policy, week_paid)
                amount = calc["payout_amount"]
                conn.execute("UPDATE claims SET status = 'PAID', payout_amount = ?"
                             " WHERE claim_id = ?", (amount, claim_id))
                existing = conn.execute(
                    "SELECT 1 FROM payouts WHERE idempotency_key = ?",
                    (claim["idempotency_key"],)).fetchone()
                payout_row = payout_engine.persist_payout(
                    conn, ids.fmt("PO", ids.next_seq(conn, "payouts")),
                    dict(claim), amount)
                audit_mod.audit(conn, "PAYOUT_APPROVED", "claim", claim_id,
                                {"amount": amount, "reviewer": body.reviewer})
                audit_mod.audit(conn, "PAYOUT_SENT", "claim", claim_id,
                                {"amount": amount, "method": "FPS (SIMULATED)",
                                 "reference": payout_row["payout_id"]})
                if existing is None:
                    # Only a genuinely new payout hits the ledger (idempotent).
                    analytics_engine.ensure_current_ledger(conn)
                    conn.execute(
                        "UPDATE premium_ledger SET actual_claims = ROUND(actual_claims + ?, 2)"
                        " WHERE week_start = ? AND platform_id = ?",
                        (amount, analytics_engine.current_week_start(), simulation.PLATFORM_ID))
                payout_row = conn.execute(
                    "SELECT * FROM payouts WHERE claim_id = ?", (claim_id,)).fetchone()
        elif body.decision == "REJECTED":
            if claim["status"] == "PAID":
                raise HTTPException(status_code=409, detail="Claim already paid; cannot reject")
            if claim["status"] != "REJECTED":
                conn.execute("UPDATE claims SET status = 'REJECTED' WHERE claim_id = ?",
                             (claim_id,))
                analytics_engine.ensure_current_ledger(conn)
                conn.execute(
                    "UPDATE premium_ledger SET fraud_prevented = ROUND(fraud_prevented + ?, 2)"
                    " WHERE week_start = ? AND platform_id = ?",
                    (claim["payout_amount"], analytics_engine.current_week_start(),
                     simulation.PLATFORM_ID))
        else:  # INVESTIGATING
            if claim["status"] not in ("HELD", "PENDING"):
                raise HTTPException(status_code=409,
                                    detail="Only a held claim can move to investigation")
        conn.commit()

    return claim_detail(claim_id, request)


def _default_loss(conn, claim):
    """Income loss for a synthesized claim that has none stored (uses the
    zone-average event disruption for its event)."""
    ev = conn.execute("SELECT * FROM weather_events WHERE event_id = ?",
                      (claim["event_id"],)).fetchone()
    worker = conn.execute("SELECT * FROM workers WHERE worker_id = ?",
                          (claim["worker_id"],)).fetchone()
    if not ev or not worker:
        return 0.0
    calc = payout_engine.compute_payout(dict(worker), {"coverage_factor": 1.0,
                                        "max_payout_per_event": 10 ** 9,
                                        "weekly_coverage_limit": 10 ** 9},
                                        ev["duration_h"])
    return calc["income_loss"]


def _fraud_json(fc):
    return {
        "check_id": fc["check_id"],
        "fraud_score": fc["fraud_score"],
        "risk_band": fc["risk_band"],
        "signals": json.loads(fc["signals"]),
        "action": fc["action"],
        "review_status": fc["review_status"],
        "reviewed_by": fc["reviewed_by"],
        "reviewed_at": fc["reviewed_at"],
    }
