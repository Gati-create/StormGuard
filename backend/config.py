"""
RideShield — centralized demo assumptions & configuration (Hong Kong edition).

EVERY threshold, weight, price component and demo constant lives here.
Changing a value in this file propagates through the risk engine,
trigger engine, pricing engine, payout engine, fraud engine and all
dashboards. Nothing financial is hardcoded elsewhere.

All monetary values are in Hong Kong dollars (HK$). All data is fictional demo data.
"""

BRAND = {
    "name": "RideShield",
    "tagline": "Protect the income behind every delivery.",
    "product_line": "B2B RIDER INCOME PROTECTION",
}

CURRENCY = "HK$"

# ---------------------------------------------------------------------------
# Demo environment
# ---------------------------------------------------------------------------
DEMO = {
    "city": "Hong Kong",
    "total_riders": 12482,          # seeded fleet size
    "random_seed": 42,              # deterministic seed for ALL generated data
    "ledger_weeks": 12,             # weeks of seeded premium/claims history
    "demo_rider_id": "W-000001",    # rider shown on the Rider dashboard
    "season": "wet",                # wet | dry | hot  (Hong Kong wet season May–Sep = typhoon/rainstorm season)
}

# Season multipliers applied to event probabilities (wet season = typhoon/rain-heavy).
SEASONALITY = {"wet": 1.45, "dry": 0.75, "hot": 1.05}

# ---------------------------------------------------------------------------
# Zones (fictional Hong Kong delivery districts, with SVG-map coordinates)
# base_risk: 0-1 long-run disruption propensity of the zone.
# flood_propensity / heat_propensity / aqi_propensity: 0-1 susceptibilities.
# historical_events_per_year drives expected-loss pricing.
# x, y, w, h: rectangle position on the simulated city map (viewBox 0 0 400 300)
# Map layout is schematic: New Territories on top, Kowloon in the middle,
# Hong Kong Island along the bottom.
# ---------------------------------------------------------------------------
ZONES = [
    {"id": "Z-MK",  "name": "Mong Kok",       "base_risk": 0.62, "flood_propensity": 0.85, "heat_propensity": 0.40, "aqi_propensity": 0.55, "historical_events_per_year": 9,  "traffic_index": 0.72, "delivery_density": 0.91, "accessibility": 0.68, "x": 175, "y": 150, "w": 90,  "h": 55},
    {"id": "Z-SSP", "name": "Sham Shui Po",   "base_risk": 0.55, "flood_propensity": 0.78, "heat_propensity": 0.38, "aqi_propensity": 0.45, "historical_events_per_year": 8,  "traffic_index": 0.58, "delivery_density": 0.79, "accessibility": 0.72, "x": 75,  "y": 145, "w": 90,  "h": 50},
    {"id": "Z-TST", "name": "Tsim Sha Tsui",  "base_risk": 0.48, "flood_propensity": 0.60, "heat_propensity": 0.42, "aqi_propensity": 0.50, "historical_events_per_year": 6,  "traffic_index": 0.66, "delivery_density": 0.84, "accessibility": 0.75, "x": 130, "y": 210, "w": 85,  "h": 45},
    {"id": "Z-WC",  "name": "Wan Chai",       "base_risk": 0.44, "flood_propensity": 0.50, "heat_propensity": 0.50, "aqi_propensity": 0.62, "historical_events_per_year": 5,  "traffic_index": 0.74, "delivery_density": 0.72, "accessibility": 0.70, "x": 185, "y": 260, "w": 95,  "h": 35},
    {"id": "Z-KT",  "name": "Kwun Tong",      "base_risk": 0.50, "flood_propensity": 0.70, "heat_propensity": 0.36, "aqi_propensity": 0.48, "historical_events_per_year": 7,  "traffic_index": 0.62, "delivery_density": 0.68, "accessibility": 0.66, "x": 275, "y": 140, "w": 105, "h": 55},
    {"id": "Z-CEN", "name": "Central",        "base_risk": 0.30, "flood_propensity": 0.30, "heat_propensity": 0.44, "aqi_propensity": 0.42, "historical_events_per_year": 3,  "traffic_index": 0.50, "delivery_density": 0.55, "accessibility": 0.82, "x": 80,  "y": 260, "w": 95,  "h": 35},
    {"id": "Z-TP",  "name": "Tai Po",         "base_risk": 0.26, "flood_propensity": 0.35, "heat_propensity": 0.52, "aqi_propensity": 0.58, "historical_events_per_year": 3,  "traffic_index": 0.42, "delivery_density": 0.44, "accessibility": 0.78, "x": 265, "y": 15,  "w": 110, "h": 55},
    {"id": "Z-TW",  "name": "Tsuen Wan",      "base_risk": 0.40, "flood_propensity": 0.55, "heat_propensity": 0.34, "aqi_propensity": 0.40, "historical_events_per_year": 5,  "traffic_index": 0.55, "delivery_density": 0.63, "accessibility": 0.80, "x": 20,  "y": 85,  "w": 100, "h": 55},
    {"id": "Z-ST",  "name": "Sha Tin",        "base_risk": 0.36, "flood_propensity": 0.45, "heat_propensity": 0.46, "aqi_propensity": 0.52, "historical_events_per_year": 4,  "traffic_index": 0.68, "delivery_density": 0.58, "accessibility": 0.64, "x": 265, "y": 80,  "w": 110, "h": 50},
    {"id": "Z-YL",  "name": "Yuen Long",      "base_risk": 0.42, "flood_propensity": 0.65, "heat_propensity": 0.40, "aqi_propensity": 0.55, "historical_events_per_year": 6,  "traffic_index": 0.70, "delivery_density": 0.60, "accessibility": 0.74, "x": 20,  "y": 15,  "w": 105, "h": 60},
]

# ---------------------------------------------------------------------------
# Worker generation profile (fictional riders are sampled from these)
# HK food-delivery riders: ~HK$80/hour, long flexible weeks.
# ---------------------------------------------------------------------------
WORKER_PROFILE = {
    "weekly_income_mean": 3600.0, "weekly_income_sd": 550.0,
    "weekly_income_min": 2200.0,  "weekly_income_max": 5800.0,
    "weekly_hours_mean": 42.0,    "weekly_hours_sd": 5.0,
    "weekly_hours_min": 28.0,     "weekly_hours_max": 60.0,
    "tenure_weeks_mean": 58.0,    "tenure_weeks_sd": 30.0,
    "tenure_weeks_min": 4.0,      "tenure_weeks_max": 220.0,
    # plan mix across the fleet
    "plan_mix": {"BASIC": 0.22, "STANDARD": 0.61, "PLUS": 0.17},
}

# ---------------------------------------------------------------------------
# Parametric trigger rules — each independently configurable.
# `params` are evaluated against the incoming weather/operational signal.
# HK references: HKO Black Rainstorm ≥70mm/h; Typhoon Signal No. 8 at ≥63 km/h;
# HKO Very Hot Weather Warning at 33°C.
# ---------------------------------------------------------------------------
TRIGGERS = {
    "HEAVY_RAIN":         {"label": "Amber/Red Rainstorm", "params": {"rainfall_mm": (">=", 64.5)}},
    "EXTREME_RAIN_FLOOD": {"label": "Black Rainstorm",     "params": {"rainfall_mm": (">=", 90.0), "flood_probability": (">=", 0.75)}, "any": True},
    "EXTREME_HEAT":       {"label": "Extreme Heat",        "params": {"temperature_c": (">=", 35.0)}, "duration_h": 2},
    "SEVERE_AQI":         {"label": "Severe AQI",          "params": {"aqi": (">=", 300)}},
    "CYCLONE":            {"label": "Typhoon (T8+)",       "params": {"wind_speed_kmh": (">=", 62.0), "cyclone_probability": (">=", 0.60)}, "any": True},
    "ZONE_CLOSURE":       {"label": "Zone Closure",        "params": {"zone_closure": ("==", True)}},
    "PLATFORM_OUTAGE":    {"label": "Platform Outage",     "params": {"platform_availability_pct": ("<", 85.0)}},
}

# ---------------------------------------------------------------------------
# Deterministic demo risk model (drop-in replaceable by XGBoost/LightGBM).
# Weighted additive score → 0-100. Each factor contributes points and is
# surfaced verbatim in the explainability output.
# ---------------------------------------------------------------------------
# Factor points = weight × min(value / normalizer, cap).
# "contextual" factors (zone_history, traffic, time_exposure, worker_exposure)
# are additionally multiplied by the event activation level:
#   activation = clamp(max(param_value / trigger_threshold across params), 0, 1)
# so a calm day scores LOW while a threshold-breaching event scores HIGH/SEVERE.
RISK_MODEL = {
    "version": "demo-deterministic-1.0",
    "trained_on_real_data": False,
    "levels": [  # (min_score_inclusive, level)
        (75, "SEVERE"), (50, "HIGH"), (25, "MODERATE"), (0, "LOW"),
    ],
    "factors": {
        "rainfall":           {"weight": 31, "normalizer": 97.0,  "cap": 1.6, "label": "Extreme rainfall",      "contextual": False},
        "flood_probability":  {"weight": 22, "normalizer": 0.82,  "cap": 1.3, "label": "Flood probability",     "contextual": False},
        "zone_history":       {"weight": 14, "normalizer": 0.85,  "cap": 1.0, "label": "Historical zone risk",  "contextual": True},
        "traffic":            {"weight": 9,  "normalizer": 0.72,  "cap": 1.0, "label": "Traffic disruption",    "contextual": True},
        "heat":               {"weight": 18, "normalizer": 5.0,   "cap": 1.2, "label": "Extreme heat",          "contextual": False},  # value = °C above 33
        "aqi":                {"weight": 12, "normalizer": 400.0, "cap": 1.3, "label": "Air pollution",         "contextual": False},
        "wind":               {"weight": 13, "normalizer": 80.0,  "cap": 1.3, "label": "Wind / typhoon",        "contextual": False},
        "time_exposure":      {"weight": 6,  "normalizer": 4.0,   "cap": 1.0, "label": "Time exposure",         "contextual": True},   # value = duration_h
        "worker_exposure":    {"weight": 5,  "normalizer": 1.0,   "cap": 1.0, "label": "Worker exposure",       "contextual": True},   # value = loss/weekly income
    },
    "confidence_base": 0.78,        # + up to +0.1 for data completeness, − for source conflict
}

# How weather turns into lost hours and payouts.
DISRUPTION = {
    "hours_multiplier": 1.55,        # affected_hours = duration_h × multiplier (secondary effects)
    "max_disruption_hours": 9.0,
    # Riders are not all scheduled during the disruption window. Per-rider
    # scheduled overlap is sampled U(min, max) (deterministic per worker_id).
    "overlap_min": 0.40, "overlap_max": 1.00, "overlap_mean": 0.74,
    "demo_rider_overlap": 1.00,      # demo rider was working the full window
}

# Attenuation of a weather signal as it spreads from the epicenter zone to
# neighbouring zones, by the zone's relevant propensity for the event type.
ZONE_ATTENUATION = [
    (0.75, 0.75),   # propensity >= 0.75 → signal × 0.75
    (0.50, 0.50),   # propensity >= 0.50 → signal × 0.50
    (0.00, 0.30),   # otherwise          → signal × 0.30
]

# ---------------------------------------------------------------------------
# Coverage plans — limits & factors, NOT arbitrary prices (prices are computed)
# ---------------------------------------------------------------------------
COVERAGE_LEVELS = {
    "BASIC":    {"coverage_factor": 0.60, "max_payout_per_event": 560,  "weekly_coverage_limit": 1760},
    "STANDARD": {"coverage_factor": 0.80, "max_payout_per_event": 1200, "weekly_coverage_limit": 2720},
    "PLUS":     {"coverage_factor": 0.90, "max_payout_per_event": 1760, "weekly_coverage_limit": 3840},
}

PAYOUT = {
    "min_payout": 40.0,             # HK$ — below this, payout is rounded up to min
    "rounding": 1.0,                # round payouts to nearest HK$1
}

# ---------------------------------------------------------------------------
# Premium construction:  ExpectedLoss + OperatingCost + FraudReserve + RiskMargin
# ExpectedLoss(rider-week) = P(trigger event in week) × E[payout | event]
# ---------------------------------------------------------------------------
PRICING = {
    "operating_cost_per_week": 6.4,      # HK$ per rider-week
    "fraud_reserve_rate": 0.12,          # × expected loss
    "risk_margin_rate": 0.34,            # × expected loss
    "subsidy_share": 0.84,               # platform share of gross premium
    "worker_affordability_cap": 45.0,    # HK$ — worker never pays more than this/week
    # P(a paid disruption event in a rider-week), fleet-average baseline.
    # Scaled per zone by (zone.base_risk / fleet_avg_base_risk) and by SEASONALITY.
    "base_weekly_event_probability": 0.30,
    # Typical event profile used by the pricing engine's E[payout | event].
    "typical_event_duration_h": 4.0,
}

# ---------------------------------------------------------------------------
# Fraud engine — additive anomaly scoring, human review above `hold_threshold`
# ---------------------------------------------------------------------------
FRAUD = {
    "hold_threshold": 60,            # score >= → HOLD FOR REVIEW
    "medium_threshold": 30,
    "base_suspicious_rate": 0.023,   # ~2.3% of claims flagged in demo scenarios
    "signals": {                     # signal → score points
        "gps_mismatch": 34,
        "impossible_travel": 40,
        "duplicate_event": 30,
        "duplicate_payout_attempt": 45,
        "unusual_claim_frequency": 22,
        "event_zone_mismatch": 28,
        "new_account_high_claim": 15,
        "historical_behaviour_flag": 18,
    },
}

# ---------------------------------------------------------------------------
# Business viability defaults (B2B profitability simulator)
# ---------------------------------------------------------------------------
VIABILITY = {
    "riders": 12482,
    "avg_weekly_income": 3360.0,
    "avg_gross_premium": 200.0,        # HK$/rider-week (blend of plans)
    "platform_subsidy_share": 0.84,
    "weekly_event_probability": 0.30,  # P(at least one paid event per rider-week) — fleet avg
    "avg_payout": 345.0,               # HK$ per paid claim
    "operating_cost_rate": 0.09,       # × premium revenue
    "fraud_loss_rate": 0.02,           # × expected claims (leakage after controls)
    "risk_reserve_rate": 0.15,         # × premium revenue, held as reserve
    "fixed_weekly_cost": 68000.0,      # HK$ — fixed ops/tech cost; drives break-even riders
    "weeks_per_year": 52,
}

# ---------------------------------------------------------------------------
# Stress-test scenario presets (Business Viability page)
# ---------------------------------------------------------------------------
STRESS_SCENARIOS = {
    "BASELINE":                    {"event_frequency_mult": 1.0,  "severity_mult": 1.0},
    "SEVERE_WEATHER":              {"event_frequency_mult": 1.25, "severity_mult": 1.2},
    "EXTREME_WEATHER":             {"event_frequency_mult": 1.5,  "severity_mult": 1.45},
    "HIGH_FREQUENCY":              {"event_frequency_mult": 1.8,  "severity_mult": 0.9},
    "LOW_FREQ_HIGH_SEVERITY":      {"event_frequency_mult": 0.7,  "severity_mult": 2.1},
}

# ---------------------------------------------------------------------------
# Demo scenario presets (Simulation page / Judge Mode)
# ---------------------------------------------------------------------------
SCENARIOS = {
    "NORMAL_DAY": {
        "label": "Normal Day", "zone_id": "Z-MK",
        "weather": {"rainfall_mm": 6, "rainfall_intensity": 2, "temperature_c": 30, "humidity": 78, "wind_speed_kmh": 14, "aqi": 92, "flood_probability": 0.12, "cyclone_probability": 0.02, "duration_h": 1.0, "platform_availability_pct": 99.9, "zone_closure": False},
    },
    "SEVERE_RAIN": {
        "label": "Red Rainstorm", "zone_id": "Z-MK",
        "weather": {"rainfall_mm": 72, "rainfall_intensity": 18, "temperature_c": 26, "humidity": 94, "wind_speed_kmh": 32, "aqi": 70, "flood_probability": 0.55, "cyclone_probability": 0.05, "duration_h": 3.0, "platform_availability_pct": 99.5, "zone_closure": False},
    },
    "EXTREME_FLOOD": {
        "label": "Black Rainstorm", "zone_id": "Z-MK",
        "weather": {"rainfall_mm": 95, "rainfall_intensity": 26, "temperature_c": 25, "humidity": 97, "wind_speed_kmh": 38, "aqi": 64, "flood_probability": 0.82, "cyclone_probability": 0.08, "duration_h": 4.0, "platform_availability_pct": 98.8, "zone_closure": False},
    },
    "BLACK_SWAN": {
        "label": "Black Swan (Super Typhoon)", "zone_id": "Z-MK",
        "weather": {"rainfall_mm": 160, "rainfall_intensity": 42, "temperature_c": 24, "humidity": 99, "wind_speed_kmh": 118, "aqi": 58, "flood_probability": 0.95, "cyclone_probability": 0.85, "duration_h": 9.0, "platform_availability_pct": 82.0, "zone_closure": True},
    },
}

# The canonical judge-demo event (matches the demo script numbers).
JUDGE_EVENT = {
    "city": "Hong Kong", "zone_id": "Z-MK", "zone_name": "Mong Kok",
    "event_type": "EXTREME_RAIN_FLOOD", "label": "Black Rainstorm",
    "rainfall_mm": 95, "duration_h": 4.0, "flood_probability": 0.82,
}

# ---------------------------------------------------------------------------
# Seeded history. The demo opens in "current underwriting week" state where a
# moderate event has ALREADY happened earlier in the week (so dashboards are
# non-empty before the presenter triggers the big demo event).
# ---------------------------------------------------------------------------
SEEDED_HISTORY = {
    # Event that already occurred earlier in the demo week.
    "pre_demo_event": {
        "event_type": "HEAVY_RAIN", "zone_id": "Z-MK", "label": "Red Rainstorm",
        "rainfall_mm": 72, "rainfall_intensity": 16, "temperature_c": 27,
        "humidity": 93, "wind_speed_kmh": 26, "aqi": 74,
        "flood_probability": 0.48, "cyclone_probability": 0.03,
        "duration_h": 4.0, "platform_availability_pct": 99.6, "zone_closure": False,
        "days_ago": 3,
    },
    # Season-to-date fraud that was held and rejected (feeds the fraud card).
    "fraud_prevented_to_date": 185000.0,
    # Past-week ledger variation (loss ratio random walk within this band).
    "past_week_loss_ratio_min": 0.34, "past_week_loss_ratio_max": 0.55,
}

DISCLAIMER = (
    "Prototype simulation. Commercial deployment would require appropriate "
    "insurance licensing/partnerships, actuarial validation, regulatory approval, "
    "data protection controls and contractual integration with participating platforms."
)
