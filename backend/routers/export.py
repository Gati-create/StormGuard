"""CSV exports (summary / payouts / risk)."""
import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import Response

from backend import config
from backend.engines import analytics_engine
from backend.routers import deps

router = APIRouter(prefix="/export", tags=["export"])


def _csv_response(rows, filename):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )


def _latest_event(conn):
    return conn.execute(
        "SELECT * FROM weather_events ORDER BY created_at DESC, event_id DESC LIMIT 1"
    ).fetchone()


@router.get("/summary.csv")
def summary_csv(request: Request):
    conn = deps.get_conn(request)
    rows = [["RideShield scenario summary (fictional demo data)"]]
    ev = _latest_event(conn)
    cards = analytics_engine.fleet_cards(conn)
    if ev is None:
        rows.append(["no events recorded"])
    else:
        rows.append([])
        rows.append(["event_id", "event_type", "zone_id", "rainfall_mm", "duration_h",
                     "data_source", "created_at"])
        rows.append([ev["event_id"], ev["event_type"], ev["zone_id"], ev["rainfall_mm"],
                     ev["duration_h"], ev["data_source"], ev["created_at"]])
        totals = conn.execute(
            "SELECT (SELECT COUNT(*) FROM claims WHERE event_id = ?) AS affected,"
            " (SELECT COUNT(*) FROM claims WHERE event_id = ? AND status = 'PAID') AS paid_claims,"
            " (SELECT COUNT(*) FROM claims WHERE event_id = ? AND status = 'HELD') AS held,"
            " (SELECT COALESCE(SUM(amount), 0) FROM payouts WHERE event_id = ?) AS paid_total",
            (ev["event_id"],) * 4).fetchone()
        rows.append([])
        rows.append(["affected_riders", "paid_claims", "held_claims", "payout_total_inr"])
        rows.append([totals["affected"], totals["paid_claims"], totals["held"],
                     round(float(totals["paid_total"]), 2)])
    rows.append([])
    rows.append(["fleet_card", "value"])
    for key in ("riders_protected", "premium_collected", "claims_paid", "loss_ratio",
                "fraud_prevented"):
        rows.append([key, cards[key]])
    return _csv_response(rows, "rideshield_summary.csv")


@router.get("/payouts.csv")
def payouts_csv(request: Request):
    conn = deps.get_conn(request)
    ev = _latest_event(conn)
    rows = [["payout_id", "claim_id", "worker_id", "event_id", "amount_inr", "method",
             "status", "created_at"]]
    if ev is not None:
        data = conn.execute(
            "SELECT payout_id, claim_id, worker_id, event_id, amount, method, status,"
            " created_at FROM payouts WHERE event_id = ? ORDER BY payout_id",
            (ev["event_id"],)).fetchall()
        for r in data:
            rows.append([r["payout_id"], r["claim_id"], r["worker_id"], r["event_id"],
                         r["amount"], r["method"], r["status"], r["created_at"]])
    return _csv_response(rows, "rideshield_payouts.csv")


@router.get("/risk.csv")
def risk_csv(request: Request):
    conn = deps.get_conn(request)
    rows = [["assessment_id", "zone_id", "zone_name", "risk_score", "risk_level",
             "expected_disruption_hours", "expected_income_loss_inr",
             "expected_payout_inr", "confidence_score", "created_at"]]
    names = {z["id"]: z["name"] for z in config.ZONES}
    for z in config.ZONES:
        r = conn.execute(
            "SELECT * FROM risk_assessments WHERE zone_id = ?"
            " ORDER BY created_at DESC, assessment_id DESC LIMIT 1", (z["id"],)).fetchone()
        if r:
            rows.append([r["assessment_id"], r["zone_id"], names[r["zone_id"]],
                         r["risk_score"], r["risk_level"], r["expected_disruption_hours"],
                         r["expected_income_loss"], r["expected_payout"],
                         r["confidence_score"], r["created_at"]])
    return _csv_response(rows, "rideshield_risk.csv")
