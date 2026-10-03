# RideShield API Contract (single source of truth)

FastAPI backend serves JSON under `/api/*` and serves the static frontend at `/`.
Python 3.9 target. All money in HKD (HK$). All timestamps ISO-8601 UTC.
All responses include `"data_source"` labels where values are fictional/simulated.

Error shape: `{"detail": "human readable message"}` with proper HTTP status.

## Shared shapes

```jsonc
// WeatherSignal (input to simulation & risk)
{
  "rainfall_mm": 95.0, "rainfall_intensity": 26.0, "temperature_c": 25.0,
  "humidity": 97.0, "wind_speed_kmh": 38.0, "aqi": 64.0,
  "flood_probability": 0.82, "cyclone_probability": 0.08,
  "duration_h": 4.0, "platform_availability_pct": 98.8, "zone_closure": false
}

// RiskFactor — explainability atom
{ "label": "Extreme rainfall", "points": 30.4 }

// RiskAssessment
{
  "assessment_id": "RA-...", "zone_id": "Z-MK", "zone_name": "Mong Kok",
  "risk_score": 90, "risk_level": "SEVERE",          // LOW|MODERATE|HIGH|SEVERE
  "expected_disruption_hours": 4.0, "expected_income_loss": 496.0,
  "expected_payout": 397.0, "confidence_score": 0.83,
  "risk_factors": [RiskFactor, ...],
  "explanation": "The risk increased primarily because ...",
  "model_version": "demo-deterministic-1.0"
}

// ZoneSummary (for map + lists)
{
  "zone_id": "Z-MK", "name": "Mong Kok", "base_risk": 0.62,
  "risk_score": 90, "risk_level": "SEVERE",
  "riders": 1685, "affected_riders": 1685,
  "rainfall_mm": 95.0, "flood_probability": 0.82,
  "income_exposure": 905000.0, "expected_payout": 474000.0,
  "active_triggers": ["EXTREME_RAIN_FLOOD"],
  "map_x": 170, "map_y": 170, "map_w": 95, "map_h": 75
}

// PipelineStage — the animated demo timeline. Backend runs the full pipeline
// synchronously; each stage carries real computed output. The frontend animates
// progression (0.5–2 s/stage) using this ordered list.
{
  "key": "WEATHER",                    // WEATHER|RISK|EXPOSURE|TRIGGER|ELIGIBILITY|FRAUD|APPROVAL|PAYOUT|FINANCE
  "title": "Weather event received",
  "status": "DONE",                    // DONE is the only state returned (pipeline completes server-side)
  "summary": "Black Rainstorm • Mong Kok • 95mm in 4h • flood probability 82%",
  "metrics": { "rainfall_mm": 95, "...": "..." },     // small stage-specific dict
  "detail": "One or two sentences of system reasoning shown to judges."
}
```

## Endpoints

### Meta
- `GET /api/health` → `{ "status": "ok" }`
- `GET /api/config` → public view of thresholds/assumptions: `{ brand, disclaimer, triggers: {...}, coverage_levels: {...}, pricing: {...}, risk_model: { version, trained_on_real_data, levels }, scenarios: {...}, season, currency }`
- `GET /api/model/card` → model card: `{ purpose, inputs[], outputs[], training_data_status, limitations[], demo_assumptions[], bias_sources[], human_review_points[], architecture: ["INPUTS","FEATURE ENGINEERING","RISK MODEL","EXPLAINABILITY","TRIGGER ENGINE","PAYOUT ENGINE"] }`

### Overview (central screen)
- `GET /api/overview` →
```jsonc
{
  "status": "SYSTEM OPERATIONAL",
  "cards": { "riders": 12482, "exposed_riders": 0, "exposure": 0, "payout_total": 0, "portfolio_risk": 34 },
  "map_zones": [ZoneSummary, ...],
  "ai_assessment": RiskAssessment | null,     // worst current zone assessment
  "active_event": { "event_id": "...", "label": "Black Rainstorm", "zone_name": "Mong Kok",
                    "rainfall_mm": 95, "flood_probability": 0.82, "event_type": "EXTREME_RAIN_FLOOD" } | null,
  "pipeline": { "trigger": true, "eligibility": true, "fraud": true, "payout": false } // ticks for completed steps of latest run; all false at baseline
}
```

### Fleet / B2B dashboard
- `GET /api/fleet/dashboard` →
```jsonc
{ "cards": { "riders_protected": 12482, "premium_collected": 2632757, "claims_paid": 1360000,
             "loss_ratio": 0.516, "fraud_prevented": 196500 },
  "week_label": "Season to date (12 weeks, simulated)",
  "map_zones": [ZoneSummary, ...],
  "exposure_by_plan": {"BASIC": n, "STANDARD": n, "PLUS": n},
  "projected_next_week_liability": 594000,
  "financials": { "platform_subsidy": ..., "worker_contribution": ..., "expected_claims": ...,
                  "actual_claims": ..., "net_risk_exposure": ... } }
```
- `GET /api/fleet/zones` → `{ "zones": [ZoneSummary, ...] }` (current ambient risk)
- `GET /api/fleet/zones/{zone_id}` → ZoneSummary + `{ "top_risk_factors": [RiskFactor,...], "recent_events": [ {event_id, label, created_at} ] }`

### Rider dashboard (demo rider = config DEMO.demo_rider_id)
- `GET /api/riders/{worker_id}/dashboard` →
```jsonc
{ "worker": { "worker_id": "W-000001", "name": "Jason Chan", "zone_name": "Mong Kok", "fps_handle": "jason.chan@fps (DEMO)" },
  "weekly_income": 3360, "protected_income": 2688, "worker_contribution": 43.75,
  "plan": "STANDARD", "coverage_status": "ACTIVE",
  "current_zone_risk": { "risk_score": 90, "risk_level": "HIGH" },
  "latest_event": null | { "label": "Severe disruption detected", "estimated_income_loss": 496,
        "protection_payout": 397, "status": "PAID",           // PROCESSING while animating client-side
        "payment_label": "HK$397 credited to FPS — DEMO / SIMULATED" },
  "recent_payouts": [ { "payout_id": "...", "amount": 397, "created_at": "...", "event_label": "Black Rainstorm" } ],
  "coverage_history": [ { "week_start": "2026-09-21", "premium": 273, "paid": true } ] }
```

### Insurer / risk-manager dashboard
- `GET /api/insurer/dashboard` →
```jsonc
{ "cards": { "portfolio_size": 12482, "premium": 2632757, "claims": 1360000, "loss_ratio": 0.516,
             "risk_reserve": 394914, "expected_loss": 1291887, "capital_exposure": 6720000, "fraud_rate": 0.023 },
  "forecast_7d": [ { "event_type": "Rainstorm", "probability": 0.42, "expected_payout": 488000 }, ... ], // 4 rows: rainstorm, typhoon, heat, AQI
  "charts": {
     "loss_ratio_over_time": [ {"week": "W27", "value": 0.51}, ... ],       // 12 pts
     "premium_vs_claims": [ {"week": "W27", "premium": 216000, "claims": 112800}, ... ],
     "claims_by_event": [ {"label": "Black Rainstorm", "value": 496000}, ... ],
     "claims_by_zone": [ {"label": "Mong Kok", "value": 384000}, ... ],
     "risk_distribution": [ {"label": "LOW", "value": 3100}, ... ],
     "payout_distribution": [ {"bucket": "HK$0-80", "value": 120}, ... ] }
}
```

### Simulation (the hero)
- `POST /api/simulate`
  body:
```jsonc
{ "zone_id": "Z-MK", "scenario_key": "EXTREME_FLOOD" | null,
  "weather": WeatherSignal,                 // may be partially specified; missing keys fall back to scenario/ambient
  "overrides": { "affected_riders": null|int, "coverage_factor": null|float, "platform_subsidy_share": null|float } }
```
  → response:
```jsonc
{ "event_id": "EV-...", "scenario_key": "EXTREME_FLOOD",
  "stages": [PipelineStage ×9],
  "assessment": RiskAssessment,              // epicenter zone
  "zones": [ZoneSummary, ...],               // post-event zone states (all 10 zones)
  "totals": { "affected_riders": 3148, "eligible_riders": 3104, "approved": 3033, "held": 71,
              "income_exposure": 1690000, "expected_payout": 885000, "avg_payout": 292,
              "platform_liability": 885000, "loss_ratio_after": 0.516 },
  "sample_claims": [ { "claim_id": "...", "worker_id": "W-...", "payout_amount": 397, "status": "PAID|HELD", "fraud_score": 12 } ×~50 ],
  "rider_impact": { "worker_id": "W-000001", "estimated_income_loss": 496, "protection_payout": 397,
                    "payment_label": "HK$397 credited to FPS — DEMO / SIMULATED" },
  "fleet_cards": { ...same shape as /api/fleet/dashboard cards... },   // updated after event
  "elapsed_ms": 340 }
```
  The call is idempotent-safe: re-running creates a NEW event but never duplicate payouts per worker+event (DB UNIQUE on idempotency keys).
- `POST /api/simulation/reset` → restores deterministic baseline (clears events/claims/payouts/fraud/audit/risk rows, re-derives ledger baseline) → `{ "status": "reset", "cards": {...baseline fleet cards...} }`
- `GET /api/events` → `{ "events": [ { event_id, event_type, label, zone_name, rainfall_mm, created_at, totals } ] }` newest first.

### Pricing
- `GET /api/pricing/plans?zone_id=Z-MK&weekly_income=3360&weekly_hours=42` →
```jsonc
{ "plans": [ { "plan": "BASIC", "coverage_factor": 0.6, "gross_premium": 206.67,
      "breakdown": { "expected_loss": 137.17, "operating_cost": 6.40, "fraud_reserve": 16.46, "risk_margin": 46.64 },
      "platform_subsidy": 173.60, "worker_contribution": 33.07, "max_payout_per_event": 560, "weekly_coverage_limit": 1760 },
    { STANDARD... }, { PLUS... } ],
  "inputs": { "zone_id": "Z-MK", "weekly_income": 3360, "weekly_hours": 42, "season": "wet_season" },
  "explain": "Premium = Expected Loss + Operating Cost + Fraud Reserve + Risk Margin. Expected loss = weekly event probability × expected payout." }
```
- `POST /api/pricing/quote` body `{ plan, zone_id, weekly_income, weekly_hours, subsidy_share? }` → same per-plan shape with `"why"` narrative string.

### Claims & fraud
- `GET /api/claims?status=HELD&limit=100` → `{ "claims": [ { claim_id, worker_id, zone_id, payout_amount, status, fraud_score, created_at } ], "counts": { "APPROVED": n, "HELD": n, "PAID": n, "REJECTED": n } }`
- `GET /api/claims/{claim_id}` → claim + fraud check detail + audit trail for that claim.
- `POST /api/claims/simulate-fraud` → generates ONE suspicious claim against the latest event (or creates a synthetic event if none): runs fraud engine →
```jsonc
{ "claim_id": "...", "worker_id": "W-...", "fraud_score": 82, "risk_band": "HIGH",
  "signals": [ {"signal": "GPS mismatch", "points": 34, "detail": "Worker GPS 12.4km outside affected zone"}, ... ],
  "action": "HOLD_FOR_REVIEW", "status": "HELD",
  "message": "Payout held. A risk manager must review before any payment." }
```
- `POST /api/claims/{claim_id}/review` body `{ "decision": "APPROVED"|"REJECTED"|"INVESTIGATING", "reviewer": "Risk Manager" }` → updated claim; approving pays it (respecting idempotency), rejecting releases reserved funds.

### Business viability
- `POST /api/viability` body (all optional → defaults from config):
```jsonc
{ "riders": 12482, "avg_weekly_income": 3360, "avg_gross_premium": 200, "platform_subsidy_share": 0.84,
  "weekly_event_probability": 0.30, "avg_payout": 345, "operating_cost_rate": 0.09, "fraud_loss_rate": 0.02 }
```
  →
```jsonc
{ "weekly": { "premium_revenue": 2496400, "expected_claims": 1291887, "operating_cost": 224676,
              "fraud_losses": 25838, "risk_reserve": 374460, "gross_contribution": 511539, "loss_ratio": 0.5175 },
  "annual": { "premium_revenue": ..., "expected_claims": ..., "operating_cost": ..., "fraud_losses": ...,
              "risk_reserve": ..., "contribution": ... },
  "break_even_riders": 1465,
  "inputs": { ...echo... },
  "explain": { "premium_revenue": "riders × avg_gross_premium", "expected_claims": "riders × weekly_event_probability × avg_payout", "...": "..." } }
```
- `POST /api/viability/sensitivity` body `{ "base": {<viability input>}, "shocks": [ {"key": "weekly_event_probability", "mult": 1.25, "label": "Severe weather +25%"}, {"key": "avg_payout", "mult": 1.20, "label": "Avg payout +20%"}, {"key": "platform_subsidy_share", "mult": 0.85, "label": "Platform subsidy −15%"} ] }` → `{ "results": [ { "label": ..., "loss_ratio": ..., "annual_contribution": ..., "break_even_riders": ... } ] }`
- `GET /api/viability/stress` → runs config.STRESS_SCENARIOS → `{ "scenarios": [ { "name": "BASELINE", "premium_revenue": ..., "expected_claims": ..., "simulated_claims": ..., "loss_ratio": ..., "operating_cost": ..., "fraud_loss": ..., "reserve_requirement": ..., "contribution_margin": ... } ×5 ] }`

### Analytics
- `GET /api/analytics/summary` → same chart series as insurer dashboard `charts` + `{ "risk_factors_avg": [ {"label": "Extreme rainfall", "points": 30.4}, ... ], "trigger_counts": [ {"label": "HEAVY_RAIN", "value": 3} ] }`

### Before / After
- `GET /api/protection/comparison` → derived from latest simulation (or baseline assumptions if none):
```jsonc
{ "without": { "label": "WITHOUT PROTECTION", "income_loss_per_rider": 496, "fleet_income_loss": 1690000,
               "platform_support_cost": 0, "worker_protection": 0 },
  "with":    { "label": "WITH RIDESHIELD", "income_loss_per_rider": 496, "payout_per_rider": 397,
               "net_loss_per_rider": 99, "fleet_payout": 885000, "weekly_protection_cost_per_rider": 273,
               "platform_subsidy_per_rider": 230 },
  "simulated": true, "note": "All values derived from the current scenario assumptions." }
```

### Audit
- `GET /api/audit?limit=200` → `{ "entries": [ { audit_id, event_code, entity_type, entity_id, detail, created_at } ] }` newest first. Event codes: WEATHER_RECEIVED, RISK_CALCULATED, TRIGGER_ACTIVATED, WORKER_ELIGIBILITY_CHECKED, FRAUD_CHECK_COMPLETED, CLAIM_APPROVED, PAYOUT_APPROVED, PAYOUT_SENT, FRAUD_HOLD, MANUAL_REVIEW, DEMO_RESET, JUDGE_MODE_STARTED.

### Export
- `GET /api/export/summary.csv` → CSV: scenario summary (latest event + totals + fleet cards)
- `GET /api/export/payouts.csv` → CSV of payouts for latest event
- `GET /api/export/risk.csv` → CSV of latest risk assessments per zone

### Judge mode
- `POST /api/judge/start` → resets demo to deterministic baseline, returns:
```jsonc
{ "status": "ready", "baseline_cards": {...}, "script": [
  { "key": "NORMAL", "title": "Normal conditions", "action": "NONE", "narration": {...} },
  { "key": "EVENT", "title": "Extreme weather arrives", "action": "SIMULATE:EXTREME_FLOOD" },
  { "key": "RISK", "title": "AI risk detection", "action": "NONE" },
  { "key": "EXPOSURE", "title": "Rider exposure", "action": "NONE" },
  { "key": "TRIGGER", "title": "Parametric trigger", "action": "NONE" },
  { "key": "ELIGIBILITY", "title": "Worker eligibility", "action": "NONE" },
  { "key": "FRAUD", "title": "Fraud check", "action": "NONE" },
  { "key": "PAYOUT", "title": "Payout", "action": "NONE" },
  { "key": "FINANCE", "title": "Platform financial impact", "action": "NONE" },
  { "key": "VIABILITY", "title": "Business viability", "action": "NONE" } ] }
```
  Judge-mode narration is client-side; the only backend actions are reset + one simulation.
```

## Conventions
- IDs: `W-000042`, `Z-MK`, `EV-<yyyymmdd>-<seq>`, `CL-<seq>`, `PO-<seq>`, `FC-<seq>`, `RA-<seq>`, `AU-<seq>`.
- The demo rider `W-000001` MUST live in zone `Z-MK` with weekly income HK$3,360, 42h, STANDARD plan, so the canonical demo produces loss HK$496 → payout HK$397 (4h affected... see note).
- Canonical judge event: EXTREME_FLOOD on Z-MK (Black Rainstorm, Mong Kok, 95mm/4h, flood probability 82%) → risk 90, affected_riders 3,148 (Mong Kok 1,685 + Sham Shui Po 1,463), eligible 3,104, approved 3,033, held 71, exposure HK$1.69M, payout HK$885K.
- Affected hours for payout = min(expected_disruption_hours, weekly_hours/7×1.2) — keep rider payout ≈ HK$300–500 for STANDARD.
- Everything deterministic: randomness only via `random.Random(config.DEMO["random_seed"])`.
