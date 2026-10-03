"""Payout computation + idempotent persistence.

affected_hours = min(duration_h x hours_multiplier x scheduled_overlap, cap)
income_loss    = avg_hourly_income x affected_hours
payout         = income_loss x coverage_factor, clamped to
                 [min_payout (when > 0), plan.max_payout_per_event] and to the
                 rider's remaining weekly coverage limit.
"""
import hashlib

from backend import config


def scheduled_overlap(worker_id):
    """Deterministic per-rider share of the disruption window actually worked.
    The demo rider was on shift for the full window (config override)."""
    d = config.DISRUPTION
    if worker_id == config.DEMO["demo_rider_id"]:
        return d["demo_rider_overlap"]
    digest = hashlib.sha256(("overlap:%s" % worker_id).encode("utf-8")).hexdigest()
    u = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
    return round(d["overlap_min"] + u * (d["overlap_max"] - d["overlap_min"]), 4)


def compute_payout(worker, policy, duration_h, weekly_paid=0.0, coverage_override=None):
    d = config.DISRUPTION
    overlap = scheduled_overlap(worker["worker_id"])
    affected_hours = min(duration_h * d["hours_multiplier"] * overlap, d["max_disruption_hours"])
    income_loss = round(worker["avg_hourly_income"] * affected_hours, 2)
    return finalize_payout(
        income_loss, policy, weekly_paid,
        coverage_factor=coverage_override if coverage_override is not None else policy["coverage_factor"],
        affected_hours=round(affected_hours, 4), overlap=overlap,
    )


def finalize_payout(income_loss, policy, weekly_paid=0.0, coverage_factor=None,
                    affected_hours=0.0, overlap=0.0):
    """Apply plan caps and the weekly coverage limit to a gross income loss."""
    cf = policy["coverage_factor"] if coverage_factor is None else coverage_factor
    note = None
    payout = income_loss * cf
    payout = min(payout, policy["max_payout_per_event"])
    remaining = max(0.0, policy["weekly_coverage_limit"] - weekly_paid)
    if payout > remaining:
        payout = remaining
        note = "WEEKLY_COVERAGE_LIMIT_REACHED"
    if 0.0 < payout < config.PAYOUT["min_payout"]:
        payout = config.PAYOUT["min_payout"]
    payout = round(payout / config.PAYOUT["rounding"]) * config.PAYOUT["rounding"]
    return {
        "affected_hours": affected_hours,
        "overlap": overlap,
        "income_loss": round(income_loss, 2),
        "payout_amount": round(payout, 2),
        "note": note,
    }


def idempotency_key(worker_id, event_id, policy_id):
    return "%s:%s:%s" % (worker_id, event_id, policy_id)


def weekly_paid_totals(conn, week_start):
    """worker_id -> payouts already paid this policy week (for limit checks)."""
    rows = conn.execute(
        "SELECT p.worker_id AS worker_id, COALESCE(SUM(p.amount), 0) AS paid"
        " FROM payouts p"
        " JOIN claims c ON c.claim_id = p.claim_id"
        " JOIN policies pol ON pol.policy_id = c.policy_id"
        " WHERE pol.week_start = ?"
        " GROUP BY p.worker_id",
        (week_start,),
    ).fetchall()
    return {r["worker_id"]: float(r["paid"]) for r in rows}


def persist_payout(conn, payout_id, claim, amount, created_at=None):
    """INSERT OR IGNORE on the idempotency key; a duplicate attempt is a no-op
    returning the existing payout row (never a second row)."""
    key = claim["idempotency_key"]
    conn.execute(
        "INSERT OR IGNORE INTO payouts"
        " (payout_id, claim_id, worker_id, event_id, amount, method, status, idempotency_key, created_at)"
        " VALUES (?,?,?,?,?, 'FPS (SIMULATED)', 'SENT', ?, COALESCE(?, datetime('now')))",
        (payout_id, claim["claim_id"], claim["worker_id"], claim["event_id"],
         round(amount, 2), key, created_at),
    )
    row = conn.execute("SELECT * FROM payouts WHERE idempotency_key = ?", (key,)).fetchone()
    return dict(row)
