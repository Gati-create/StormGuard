# RideShield — Demo Script (~3 minutes)

A timed run of show for presenting to judges. Everything is deterministic (seed 42), so the
numbers below are the numbers on screen. Judge Mode automates the sequence (10 guided stages);
this script works with or without it.

**Pre-flight (30 s before starting):** open `http://localhost:8000`, click **RESET DEMO** (or
start Judge Mode, which resets automatically). Confirm Fleet Risk shows 12,482 riders and a
≈18% loss ratio. One narratable detail: claims are non-zero at open because a moderate
Amber/Red Rainstorm event hit Mong Kok (72 mm in 4 h, flood probability 48%) three days
earlier in the seeded week — the books are already live.

## Run of show

| # | Time | Screen / action | Key beat |
|---|---|---|---|
| 1 | 0:00–0:15 | **Fleet Risk** | Normal week: 12,482 riders, HK$2.63M premium, loss ratio 18% |
| 2 | 0:15–0:25 | **SIMULATE DISRUPTION** → Black Rainstorm, Mong Kok | 95 mm in 4 h, flood probability 82% |
| 3 | 0:25–1:35 | Pipeline animates (9 stages) | Risk 90 → trigger → 3,148 affected → 3,033 approved / 71 held → HK$885K paid |
| 4 | 1:35–2:00 | **Rider Protection** | Jason Chan loses HK$496, receives HK$397 — FPS (DEMO / SIMULATED) |
| 5 | 2:00–2:25 | **Fleet/Insurer dashboards** | Loss ratio 18% → 52%; claims HK$473K → HK$1.36M |
| 6 | 2:25–2:45 | **Business Viability** + one sensitivity | Baseline vs +25% event frequency |
| 7 | 2:45–3:00 | Close | Why it matters; what is simulated |

## Detailed beats with speaker notes

### 1 — 0:00 — Fleet Risk, normal conditions

> "Twelve and a half thousand delivery riders in Hong Kong. The platform buys income protection
> for the whole fleet — riders pay at most HK$45 a week. This week: HK$2.63 million of premium,
> HK$473,000 of claims — an 18% loss ratio. A normal wet-season week. Watch what happens when
> it isn't."

*Why:* establish the B2B2C shape (platform buys, riders protected) and the baseline numbers
every later delta is measured against.

### 2 — 0:15 — SIMULATE DISRUPTION

Select **Black Rainstorm** (or run Judge Mode) — Mong Kok, 95 mm in 4 hours, flood
probability 82%.

> "A black rainstorm parks over Mong Kok — our highest-risk, highest-density district. No rider
> calls anyone. No claim is filed. The system just watches the weather."

### 3 — 0:25 — The 9-stage pipeline

Let the stages animate. One sentence per stage — the pattern to keep repeating is
**what happened / why / what the system did**:

| Stage | Say this |
|---|---|
| **WEATHER** | "The event lands: 95 mm, 4 hours, 82% flood probability — labeled SIMULATED, because we fake nothing." |
| **RISK** | "The risk model scores it **90 out of 100 — SEVERE**. And it shows its work: +30 rainfall, +22 flood probability, +14 district history, +9 traffic, +6 wind, +6 duration, +2 AQI, +1 worker exposure. Every point explained — no black box." |
| **EXPOSURE** | "It propagates the signal to neighbouring districts with attenuation, and sizes the damage: **3,148 riders** in the disruption window — Mong Kok 1,685, Sham Shui Po 1,463 — **≈ HK$1.69 million** of income at risk." |
| **TRIGGER** | "The Black Rainstorm trigger fires: rainfall ≥ 90 mm, flood probability ≥ 0.75 — HKO Black Rainstorm territory. Objective, pre-agreed, no adjusters. This is the moment a parametric product becomes a promise." |
| **ELIGIBILITY** | "3,148 riders checked: active policy, right district, actually scheduled in the window. 3,104 qualify. Not pay-for-not-working — pay-for-*couldn't*-work." |
| **FRAUD** | "Every claim gets an anomaly score. **3,033 auto-approved; 71 held** — GPS mismatches, impossible travel, duplicates. Nothing held is paid; a human risk manager reviews each one." |
| **APPROVAL** | "Clean claims approve in bulk. The 71 stay frozen in the review queue." |
| **PAYOUT** | "**HK$885,000** goes out — average HK$292 per rider — idempotently: one rider, one event, one policy means one payout, enforced by a database unique key. Double-click, retry, re-run — never a double payment." |
| **FINANCE** | "And the business feels it instantly: weekly claims jump HK$473K to HK$1.36M, loss ratio 18% to ~52%." |

*What the AI did:* scored and explained the risk, propagated exposure, screened 3,104 claims
for fraud in one pass.
*What the business did:* nothing manually — premium collected in quiet weeks funded a bad day
automatically; the audit log recorded every decision.

### 4 — 1:35 — Rider Protection dashboard

> "Zoom into one rider. Jason Chan, Mong Kok, HK$3,360 a week, STANDARD plan — HK$44 a week out
> of his pocket, with the platform carrying the other HK$230 of his HK$273 premium. The storm
> cost him **HK$496**. He was credited **HK$397** — 80% coverage — straight to
> FPS. Labeled DEMO, obviously. For Jason, a rained-out evening is a bad day, not a missed
> rent payment."

*What the rider received:* 80% of his verified loss, within minutes, with zero paperwork.

### 5 — 2:00 — Fleet / Insurer dashboards

> "The risk-carrier view: premium HK$2.63M against claims now HK$1.36M — loss ratio 51.6%. The
> trend chart shows twelve weeks of history; fraud controls have already saved HK$196.5K this
> season. One bad week is exactly what the 15% risk reserve exists for."

### 6 — 2:25 — Business Viability + one sensitivity

> "Does the model survive its own product? Baseline: 51.75% loss ratio, HK$512K weekly
> contribution, break-even at ~1,465 riders against 12,482 enrolled. Now shock it — severe
> weather, event frequency **+25%**: loss ratio climbs to ~65%, contribution falls by nearly
> two-thirds to HK$182K, and the model still clears break-even. That — plus the 34% risk margin
> in every premium — is why this is underwritable."

### 7 — 2:45 — Close

> "Parametric triggers make payouts instant and objective. Additive, explainable models make
> every decision auditable. Humans stay in the loop exactly where judgment matters — fraud
> review. Everything you saw is simulated and deterministic; the disclaimer is on every screen.
> Commercially, this would ride on a licensed insurance partner with actuarial validation.
> RideShield: protect the income behind every delivery."

## Recovery moves

| Situation | Move |
|---|---|
| State looks stale / wrong from a previous run | **RESET DEMO** button (or `POST /api/simulation/reset`) — restores the exact deterministic baseline in < 1 s, then re-run |
| Running long / audience wants the ending | Judge Mode **SKIP TO PAYOUT** (rider impact + HK$885K), **SKIP TO FRAUD** (71 held, review queue), or **SKIP TO BUSINESS** (viability) buttons |
| Live pipeline animation misbehaves | The backend already completed all 9 stages synchronously — refresh; the event, claims and dashboards are persisted, nothing is lost |
| Asked to re-run the simulation | Safe: re-running creates a *new* event but can never double-pay (idempotency keys). Or reset first for identical numbers |
| Server dies | `./start.sh`; the SQLite DB persists. Reset to restore canonical numbers |
| Numbers differ from script | Someone edited `backend/config.py` — restore it; every number derives from that file |

## Q&A defense points

- **"Can it double-pay?"** No. Idempotency key = worker + event + policy, enforced by a UNIQUE
  constraint and unique indexes at the database level. Retries, double-clicks and re-runs are
  no-ops. There's a test for it.
- **"Is the AI a black box?"** There is no black box. The risk score is a visible sum of
  labeled points (+30 rainfall, +22 flood probability, +14 district history, …), every payout
  traces to a trigger rule, and every
  decision is in the audit log. `/api/model/card` states plainly:
  `trained_on_real_data: false`.
- **"Is this fake AI?"** No fake anything. It's a deterministic demo model — version
  `demo-deterministic-1.0` — with a documented swap path to XGBoost/LightGBM behind the same
  assessment contract, SHAP feeding the same explainability panel. Weather is labeled
  SIMULATED; payouts are labeled DEMO/SIMULATED.
- **"Where is the human?"** Fraud score ≥ 60 → HOLD_FOR_REVIEW; held money does not move until
  a risk manager approves or rejects. Thresholds and prices change only through reviewed
  config changes.
- **"Regulatory path?"** This is a prototype. A real product would be structured with a
  licensed insurer carrying the risk (authorization from the Hong Kong Insurance Authority,
  likely via a parametric pilot), actuarial
  validation of the pricing, data-protection controls for worker data, and contracts with each
  participating platform. That's printed in the disclaimer on every screen.
- **"Why would the platform pay 84%?"** Cheaper than churn. It buys fleet stability through
  bad weather, predictable weekly cost instead of ad-hoc relief, and a benefit riders actually
  feel — see Business Viability for the math.
- **"What stops riders from claiming without working?"** Three things: an objective external
  trigger, verified scheduled overlap with the disruption window, and the fraud engine's
  anomaly scoring with human review.

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
