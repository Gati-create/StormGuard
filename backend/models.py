"""Pydantic request models (Python 3.9 compatible)."""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WeatherSignal(BaseModel):
    # All fields optional: a simulation request may partially specify the
    # signal; missing keys fall back to the scenario / ambient defaults.
    rainfall_mm: Optional[float] = Field(default=None, ge=0)
    rainfall_intensity: Optional[float] = Field(default=None, ge=0)
    temperature_c: Optional[float] = None
    humidity: Optional[float] = Field(default=None, ge=0, le=100)
    wind_speed_kmh: Optional[float] = Field(default=None, ge=0)
    aqi: Optional[float] = Field(default=None, ge=0)
    flood_probability: Optional[float] = Field(default=None, ge=0, le=1)
    cyclone_probability: Optional[float] = Field(default=None, ge=0, le=1)
    duration_h: Optional[float] = Field(default=None, gt=0)
    platform_availability_pct: Optional[float] = Field(default=None, ge=0, le=100)
    zone_closure: Optional[bool] = None


class SimulateOverrides(BaseModel):
    affected_riders: Optional[int] = Field(default=None, ge=0)
    coverage_factor: Optional[float] = Field(default=None, gt=0, le=1)
    platform_subsidy_share: Optional[float] = Field(default=None, ge=0, le=1)


class SimulateRequest(BaseModel):
    zone_id: Optional[str] = None
    scenario_key: Optional[str] = None
    weather: Optional[WeatherSignal] = None
    overrides: Optional[SimulateOverrides] = None


class QuoteRequest(BaseModel):
    plan: str
    zone_id: str
    weekly_income: float = Field(gt=0)
    weekly_hours: float = Field(gt=0)
    subsidy_share: Optional[float] = Field(default=None, ge=0, le=1)


class ReviewRequest(BaseModel):
    decision: str  # APPROVED | REJECTED | INVESTIGATING
    reviewer: str = "Risk Manager"


class ViabilityRequest(BaseModel):
    riders: Optional[int] = Field(default=None, gt=0)
    avg_weekly_income: Optional[float] = Field(default=None, gt=0)
    avg_gross_premium: Optional[float] = Field(default=None, gt=0)
    platform_subsidy_share: Optional[float] = Field(default=None, ge=0, le=1)
    weekly_event_probability: Optional[float] = Field(default=None, ge=0)
    avg_payout: Optional[float] = Field(default=None, ge=0)
    operating_cost_rate: Optional[float] = Field(default=None, ge=0)
    fraud_loss_rate: Optional[float] = Field(default=None, ge=0)


class Shock(BaseModel):
    key: str
    mult: float = Field(gt=0)
    label: Optional[str] = None


class SensitivityRequest(BaseModel):
    base: Optional[Dict[str, float]] = None
    shocks: List[Shock] = Field(default_factory=list)
