# RideShield — Pricing Model

Premiums are **computed, never hardcoded**. Every quote is built from four transparent
components, all parameterized in `config.PRICING`.

## Premium construction

```
Gross premium (per rider-week)
    = ExpectedLoss + OperatingCost + FraudReserve + RiskMargin

where
    ExpectedLoss  = P(paid disruption event in the rider-week) × E[payout | event]
    OperatingCost = HK$6.40 flat per rider-week
    FraudReserve  = 12% × ExpectedLoss
    RiskMargin    = 34% × ExpectedLoss
```

- **P(event)** starts from a fleet-average baseline of 0.30 per rider-week, is scaled per
  district by `zone.base_risk ÷ fleet-average base_risk`, and scaled by season (wet season
  ×1.45, summer ×1.05, winter ×0.75). The engine calibrates the result so fleet-wide weekly
  premium lands in the ≈ HK$2.2M–2.7M band.
- **E[payout | event]** comes from a typical event profile (4 h duration → 4 × 1.55 = 6.2
  affected hours, capped at 9 h), the fleet's mean scheduled overlap (0.74), the rider's hourly
  income, and the plan's coverage factor, subject to the plan's per-event cap.

Because every rider-week premium is stored with its full component breakdown in
`weekly_plans`, any quote can be explained line by line.

## Worked example — STANDARD, Mong Kok, HK$3,360/week

The canonical rider: `W-000001` Jason Chan, zone Z-MK, HK$3,360/week, 42 h (HK$80/h), wet
season.

| Component | Basis | Amount |
|---|---|---:|
| Expected loss | weekly event probability 0.6229 (district- and season-adjusted) × E[payout \| event] HK$293.63 | **HK$182.89** |
| Operating cost | flat | **HK$6.40** |
| Fraud reserve | 12% × 182.89 | **HK$21.95** |
| Risk margin | 34% × 182.89 | **HK$62.18** |
| **Gross premium** | sum | **HK$273.42 / week** |
| Platform subsidy | 84% × 273.42 | **−HK$229.67** |
| **Worker contribution** | 16% × 273.42 | **HK$43.75 / week** |

(The UI rounds the worker contribution to HK$44.)

For a typical 4 h disruption Jason's expected payout is 6.2 h × HK$80 × 80% ≈ **HK$397** — the
exact figure the demo event produces — against a HK$43.75/week out-of-pocket cost: a 16% share
that sits just under the HK$45 affordability cap (see below).

## Subsidy mechanics

```
platform_share = subsidy_share × gross              # subsidy_share = 0.84
worker_share   = gross − platform_share, capped at HK$45/week
```

- The platform (the B2B customer) pays **84%** of every premium as a fleet benefit — and
  absorbs anything the worker cap pushes back onto it.
- The rider pays the remaining 16%, **never more than HK$45/week**. The cap binds once gross
  premium reaches HK$281.25 — on the canonical STANDARD policy the worker's 16% (HK$43.75)
  sits just under it, while on PLUS (gross HK$306.79) the cap binds and the platform absorbs
  the excess. At lower incomes the 16% share falls further below the cap.

## Plan differentiation

Plans differ only in **coverage factor, per-event cap and weekly coverage limit** — the pricing
formula is identical, so premiums scale roughly with the coverage factor (expected payout, and
therefore expected loss, is proportional to it).

| Plan | Coverage factor | Max payout / event | Weekly coverage limit | Gross premium* | Worker pays | Platform pays |
|---|---:|---:|---:|---:|---:|---:|
| BASIC | 60% | HK$560 | HK$1,760 | HK$206.67 | HK$33.07 | HK$173.60 |
| STANDARD | 80% | HK$1,200 | HK$2,720 | **HK$273.42** | **HK$43.75** | **HK$229.67** |
| PLUS | 90% | HK$1,760 | HK$3,840 | HK$306.79 | HK$45.00 | HK$261.79 |

\* Same rider as the worked example (Z-MK, HK$3,360/wk, wet season), live from the pricing
engine. Gross = EL + HK$6.40 + 12% EL + 34% EL, with EL of HK$137.17 (BASIC), HK$182.89
(STANDARD) and HK$205.75 (PLUS). Fleet plan mix: BASIC 22% · STANDARD 61% · PLUS 17%.

At this income the HK$45 cap binds only on PLUS, so worker contributions diverge modestly
(HK$33.07 / 43.75 / 45.00) — plans differentiate mainly on **coverage (60/80/90%) and payout
caps**, with the platform subsidy carrying most of the difference.

Payouts are additionally floored at HK$40 (anything smaller is topped up) and rounded to the
nearest HK$1 (`config.PAYOUT`).

## Why no personal characteristics are used

Pricing uses **district, environment, income exposure and plan** — nothing else. No age,
gender, health, claims history, or behavioural scoring:

- **Parametric by design.** Payouts follow an objective external trigger, not individual loss
  adjustment, so individual risk classification adds cost without adding accuracy.
- **Same district + income + plan ⇒ same price.** Simple to explain to riders, platforms and
  regulators; structurally avoids protected-class discrimination.
- **Income exposure is not a personal rating factor.** Weekly income only sizes the *benefit*
  (income replacement) and therefore the expected loss — it is the quantity being insured.

A commercial product would still require actuarial validation and regulatory filing; this
prototype only demonstrates the mechanics.

## Sensitivity of premium to district and season

Same STANDARD rider (HK$3,360/wk), moving only one variable at a time (EL scales ∝ district
base_risk and ∝ season multiplier; approximate):

| District (base_risk) | Gross premium | | Season | Gross premium |
|---|---:|---|---|---:|
| Mong Kok (0.62) | **HK$273.42** | | Wet season (×1.45) | **HK$273.42** |
| Kwun Tong (0.50) | ≈ HK$222 | | Summer (×1.05) | ≈ HK$200 |
| Tsuen Wan (0.40) | ≈ HK$179 | | Winter (×0.75) | ≈ HK$145 |
| Central (0.30) | ≈ HK$136 | | | |

Premium scales with income in the same way (higher income ⇒ larger expected payout ⇒ larger
expected loss). The fleet-blended average used by the business model (HK$200) sits **below**
this quote because Mong Kok is the fleet's highest-risk district. Above HK$281.25 gross the
HK$45 worker cap binds, so further district/season/income sensitivity is absorbed by the
platform subsidy, not passed to the rider.

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
