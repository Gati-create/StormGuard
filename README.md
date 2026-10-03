# RideShield

**Protect the income behind every delivery.**

RideShield is a working prototype of a **B2B parametric income-protection platform** for gig
delivery riders. When a disruption — black rainstorm, flood, typhoon, extreme heat, hazardous
air, zone closure or platform outage — makes it impossible to work, RideShield detects the
event, scores the risk, verifies rider eligibility, screens for fraud and pays affected riders
automatically. No claim forms, no adjusters, no waiting.

The demo simulates a fictional Hong Kong fleet of **12,482 riders** across 10 delivery
districts, priced in HKD, fully deterministic (seed 42).

## Positioning: B2B2C

A **delivery platform buys the cover on behalf of its fleet** and subsidizes 84% of every
premium; riders are protected automatically, week by week, and never pay more than HK$45/week.
Riders get income continuity; the platform gets a protected, more stable fleet and a predictable
financial exposure instead of ad-hoc disaster relief.

## What RideShield is NOT

- **Not health, accident or vehicle insurance.** It replaces *lost income* for a defined
  disruption window only — nothing else.
- **Not pay-for-not-working.** Payouts happen only when an objective parametric trigger fires
  *and* the rider was actually scheduled inside the disruption window. It is not an unemployment
  benefit or an income top-up.
- **Not a real insurance product.** All data, riders, weather and payouts are simulated.

## Feature tour — 11 screens

| Screen | What it shows |
|---|---|
| **Overview** | System status, fleet cards, live zone map, current AI risk assessment, pipeline ticks |
| **Rider Protection** | Demo rider (Jason Chan): plan, protected income, district risk, latest payout (DEMO FPS), coverage history |
| **Fleet Risk** | B2B dashboard: riders protected, premium collected, claims paid, loss ratio, fraud prevented, zone exposure |
| **Live Events** | Every simulated disruption with type, zone, rainfall and totals, newest first |
| **Pricing** | Per-plan quotes with full premium breakdown (expected loss + operating + fraud reserve + risk margin) |
| **Claims & Fraud** | Claim ledger, fraud scores and signals, HOLD queue, manual review actions |
| **Risk Analytics** | Loss-ratio trend, premium vs claims, claims by event/zone, risk & payout distributions, average risk factors |
| **Business Viability** | Unit economics, weekly/annual P&L, break-even riders, stress scenarios, sensitivity shocks |
| **Simulation** | The hero screen: pick a preset or custom weather, run the 9-stage pipeline, watch every engine decide |
| **Audit Log** | Immutable event stream (WEATHER_RECEIVED → … → PAYOUT_SENT), one row per system decision |
| **Judge Mode** | Guided 10-stage demo: resets to baseline, runs the canonical Extreme Rain event, narrates each stage |

## Quickstart

```bash
cd rideshield
./start.sh                    # creates .venv, installs deps, starts uvicorn on :8000
open http://localhost:8000
```

Run the tests:

```bash
./run_tests.sh                # .venv/bin/pytest -q
```

## The canonical demo event

Black Rainstorm over **Mong Kok (Z-MK)**: 95 mm in 4 h, flood probability 82% →
risk score **90 (SEVERE)** → parametric trigger fires → **3,148 riders** affected (3,104
eligible) → fraud engine approves **3,033** and holds **71** for human review →
**≈ HK$885K** paid out, avg HK$292/rider → demo rider Jason Chan loses HK$496 of income and
receives **HK$397** via FPS (DEMO / SIMULATED) → fleet loss ratio jumps **18% → 52%**. See
[DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the timed presenter script.

## Tech stack

- **Backend:** Python 3.9+, FastAPI, SQLite (WAL mode) — no external services, no API keys
- **Frontend:** no-build SPA — vanilla JS (hash router), custom CSS, SVG city map and charts
- **Tests:** pytest + httpx (FastAPI TestClient)
- **Config:** every threshold, weight, price component and scenario lives in `backend/config.py`

## Project layout

```
rideshield/
├── backend/
│   ├── main.py            # FastAPI app, router registration, static mount
│   ├── config.py          # single source of assumptions, weights, thresholds, scenarios
│   ├── database.py        # SQLite connection + schema bootstrap
│   ├── schema.sql         # 13-table schema incl. idempotency indexes
│   ├── engines/           # risk, exposure, trigger, eligibility, fraud, payout, pricing, analytics, viability
│   ├── routers/           # /api/* endpoint modules (thin HTTP layer)
│   └── services/          # 9-stage pipeline orchestration, deterministic seeding, demo reset
├── frontend/              # no-build SPA
│   ├── index.html
│   ├── css/               # custom design system
│   └── js/                # hash router, views, SVG map & charts, judge-mode narration
├── tests/                 # pytest suite (API, engines, idempotency)
├── API_CONTRACT.md        # REST contract (source of truth)
├── ARCHITECTURE.md        # components, request lifecycle, data model, model swap
├── RISK_MODEL.md          # risk model card
├── PRICING_MODEL.md       # premium construction & subsidy mechanics
├── BUSINESS_MODEL.md      # unit economics, viability, stress tests
├── DEMO_SCRIPT.md         # timed ~3-minute presenter script
├── DEMO_DATA.md           # fictional entities, labeling policy, determinism
├── SETUP.md               # install, run, reset, troubleshooting
├── requirements.txt
├── start.sh               # one-command run
└── run_tests.sh           # one-command test
```

## Documentation

- [SETUP.md](SETUP.md) — install, run, reset, troubleshooting
- [API_CONTRACT.md](API_CONTRACT.md) — every endpoint, request/response shapes
- [ARCHITECTURE.md](ARCHITECTURE.md) — components, pipeline lifecycle, data model
- [RISK_MODEL.md](RISK_MODEL.md) — model card: inputs, formula, explainability, limitations
- [PRICING_MODEL.md](PRICING_MODEL.md) — premium math, subsidy, plan differentiation
- [BUSINESS_MODEL.md](BUSINESS_MODEL.md) — B2B2C flow, unit economics, stress scenarios
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — judge-ready 3-minute run of show
- [DEMO_DATA.md](DEMO_DATA.md) — fictional data catalog and determinism

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
