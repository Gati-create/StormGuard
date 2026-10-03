# RideShield — Risk Model Card

| | |
|---|---|
| **Model name / version** | `demo-deterministic-1.0` |
| **Type** | Deterministic weighted-additive scoring model (drop-in replaceable by XGBoost/LightGBM) |
| **TRAINING-DATA STATUS** | **NOT trained on real insurance data.** No fitting, no learning. Weights are hand-set demo assumptions in `backend/config.py`. |
| **Owner surface** | `engines/risk.py`, configured by `config.RISK_MODEL` |

## Purpose

Produce, for a given zone and weather/operational signal, a **0–100 disruption-risk score**
with a factor-level explanation, plus derived expectations (lost hours, income loss, payout)
that drive the trigger, eligibility and payout engines. It answers: *"how bad is this event
for riders' ability to earn in this zone, and why?"*

## Inputs

| Group | Fields |
|---|---|
| **Environmental** | `rainfall_mm`, `rainfall_intensity`, `temperature_c`, `humidity`, `wind_speed_kmh`, `aqi`, `flood_probability`, `cyclone_probability` (typhoon) |
| **Operational** | `platform_availability_pct`, `zone_closure` |
| **Temporal** | `duration_h`, season (wet season/summer/winter multipliers), scheduled-overlap window |
| **Worker exposure** | home zone (propensities, traffic index, historical event rate), weekly income & hours (→ hourly income), expected loss ÷ weekly income |

## Outputs

| Field | Meaning |
|---|---|
| `risk_score` | 0–100 weighted-additive score |
| `risk_level` | LOW (<25) · MODERATE (25–49) · HIGH (50–74) · SEVERE (≥75) |
| `expected_disruption_hours` | `duration_h × 1.55` (secondary effects), capped at 9 h |
| `expected_income_loss` | HK$ per affected rider: lost hours × scheduled overlap × hourly income |
| `expected_payout` | HK$ per affected rider after plan coverage factor and caps |
| `confidence_score` | 0–1; base 0.78, + up to 0.10 for data completeness, − for source conflict |
| `risk_factors` | `[{label, points}]` — the additive contributions, surfaced verbatim in the UI |
| `explanation` | Natural-language "why" generated from the top factors |
| `model_version` | `demo-deterministic-1.0` |

## Scoring formula

For each factor *f* with weight *w*, normalizer *N* and cap *c*:

```
points_f = w_f × min(value_f / N_f, c_f) × (activation  if f is contextual  else 1)

risk_score = clamp( Σ points_f , 0, 100 )
```

**Activation** is what separates a calm day from an event day. Contextual factors (zone
history, traffic, time exposure, worker exposure) only matter when something is actually
happening, so they are scaled by how close the signal is to breaching a trigger:

```
activation = clamp( max over trigger params of (param_value / trigger_threshold), 0, 1 )
```

A drizzle in a risky zone still scores LOW; a threshold-breaching storm pushes contextual
factors to full strength and the score to HIGH/SEVERE.

### Factor table (from `config.RISK_MODEL`)

| Factor | Max points (weight) | Normalizer | Cap | Contextual | Input value |
|---|---:|---:|---:|:---:|---|
| Extreme rainfall | 31 | 97 mm | 1.6 | no | `rainfall_mm` |
| Flood probability | 22 | 0.82 | 1.3 | no | `flood_probability` |
| Extreme heat | 18 | 5.0 | 1.2 | no | °C above 33 (HKO Very Hot Weather Warning zero-point) |
| Wind / typhoon | 13 | 80 km/h | 1.3 | no | `wind_speed_kmh` |
| Air pollution | 12 | 400 | 1.3 | no | `aqi` |
| Historical zone risk | 14 | 0.85 | 1.0 | yes | zone propensity |
| Traffic disruption | 9 | 0.72 | 1.0 | yes | zone traffic index |
| Time exposure | 6 | 4 h | 1.0 | yes | `duration_h` |
| Worker exposure | 5 | 1.0 | 1.0 | yes | expected loss ÷ weekly income |

## Explainability — canonical example

Judge event: **Black Rainstorm, Mong Kok (Z-MK)** — 95 mm in 4 h, flood probability 82%,
activation = 1.0 (both rainfall ≥ 90 mm and flood probability ≥ 0.75 breach their trigger
thresholds). The live deterministic model returns **90 / 100 → SEVERE** for this event:

| Factor | Points |
|---|---:|
| Extreme rainfall (95 mm vs 97 mm normalizer) | **+30.4** |
| Flood probability (0.82 vs 0.82) | **+22.0** |
| Historical zone risk (Mong Kok flood propensity 0.85) | **+14.0** |
| Traffic disruption (traffic index 0.72) | **+9.0** |
| Wind / typhoon (38 km/h) | **+6.2** |
| Time exposure (4 h duration) | **+6.0** |
| Air pollution (AQI 64) | **+1.9** |
| Worker exposure (expected loss ÷ weekly income) | **+0.7** |
| **Total** | **90 / 100 → SEVERE** |

Heat contributes nothing (25 °C is below the 33 °C HKO Very Hot Weather Warning zero-point);
AQI, wind and worker exposure
contribute small but non-zero points, which is why the live score sits a few points above the
round-number illustrative decomposition (+31 rainfall, +22 flood, +14 zone history, +9
traffic, +6 time, +5 worker exposure = 87/100) quoted in earlier versions of this card.
Confidence: **0.83** (0.78 base + completeness bonus). Because the model is a literal sum, the
UI can show every point and its reason — there is no black box to explain away.

## Known limitations

- **Not actuarially valid.** Weights are hand-tuned so demo scenarios produce sensible
  narratives; the score is an ordinal severity indicator, not a calibrated probability.
- **No learning from history.** Zone propensities and event rates are static fictional
  constants; the model cannot improve or drift with data.
- **Fixed spatial spillover.** Signal attenuation to neighbouring zones is a 3-step lookup by
  propensity (×0.75 / ×0.50 / ×0.30), not a learned or meteorological diffusion.
- **Coarse seasonality.** Three season multipliers (wet season 1.45, summer 1.05, winter 0.75);
  no climate trend, no diurnal pattern.
- **Saturation.** Factor caps make scores bunch at the top for compound catastrophes (by
  design, for demo legibility).
- **Heuristic confidence.** The confidence score reflects data completeness, not predictive
  accuracy.
- **Single-event, single-week horizon.** No accumulation across consecutive events.

## Potential bias sources

- **Zone propensities as proxies.** Fictional zone-level risk scores could, in a real
  deployment, correlate with neighbourhood socio-economics. Pricing uses the same zone
  variables, so any bias here propagates to premiums. Mitigation path: actuarial review and
  fairness testing before any real launch.
- **Income-proportional payouts.** Payouts scale with declared weekly income, so higher-earning
  riders receive larger payouts for the same event. This is intentional (income replacement),
  but it is a distributional choice, not a neutral one.
- **Traffic/density indices.** Invented per-zone constants; real indices would import the
  biases of their data providers.
- **Scheduled-overlap sampling.** Riders with atypical working patterns may be systematically
  under- or over-compensated by the uniform overlap model (U(0.40, 1.00), mean 0.74).

## Human review points

| Stage | Human in the loop |
|---|---|
| Fraud | Score ≥ 60 → **HOLD_FOR_REVIEW**; no held claim is paid or rejected without a risk manager (`POST /api/claims/{id}/review`) |
| Configuration | Trigger thresholds, model weights and plan terms change only by editing `config.py` — a deliberate, reviewable act |
| Model governance | `/api/model/card` exposes purpose, inputs, limitations and `trained_on_real_data: false` |
| Audit | Every score, trigger evaluation, eligibility decision and payout lands in `audit_events` |
| Money movement | All payouts are labeled `FPS (SIMULATED)`; no real payment rail exists in the prototype |

## Replacement path

The deterministic model exists to be replaced. The assessment contract (fields above) is the
seam: an XGBoost/LightGBM model trained on real disruption and claims data can implement the
same interface — with SHAP values mapped into `risk_factors` — without touching the trigger,
eligibility, fraud or payout engines. See **ARCHITECTURE.md → Swapping the risk model**.

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
