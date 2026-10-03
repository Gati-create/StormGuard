"""Meta endpoints: health, public config, model card."""
from fastapi import APIRouter

from backend import config

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/config")
def public_config():
    return {
        "brand": config.BRAND,
        "disclaimer": config.DISCLAIMER,
        "triggers": config.TRIGGERS,
        "coverage_levels": config.COVERAGE_LEVELS,
        "pricing": config.PRICING,
        "risk_model": {
            "version": config.RISK_MODEL["version"],
            "trained_on_real_data": config.RISK_MODEL["trained_on_real_data"],
            "levels": config.RISK_MODEL["levels"],
        },
        "scenarios": config.SCENARIOS,
        "season": config.DEMO["season"],
        "currency": config.CURRENCY,
    }


@router.get("/model/card")
def model_card():
    rm = config.RISK_MODEL
    return {
        "purpose": "Parametric income-protection risk scoring for delivery riders: "
                   "estimates disruption-driven income loss per zone so payouts can "
                   "be released automatically when objective triggers fire.",
        "inputs": [
            "rainfall_mm", "rainfall_intensity", "temperature_c", "humidity",
            "wind_speed_kmh", "aqi", "flood_probability", "cyclone_probability",
            "duration_h", "platform_availability_pct", "zone_closure",
            "zone base_risk / flood / heat / AQI propensities", "traffic_index",
            "worker avg_hourly_income & weekly_income",
        ],
        "outputs": [
            "risk_score (0-100)", "risk_level (LOW|MODERATE|HIGH|SEVERE)",
            "expected_disruption_hours", "expected_income_loss", "expected_payout",
            "confidence_score", "risk_factors (explainability)", "explanation",
        ],
        "training_data_status": "Not trained on real data — deterministic weighted "
                                "additive model (%s), drop-in replaceable by an "
                                "ML model (e.g. XGBoost/LightGBM) behind the same "
                                "interface." % rm["version"],
        "limitations": [
            "Linear additive factors cannot capture interactions between hazards.",
            "Zone propensities are static demo assumptions, not fitted values.",
            "Scheduled-overlap of riders is simulated, not observed.",
            "Confidence score is a heuristic, not a calibrated probability.",
        ],
        "demo_assumptions": [
            "All weather data is SIMULATED or MOCK DATA; no external APIs are called.",
            "Fleet of %d fictional riders in %s." % (config.DEMO["total_riders"], config.DEMO["city"]),
            "Season multiplier: %s." % config.DEMO["season"],
            "Every payout is a simulated FPS transfer.",
        ],
        "bias_sources": [
            "Zone base-risk priors encode historical geography and may under/over-state "
            "risk for individual riders.",
            "Income-based payouts scale with earnings, so higher-earning riders receive "
            "larger payouts for the same event.",
            "Fraud signals may correlate with rider tenure and device quality.",
        ],
        "human_review_points": [
            "All claims scoring >= %d on the fraud engine are held for a human risk "
            "manager (HOLD_FOR_REVIEW)." % config.FRAUD["hold_threshold"],
            "Manual review decisions (APPROVED / REJECTED / INVESTIGATING) are "
            "recorded with reviewer identity.",
            "Model configuration changes require actuarial sign-off in production.",
        ],
        "architecture": ["INPUTS", "FEATURE ENGINEERING", "RISK MODEL",
                         "EXPLAINABILITY", "TRIGGER ENGINE", "PAYOUT ENGINE"],
    }
