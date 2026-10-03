"""Before / after protection comparison, derived from the latest simulation
(or the canonical judge-event assumptions when nothing has been run yet)."""
from fastapi import APIRouter, Request

from backend import config
from backend.engines import analytics_engine, payout_engine, pricing_engine
from backend.routers import deps

router = APIRouter(prefix="/protection", tags=["protection"])


@router.get("/comparison")
def comparison(request: Request):
    conn = deps.get_conn(request)
    sim = getattr(request.app.state, "last_simulation", None)
    week_start = analytics_engine.current_week_start()

    avg_worker = conn.execute(
        "SELECT AVG(worker_contribution) AS w, AVG(platform_subsidy) AS s"
        " FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
    weekly_cost = round(float(avg_worker["w"] or 0.0), 2)
    subsidy = round(float(avg_worker["s"] or 0.0), 2)

    if sim:
        totals = sim["totals"]
        affected = totals["affected_riders"] or 1
        per_rider_loss = round(totals["income_exposure"] / affected, 2)
        per_rider_payout = round(totals["expected_payout"] / max(totals["approved"], 1), 2)
        return {
            "without": {
                "label": "WITHOUT PROTECTION",
                "income_loss_per_rider": per_rider_loss,
                "fleet_income_loss": totals["income_exposure"],
                "platform_support_cost": 0,
                "worker_protection": 0,
            },
            "with": {
                "label": "WITH RIDESHIELD",
                "income_loss_per_rider": per_rider_loss,
                "payout_per_rider": per_rider_payout,
                "net_loss_per_rider": round(per_rider_loss - per_rider_payout, 2),
                "fleet_payout": totals["expected_payout"],
                "weekly_protection_cost_per_rider": weekly_cost,
                "platform_subsidy_per_rider": subsidy,
            },
            "simulated": True,
            "note": "All values derived from the current scenario assumptions.",
        }

    # Baseline: canonical judge-event assumptions for the demo rider.
    j = config.JUDGE_EVENT
    demo = config.DEMO["demo_rider_id"]
    worker_row = conn.execute("SELECT * FROM workers WHERE worker_id = ?", (demo,)).fetchone()
    policy_row = conn.execute(
        "SELECT * FROM policies WHERE worker_id = ? AND week_start = ?",
        (demo, week_start)).fetchone()
    if worker_row and policy_row:
        calc = payout_engine.compute_payout(dict(worker_row), dict(policy_row),
                                            j["duration_h"])
        loss = calc["income_loss"]
        payout = calc["payout_amount"]
    else:
        loss = 0.0
        payout = 0.0
    riders = analytics_engine._rider_count(conn)
    affected_share = max(z["delivery_density"] for z in config.ZONES) / \
        sum(z["delivery_density"] for z in config.ZONES)
    fleet_loss = round(loss * riders * affected_share, 2)
    return {
        "without": {
            "label": "WITHOUT PROTECTION",
            "income_loss_per_rider": loss,
            "fleet_income_loss": fleet_loss,
            "platform_support_cost": 0,
            "worker_protection": 0,
        },
        "with": {
            "label": "WITH RIDESHIELD",
            "income_loss_per_rider": loss,
            "payout_per_rider": payout,
            "net_loss_per_rider": round(loss - payout, 2),
            "fleet_payout": round(payout * riders * affected_share, 2),
            "weekly_protection_cost_per_rider": weekly_cost,
            "platform_subsidy_per_rider": subsidy,
        },
        "simulated": False,
        "note": "All values derived from the current scenario assumptions.",
    }
