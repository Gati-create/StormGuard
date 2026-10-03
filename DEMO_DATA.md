# RideShield — Demo Data Catalog

Everything in RideShield is fictional. This document is the inventory of what is simulated,
how it is labeled, and how to regenerate it.

## Data-source labeling policy

Every `weather_events` row carries a `data_source` field, and API responses include
`data_source` labels wherever values are fictional or simulated. The vocabulary:

| Label | Meaning | Used in this prototype |
|---|---|---|
| `REAL API` | Fetched from a live external provider (e.g. HKO weather, an AQI API) | **Never** — no external APIs are wired |
| `MOCK DATA` | Static fixture mimicking a real provider's format | Not currently used |
| `SIMULATED` | Generated deterministically by the seeding/pipeline code | **Everything**: fleet, ledger, events, payouts |
| `USER INPUT` | Entered live by a presenter (custom simulation parameters, review decisions) | Custom scenarios from the Simulation screen |

Payout strings carry their own label — `HK$397 credited to FPS — DEMO / SIMULATED` — and
payout rows use method `FPS (SIMULATED)`. No real payment rail exists.

## Districts (10, fictional Hong Kong)

From `config.ZONES`. `base_risk` is the long-run disruption propensity; the three propensities
drive attenuation and event-type susceptibility; historical events/year feeds expected-loss
pricing. Map coordinates place the district rectangles on the SVG city map (viewBox 400×300);
the layout is schematic — New Territories on top, Kowloon in the middle, Hong Kong Island at
the bottom.

| ID | District | base_risk | flood | heat | aqi | events/yr | traffic | density |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Z-MK | Mong Kok | 0.62 | 0.85 | 0.40 | 0.55 | 9 | 0.72 | 0.91 |
| Z-TST | Tsim Sha Tsui | 0.48 | 0.60 | 0.42 | 0.50 | 6 | 0.66 | 0.84 |
| Z-SSP | Sham Shui Po | 0.55 | 0.78 | 0.38 | 0.45 | 8 | 0.58 | 0.79 |
| Z-WC | Wan Chai | 0.44 | 0.50 | 0.50 | 0.62 | 5 | 0.74 | 0.72 |
| Z-KT | Kwun Tong | 0.50 | 0.70 | 0.36 | 0.48 | 7 | 0.62 | 0.68 |
| Z-CEN | Central | 0.30 | 0.30 | 0.44 | 0.42 | 3 | 0.50 | 0.55 |
| Z-TP | Tai Po | 0.26 | 0.35 | 0.52 | 0.58 | 3 | 0.42 | 0.44 |
| Z-TW | Tsuen Wan | 0.40 | 0.55 | 0.34 | 0.40 | 5 | 0.55 | 0.63 |
| Z-ST | Sha Tin | 0.36 | 0.45 | 0.46 | 0.52 | 4 | 0.68 | 0.58 |
| Z-YL | Yuen Long | 0.42 | 0.65 | 0.40 | 0.55 | 6 | 0.70 | 0.60 |

## Fleet composition (12,482 riders)

Sampled from `config.WORKER_PROFILE`:

| Attribute | Distribution |
|---|---|
| Weekly income | Normal(mean HK$3,360, sd HK$520), clamped to HK$2,080–HK$5,440 |
| Weekly hours | Normal(mean 42 h, sd 5 h), clamped to 28–60 h |
| Tenure | Normal(mean 58 weeks, sd 30), clamped to 4–220 weeks |
| Plan mix | BASIC 22% (≈2,746) · STANDARD 61% (≈7,614) · PLUS 17% (≈2,122) |
| Platform | One fictional Hong Kong delivery platform (LionRock Logistics), subsidy share 84% |

Derived per rider: `avg_hourly_income = weekly_income ÷ weekly_hours` (demo rider: HK$80/h).
Each rider holds a weekly ACTIVE policy matching their plan, and a computed `weekly_plans`
premium row with the full ExpectedLoss/OperatingCost/FraudReserve/RiskMargin breakdown.

## Demo rider

| Field | Value |
|---|---|
| worker_id | `W-000001` |
| Name | Jason Chan |
| Home district | Mong Kok (Z-MK) |
| Weekly income / hours | HK$3,360 / 42 h (HK$80/h) |
| Tenure | 78 weeks |
| Plan | STANDARD (80% coverage, HK$1,200/event cap) |
| Worker contribution | HK$43.75/week (UI rounds to HK$44) — 16% of HK$273.42 gross; platform subsidizes HK$229.67 |
| FPS handle | `jason.chan@fps (DEMO)` |
| Canonical event impact | loses HK$496 (6.2 affected h × HK$80/h, full-window overlap) → receives **HK$397** |

## Seeded history

| Entity | Contents |
|---|---|
| Premium ledger | 12 weeks of seeded history; past-week loss ratios in a 34–55% band; current week opens at ≈ HK$2.63M premium / ≈ HK$473K claims (18.0%) |
| Pre-demo event | Amber/Red Rainstorm, Mong Kok (Z-MK), 72 mm over 4 h, flood probability 48%, 3 days before demo open — so dashboards are non-empty before the presenter acts |
| Fraud card | HK$196,500 fraud prevented season-to-date (held-and-rejected claims) |
| Canonical judge event | Black Rainstorm, Z-MK, 95 mm / 4 h / 82% flood → risk 90, 3,148 affected (Mong Kok 1,685 + Sham Shui Po 1,463), 3,104 eligible, 3,033 approved, 71 held, ≈ HK$1.69M exposure, ≈ HK$885K payout, Jason HK$397 |

## Scenario presets

From `config.SCENARIOS` (Simulation screen): **Normal Day** (6 mm), **Amber/Red Rainstorm**
(72 mm), **Black Rainstorm** (95 mm — the canonical event), **Black Swan** (160 mm, typhoon,
zone closure, platform availability 82%). Presenter-entered custom weather is stored with
`data_source = USER INPUT`.

## How determinism works

- A single seeded RNG — `random.Random(config.DEMO["random_seed"])` with seed **42** — drives
  all generation: worker sampling, plan assignment, ledger history, per-rider scheduled
  overlap (sampled U(0.40, 1.00), mean 0.74, keyed deterministically per worker).
- Engines are pure functions of config + inputs; inference has no randomness at all.
- Consequence: every install, every reset, every demo run produces identical fleets and
  identical canonical numbers (risk 90, 3,148 affected riders, HK$885K payout, HK$397 to
  Jason). Seed 42 pins the actual values.

## How to regenerate

| Goal | Action |
|---|---|
| Restore the canonical baseline | **RESET DEMO** button, or `POST /api/simulation/reset` — clears events/claims/payouts/fraud/audit/risk rows and re-derives the ledger baseline |
| Full rebuild from scratch | Stop server, delete `rideshield.db*`, `./start.sh` — schema and seed data are recreated on startup |
| A different fictional fleet | Change `DEMO.random_seed` (and optionally `DEMO.total_riders`, `WORKER_PROFILE`) in `backend/config.py`, then delete the DB and restart |

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
