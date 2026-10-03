"""Mock external providers. Every payload is labelled "MOCK DATA" and all
values are deterministic — each provider derives its RNG seed from its name
and arguments, so repeated calls return identical data."""
import hashlib
import random

from backend import config

MOCK = "MOCK DATA"


def _rng(*parts):
    return random.Random("mock:" + ":".join(str(p) for p in parts))


def _zone(zone_id):
    for z in config.ZONES:
        if z["id"] == zone_id:
            return z
    return config.ZONES[0]


def weather_current(zone_id):
    # Ambient conditions are mild on purpose: the ambient risk of every zone
    # must score LOW on a normal day.
    r = _rng("weather", zone_id)
    weather = {
        "rainfall_mm": round(r.uniform(0.0, 10.0), 1),
        "rainfall_intensity": round(r.uniform(0.0, 3.0), 1),
        "temperature_c": round(r.uniform(28.0, 35.0), 1),
        "humidity": round(r.uniform(55.0, 80.0), 1),
        "wind_speed_kmh": round(r.uniform(8.0, 18.0), 1),
        "aqi": round(r.uniform(60.0, 120.0), 0),
        "flood_probability": round(r.uniform(0.05, 0.18), 2),
        "cyclone_probability": round(r.uniform(0.01, 0.05), 2),
        "duration_h": round(r.uniform(0.5, 1.5), 1),
        "platform_availability_pct": round(r.uniform(99.0, 99.9), 1),
        "zone_closure": False,
    }
    return {"data_source": MOCK, "provider": "HKO-SIM (fictional)",
            "zone_id": zone_id, "weather": weather}


def aqi_current(zone_id):
    r = _rng("aqi", zone_id)
    aqi = round(r.uniform(60.0, 120.0), 0)
    category = "Good" if aqi < 100 else "Moderate"
    return {"data_source": MOCK, "provider": "CPCB-SIM (fictional)",
            "zone_id": zone_id, "aqi": aqi, "category": category}


def traffic_current(zone_id):
    z = _zone(zone_id)
    r = _rng("traffic", zone_id)
    index = round(min(1.0, max(0.0, z["traffic_index"] + r.uniform(-0.08, 0.08))), 2)
    return {"data_source": MOCK, "provider": "TRAFFIC-SIM (fictional)",
            "zone_id": zone_id, "congestion_index": index,
            "avg_speed_kmh": round(38.0 * (1.0 - index) + 8.0, 1)}


def platform_status():
    r = _rng("platform")
    availability = round(r.uniform(99.0, 99.95), 2)
    return {"data_source": MOCK, "provider": "SwiftDash Logistics (fictional)",
            "platform_availability_pct": availability,
            "status": "OPERATIONAL" if availability >= 85.0 else "DEGRADED"}


def forecast_7d(fleet_size, avg_payout):
    """7-day hazard outlook for the insurer dashboard. Expected payout is
    probability x fleet x typical payout x the largest single-zone reach of an
    event (derived from zone delivery densities)."""
    r = _rng("forecast7d")
    densities = [z["delivery_density"] for z in config.ZONES]
    reach = max(densities) / sum(densities)  # single-event reach share
    outlook = [
        ("Heavy rain", r.uniform(0.30, 0.50)),
        ("Flood", r.uniform(0.20, 0.40)),
        ("Extreme heat", r.uniform(0.05, 0.20)),
        ("Severe AQI", r.uniform(0.10, 0.30)),
    ]
    rows = []
    for label, prob in outlook:
        prob = round(prob, 2)
        rows.append({
            "event_type": label,
            "probability": prob,
            "expected_payout": round(prob * fleet_size * avg_payout * reach, -2),
        })
    return {"data_source": MOCK, "horizon_days": 7, "forecast": rows}


def send_upi_payment(worker, amount):
    digest = hashlib.sha256(
        ("upi:%s:%s" % (worker["worker_id"], round(amount, 2))).encode("utf-8")
    ).hexdigest()
    reference = "FPS-DEMO-%s" % digest[:12].upper()
    return {"data_source": MOCK, "status": "SENT", "reference": reference,
            "method": "FPS (SIMULATED)", "amount": round(amount, 2),
            "handle": worker.get("fps_handle", "")}
