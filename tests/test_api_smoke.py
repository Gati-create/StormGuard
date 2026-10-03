"""End-to-end API smoke tests over the small (600-rider) test fleet."""
import os

import pytest

from backend import config


# -- meta -------------------------------------------------------------------

def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_config_and_model_card(client):
    cfg = client.get("/api/config").json()
    assert cfg["triggers"]["HEAVY_RAIN"]["params"]["rainfall_mm"] == [">=", 64.5]
    assert cfg["season"] == config.DEMO["season"]
    card = client.get("/api/model/card").json()
    assert card["architecture"] == ["INPUTS", "FEATURE ENGINEERING", "RISK MODEL",
                                    "EXPLAINABILITY", "TRIGGER ENGINE", "PAYOUT ENGINE"]


def test_overview_and_fleet(client):
    ov = client.get("/api/overview").json()
    assert ov["status"] == "SYSTEM OPERATIONAL"
    assert ov["cards"]["riders"] == 600
    assert len(ov["map_zones"]) == 10
    assert ov["pipeline"] == {"trigger": False, "eligibility": False,
                              "fraud": False, "payout": False}

    dash = client.get("/api/fleet/dashboard").json()
    for key in ("riders_protected", "premium_collected", "claims_paid", "loss_ratio",
                "fraud_prevented"):
        assert key in dash["cards"]
    assert dash["cards"]["premium_collected"] > 0
    assert set(dash["exposure_by_plan"]) == {"BASIC", "STANDARD", "PLUS"}

    zones = client.get("/api/fleet/zones").json()["zones"]
    assert len(zones) == 10
    detail = client.get("/api/fleet/zones/Z-MK").json()
    assert detail["name"] == "Mong Kok"
    assert len(detail["top_risk_factors"]) == 3
    assert client.get("/api/fleet/zones/Z-NOPE").status_code == 404


def test_rider_dashboard_baseline(client):
    r = client.get("/api/riders/W-000001/dashboard").json()
    assert r["worker"]["name"] == "Jason Chan"
    assert r["worker"]["zone_name"] == "Mong Kok"
    assert r["weekly_income"] == 3360.0
    assert r["protected_income"] == 2688.0
    assert r["plan"] == "STANDARD"
    assert r["coverage_status"] == "ACTIVE"
    assert client.get("/api/riders/W-999999/dashboard").status_code == 404


# -- pricing -----------------------------------------------------------------

def test_pricing_plans_and_quote(client):
    r = client.get("/api/pricing/plans?zone_id=Z-MK&weekly_income=3360&weekly_hours=42").json()
    assert [p["plan"] for p in r["plans"]] == ["BASIC", "STANDARD", "PLUS"]
    std = r["plans"][1]
    assert 180 <= std["gross_premium"] <= 290
    assert std["worker_contribution"] == 43.75

    q = client.post("/api/pricing/quote", json={
        "plan": "STANDARD", "zone_id": "Z-MK", "weekly_income": 3360,
        "weekly_hours": 42}).json()
    assert q["gross_premium"] == std["gross_premium"]
    assert "why" in q and "Expected loss" in q["why"]
    assert client.post("/api/pricing/quote", json={
        "plan": "GOLD", "zone_id": "Z-MK", "weekly_income": 1, "weekly_hours": 1}
    ).status_code == 400


# -- simulation ---------------------------------------------------------------

def _simulate(client, key):
    r = client.post("/api/simulate", json={"scenario_key": key})
    assert r.status_code == 200, r.text
    return r.json()


def test_simulate_normal_day_no_trigger(client):
    res = _simulate(client, "NORMAL_DAY")
    assert [s["key"] for s in res["stages"]] == [
        "WEATHER", "RISK", "EXPOSURE", "TRIGGER", "ELIGIBILITY", "FRAUD",
        "APPROVAL", "PAYOUT", "FINANCE"]
    assert all(s["status"] == "DONE" for s in res["stages"])
    assert res["totals"]["affected_riders"] == 0
    assert res["totals"]["expected_payout"] == 0
    trigger_stage = next(s for s in res["stages"] if s["key"] == "TRIGGER")
    assert "No parametric trigger satisfied" in trigger_stage["summary"]


def test_simulate_extreme_flood_canonical(client):
    res = _simulate(client, "EXTREME_FLOOD")
    assert 85 <= res["assessment"]["risk_score"] <= 95
    t = res["totals"]
    assert t["affected_riders"] == 151            # Z-MK (81) + Z-SSP (70) spillover
    assert t["eligible_riders"] <= t["affected_riders"]
    assert t["approved"] + t["held"] == t["eligible_riders"]
    assert t["expected_payout"] > 0
    assert res["rider_impact"]["estimated_income_loss"] == 496.0
    assert res["rider_impact"]["protection_payout"] == 397.0
    assert len(res["zones"]) == 10
    assert len(res["sample_claims"]) <= 50
    assert res["fleet_cards"]["claims_paid"] > 0
    assert res["elapsed_ms"] < 2500

    kor = next(z for z in res["zones"] if z["zone_id"] == "Z-MK")
    assert "EXTREME_RAIN_FLOOD" in kor["active_triggers"]
    mal = next(z for z in res["zones"] if z["zone_id"] == "Z-CEN")
    assert mal["affected_riders"] == 0


def test_simulate_black_swan_multi_trigger(client):
    res = _simulate(client, "BLACK_SWAN")
    trigger_stage = next(s for s in res["stages"] if s["key"] == "TRIGGER")
    fired = set(trigger_stage["metrics"]["fired_types"])
    for expected in ("EXTREME_RAIN_FLOOD", "CYCLONE", "ZONE_CLOSURE", "PLATFORM_OUTAGE"):
        assert expected in fired
    # Zone closure + outage apply city-wide: the whole fleet is affected.
    assert res["totals"]["affected_riders"] == 600


def test_events_list(client):
    _simulate(client, "EXTREME_FLOOD")
    events = client.get("/api/events").json()["events"]
    assert len(events) >= 2                       # pre-demo + this one
    assert events[0]["created_at"] >= events[-1]["created_at"]
    assert "totals" in events[0]


# -- rider after event ---------------------------------------------------------

def test_rider_dashboard_after_event(client):
    _simulate(client, "EXTREME_FLOOD")
    r = client.get("/api/riders/W-000001/dashboard").json()
    assert r["latest_event"]["estimated_income_loss"] == 496.0
    assert r["latest_event"]["protection_payout"] == 397.0
    assert r["latest_event"]["status"] == "PAID"
    assert "HK$397 credited to FPS" in r["latest_event"]["payment_label"]
    assert r["recent_payouts"][0]["amount"] == 397.0
    assert r["current_zone_risk"]["risk_score"] >= 85


# -- claims & fraud --------------------------------------------------------------

def test_claims_list_and_detail(client):
    _simulate(client, "EXTREME_FLOOD")
    data = client.get("/api/claims").json()
    assert data["counts"].get("PAID", 0) > 0
    assert data["counts"].get("HELD", 0) >= 1
    held = client.get("/api/claims?status=HELD").json()["claims"]
    assert held and all(c["status"] == "HELD" for c in held)
    detail = client.get("/api/claims/%s" % held[0]["claim_id"]).json()
    assert detail["fraud_check"]["fraud_score"] >= 60
    assert client.get("/api/claims/CL-NOPE").status_code == 404


def test_simulate_fraud_and_review_flow(client):
    _simulate(client, "EXTREME_FLOOD")
    fraud = client.post("/api/claims/simulate-fraud").json()
    assert fraud["fraud_score"] == 84
    assert fraud["risk_band"] == "HIGH"
    assert fraud["action"] == "HOLD_FOR_REVIEW"
    assert fraud["status"] == "HELD"
    assert "risk manager" in fraud["message"].lower()

    cid = fraud["claim_id"]
    cards_before = client.get("/api/fleet/dashboard").json()["cards"]
    approved = client.post("/api/claims/%s/review" % cid,
                           json={"decision": "APPROVED", "reviewer": "Risk Manager"})
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "PAID"
    assert body["payout"] is not None
    payout_id = body["payout"]["payout_id"]
    cards_mid = client.get("/api/fleet/dashboard").json()["cards"]
    assert cards_mid["claims_paid"] > cards_before["claims_paid"]

    # Idempotent re-approve: same payout, no double ledger credit.
    again = client.post("/api/claims/%s/review" % cid,
                        json={"decision": "APPROVED", "reviewer": "Risk Manager"}).json()
    assert again["payout"]["payout_id"] == payout_id
    cards_after = client.get("/api/fleet/dashboard").json()["cards"]
    assert cards_after["claims_paid"] == cards_mid["claims_paid"]


def test_review_reject_releases_funds(client):
    _simulate(client, "EXTREME_FLOOD")
    fraud = client.post("/api/claims/simulate-fraud").json()
    before = client.get("/api/fleet/dashboard").json()["cards"]
    r = client.post("/api/claims/%s/review" % fraud["claim_id"],
                    json={"decision": "REJECTED", "reviewer": "Risk Manager"})
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"
    after = client.get("/api/fleet/dashboard").json()["cards"]
    assert after["fraud_prevented"] > before["fraud_prevented"]


# -- viability -------------------------------------------------------------------

def test_viability_defaults(client):
    r = client.post("/api/viability", json={}).json()
    w = r["weekly"]
    v = config.VIABILITY
    assert w["premium_revenue"] == v["riders"] * v["avg_gross_premium"]
    assert w["expected_claims"] == pytest.approx(
        v["riders"] * v["weekly_event_probability"] * v["avg_payout"], rel=1e-6)
    assert w["loss_ratio"] == pytest.approx(w["expected_claims"] / w["premium_revenue"], rel=1e-3)
    assert r["annual"]["premium_revenue"] == w["premium_revenue"] * v["weeks_per_year"]
    assert r["break_even_riders"] is not None
    assert w["fixed_weekly_cost"] == v["fixed_weekly_cost"]


def test_viability_sensitivity_direction(client):
    base = client.post("/api/viability", json={}).json()["weekly"]["loss_ratio"]
    r = client.post("/api/viability/sensitivity", json={
        "base": {},
        "shocks": [{"key": "weekly_event_probability", "mult": 1.25,
                    "label": "Severe weather +25%"},
                   {"key": "avg_payout", "mult": 1.2, "label": "Avg payout +20%"}],
    }).json()
    assert len(r["results"]) == 2
    assert r["results"][0]["loss_ratio"] > base
    assert r["results"][1]["loss_ratio"] > base


def test_viability_stress(client):
    r = client.get("/api/viability/stress").json()
    assert [s["name"] for s in r["scenarios"]] == list(config.STRESS_SCENARIOS)
    by_name = {s["name"]: s for s in r["scenarios"]}
    assert by_name["EXTREME_WEATHER"]["loss_ratio"] > by_name["BASELINE"]["loss_ratio"]


# -- analytics / protection / audit / export / judge ------------------------------

def test_analytics_summary(client):
    _simulate(client, "EXTREME_FLOOD")
    r = client.get("/api/analytics/summary").json()
    for key in ("loss_ratio_over_time", "premium_vs_claims", "claims_by_event",
                "claims_by_zone", "risk_distribution", "payout_distribution",
                "risk_factors_avg", "trigger_counts"):
        assert key in r
    assert len(r["loss_ratio_over_time"]) == 12
    assert len(r["premium_vs_claims"]) == 12
    assert sum(x["value"] for x in r["risk_distribution"]) == 600
    assert sum(x["value"] for x in r["payout_distribution"]) > 0
    assert any(t["label"] == "EXTREME_RAIN_FLOOD" for t in r["trigger_counts"])


def test_protection_comparison(client):
    before = client.get("/api/protection/comparison").json()
    assert before["without"]["income_loss_per_rider"] == 496.0
    assert before["with"]["payout_per_rider"] == 397.0
    _simulate(client, "EXTREME_FLOOD")
    after = client.get("/api/protection/comparison").json()
    assert after["simulated"] is True
    assert after["with"]["fleet_payout"] > 0


def test_insurer_dashboard(client):
    _simulate(client, "EXTREME_FLOOD")
    r = client.get("/api/insurer/dashboard").json()
    for key in ("portfolio_size", "premium", "claims", "loss_ratio", "risk_reserve",
                "expected_loss", "capital_exposure", "fraud_rate"):
        assert key in r["cards"]
    assert len(r["forecast_7d"]) == 4
    assert len(r["charts"]["loss_ratio_over_time"]) == 12


def test_audit_trail_after_simulate(client):
    res = _simulate(client, "EXTREME_FLOOD")
    entries = client.get("/api/audit").json()["entries"]
    assert entries
    codes = {e["event_code"] for e in entries}
    for expected in ("WEATHER_RECEIVED", "RISK_CALCULATED", "TRIGGER_ACTIVATED",
                     "WORKER_ELIGIBILITY_CHECKED", "FRAUD_CHECK_COMPLETED",
                     "CLAIM_APPROVED", "PAYOUT_APPROVED", "PAYOUT_SENT", "FRAUD_HOLD"):
        assert expected in codes
    assert entries[0]["audit_id"].startswith("AU-")


def test_exports_csv(client):
    _simulate(client, "EXTREME_FLOOD")
    for path in ("summary.csv", "payouts.csv", "risk.csv"):
        r = client.get("/api/export/%s" % path)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert len(r.text.splitlines()) > 1
    assert "PO-" in client.get("/api/export/payouts.csv").text


def test_judge_start(client):
    r = client.post("/api/judge/start").json()
    assert r["status"] == "ready"
    assert r["baseline_cards"]["riders_protected"] == 600
    keys = [s["key"] for s in r["script"]]
    assert keys == ["NORMAL", "EVENT", "RISK", "EXPOSURE", "TRIGGER", "ELIGIBILITY",
                    "FRAUD", "PAYOUT", "FINANCE", "VIABILITY"]
    assert r["script"][1]["action"] == "SIMULATE:EXTREME_FLOOD"


def test_reset_restores_baseline(client):
    baseline = client.get("/api/fleet/dashboard").json()["cards"]
    _simulate(client, "EXTREME_FLOOD")
    _simulate(client, "BLACK_SWAN")
    r = client.post("/api/simulation/reset")
    assert r.status_code == 200
    assert r.json()["status"] == "reset"
    restored = client.get("/api/fleet/dashboard").json()["cards"]
    assert restored == baseline
    ov = client.get("/api/overview").json()
    assert ov["pipeline"] == {"trigger": False, "eligibility": False,
                              "fraud": False, "payout": False}


# -- canonical-size fleet (opt-in; needs RIDESHIELD_FULL=1) ------------------------

@pytest.mark.skipif(os.environ.get("RIDESHIELD_FULL") != "1",
                    reason="canonical 12,482-rider test disabled (set RIDESHIELD_FULL=1)")
def test_canonical_fleet_targets(tmp_path):
    from backend import database
    from backend.seed import seed
    from backend.services import simulation

    conn = database.init_db(str(tmp_path / "canonical.db"))
    seed(conn)
    led = conn.execute("SELECT * FROM premium_ledger ORDER BY week_start DESC LIMIT 1").fetchone()
    assert 2_400_000 <= led["premium_collected"] <= 2_900_000

    res = simulation.run_pipeline(conn, "Z-MK", config.SCENARIOS["EXTREME_FLOOD"]["weather"],
                                  scenario_key="EXTREME_FLOOD", label="Extreme Rain")
    conn.commit()
    assert 85 <= res["assessment"]["risk_score"] <= 95
    assert 3100 <= res["totals"]["affected_riders"] <= 3300
    assert 65 <= res["totals"]["held"] <= 85
    assert res["rider_impact"]["estimated_income_loss"] == 496.0
    assert res["rider_impact"]["protection_payout"] == 397.0
    assert res["elapsed_ms"] < 2500
    conn.close()
