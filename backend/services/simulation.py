"""The 9-stage parametric pipeline behind POST /api/simulate.

Stages: WEATHER -> RISK -> EXPOSURE -> TRIGGER -> ELIGIBILITY -> FRAUD ->
APPROVAL -> PAYOUT -> FINANCE. Everything is computed synchronously inside one
transaction; callers commit on success / roll back on error.
"""
import json
import time
from datetime import datetime, timedelta

from backend import config
from backend.engines import (analytics_engine, eligibility_engine, fraud_engine,
                             payout_engine, risk_engine, trigger_engine)
from backend.services import audit as audit_mod
from backend.services import ids, mock_apis

WEATHER_KEYS = [
    "rainfall_mm", "rainfall_intensity", "temperature_c", "humidity",
    "wind_speed_kmh", "aqi", "flood_probability", "cyclone_probability",
    "duration_h", "platform_availability_pct", "zone_closure",
]

PLATFORM_ID = "PL-SWIFTDASH"

_AMBIENT = config.SCENARIOS["NORMAL_DAY"]["weather"]


def complete_weather(partial):
    """Fill any missing weather keys with ambient (normal-day) defaults."""
    w = dict(_AMBIENT)
    for k in WEATHER_KEYS:
        if partial.get(k) is not None:
            w[k] = partial[k]
    w["zone_closure"] = bool(w.get("zone_closure"))
    return w


def dominant_hazard(weather):
    """Which hazard family drives attenuation / zone-history for this signal."""
    t = config.TRIGGERS
    heat_span = t["EXTREME_HEAT"]["params"]["temperature_c"][1] - risk_engine.HEAT_ZERO_C
    ratios = {
        "rain": max(
            weather["rainfall_mm"] / t["HEAVY_RAIN"]["params"]["rainfall_mm"][1],
            weather["rainfall_mm"] / t["EXTREME_RAIN_FLOOD"]["params"]["rainfall_mm"][1],
            weather["flood_probability"] / t["EXTREME_RAIN_FLOOD"]["params"]["flood_probability"][1],
        ),
        "heat": max(0.0, weather["temperature_c"] - risk_engine.HEAT_ZERO_C) / heat_span,
        "aqi": weather["aqi"] / t["SEVERE_AQI"]["params"]["aqi"][1],
        "wind": max(
            weather["wind_speed_kmh"] / t["CYCLONE"]["params"]["wind_speed_kmh"][1],
            weather["cyclone_probability"] / t["CYCLONE"]["params"]["cyclone_probability"][1],
        ),
    }
    kind = max(ratios, key=lambda k: ratios[k])
    if ratios[kind] < 0.5 and (weather.get("zone_closure")
                               or weather["platform_availability_pct"]
                               < t["PLATFORM_OUTAGE"]["params"]["platform_availability_pct"][1]):
        return "outage"
    return kind


def attenuation_for(zone, hazard):
    """Epicenter is 1.0; other zones scale by their event-relevant propensity
    bucketed via config.ZONE_ATTENUATION. Outages/closures apply city-wide."""
    if hazard in ("outage", "closure"):
        return 1.0
    prop_key = risk_engine.HAZARD_PROPENSITY.get(hazard) or "flood_propensity"
    prop = zone[prop_key]
    for threshold, attenuation in config.ZONE_ATTENUATION:
        if prop >= threshold:
            return attenuation
    return config.ZONE_ATTENUATION[-1][1]


def attenuated_weather(zone, epicenter_weather, hazard, epicenter_zone_id):
    if zone["id"] == epicenter_zone_id:
        return dict(epicenter_weather)
    att = attenuation_for(zone, hazard)
    w = dict(epicenter_weather)
    w["rainfall_mm"] = round(w["rainfall_mm"] * att, 2)
    w["rainfall_intensity"] = round(w["rainfall_intensity"] * att, 2)
    w["flood_probability"] = round(w["flood_probability"] * att, 4)
    w["cyclone_probability"] = round(w["cyclone_probability"] * att, 4)
    w["wind_speed_kmh"] = round(w["wind_speed_kmh"] * att, 2)
    w["aqi"] = round(w["aqi"] * att, 1)
    w["temperature_c"] = round(w["temperature_c"] - (1.0 - att) * 3.0, 2)
    # Booleans / platform availability / duration apply city-wide, unchanged.
    return w


def run_pipeline(conn, zone_id, weather, scenario_key=None, label=None,
                 data_source="SIMULATED", overrides=None, created_at=None):
    t0 = time.perf_counter()
    overrides = overrides or {}
    zones = {z["id"]: z for z in config.ZONES}
    epicenter = zones[zone_id]
    weather = complete_weather(weather)
    created_at = created_at or (datetime.utcnow().isoformat(timespec="seconds") + "Z")
    week_start = analytics_engine.current_week_start()
    stages = []

    hazard = dominant_hazard(weather)
    att_weather = {z["id"]: attenuated_weather(z, weather, hazard, zone_id)
                   for z in config.ZONES}
    evaluations = {zid: trigger_engine.evaluate(w) for zid, w in att_weather.items()}
    event_type = trigger_engine.event_type_for(evaluations[zone_id])
    if label is None:
        label = config.TRIGGERS[event_type]["label"] if event_type in config.TRIGGERS else "Weather event"

    # -- 1. WEATHER ---------------------------------------------------------
    event_id = ids.next_event_id(conn, created_at[:10].replace("-", ""))
    conn.execute(
        "INSERT INTO weather_events (event_id, event_type, scenario_key, city, zone_id,"
        " rainfall_mm, rainfall_intensity, temperature_c, humidity, wind_speed_kmh, aqi,"
        " flood_probability, cyclone_probability, duration_h, platform_availability_pct,"
        " zone_closure, data_source, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, event_type, scenario_key, config.DEMO["city"], zone_id,
         weather["rainfall_mm"], weather["rainfall_intensity"], weather["temperature_c"],
         weather["humidity"], weather["wind_speed_kmh"], weather["aqi"],
         weather["flood_probability"], weather["cyclone_probability"], weather["duration_h"],
         weather["platform_availability_pct"], 1 if weather["zone_closure"] else 0,
         data_source, created_at),
    )
    audit_mod.audit(conn, "WEATHER_RECEIVED", "event", event_id, {
        "zone_id": zone_id, "event_type": event_type, "data_source": data_source,
        "rainfall_mm": weather["rainfall_mm"], "duration_h": weather["duration_h"],
    }, created_at)
    stages.append(_stage(
        "WEATHER", "Weather event received",
        "%s • %s • %gmm in %gh • flood probability %g%%" % (
            label, epicenter["name"], weather["rainfall_mm"],
            weather["duration_h"], weather["flood_probability"] * 100.0),
        {"event_id": event_id, "rainfall_mm": weather["rainfall_mm"],
         "duration_h": weather["duration_h"],
         "flood_probability": weather["flood_probability"],
         "data_source": data_source},
        "Event %s ingested from a %s feed for %s and persisted; the signal is "
        "fanned out to the risk engine for all %d zones." % (
            event_id, data_source, epicenter["name"], len(config.ZONES)),
    ))

    # -- 2. RISK ------------------------------------------------------------
    assessments = {}
    ra_base = ids.next_seq(conn, "risk_assessments")
    ra_rows = []
    for i, z in enumerate(config.ZONES):
        a = risk_engine.assess(att_weather[z["id"]], z, hazard=hazard)
        assessment_id = ids.fmt("RA", ra_base + i)
        assessments[z["id"]] = dict(a, assessment_id=assessment_id)
        ra_rows.append((
            assessment_id, event_id, z["id"], a["risk_score"], a["risk_level"],
            a["expected_disruption_hours"], a["expected_income_loss"],
            a["expected_payout"], a["confidence_score"],
            json.dumps(a["risk_factors"]), a["explanation"],
            a["model_version"], created_at,
        ))
    conn.executemany(
        "INSERT INTO risk_assessments (assessment_id, event_id, zone_id, risk_score,"
        " risk_level, expected_disruption_hours, expected_income_loss, expected_payout,"
        " confidence_score, risk_factors, explanation, model_version, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ra_rows,
    )
    audit_mod.audit(conn, "RISK_CALCULATED", "event", event_id, {
        "zones": len(config.ZONES), "epicenter_score": assessments[zone_id]["risk_score"],
        "model_version": config.RISK_MODEL["version"],
    }, created_at)
    worst = max(assessments.values(), key=lambda a: a["risk_score"])
    calmest = min(assessments.values(), key=lambda a: a["risk_score"])
    epic_assessment = assessments[zone_id]
    stages.append(_stage(
        "RISK", "AI risk assessment",
        "Epicenter risk %d (%s) • %d zones scored" % (
            epic_assessment["risk_score"], epic_assessment["risk_level"], len(config.ZONES)),
        {"epicenter_score": epic_assessment["risk_score"],
         "epicenter_level": epic_assessment["risk_level"],
         "model_version": config.RISK_MODEL["version"],
         "zones_assessed": len(config.ZONES)},
        "Deterministic additive model %s scored every zone on attenuated signals: "
        "highest %s at %d, lowest %s at %d. %s" % (
            config.RISK_MODEL["version"], zones[worst["zone_id"]]["name"],
            worst["risk_score"], zones[calmest["zone_id"]]["name"],
            calmest["risk_score"], epic_assessment["explanation"]),
    ))

    # -- 3. EXPOSURE --------------------------------------------------------
    affected_zone_ids = sorted({zid for zid, evs in evaluations.items()
                                if trigger_engine.fired_types(evs)})
    workers = eligibility_engine.fetch_affected_workers(conn, affected_zone_ids)
    d = config.DISRUPTION
    income_exposure = round(sum(
        w["avg_hourly_income"] * weather["duration_h"] * d["hours_multiplier"]
        for w in workers
    ), 2)
    zone_counts = {zid: 0 for zid in affected_zone_ids}
    for w in workers:
        zone_counts[w["home_zone_id"]] += 1
    stages.append(_stage(
        "EXPOSURE", "Rider exposure computed",
        "%d riders in %d affected zones" % (len(workers), len(affected_zone_ids)),
        {"affected_riders": len(workers), "affected_zones": len(affected_zone_ids),
         "income_exposure": income_exposure},
        ("Affected riders are active workers whose home zone fired >= 1 trigger: %s. "
         "Gross income exposure = sum(avg hourly income) x %gh x %g disruption "
         "multiplier = HK$%s.") % (
            ", ".join("%s %d" % (zones[zid]["name"], n) for zid, n in zone_counts.items())
            or "none", weather["duration_h"], d["hours_multiplier"],
            _inr(income_exposure)),
    ))

    # -- 4. TRIGGER ---------------------------------------------------------
    tr_base = ids.next_seq(conn, "triggers")
    tr_rows = []
    seq = tr_base
    for zid in sorted(evaluations.keys()):
        for ev in evaluations[zid]:
            tr_rows.append((ids.fmt("TR", seq), event_id, zid, ev["trigger_type"],
                            ev["threshold_desc"], ev["observed_value"],
                            1 if ev["fired"] else 0, created_at))
            seq += 1
    conn.executemany(
        "INSERT INTO triggers (trigger_id, event_id, zone_id, trigger_type,"
        " threshold_desc, observed_value, fired, created_at) VALUES (?,?,?,?,?,?,?,?)",
        tr_rows,
    )
    fired_summary = {zid: trigger_engine.fired_types(evs)
                     for zid, evs in evaluations.items() if trigger_engine.fired_types(evs)}
    n_fired = sum(len(v) for v in fired_summary.values())
    audit_mod.audit(conn, "TRIGGER_ACTIVATED", "event", event_id, {
        "fired": n_fired, "zones": fired_summary,
    }, created_at)
    if fired_summary:
        trig_detail = "Fired: %s." % "; ".join(
            "%s [%s]" % (zones[zid]["name"], ", ".join(types))
            for zid, types in fired_summary.items())
        trig_summary = "%d trigger(s) fired across %d zones" % (n_fired, len(fired_summary))
    else:
        trig_detail = ("No parametric trigger satisfied in any zone — all %d rule "
                       "evaluations were below threshold, so the pipeline completes "
                       "with zero payouts." % len(tr_rows))
        trig_summary = "No parametric trigger satisfied"
    stages.append(_stage(
        "TRIGGER", "Parametric trigger evaluation", trig_summary,
        {"evaluated": len(tr_rows), "fired": n_fired,
         "fired_types": sorted({t for v in fired_summary.values() for t in v})},
        trig_detail,
    ))

    # Remaining stages depend on triggers; build empty defaults first.
    eligible_pairs, ineligible = [], []
    claim_rows, claims_by_id = [], {}
    fraud_results, held_ids, approved_ids = {}, [], []
    total_paid = 0.0
    n_paid = 0

    if affected_zone_ids:
        # -- 5. ELIGIBILITY -------------------------------------------------
        policies = eligibility_engine.fetch_policies(
            conn, [w["worker_id"] for w in workers], week_start)
        eligible_pairs, ineligible = eligibility_engine.partition(workers, policies)
        cap = overrides.get("affected_riders")
        if cap is not None:
            eligible_pairs = eligible_pairs[:cap]
        weekly_paid = payout_engine.weekly_paid_totals(conn, week_start)
        cl_base = ids.next_seq(conn, "claims")
        seq = cl_base
        for w, pol in eligible_pairs:
            calc = payout_engine.compute_payout(
                w, pol, weather["duration_h"],
                weekly_paid.get(w["worker_id"], 0.0),
                coverage_override=overrides.get("coverage_factor"))
            claim_id = ids.fmt("CL", seq)
            seq += 1
            key = payout_engine.idempotency_key(w["worker_id"], event_id, pol["policy_id"])
            row = (claim_id, event_id, w["worker_id"], pol["policy_id"],
                   w["home_zone_id"], 1, None, calc["affected_hours"],
                   calc["income_loss"], calc["payout_amount"], "PENDING", key, created_at)
            claim_rows.append(row)
            claims_by_id[claim_id] = dict(zip(
                ("claim_id", "event_id", "worker_id", "policy_id", "zone_id",
                 "eligible", "ineligibility_reason", "affected_hours", "income_loss",
                 "payout_amount", "status", "idempotency_key", "created_at"), row))
        for w, pol, reason in ineligible:
            if pol is None:
                continue  # no policy row to reference; counted but not claimable
            claim_id = ids.fmt("CL", seq)
            seq += 1
            key = payout_engine.idempotency_key(w["worker_id"], event_id, pol["policy_id"])
            claim_rows.append((claim_id, event_id, w["worker_id"], pol["policy_id"],
                               w["home_zone_id"], 0, reason, 0.0, 0.0, 0.0,
                               "INELIGIBLE", key, created_at))
        conn.executemany(
            "INSERT OR IGNORE INTO claims (claim_id, event_id, worker_id, policy_id,"
            " zone_id, eligible, ineligibility_reason, affected_hours, income_loss,"
            " payout_amount, status, idempotency_key, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            claim_rows,
        )
        audit_mod.audit(conn, "WORKER_ELIGIBILITY_CHECKED", "event", event_id, {
            "affected": len(workers), "eligible": len(eligible_pairs),
            "ineligible": len(ineligible),
        }, created_at)

        # -- 6. FRAUD -------------------------------------------------------
        eligible_claim_ids = [c[0] for c in claim_rows if c[5] == 1]
        fraud_results = fraud_engine.bulk_scores(eligible_claim_ids, event_id)
        fc_base = ids.next_seq(conn, "fraud_checks")
        fc_rows = []
        seq = fc_base
        for cid in sorted(eligible_claim_ids):
            fr = fraud_results[cid]
            fc_rows.append((ids.fmt("FC", seq), cid, claims_by_id[cid]["worker_id"],
                            event_id, fr["fraud_score"], fr["risk_band"],
                            json.dumps(fr["signals"]), fr["action"],
                            None, None, None, created_at))
            seq += 1
        conn.executemany(
            "INSERT INTO fraud_checks (check_id, claim_id, worker_id, event_id,"
            " fraud_score, risk_band, signals, action, review_status, reviewed_by,"
            " reviewed_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            fc_rows,
        )
        held_ids = [cid for cid in eligible_claim_ids
                    if fraud_results[cid]["action"] == "HOLD_FOR_REVIEW"]
        approved_ids = [cid for cid in eligible_claim_ids
                        if fraud_results[cid]["action"] == "AUTO_APPROVE"]
        audit_mod.audit(conn, "FRAUD_CHECK_COMPLETED", "event", event_id, {
            "scored": len(eligible_claim_ids), "held": len(held_ids),
        }, created_at)
        if held_ids:
            audit_mod.audit(conn, "FRAUD_HOLD", "event", event_id, {
                "held": len(held_ids),
                "message": "Held claims await human review; no accusation is made.",
            }, created_at)

        # -- 7. APPROVAL ----------------------------------------------------
        if held_ids:
            marks = ",".join("?" for _ in held_ids)
            conn.execute("UPDATE claims SET status = 'HELD' WHERE claim_id IN (%s)" % marks,
                         held_ids)
        if approved_ids:
            marks = ",".join("?" for _ in approved_ids)
            conn.execute("UPDATE claims SET status = 'APPROVED' WHERE claim_id IN (%s)" % marks,
                         approved_ids)
        audit_mod.audit(conn, "CLAIM_APPROVED", "event", event_id, {
            "approved": len(approved_ids),
        }, created_at)

        # -- 8. PAYOUT ------------------------------------------------------
        po_base = ids.next_seq(conn, "payouts")
        po_rows = []
        paid_claim_ids = []
        seq = po_base
        sample_ref = None
        handles = _fps_handles(conn, [claims_by_id[cid]["worker_id"] for cid in approved_ids])
        for cid in approved_ids:
            claim = claims_by_id[cid]
            amount = claim["payout_amount"]
            if amount <= 0:
                continue  # weekly coverage limit reached; claim stays APPROVED
            payment = mock_apis.send_upi_payment(
                {"worker_id": claim["worker_id"],
                 "fps_handle": handles.get(claim["worker_id"], "")}, amount)
            sample_ref = sample_ref or payment["reference"]
            po_rows.append((ids.fmt("PO", seq), cid, claim["worker_id"], event_id,
                            amount, "FPS (SIMULATED)", "SENT",
                            claim["idempotency_key"], created_at))
            paid_claim_ids.append(cid)
            total_paid = round(total_paid + amount, 2)
            seq += 1
        conn.executemany(
            "INSERT OR IGNORE INTO payouts (payout_id, claim_id, worker_id, event_id,"
            " amount, method, status, idempotency_key, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            po_rows,
        )
        n_paid = len(paid_claim_ids)
        if paid_claim_ids:
            marks = ",".join("?" for _ in paid_claim_ids)
            conn.execute("UPDATE claims SET status = 'PAID' WHERE claim_id IN (%s)" % marks,
                         paid_claim_ids)
        audit_mod.audit(conn, "PAYOUT_APPROVED", "event", event_id, {
            "count": n_paid, "total": total_paid,
        }, created_at)
        audit_mod.audit(conn, "PAYOUT_SENT", "event", event_id, {
            "count": n_paid, "total": total_paid, "method": "FPS (SIMULATED)",
            "sample_reference": sample_ref,
        }, created_at)

    stages.append(_stage(
        "ELIGIBILITY", "Worker eligibility checked",
        "%d eligible • %d ineligible of %d affected" % (
            len(eligible_pairs), len(ineligible), len(workers)),
        {"affected": len(workers), "eligible": len(eligible_pairs),
         "ineligible": len(ineligible)},
        ("%d riders matched: home zone in the triggered set, ACTIVE policy for the "
         "current week, no duplicate claim for this event. %d ineligible "
         "(policy expired or missing) receive INELIGIBLE claim records with reasons."
         % (len(eligible_pairs), len(ineligible)))
        if affected_zone_ids else
        "Skipped: no parametric trigger fired, so there is no affected rider set.",
    ))
    stages.append(_stage(
        "FRAUD", "Fraud & abuse screening",
        "%d held for review of %d scored" % (len(held_ids), len(fraud_results)),
        {"scored": len(fraud_results), "held": len(held_ids),
         "hold_threshold": config.FRAUD["hold_threshold"]},
        ("Additive anomaly scoring across %d signals; %.1f%% baseline suspicious "
         "rate. %d claims score >= %d and are HELD for a human risk manager — "
         "the engine never auto-accuses or auto-rejects."
         % (len(config.FRAUD["signals"]), config.FRAUD["base_suspicious_rate"] * 100.0,
            len(held_ids), config.FRAUD["hold_threshold"]))
        if affected_zone_ids else
        "Skipped: no eligible claims to score.",
    ))
    stages.append(_stage(
        "APPROVAL", "Claim approval",
        "%d claims auto-approved" % len(approved_ids),
        {"approved": len(approved_ids), "held": len(held_ids)},
        ("Claims scoring below the fraud hold threshold are auto-approved under the "
         "parametric policy terms — no manual adjustment, no paperwork.")
        if affected_zone_ids else
        "Skipped: nothing to approve.",
    ))
    stages.append(_stage(
        "PAYOUT", "Payout execution",
        "HK$%s sent to %s riders" % (_inr(total_paid), "{:,}".format(n_paid)),
        {"payouts": n_paid, "total_paid": total_paid, "method": "FPS (SIMULATED)"},
        ("Instant FPS push (SIMULATED) of HK$%s across %s approved claims; every "
         "payout carries an idempotency key (worker:event:policy) so a duplicate "
         "run can never pay twice." % (_inr(total_paid), "{:,}".format(n_paid)))
        if affected_zone_ids else
        "Skipped: no approved claims.",
    ))

    # -- 9. FINANCE ---------------------------------------------------------
    analytics_engine.ensure_current_ledger(conn)
    if total_paid:
        conn.execute(
            "UPDATE premium_ledger SET actual_claims = ROUND(actual_claims + ?, 2)"
            " WHERE week_start = ? AND platform_id = ?",
            (total_paid, week_start, PLATFORM_ID),
        )
    ledger = analytics_engine.current_ledger(conn)
    premium = ledger["premium_collected"] if ledger else 0.0
    actual = ledger["actual_claims"] if ledger else 0.0
    loss_ratio_after = round(actual / premium, 4) if premium else 0.0
    loss_ratio_before = round((actual - total_paid) / premium, 4) if premium else 0.0
    stages.append(_stage(
        "FINANCE", "Platform financial impact",
        "Loss ratio %s → %s" % (_pct(loss_ratio_before), _pct(loss_ratio_after)),
        {"premium_collected": round(premium, 2), "claims_paid_week": round(actual, 2),
         "loss_ratio_before": loss_ratio_before, "loss_ratio_after": loss_ratio_after},
        "Week-to-date claims of HK$%s are booked against HK$%s of collected premiums in "
        "the premium ledger; the loss ratio moves from %s to %s."
        % (_inr(actual), _inr(premium), _pct(loss_ratio_before), _pct(loss_ratio_after)),
    ))

    # -- Response assembly ----------------------------------------------------
    zone_summaries = analytics_engine.zone_summaries(conn, event_id=event_id)
    expected_payout_total = total_paid
    avg_payout = round(expected_payout_total / n_paid, 2) if n_paid else 0.0
    sample_claims = _sample_claims(conn, event_id)
    rider_impact = _rider_impact(conn, event_id)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    return {
        "event_id": event_id,
        "scenario_key": scenario_key,
        "stages": stages,
        "assessment": _assessment_payload(epic_assessment, epicenter),
        "zones": zone_summaries,
        "totals": {
            "affected_riders": len(workers),
            "eligible_riders": len(eligible_pairs),
            "approved": len(approved_ids),
            "held": len(held_ids),
            "income_exposure": income_exposure,
            "expected_payout": expected_payout_total,
            "avg_payout": avg_payout,
            "platform_liability": expected_payout_total,
            "loss_ratio_after": loss_ratio_after,
        },
        "sample_claims": sample_claims,
        "rider_impact": rider_impact,
        "fleet_cards": analytics_engine.fleet_cards(conn),
        "elapsed_ms": elapsed_ms,
    }


def _stage(key, title, summary, metrics, detail):
    return {"key": key, "title": title, "status": "DONE",
            "summary": summary, "metrics": metrics, "detail": detail}


def _inr(amount):
    if amount >= 1e6:
        return "%.2fM" % (amount / 1e6)
    if amount >= 1e4:
        return "%.1fK" % (amount / 1e3)
    return "{:,.0f}".format(amount)


def _pct(ratio):
    return "{:.1f}%".format(ratio * 100.0)


def _fps_handles(conn, worker_ids):
    if not worker_ids:
        return {}
    marks = ",".join("?" for _ in worker_ids)
    rows = conn.execute(
        "SELECT worker_id, fps_handle FROM workers WHERE worker_id IN (%s)" % marks,
        list(worker_ids),
    ).fetchall()
    return {r["worker_id"]: r["fps_handle"] for r in rows}


def _assessment_payload(a, zone):
    return {
        "assessment_id": a.get("assessment_id"),
        "zone_id": a["zone_id"],
        "zone_name": zone["name"],
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


def _sample_claims(conn, event_id, limit=50):
    # fraud_scores are fetched separately: joining on fraud_checks.claim_id
    # would be an unindexed nested scan over large events.
    rows = conn.execute(
        "SELECT claim_id, worker_id, payout_amount, status FROM claims"
        " WHERE event_id = ? ORDER BY claim_id LIMIT ?",
        (event_id, limit),
    ).fetchall()
    scores = {r["claim_id"]: r["fraud_score"] for r in conn.execute(
        "SELECT claim_id, fraud_score FROM fraud_checks WHERE event_id = ?",
        (event_id,)).fetchall()}
    return [dict(r, fraud_score=scores.get(r["claim_id"], 0)) for r in rows]


def _rider_impact(conn, event_id):
    demo = config.DEMO["demo_rider_id"]
    row = conn.execute(
        "SELECT * FROM claims WHERE event_id = ? AND worker_id = ? AND eligible = 1",
        (event_id, demo),
    ).fetchone()
    if not row:
        return None
    payout = row["payout_amount"] if row["status"] == "PAID" else 0.0
    label = ("HK$%g credited to FPS — DEMO / SIMULATED" % payout) if payout else "No payout due"
    return {
        "worker_id": demo,
        "estimated_income_loss": row["income_loss"],
        "protection_payout": payout,
        "status": row["status"],
        "payment_label": label,
    }


def pre_demo_event(conn):
    """Replays the seeded earlier-in-the-week Mong Kok rainstorm event through the same
    pipeline, then resolves its held claims as reviewed-rejected so their value
    counts toward the fraud-prevented ledger figure."""
    ev = config.SEEDED_HISTORY["pre_demo_event"]
    created = (datetime.utcnow() - timedelta(days=ev["days_ago"])).isoformat(timespec="seconds") + "Z"
    weather = {k: ev[k] for k in WEATHER_KEYS}
    result = run_pipeline(conn, zone_id=ev["zone_id"], weather=weather,
                          scenario_key=None, label=ev["label"],
                          data_source="SIMULATED", created_at=created)
    held = conn.execute(
        "SELECT claim_id, payout_amount FROM claims WHERE event_id = ? AND status = 'HELD'",
        (result["event_id"],),
    ).fetchall()
    prevented = 0.0
    for h in held:
        conn.execute("UPDATE claims SET status = 'REJECTED' WHERE claim_id = ?",
                     (h["claim_id"],))
        conn.execute(
            "UPDATE fraud_checks SET review_status = 'REJECTED', reviewed_by = ?,"
            " reviewed_at = ? WHERE claim_id = ?",
            ("Risk Manager", created, h["claim_id"]),
        )
        prevented += h["payout_amount"]
    analytics_engine.ensure_current_ledger(conn)
    conn.execute(
        "UPDATE premium_ledger SET fraud_prevented = ROUND(fraud_prevented + ?, 2)"
        " WHERE week_start = ? AND platform_id = ?",
        (round(prevented, 2), analytics_engine.current_week_start(), PLATFORM_ID),
    )
    return result


def reset_demo(conn):
    """Restore the deterministic baseline: clear all run tables, re-run the
    pre-demo event, and put the current-week ledger back to baseline."""
    # Children first — triggers/claims/payouts reference weather_events.
    for table in ("payouts", "fraud_checks", "claims", "triggers",
                  "risk_assessments", "audit_events", "weather_events"):
        conn.execute("DELETE FROM %s" % table)
    analytics_engine.ensure_current_ledger(conn)
    conn.execute(
        "UPDATE premium_ledger SET actual_claims = 0, fraud_prevented = ?"
        " WHERE week_start = ? AND platform_id = ?",
        (config.SEEDED_HISTORY["fraud_prevented_to_date"],
         analytics_engine.current_week_start(), PLATFORM_ID),
    )
    pre_demo_event(conn)
    audit_mod.audit(conn, "DEMO_RESET", "platform", PLATFORM_ID,
                    {"restored": "deterministic baseline"})
    return analytics_engine.fleet_cards(conn)
