-- RideShield demo database schema (SQLite).
-- All IDs are human-readable TEXT ids (e.g. W-000001, Z-MK, EV-20261003-001).
-- Every monetary value is INR.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS platforms (
    platform_id      TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    city             TEXT NOT NULL,
    subsidy_share    REAL NOT NULL,      -- platform share of gross premium
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS zones (
    zone_id          TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    city             TEXT NOT NULL,
    base_risk        REAL NOT NULL,
    flood_propensity REAL NOT NULL,
    heat_propensity  REAL NOT NULL,
    aqi_propensity   REAL NOT NULL,
    historical_events_per_year INTEGER NOT NULL,
    traffic_index    REAL NOT NULL,
    delivery_density REAL NOT NULL,
    accessibility    REAL NOT NULL,
    map_x REAL, map_y REAL, map_w REAL, map_h REAL
);

CREATE TABLE IF NOT EXISTS workers (
    worker_id        TEXT PRIMARY KEY,
    platform_id      TEXT NOT NULL REFERENCES platforms(platform_id),
    home_zone_id     TEXT NOT NULL REFERENCES zones(zone_id),
    name             TEXT NOT NULL,
    weekly_income    REAL NOT NULL,
    weekly_hours     REAL NOT NULL,
    avg_hourly_income REAL NOT NULL,     -- weekly_income / weekly_hours
    tenure_weeks     REAL NOT NULL,
    fps_handle       TEXT NOT NULL,      -- fictional demo handle
    active           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS policies (
    policy_id        TEXT PRIMARY KEY,
    worker_id        TEXT NOT NULL REFERENCES workers(worker_id),
    plan             TEXT NOT NULL,             -- BASIC | STANDARD | PLUS
    coverage_factor  REAL NOT NULL,
    max_payout_per_event REAL NOT NULL,
    weekly_coverage_limit REAL NOT NULL,
    status           TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | EXPIRED | LAPSED
    week_start       TEXT NOT NULL,
    week_end         TEXT NOT NULL,
    UNIQUE(worker_id, week_start)
);

CREATE TABLE IF NOT EXISTS weekly_plans (
    plan_id          TEXT PRIMARY KEY,          -- worker_id + week_start
    worker_id        TEXT NOT NULL REFERENCES workers(worker_id),
    week_start       TEXT NOT NULL,
    gross_premium    REAL NOT NULL,             -- computed by pricing engine
    expected_loss    REAL NOT NULL,
    operating_cost   REAL NOT NULL,
    fraud_reserve    REAL NOT NULL,
    risk_margin      REAL NOT NULL,
    platform_subsidy REAL NOT NULL,
    worker_contribution REAL NOT NULL,
    UNIQUE(worker_id, week_start)
);

CREATE TABLE IF NOT EXISTS weather_events (
    event_id         TEXT PRIMARY KEY,
    event_type       TEXT NOT NULL,             -- key from config.TRIGGERS or 'NONE'
    scenario_key     TEXT,                      -- preset key if launched from a preset
    city             TEXT NOT NULL,
    zone_id          TEXT NOT NULL REFERENCES zones(zone_id),
    rainfall_mm      REAL NOT NULL,
    rainfall_intensity REAL NOT NULL,
    temperature_c    REAL NOT NULL,
    humidity         REAL NOT NULL,
    wind_speed_kmh   REAL NOT NULL,
    aqi              REAL NOT NULL,
    flood_probability REAL NOT NULL,
    cyclone_probability REAL NOT NULL,
    duration_h       REAL NOT NULL,
    platform_availability_pct REAL NOT NULL,
    zone_closure     INTEGER NOT NULL DEFAULT 0,
    data_source      TEXT NOT NULL DEFAULT 'SIMULATED',  -- REAL API | MOCK DATA | SIMULATED | USER INPUT
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risk_assessments (
    assessment_id    TEXT PRIMARY KEY,
    event_id         TEXT REFERENCES weather_events(event_id),  -- NULL for ambient assessments
    zone_id          TEXT NOT NULL REFERENCES zones(zone_id),
    risk_score       REAL NOT NULL,             -- 0-100
    risk_level       TEXT NOT NULL,             -- LOW | MODERATE | HIGH | SEVERE
    expected_disruption_hours REAL NOT NULL,
    expected_income_loss REAL NOT NULL,         -- per affected rider, HK$
    expected_payout  REAL NOT NULL,             -- per affected rider, HK$
    confidence_score REAL NOT NULL,             -- 0-1
    risk_factors     TEXT NOT NULL,             -- JSON [{label, points}]
    explanation      TEXT NOT NULL,             -- natural-language "why"
    model_version    TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS triggers (
    trigger_id       TEXT PRIMARY KEY,
    event_id         TEXT NOT NULL REFERENCES weather_events(event_id),
    zone_id          TEXT NOT NULL REFERENCES zones(zone_id),
    trigger_type     TEXT NOT NULL,             -- key from config.TRIGGERS
    threshold_desc   TEXT NOT NULL,             -- e.g. "rainfall_mm >= 90.0"
    observed_value   TEXT NOT NULL,             -- e.g. "95.0"
    fired            INTEGER NOT NULL,          -- 1 fired / 0 evaluated-but-not-fired
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id         TEXT PRIMARY KEY,
    event_id         TEXT NOT NULL REFERENCES weather_events(event_id),
    worker_id        TEXT NOT NULL REFERENCES workers(worker_id),
    policy_id        TEXT NOT NULL REFERENCES policies(policy_id),
    zone_id          TEXT NOT NULL REFERENCES zones(zone_id),
    eligible         INTEGER NOT NULL,
    ineligibility_reason TEXT,
    affected_hours   REAL NOT NULL,
    income_loss      REAL NOT NULL,
    payout_amount    REAL NOT NULL,
    status           TEXT NOT NULL,             -- PENDING | APPROVED | HELD | PAID | REJECTED | INELIGIBLE
    idempotency_key  TEXT NOT NULL UNIQUE,      -- worker_id + event_id + policy_id
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payouts (
    payout_id        TEXT PRIMARY KEY,
    claim_id         TEXT NOT NULL REFERENCES claims(claim_id),
    worker_id        TEXT NOT NULL REFERENCES workers(worker_id),
    event_id         TEXT NOT NULL REFERENCES weather_events(event_id),
    amount           REAL NOT NULL,
    method           TEXT NOT NULL DEFAULT 'FPS (SIMULATED)',
    status           TEXT NOT NULL DEFAULT 'SENT',  -- SENT | FAILED | HELD
    idempotency_key  TEXT NOT NULL UNIQUE,      -- same key as claim → duplicate impossible
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fraud_checks (
    check_id         TEXT PRIMARY KEY,
    claim_id         TEXT NOT NULL REFERENCES claims(claim_id),
    worker_id        TEXT NOT NULL REFERENCES workers(worker_id),
    event_id         TEXT NOT NULL REFERENCES weather_events(event_id),
    fraud_score      REAL NOT NULL,             -- 0-100
    risk_band        TEXT NOT NULL,             -- LOW | MEDIUM | HIGH
    signals          TEXT NOT NULL,             -- JSON [{signal, points, detail}]
    action           TEXT NOT NULL,             -- AUTO_APPROVE | HOLD_FOR_REVIEW
    review_status    TEXT,                      -- NULL | APPROVED | REJECTED | INVESTIGATING
    reviewed_by      TEXT,
    reviewed_at      TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS premium_ledger (      -- seeded weekly history + live weeks
    ledger_id        TEXT PRIMARY KEY,
    week_start       TEXT NOT NULL,
    platform_id      TEXT NOT NULL REFERENCES platforms(platform_id),
    riders_covered   INTEGER NOT NULL,
    premium_collected REAL NOT NULL,            -- platform subsidy + worker contribution
    platform_subsidy REAL NOT NULL,
    worker_contribution REAL NOT NULL,
    expected_claims  REAL NOT NULL,
    actual_claims    REAL NOT NULL,
    fraud_prevented  REAL NOT NULL,             -- HK$ value of held-and-rejected fraud
    UNIQUE(week_start, platform_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id         TEXT PRIMARY KEY,
    event_code       TEXT NOT NULL,             -- WEATHER_RECEIVED, RISK_CALCULATED, ...
    entity_type      TEXT NOT NULL,
    entity_id        TEXT NOT NULL,
    detail           TEXT NOT NULL,             -- JSON payload
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Idempotency hard-stop at the DB level (in addition to UNIQUE columns above).
CREATE UNIQUE INDEX IF NOT EXISTS idx_claims_idem ON claims(idempotency_key);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payouts_idem ON payouts(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_workers_zone ON workers(home_zone_id);
CREATE INDEX IF NOT EXISTS idx_claims_event ON claims(event_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);
