"""Deterministic fleet seed. All randomness flows from
random.Random(config.DEMO["random_seed"]) and workers are generated in a fixed
order, so seed(limit=600) yields the exact prefix of the full 12,482-rider
fleet (used by the test-suite for speed)."""
import random
from datetime import date, timedelta

from backend import config
from backend.engines import analytics_engine, pricing_engine
from backend.services import simulation

PLATFORM_ID = "PL-SWIFTDASH"
PLATFORM_NAME = "LionRock Logistics"  # fictional delivery platform

_FIRST_NAMES = [
    "Jason", "Kelvin", "Marco", "Felix", "Hugo", "Oscar", "Ivan", "Derek",
    "Aaron", "Brian", "Calvin", "Dennis", "Eric", "Frank", "Gary", "Henry",
    "Jack", "Kevin", "Leo", "Marcus", "Nathan", "Peter", "Raymond", "Simon",
    "Terry", "Victor", "Wilson", "Andy", "Ben", "Chris", "Daniel", "Edward",
]
# Common HK surname initials (Chan, Cheung, Wong, Lau, Lam, Lee, Ng, Ho, Kwok, ...)
_LAST_INITIALS = list("CCCWWLLLNHKYTFMK")


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def zone_worker_counts(total):
    """Exact per-zone headcounts proportional to delivery_density (largest
    remainder, deterministic tie-break by config zone order)."""
    densities = [z["delivery_density"] for z in config.ZONES]
    dsum = sum(densities)
    raw = [total * d / dsum for d in densities]
    counts = [int(x) for x in raw]
    remainder = total - sum(counts)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - int(raw[i])), i))
    for i in order[:remainder]:
        counts[i] += 1
    return counts


def _generate_workers(rng, total):
    counts = zone_worker_counts(total)
    zone_of = []
    for z, n in zip(config.ZONES, counts):
        zone_of.extend([z["id"]] * n)

    prof = config.WORKER_PROFILE
    plans = list(prof["plan_mix"].items())
    workers = []
    for i in range(1, total + 1):
        worker_id = "W-%06d" % i
        name = "%s %s." % (rng.choice(_FIRST_NAMES), rng.choice(_LAST_INITIALS))
        income = round(_clamp(rng.gauss(prof["weekly_income_mean"], prof["weekly_income_sd"]),
                              prof["weekly_income_min"], prof["weekly_income_max"]), 2)
        hours = round(_clamp(rng.gauss(prof["weekly_hours_mean"], prof["weekly_hours_sd"]),
                             prof["weekly_hours_min"], prof["weekly_hours_max"]), 2)
        tenure = round(_clamp(rng.gauss(prof["tenure_weeks_mean"], prof["tenure_weeks_sd"]),
                              prof["tenure_weeks_min"], prof["tenure_weeks_max"]), 1)
        r = rng.random()
        acc = 0.0
        plan = plans[-1][0]
        for name_p, share in plans:
            acc += share
            if r < acc:
                plan = name_p
                break
        expired = rng.random() < 0.015
        upi = "demo.w%06d@upi (DEMO)" % i
        workers.append({
            "worker_id": worker_id,
            "home_zone_id": zone_of[i - 1],
            "name": name,
            "weekly_income": income,
            "weekly_hours": hours,
            "avg_hourly_income": round(income / hours, 2),
            "tenure_weeks": tenure,
            "fps_handle": upi,
            "plan": plan,
            "expired": expired,
        })

    # The demo rider is pinned so the canonical demo lands on its targets.
    demo = workers[0]
    demo.update({
        "name": "Jason Chan",
        "home_zone_id": "Z-MK",
        "weekly_income": 3360.0,
        "weekly_hours": 42.0,
        "avg_hourly_income": 80.0,
        "tenure_weeks": 78.0,
        "fps_handle": "jason.chan@fps (DEMO)",
        "plan": "STANDARD",
        "expired": False,
    })
    return workers


def seed(conn, limit=None):
    rng = random.Random(config.DEMO["random_seed"])
    total = int(limit) if limit else int(config.DEMO["total_riders"])
    week_start = analytics_engine.current_week_start()
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()

    conn.execute(
        "INSERT OR REPLACE INTO platforms (platform_id, name, city, subsidy_share) VALUES (?,?,?,?)",
        (PLATFORM_ID, PLATFORM_NAME, config.DEMO["city"], config.PRICING["subsidy_share"]),
    )
    conn.executemany(
        "INSERT OR REPLACE INTO zones (zone_id, name, city, base_risk, flood_propensity,"
        " heat_propensity, aqi_propensity, historical_events_per_year, traffic_index,"
        " delivery_density, accessibility, map_x, map_y, map_w, map_h)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(z["id"], z["name"], config.DEMO["city"], z["base_risk"], z["flood_propensity"],
          z["heat_propensity"], z["aqi_propensity"], z["historical_events_per_year"],
          z["traffic_index"], z["delivery_density"], z["accessibility"],
          z["x"], z["y"], z["w"], z["h"]) for z in config.ZONES],
    )

    workers = _generate_workers(rng, total)
    conn.executemany(
        "INSERT OR REPLACE INTO workers (worker_id, platform_id, home_zone_id, name,"
        " weekly_income, weekly_hours, avg_hourly_income, tenure_weeks, fps_handle, active)"
        " VALUES (?,?,?,?,?,?,?,?,?,1)",
        [(w["worker_id"], PLATFORM_ID, w["home_zone_id"], w["name"], w["weekly_income"],
          w["weekly_hours"], w["avg_hourly_income"], w["tenure_weeks"], w["fps_handle"])
         for w in workers],
    )

    conn.executemany(
        "INSERT OR REPLACE INTO policies (policy_id, worker_id, plan, coverage_factor,"
        " max_payout_per_event, weekly_coverage_limit, status, week_start, week_end)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        [("POL-%06d" % (i + 1), w["worker_id"], w["plan"],
          config.COVERAGE_LEVELS[w["plan"]]["coverage_factor"],
          config.COVERAGE_LEVELS[w["plan"]]["max_payout_per_event"],
          config.COVERAGE_LEVELS[w["plan"]]["weekly_coverage_limit"],
          "EXPIRED" if w["expired"] else "ACTIVE", week_start, week_end)
         for i, w in enumerate(workers)],
    )

    # Current-week pricing per rider (batch).
    zones = {z["id"]: z for z in config.ZONES}
    plan_rows = []
    sums = {"gross": 0.0, "el": 0.0, "subsidy": 0.0, "worker": 0.0}
    for w in workers:
        priced = pricing_engine.price(w["avg_hourly_income"], zones[w["home_zone_id"]], w["plan"])
        plan_rows.append((
            "%s:%s" % (w["worker_id"], week_start), w["worker_id"], week_start,
            priced["gross_premium"], priced["breakdown"]["expected_loss"],
            priced["breakdown"]["operating_cost"], priced["breakdown"]["fraud_reserve"],
            priced["breakdown"]["risk_margin"], priced["platform_subsidy"],
            priced["worker_contribution"],
        ))
        sums["gross"] += priced["gross_premium"]
        sums["el"] += priced["breakdown"]["expected_loss"]
        sums["subsidy"] += priced["platform_subsidy"]
        sums["worker"] += priced["worker_contribution"]
    conn.executemany(
        "INSERT OR REPLACE INTO weekly_plans (plan_id, worker_id, week_start, gross_premium,"
        " expected_loss, operating_cost, fraud_reserve, risk_margin, platform_subsidy,"
        " worker_contribution) VALUES (?,?,?,?,?,?,?,?,?,?)",
        plan_rows,
    )

    # Ledger: 11 completed weeks + the live week.
    hist = config.SEEDED_HISTORY
    ledger_rows = []
    for k in range(config.DEMO["ledger_weeks"] - 1, 0, -1):
        ws = (date.fromisoformat(week_start) - timedelta(weeks=k)).isoformat()
        premium = round(sums["gross"] * rng.uniform(0.94, 1.05), 2)
        actual = round(premium * rng.uniform(hist["past_week_loss_ratio_min"],
                                             hist["past_week_loss_ratio_max"]), 2)
        subsidy = round(premium * config.PRICING["subsidy_share"], 2)
        ledger_rows.append((
            "LED-%s" % ws, ws, PLATFORM_ID, total, premium, subsidy,
            round(premium - subsidy, 2),
            round(sums["el"] * rng.uniform(0.94, 1.05), 2), actual,
            round(rng.uniform(8000.0, 22000.0), 2),
        ))
    ledger_rows.append((
        "LED-%s" % week_start, week_start, PLATFORM_ID, total,
        round(sums["gross"], 2), round(sums["subsidy"], 2), round(sums["worker"], 2),
        round(sums["el"], 2), 0.0, hist["fraud_prevented_to_date"],
    ))
    conn.executemany(
        "INSERT OR REPLACE INTO premium_ledger (ledger_id, week_start, platform_id,"
        " riders_covered, premium_collected, platform_subsidy, worker_contribution,"
        " expected_claims, actual_claims, fraud_prevented) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ledger_rows,
    )

    # The earlier-in-the-week event that makes dashboards non-empty at open.
    simulation.pre_demo_event(conn)
    conn.commit()
    return {"workers": total, "week_start": week_start}
