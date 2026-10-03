# RideShield — Setup & Run

## Prerequisites

| Requirement | Notes |
|---|---|
| Python **3.9+** | check with `python3 --version` |
| pip | ships with Python; used inside the venv |
| ~200 MB disk | venv + dependencies |

That's all. **No Node.js, no build step, no database server, no API keys.** The frontend is a
static no-build SPA served by FastAPI; the database is a local SQLite file created on first run;
all weather and fleet data is simulated deterministically.

## Install & run

```bash
cd rideshield
./start.sh
```

`start.sh` does exactly three things:

1. creates `.venv/` if it doesn't exist (`python3 -m venv .venv`),
2. installs `requirements.txt` into it (first run only),
3. starts uvicorn: `.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}`.

Then open **http://localhost:8000**.

### Manual equivalent

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Different port

```bash
PORT=8001 ./start.sh
```

`PORT` can also live in `.env` — see `.env.example`. All environment variables are optional.

## Running the tests

```bash
./run_tests.sh          # or: .venv/bin/pytest -q
```

The suite covers engine math, API contract shapes and payout idempotency.

## Resetting the demo

Three equivalent ways, easiest first:

1. **UI:** the **RESET DEMO** button (also runs automatically when Judge Mode starts).
2. **API:** `curl -X POST http://localhost:8000/api/simulation/reset`
3. **Hard reset:** stop the server, delete the database file, restart — it re-seeds on startup:

   ```bash
   rm rideshield.db rideshield.db-wal rideshield.db-shm 2>/dev/null; ./start.sh
   ```

Reset clears events, claims, payouts, fraud checks, audit rows and risk assessments, and
restores the deterministic baseline (12,482 riders, 12-week ledger, the pre-demo Mong Kok
rainstorm event, HK$196.5K fraud-prevented card). Because the seed is fixed (42), every reset produces
byte-identical demo data.

## Configuration

Everything tunable lives in **`backend/config.py`** — nothing financial is hardcoded elsewhere:

- `DEMO` — fleet size, seed, demo rider, season
- `ZONES` — 10 fictional zones with propensities and map coordinates
- `TRIGGERS` — parametric trigger rules (thresholds, durations, any/all)
- `RISK_MODEL` — factor weights, normalizers, caps, level bands
- `COVERAGE_LEVELS` / `PAYOUT` — plan coverage factors, caps, minimums
- `PRICING` — operating cost, fraud reserve, risk margin, subsidy share, worker cap
- `FRAUD` — signal points, hold threshold
- `VIABILITY` / `STRESS_SCENARIOS` — business-simulator defaults
- `SCENARIOS` / `JUDGE_EVENT` — simulation presets and the canonical judge event

Edit values and restart the server; every engine, dashboard and document number derives from
this file.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Address already in use` / port 8000 busy | `PORT=8001 ./start.sh`, or free the port: `lsof -ti :8000 \| xargs kill` |
| `python3: command not found` or version < 3.9 | Install Python 3.9+ (python.org, `brew install python@3.13`, etc.), then retry |
| Broken/stale venv (e.g. Python upgraded) | `rm -rf .venv && ./start.sh` — it rebuilds from scratch |
| `uvicorn: command not found` | You activated nothing — always run via `.venv/bin/uvicorn` (or `./start.sh`) |
| `No module named fastapi` inside venv | `.venv/bin/pip install -r requirements.txt` |
| Database looks corrupt / want a clean slate | Stop server, `rm rideshield.db*` (see Hard reset above) — the DB is disposable and re-seeded |
| pip install fails on network/SSL | Retry on a different network, or `pip install --index-url https://pypi.org/simple -r requirements.txt` |
| Tests fail after editing `config.py` | Some tests assert canonical demo numbers (risk ≈ 90, payout HK$397). Restore the values or update expectations |

---

*Prototype simulation. Commercial deployment would require appropriate insurance
licensing/partnerships, actuarial validation, regulatory approval, data protection controls
and contractual integration with participating platforms.*
