# RideShield — Business Model

## B2B2C flow

```
        weekly premium (84% subsidized)                automatic parametric payout
 ┌─────────────────┐ ───────────────────────▶ ┌──────────────────┐ ───────────────────────▶
 │ DELIVERY PLATFORM│                            │   RIDESHIELD     │    HK$397 to Jason Chan│
 │ (B2B customer)   │ ◀─────────────────────── │  risk + payout   │   (FPS, SIMULATED)     │
 │ 12,482 riders    │   protected, stable fleet  │     engine       │                        │
 └─────────────────┘                            └──────────────────┘
          ▲ worker contribution ≤ HK$45/week               ▲
          └────────────────────── RIDERS (protected automatically, no claims process)
```

The **platform is the customer**; riders are the beneficiaries. The platform buys weekly group
cover for its fleet, subsidizes 84% of every premium, and riders are enrolled automatically —
no sign-up, no claim forms. When a parametric trigger fires, eligible riders are paid within
the pipeline run. In a commercial structure, a licensed insurer would carry the risk with
RideShield as the parametric technology and program layer; the prototype simulates both sides.

## Unit economics — per rider-week (viability defaults)

Blended fleet averages from `config.VIABILITY` (adjustable live on the Business Viability
screen; this planning model works on averages, not per-rider quotes):

| Line | Basis | HK$ / rider-week |
|---|---|---:|
| Gross premium | blended across plans/districts/incomes | 200.00 |
| — platform subsidy | 84% | 168.00 |
| — worker contribution | 16% (under the HK$45 cap) | 32.00 |
| Expected claims | 0.30 weekly event probability × HK$345 avg payout | 103.50 |
| Operating cost | 9% × premium | 18.00 |
| Fraud losses | 2% × expected claims (leakage after controls) | 2.07 |
| Risk reserve | 15% × premium | 30.00 |
| Contribution margin | premium − claims − opex − fraud − reserve | 46.43 |
| Fixed cost allocation | HK$68,000/week ÷ 12,482 riders | 5.45 |
| **Net contribution** | margin − fixed allocation | **40.98** |

## Viability formulas

```
weekly_revenue     = riders × avg_gross_premium
expected_claims    = riders × weekly_event_probability × avg_payout
operating_cost     = operating_cost_rate × weekly_revenue
fraud_losses       = fraud_loss_rate × expected_claims
risk_reserve       = risk_reserve_rate × weekly_revenue
contribution       = weekly_revenue − expected_claims − operating_cost − fraud_losses − risk_reserve − fixed_weekly_cost
loss_ratio         = expected_claims ÷ weekly_revenue
break_even_riders  = fixed_weekly_cost ÷ per_rider_contribution_margin  # margin before fixed costs
annual figures     = weekly × 52
```

## Fleet economics — 12,482 riders

| Line | Weekly | Annual (×52) |
|---|---:|---:|
| Premium revenue | HK$2,496,400 | ≈ HK$129.8M |
| Expected claims | HK$1,291,887 | ≈ HK$67.2M |
| Operating cost | HK$224,676 | ≈ HK$11.7M |
| Fraud losses | HK$25,838 | ≈ HK$1.3M |
| Risk reserve | HK$374,460 | ≈ HK$19.5M |
| Fixed weekly cost | HK$68,000 | ≈ HK$3.5M |
| **Contribution** | **HK$511,539** | **≈ HK$26.6M** |
| Loss ratio | **51.75%** | — |

**Break-even: 68,000 ÷ 46.4 ≈ 1,465 riders** (per-rider contribution margin before fixed
costs; net of fixed costs the fleet earns ≈ HK$41 per rider-week). At 12,482 riders the fleet
runs at ~8.5× break-even — the model is strongly scale-driven because fixed costs
(HK$68,000/week ops & tech) are small relative to premium volume. (The app recomputes all of
these live from the inputs on the Business Viability screen.)

The live dashboards tell the same story on seeded data: the current underwriting week opens at
≈ **HK$2.63M** premium collected against ≈ **HK$473K** claims (loss ratio **18.0%**), rising
to ≈ **HK$1.36M** claims (loss ratio **51.6%**) after the canonical Black Rainstorm event —
one bad week is absorbable precisely because the risk reserve (15% of premium) accumulates in
quiet weeks.

## Stress scenarios

From `config.STRESS_SCENARIOS` (`GET /api/viability/stress`), applied to the fleet defaults
(multipliers combine: claims scale with frequency × severity):

| Scenario | Event frequency | Severity | Expected claims / wk | Loss ratio | Weekly contribution |
|---|---:|---:|---:|---:|---:|
| BASELINE | ×1.00 | ×1.00 | HK$1.29M | 51.75% | **+HK$511,539** |
| SEVERE_WEATHER | ×1.25 | ×1.20 | HK$1.94M | 77.62% | −HK$147,323 |
| EXTREME_WEATHER | ×1.50 | ×1.45 | HK$2.81M | 112.56% | −HK$1,036,787 |
| HIGH_FREQUENCY | ×1.80 | ×0.90 | HK$2.09M | 83.84% | −HK$305,450 |
| LOW_FREQ_HIGH_SEVERITY | ×0.70 | ×2.10 | HK$1.90M | 76.07% | −HK$107,791 |

The demo takeaway: **baseline economics are healthy, but a sustained severe season erases
margin** — which is exactly why the premium carries a 34% risk margin and the balance sheet
holds a 15%-of-premium reserve; a real deployment would add reinsurance and seasonal repricing.

## Sensitivity analyses

`POST /api/viability/sensitivity`, one shock at a time on the baseline:

| Shock | Loss ratio | Weekly contribution | Break-even riders |
|---|---:|---:|---:|
| Baseline | 51.75% | HK$511,539 | ≈1,465 |
| Event frequency +25% | 64.7% | HK$182,108 | ≈3,394 |
| Average payout +20% | 62.1% | HK$247,995 | ≈2,686 |
| Platform subsidy −15% (0.84 → 0.714) | 51.75% (unchanged) | HK$511,539 (unchanged) | ≈1,465 |

The subsidy shock is the instructive one: subsidy share moves money **between platform and
worker** — it does not change gross premium, claims or loss ratio. A −15% subsidy would
nominally shift ≈ HK$315K/week off the platform, pushing the worker's 16% share from HK$32
toward HK$57 — past the HK$45/week affordability cap, which then absorbs HK$12 of that back
onto the platform. Affordability, not underwriting, is the binding constraint.

## Why a platform buys this

- **Worker protection as a benefit.** Automatic, dignified income support — no claim forms, no
  waiting — at ≤ HK$45/week cost to the rider.
- **Income continuity → supply stability.** Riders who don't absorb a HK$496 shock keep showing
  up; the platform protects fleet retention and service levels through bad weather.
- **Operational risk management.** District-level exposure, live triggers and 7-day event
  forecasts turn weather from an anecdote into a managed variable.
- **Predictable financial exposure.** A fixed weekly premium (HK$168/rider platform share at
  fleet average) replaces unpredictable ad-hoc relief payouts; the demo event moves ≈ HK$885K
  to riders with zero platform decision latency.
- **Fraud control included.** Additive anomaly scoring with human review has prevented
  ≈ HK$196.5K of leakage season-to-date in the simulated ledger.

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
