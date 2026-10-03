# RideShield — Architecture

RideShield is a self-contained monolith: a FastAPI backend with an embedded SQLite database
serving a static, no-build frontend. There are no external services, no message queues, no API
keys. All behavior is deterministic and driven by a single configuration module.

## Component diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│ BROWSER — frontend/  (no build step, served statically at /)              │
│                                                                           │
│  index.html · css/app.css                                                 │
│  js/router.js   hash router (#/overview, #/simulation, ...)               │
│  js/api.js      fetch wrapper over /api/*                                 │
│  js/views/*     11 screens (Overview … Judge Mode)                        │
│  js/map.js      SVG city map (viewBox 0 0 400 300, zone rects)            │
│  js/charts.js   SVG line/bar/donut charts                                 │
│  js/judge.js    client-side Judge Mode narrator                           │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    │ GET/POST /api/* (JSON)
┌───────────────────────────────────▼───────────────────────────────────────┐
│ FastAPI APP — backend/main.py                                             │
│   routers/        thin HTTP layer, one module per API area:               │
│   meta · overview · fleet · riders · insurer · simulation · pricing ·     │
│   claims · viability · analytics · protection · audit · export · judge    │
├───────────────────────────────────────────────────────────────────────────┤
│ services/                                                                 │
│   pipeline.py     9-stage orchestration of a simulation run               │
│   seed.py         deterministic fleet / policy / ledger seeding (seed 42) │
│   reset.py        DEMO RESET → restores the seeded baseline               │
├───────────────────────────────────────────────────────────────────────────┤
│ engines/        pure, deterministic, config-driven business logic         │
│   risk.py         additive 0–100 scoring + explainability                 │
│   exposure.py     affected riders, zone attenuation, income exposure      │
│   trigger.py      parametric rule evaluation (config.TRIGGERS)            │
│   eligibility.py  policy status, zone match, scheduled overlap, limits    │
│   fraud.py        additive anomaly scoring, HOLD_FOR_REVIEW ≥ 60          │
│   payout.py       amount calc + idempotent payout creation                │
│   pricing.py      weekly premium construction per rider/plan/zone         │
│   analytics.py    dashboard aggregates and chart series                   │
│   viability.py    unit economics, stress scenarios, sensitivities         │
├───────────────────────────────────────────────────────────────────────────┤
│ backend/config.py — EVERY threshold, weight, price component, scenario.   │
│                     Nothing financial is hardcoded anywhere else.         │
├───────────────────────────────────────────────────────────────────────────┤
│ backend/database.py + schema.sql → SQLite  rideshield.db  (WAL mode)      │
└───────────────────────────────────────────────────────────────────────────┘
```

## Module responsibilities

| Module | Responsibility |
|---|---|
| `backend/main.py` | App factory, router registration, static mount at `/`, startup seeding |
| `backend/config.py` | Single source of truth: zones, triggers, model weights, pricing, fraud, viability, scenarios, disclaimer |
| `backend/database.py` | SQLite connection management, `schema.sql` bootstrap, WAL + foreign keys |
| `engines/risk.py` | Deterministic additive risk score per zone, factor-level explainability, confidence |
| `engines/exposure.py` | Which riders are affected; attenuates the signal to neighbouring zones by propensity |
| `engines/trigger.py` | Evaluates every rule in `config.TRIGGERS` per zone; records fired *and* evaluated-not-fired |
| `engines/eligibility.py` | Per affected rider: ACTIVE policy this week, zone match, scheduled overlap > 0, within weekly coverage limit |
| `engines/fraud.py` | Sums anomaly-signal points; score ≥ 60 → `HOLD_FOR_REVIEW`, else auto-approve path |
| `engines/payout.py` | `payout = clamp(loss × coverage_factor, min HK$40, per-event cap)`, rounded to HK$1; idempotent insert |
| `engines/pricing.py` | `gross = ExpectedLoss + OperatingCost + FraudReserve + RiskMargin`, subsidy split, worker cap |
| `engines/analytics.py` | Loss-ratio trend, premium-vs-claims, distributions for dashboards |
| `engines/viability.py` | Weekly/annual economics, break-even riders, stress scenarios, sensitivity shocks |
| `services/pipeline.py` | Runs the 9 stages in order, persists each stage's outputs, writes audit events |
| `services/seed.py` | Generates 12,482 workers, policies, 12-week premium ledger from `random.Random(42)` |
| `services/reset.py` | Clears transactional tables and re-derives the deterministic baseline |
| `routers/*` | Request validation and response shaping exactly per `API_CONTRACT.md`; no business logic |

Engines never perform I/O beyond what the pipeline hands them, never read each other's
internals, and never import routers. Each engine consumes `config.py` plus its inputs and
returns plain dicts — which is what makes the risk model (or any engine) replaceable.

## Request lifecycle: `POST /api/simulate`

The backend executes the entire pipeline synchronously (typically < 1 s) and returns all nine
stage payloads; the frontend then animates stage progression (0.5–2 s per stage) using the
ordered `stages` array.

```
client                routers/simulation      services/pipeline              engines                    SQLite
  │  POST /api/simulate      │                      │                           │                        │
  │─────────────────────────▶│  validate body;      │                           │                        │
  │                          │  merge preset +      │                           │                        │
  │                          │  partial weather +   │                           │                        │
  │                          │  ambient defaults    │                           │                        │
  │                          │─────────────────────▶│                           │                        │
  │                          │                      │ 1 WEATHER                 │                        │
  │                          │                      │   persist weather_events  │───────────────────────▶│
  │                          │                      │   audit WEATHER_RECEIVED  │                        │
  │                          │                      │ 2 RISK ──────────────────▶│ risk.py: score every   │
  │                          │                      │   risk_assessments row    │ zone (epicenter +      │
  │                          │                      │   audit RISK_CALCULATED   │ attenuated neighbours) │
  │                          │                      │ 3 EXPOSURE ──────────────▶│ exposure.py: affected  │
  │                          │                      │   lost hours = duration   │ riders, lost hours,    │
  │                          │                      │   ×1.55 (≤9h) × overlap   │ HK$ exposure per zone  │
  │                          │                      │ 4 TRIGGER ───────────────▶│ trigger.py: evaluate   │
  │                          │                      │   triggers rows (fired +  │ config.TRIGGERS,       │
  │                          │                      │   not-fired)              │ e.g. rain ≥90mm        │
  │                          │                      │   audit TRIGGER_ACTIVATED │                        │
  │                          │                      │ 5 ELIGIBILITY ───────────▶│ eligibility.py: policy │
  │                          │                      │   claims rows (PENDING,   │ ACTIVE? zone? overlap? │
  │                          │                      │   idempotency_key set)    │ weekly limit?          │
  │                          │                      │   audit WORKER_ELIGIBILITY│                        │
  │                          │                      │ 6 FRAUD ─────────────────▶│ fraud.py: signal sum   │
  │                          │                      │   fraud_checks rows;      │ per claim; ≥60 → HELD  │
  │                          │                      │   audit FRAUD_CHECK_*/    │                        │
  │                          │                      │   FRAUD_HOLD              │                        │
  │                          │                      │ 7 APPROVAL                │ claims → APPROVED /    │
  │                          │                      │   audit CLAIM_APPROVED    │ stays HELD             │
  │                          │                      │ 8 PAYOUT ────────────────▶│ payout.py: amount per  │
  │                          │                      │   INSERT … idempotency    │ plan; idempotent write │
  │                          │                      │   key (UNIQUE) → PAID     │ (duplicates impossible)│
  │                          │                      │   audit PAYOUT_APPROVED / │                        │
  │                          │                      │   PAYOUT_SENT             │                        │
  │                          │                      │ 9 FINANCE ───────────────▶│ premium_ledger update; │
  │                          │                      │   fleet cards, loss ratio │ fleet totals           │
  │  { stages[9], assessment, zones, totals,       │                           │                        │
  │    sample_claims, rider_impact, fleet_cards }◀─│                           │                        │
  │◀─────────────────────────│                      │                           │                        │
```

Stage keys returned to the UI, in order:
`WEATHER → RISK → EXPOSURE → TRIGGER → ELIGIBILITY → FRAUD → APPROVAL → PAYOUT → FINANCE`.

Re-running a simulation creates a **new** event but can never double-pay: payout idempotency
keys (`worker_id + event_id + policy_id`) are UNIQUE at the database level.

## Data model — 13 tables

| Table | Purpose | Key relationships |
|---|---|---|
| `platforms` | The B2B customer (fleet operator) and its subsidy share | 1 → N workers, ledger rows |
| `zones` | 10 fictional Hong Kong districts: propensities, traffic, map rects | 1 → N workers, events, assessments |
| `workers` | 12,482 fictional riders: income, hours, tenure, FPS handle (demo) | N → 1 platform, 1 home zone |
| `policies` | Weekly coverage per worker (plan, coverage factor, caps, status) | N → 1 worker; UNIQUE(worker, week) |
| `weekly_plans` | Computed premium per worker-week with full breakdown | N → 1 worker; UNIQUE(worker, week) |
| `weather_events` | Every simulated/entered disruption, with `data_source` label | 1 → N assessments, triggers, claims |
| `risk_assessments` | 0–100 score, level, expected hours/loss/payout, factors JSON, explanation | N → 1 event (NULL = ambient), 1 zone |
| `triggers` | Per-zone rule evaluations: threshold description, observed value, fired flag | N → 1 event, 1 zone |
| `claims` | Per affected rider: eligibility, affected hours, loss, payout, status | N → 1 event, worker, policy, zone |
| `payouts` | Money movement records (method `FPS (SIMULATED)`) | 1 → 1 claim |
| `fraud_checks` | Score, band, signals JSON, action, review outcome | 1 → 1 claim |
| `premium_ledger` | Weekly premium/claims/fraud-prevented history (12 seeded weeks + live) | UNIQUE(week, platform) |
| `audit_events` | Immutable log of every system decision with JSON detail | references any entity |

ID conventions: `W-000042` workers, `Z-MK` zones, `EV-<yyyymmdd>-<seq>` events, `CL-`/`PO-`/
`FC-`/`RA-`/`AU-` claims, payouts, fraud checks, assessments, audit entries.

### Idempotency design

Duplicate payment is the worst failure mode of an auto-payout system, so it is made
structurally impossible at three layers:

1. **Key construction** — every claim and payout carries
   `idempotency_key = worker_id + event_id + policy_id`. One rider, one event, one policy ⇒
   one payout, ever.
2. **Database hard-stop** — `UNIQUE` column plus explicit unique indexes
   (`idx_claims_idem`, `idx_payouts_idem`). A duplicate insert fails at the DB layer even under
   retries, double-clicks or concurrent requests.
3. **Engine discipline** — the payout engine inserts idempotently (conflict → no-op) and never
   updates amounts in place; corrections would be new reversing rows.

The same key protects the manual-review path: approving a held claim pays it through the same
idempotent insert.

## Swapping the deterministic risk model for XGBoost/LightGBM

The risk engine is deliberately small and replaceable. Everything downstream — trigger,
eligibility, fraud, payout, dashboards — consumes only the **assessment contract**, so a
machine-learned model can replace the deterministic one without touching any other module.

**Interface to implement** (kept in `engines/risk.py`):

```python
def assess(zone: dict, weather: dict, context: dict) -> dict:
    return {
        "zone_id": zone["id"],
        "risk_score": float,                 # 0–100
        "risk_level": "LOW|MODERATE|HIGH|SEVERE",
        "expected_disruption_hours": float,
        "expected_income_loss": float,       # HK$ per affected rider
        "expected_payout": float,            # HK$ per affected rider
        "confidence_score": float,           # 0–1
        "risk_factors": [{"label": str, "points": float}],   # explainability atoms
        "explanation": str,                  # natural-language "why"
        "model_version": str,                # e.g. "xgboost-1.3.0"
    }
```

**Migration path:**

1. **Features** — reuse the exact inputs of the deterministic model: weather signal fields,
   zone propensities, traffic index, duration, worker-exposure ratio.
2. **Targets** — train offline on historical disruption/claims data: a classifier for
   P(material disruption) and/or a regressor for expected lost hours / expected loss.
3. **Calibration** — map model output onto the same 0–100 scale and keep the level bands
   (25/50/75) so triggers and UI thresholds are untouched. Gradient-boosted models are
   deterministic at inference, so demo reproducibility is preserved.
4. **Explainability** — convert per-prediction SHAP contributions into the existing
   `[{label, points}]` factor list so the UI's "why" panel keeps working unchanged.
5. **Honesty flags** — bump `model_version` and set `trained_on_real_data` accordingly;
   both surface in `/api/config` and `/api/model/card`.
6. **Shadow then cut over** — run both models, persist both scores, compare; then flip the
   active engine in config.

## Frontend architecture

- **No build step.** Plain ES modules loaded by `index.html`; served by FastAPI as static files.
- **Hash router** (`#/overview`, `#/simulation`, …): each route renders one of the 11 screens
  into a single app shell; deep-linkable and refresh-safe.
- **`api.js`** — tiny fetch wrapper; every screen renders exclusively from `/api/*` JSON and
  re-fetches after mutations (simulate / reset / review), so the backend stays the only source
  of truth.
- **SVG city map** — zone rectangles positioned from `config.ZONES` (`viewBox 0 0 400 300`),
  colored by live risk level; no mapping library, no tiles, no network.
- **SVG charts** — line (loss ratio), bars (premium vs claims), donuts (plan mix,
  distributions), hand-rolled to keep the zero-dependency constraint.
- **Simulation animation** — `POST /api/simulate` returns all 9 completed stages; the UI
  reveals them on a 0.5–2 s stagger with stage metrics and reasoning text.
- **Judge Mode** — `POST /api/judge/start` resets the demo and returns a 10-step script;
  narration is client-side, the only backend actions are the reset and one simulation.

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
