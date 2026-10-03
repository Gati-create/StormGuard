"""Dashboard aggregates + chart series, built from the ledger, claims and
zones tables. Season-level synthetic series are labelled SIMULATED — all data
is fictional demo data."""
import json
import random
from datetime import date, timedelta

from backend import config
from backend.engines import pricing_engine, risk_engine
from backend.services import mock_apis

PLATFORM_ID = "PL-SWIFTDASH"


def current_week_start(today=None):
    today = today or date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def ensure_current_ledger(conn):
    week = current_week_start()
    conn.execute(
        "INSERT OR IGNORE INTO premium_ledger (ledger_id, week_start, platform_id,"
        " riders_covered, premium_collected, platform_subsidy, worker_contribution,"
        " expected_claims, actual_claims, fraud_prevented)"
        " VALUES (?,?,?,?,0,0,0,0,0,0)",
        ("LED-%s" % week, week, PLATFORM_ID, _rider_count(conn)),
    )


def current_ledger(conn):
    row = conn.execute(
        "SELECT * FROM premium_ledger WHERE week_start = ? AND platform_id = ?",
        (current_week_start(), PLATFORM_ID),
    ).fetchone()
    return dict(row) if row else None


def _rider_count(conn):
    return int(conn.execute("SELECT COUNT(*) AS c FROM workers").fetchone()["c"])


# ---------------------------------------------------------------------------
# Cards & zone summaries
# ---------------------------------------------------------------------------

def fleet_cards(conn):
    ledger = current_ledger(conn)
    riders = _rider_count(conn)
    premium = ledger["premium_collected"] if ledger else 0.0
    actual = ledger["actual_claims"] if ledger else 0.0
    return {
        "riders_protected": riders,
        "premium_collected": round(premium, 2),
        "claims_paid": round(actual, 2),
        "loss_ratio": round(actual / premium, 4) if premium else 0.0,
        "fraud_prevented": round(ledger["fraud_prevented"], 2) if ledger else 0.0,
    }


def ambient_assessment(zone):
    """Current ambient risk of a zone from the (deterministic) mock weather feed."""
    weather = mock_apis.weather_current(zone["id"])["weather"]
    return risk_engine.assess(weather, zone, hazard="ambient"), weather


def zone_summaries(conn, event_id=None):
    """ZoneSummary list for the city map. With an event_id the summaries are
    post-event (risk/triggers/claims from that event); otherwise ambient."""
    rider_rows = conn.execute(
        "SELECT home_zone_id AS z, COUNT(*) AS n FROM workers GROUP BY home_zone_id"
    ).fetchall()
    riders = {r["z"]: int(r["n"]) for r in rider_rows}

    per_zone = {}
    if event_id:
        for r in conn.execute(
                "SELECT * FROM risk_assessments WHERE event_id = ?", (event_id,)).fetchall():
            per_zone[r["zone_id"]] = dict(r)
        trig_rows = conn.execute(
            "SELECT zone_id, trigger_type FROM triggers WHERE event_id = ? AND fired = 1",
            (event_id,),
        ).fetchall()
        triggers = {}
        for t in trig_rows:
            triggers.setdefault(t["zone_id"], []).append(t["trigger_type"])
        aff_rows = conn.execute(
            "SELECT zone_id, COUNT(*) AS n FROM claims WHERE event_id = ? GROUP BY zone_id",
            (event_id,)).fetchall()
        affected = {r["zone_id"]: int(r["n"]) for r in aff_rows}
        expo_rows = conn.execute(
            "SELECT c.zone_id AS z, SUM(w.avg_hourly_income) AS s"
            " FROM claims c JOIN workers w ON w.worker_id = c.worker_id"
            " WHERE c.event_id = ? GROUP BY c.zone_id", (event_id,)).fetchall()
        pay_rows = conn.execute(
            "SELECT c.zone_id AS z, SUM(p.amount) AS s"
            " FROM payouts p JOIN claims c ON c.claim_id = p.claim_id"
            " WHERE p.event_id = ? GROUP BY c.zone_id", (event_id,)).fetchall()
        payouts = {r["z"]: round(float(r["s"] or 0.0), 2) for r in pay_rows}
        ev = conn.execute("SELECT * FROM weather_events WHERE event_id = ?",
                          (event_id,)).fetchone()
        mult = config.DISRUPTION["hours_multiplier"]
        exposure = {r["z"]: round(float(r["s"] or 0.0) * ev["duration_h"] * mult, 2)
                    for r in expo_rows}
        att_weather = None
        from backend.services import simulation  # local import avoids a cycle
        hazard = simulation.dominant_hazard(dict(ev))
        att_weather = {z["id"]: simulation.attenuated_weather(z, dict(ev), hazard, ev["zone_id"])
                       for z in config.ZONES}

        out = []
        for z in config.ZONES:
            a = per_zone.get(z["id"])
            w = att_weather[z["id"]]
            out.append({
                "zone_id": z["id"], "name": z["name"], "base_risk": z["base_risk"],
                "risk_score": a["risk_score"] if a else 0,
                "risk_level": a["risk_level"] if a else "LOW",
                "riders": riders.get(z["id"], 0),
                "affected_riders": affected.get(z["id"], 0),
                "rainfall_mm": w["rainfall_mm"],
                "flood_probability": w["flood_probability"],
                "income_exposure": exposure.get(z["id"], 0.0),
                "expected_payout": payouts.get(z["id"], 0.0),
                "active_triggers": triggers.get(z["id"], []),
                "map_x": z["x"], "map_y": z["y"], "map_w": z["w"], "map_h": z["h"],
            })
        return out

    out = []
    for z in config.ZONES:
        a, w = ambient_assessment(z)
        out.append({
            "zone_id": z["id"], "name": z["name"], "base_risk": z["base_risk"],
            "risk_score": a["risk_score"], "risk_level": a["risk_level"],
            "riders": riders.get(z["id"], 0), "affected_riders": 0,
            "rainfall_mm": w["rainfall_mm"], "flood_probability": w["flood_probability"],
            "income_exposure": 0.0, "expected_payout": 0.0, "active_triggers": [],
            "map_x": z["x"], "map_y": z["y"], "map_w": z["w"], "map_h": z["h"],
        })
    return out


def portfolio_risk(conn):
    """Rider-weighted average ambient zone risk score, 0-100."""
    total = 0.0
    n = 0
    rider_rows = conn.execute(
        "SELECT home_zone_id AS z, COUNT(*) AS n FROM workers GROUP BY home_zone_id"
    ).fetchall()
    counts = {r["z"]: int(r["n"]) for r in rider_rows}
    for z in config.ZONES:
        a, _w = ambient_assessment(z)
        total += a["risk_score"] * counts.get(z["id"], 0)
        n += counts.get(z["id"], 0)
    return round(total / n) if n else 0


# ---------------------------------------------------------------------------
# Chart series
# ---------------------------------------------------------------------------

def _week_label(week_start):
    d = date.fromisoformat(week_start)
    return "W%02d" % d.isocalendar()[1]


def loss_ratio_over_time(conn):
    rows = conn.execute(
        "SELECT * FROM premium_ledger WHERE platform_id = ? ORDER BY week_start",
        (PLATFORM_ID,),
    ).fetchall()[-config.DEMO["ledger_weeks"]:]
    out = []
    for r in rows:
        premium = r["premium_collected"]
        out.append({
            "week": _week_label(r["week_start"]),
            "value": round(r["actual_claims"] / premium, 3) if premium else 0.0,
        })
    return out


def premium_vs_claims(conn):
    rows = conn.execute(
        "SELECT * FROM premium_ledger WHERE platform_id = ? ORDER BY week_start",
        (PLATFORM_ID,),
    ).fetchall()[-config.DEMO["ledger_weeks"]:]
    return [{
        "week": _week_label(r["week_start"]),
        "premium": round(r["premium_collected"], 2),
        "claims": round(r["actual_claims"], 2),
    } for r in rows]


def _season_pool(conn):
    """Season-to-date claims pool = actual claims of completed past weeks."""
    week = current_week_start()
    row = conn.execute(
        "SELECT COALESCE(SUM(actual_claims), 0) AS s FROM premium_ledger"
        " WHERE platform_id = ? AND week_start < ?",
        (PLATFORM_ID, week),
    ).fetchone()
    return float(row["s"])


def claims_by_event(conn):
    """Season aggregate by event type (SIMULATED season distribution) plus the
    current week's actual paid claims by event label."""
    rng = random.Random("analytics:claims_by_event")
    shares = [("Extreme Rain / Flood", 0.24), ("Heavy Rain", 0.32),
              ("Extreme Heat", 0.18), ("Severe AQI", 0.16), ("Cyclone", 0.10)]
    pool = _season_pool(conn)
    values = {}
    for label, share in shares:
        values[label] = round(pool * share * rng.uniform(0.9, 1.1), -2)
    week = current_week_start()
    rows = conn.execute(
        "SELECT e.event_type AS t, e.scenario_key AS s, SUM(p.amount) AS v"
        " FROM payouts p JOIN weather_events e ON e.event_id = p.event_id"
        " JOIN claims c ON c.claim_id = p.claim_id"
        " JOIN policies pol ON pol.policy_id = c.policy_id"
        " WHERE pol.week_start = ? GROUP BY e.event_id", (week,),
    ).fetchall()
    for r in rows:
        label = event_label(r["t"], r["s"])
        values[label] = round(values.get(label, 0.0) + float(r["v"] or 0.0), 2)
    return [{"label": k, "value": round(v, 2)} for k, v in values.items()]


def claims_by_zone(conn):
    """Season aggregate by zone (SIMULATED, propensity-weighted) plus actual
    current-week payouts per zone."""
    rng = random.Random("analytics:claims_by_zone")
    rider_rows = conn.execute(
        "SELECT home_zone_id AS z, COUNT(*) AS n FROM workers GROUP BY home_zone_id"
    ).fetchall()
    counts = {r["z"]: int(r["n"]) for r in rider_rows}
    weights = {z["id"]: counts.get(z["id"], 0) * z["base_risk"] for z in config.ZONES}
    wsum = sum(weights.values()) or 1.0
    pool = _season_pool(conn)
    values = {}
    for z in config.ZONES:
        values[z["name"]] = round(pool * weights[z["id"]] / wsum * rng.uniform(0.92, 1.08), -2)
    week = current_week_start()
    rows = conn.execute(
        "SELECT c.zone_id AS z, SUM(p.amount) AS v"
        " FROM payouts p JOIN claims c ON c.claim_id = p.claim_id"
        " JOIN policies pol ON pol.policy_id = c.policy_id"
        " WHERE pol.week_start = ? GROUP BY c.zone_id", (week,),
    ).fetchall()
    names = {z["id"]: z["name"] for z in config.ZONES}
    for r in rows:
        values[names[r["z"]]] = round(values.get(names[r["z"]], 0.0) + float(r["v"] or 0.0), 2)
    return [{"label": k, "value": round(v, 2)} for k, v in values.items()]


def risk_distribution(conn):
    """Headcount of riders by their home zone's current ambient risk level."""
    rider_rows = conn.execute(
        "SELECT home_zone_id AS z, COUNT(*) AS n FROM workers GROUP BY home_zone_id"
    ).fetchall()
    counts = {r["z"]: int(r["n"]) for r in rider_rows}
    dist = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "SEVERE": 0}
    for z in config.ZONES:
        a, _w = ambient_assessment(z)
        dist[a["risk_level"]] += counts.get(z["id"], 0)
    return [{"label": k, "value": v} for k, v in dist.items()]


_PAYOUT_BUCKETS = [(0, 100, "HK$0-100"), (100, 250, "HK$100-250"), (250, 500, "HK$250-500"),
                   (500, 1000, "HK$500-1000"), (1000, None, "HK$1000+")]


def payout_distribution(conn):
    rows = conn.execute("SELECT amount FROM payouts").fetchall()
    counts = {label: 0 for _lo, _hi, label in _PAYOUT_BUCKETS}
    for r in rows:
        amount = float(r["amount"])
        for lo, hi, label in _PAYOUT_BUCKETS:
            if amount >= lo and (hi is None or amount < hi):
                counts[label] += 1
                break
    return [{"bucket": label, "value": counts[label]} for _lo, _hi, label in _PAYOUT_BUCKETS]


def risk_factors_avg(conn):
    """Average factor points across each zone's latest risk assessment."""
    totals = {}
    counts = {}
    for z in config.ZONES:
        row = conn.execute(
            "SELECT risk_factors FROM risk_assessments WHERE zone_id = ?"
            " ORDER BY created_at DESC, assessment_id DESC LIMIT 1", (z["id"],),
        ).fetchone()
        if row:
            factors = json.loads(row["risk_factors"])
        else:
            a, _w = ambient_assessment(z)
            factors = a["risk_factors"]
        for f in factors:
            totals[f["label"]] = totals.get(f["label"], 0.0) + f["points"]
            counts[f["label"]] = counts.get(f["label"], 0) + 1
    return [{"label": k, "points": round(totals[k] / counts[k], 2)}
            for k in sorted(totals, key=lambda k: -totals[k])]


def trigger_counts(conn):
    rows = conn.execute(
        "SELECT trigger_type AS t, COUNT(*) AS n FROM triggers WHERE fired = 1"
        " GROUP BY trigger_type ORDER BY n DESC"
    ).fetchall()
    return [{"label": r["t"], "value": int(r["n"])} for r in rows]


def all_charts(conn):
    return {
        "loss_ratio_over_time": loss_ratio_over_time(conn),
        "premium_vs_claims": premium_vs_claims(conn),
        "claims_by_event": claims_by_event(conn),
        "claims_by_zone": claims_by_zone(conn),
        "risk_distribution": risk_distribution(conn),
        "payout_distribution": payout_distribution(conn),
    }


def event_label(event_type, scenario_key=None):
    if scenario_key and scenario_key in config.SCENARIOS:
        return config.SCENARIOS[scenario_key]["label"]
    if event_type in config.TRIGGERS:
        return config.TRIGGERS[event_type]["label"]
    return "Weather event"
