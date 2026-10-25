from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import math
import os
import uvicorn
from fastapi.responses import HTMLResponse
import zones
from risk_engine import UrbanRiskEngine
from city_profiles import CITIES
from weather_service import weather_service as ws

app = FastAPI(title="UrbanShield Deep Intelligence Engine v2.5")
engine = UrbanRiskEngine()


def _distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points, in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def resolve_city(city_name, lat, lon):
    """
    Pick which city profile to use.
    1. If the name matches a known city, use it.
    2. Otherwise (map click, searched neighbourhood, etc.) use the NEAREST known city
       to the given coordinates, and report that the profile is approximate.
    Returns (key, profile, distance_km, is_approximate).
    """
    if isinstance(city_name, str):
        for key in CITIES:
            if key.lower() == city_name.strip().lower():
                return key, CITIES[key], 0.0, False
    if lat is None or lon is None:
        # No coordinates to go on: fall back to the default city.
        return "Bengaluru", CITIES["Bengaluru"], 0.0, True
    best_key, best_d = None, float("inf")
    for key, prof in CITIES.items():
        d = _distance_km(lat, lon, prof["lat"], prof["lon"])
        if d < best_d:
            best_key, best_d = key, d
    return best_key, CITIES[best_key], round(best_d, 1), True

class SimulationInputs(BaseModel):
    rainfall_mm: float
    avg_temperature_c: float
    humidity_percent: float
    drainage_capacity_index: float # 0-100
    green_cover_percent: float # 0-100
    population_density: float
    elevation_index: Optional[float] = 50.0
    infrastructure_strength: Optional[float] = 70.0
    emergency_response: Optional[float] = 80.0

@app.get("/health")
async def health_check():
    return {
        "status": "online", 
        "version": "2.5.0-DEEP-INTEL", 
        "engine": "Hybrid-ML-Optimization"
    }

@app.post("/simulate")
async def simulate_risk(inputs: SimulationInputs):
    try:
        data = inputs.dict()
        result = engine.calculate_risk(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sensitivity")
async def analyze_sensitivity(inputs: SimulationInputs):
    """
    Upgrade 5: Sensitivity Analysis for systemic volatility.
    """
    try:
        data = inputs.dict()
        sensitivity_report = engine.analyze_sensitivity(data)
        return sensitivity_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Zone-level flood risk for Bengaluru, Mumbai, Delhi, Chennai and Hyderabad. See zones.py.
# ---------------------------------------------------------------------------
ZONE_DATA_NOTE = (
    "Zone attributes are illustrative estimates for this prototype, not measured data. "
    "Only the reported-flooding labels come from news or government reports. "
    "See zones.py for how to replace the estimates with terrain, drain and land-cover data."
)


def _clean_rain(rainfall_mm):
    return max(0.0, min(float(rainfall_mm), 300.0))


@app.get("/zones/cities")
async def zone_cities():
    """Cities that have zone data, with how many zones each has."""
    return {"cities": [{"name": c, "zones": len(zones.zones_for_city(c))} for c in zones.CITY_NAMES]}


@app.get("/zones")
async def list_zones(rainfall_mm: float = 60.0, city: str = "Bengaluru"):
    """All zones of one city scored for rainfall_mm falling over 2 hours, most urgent first."""
    key = zones.resolve_city_name(city)
    if key is None:
        raise HTTPException(status_code=404, detail="Unknown city. Choose one of: " + ", ".join(zones.CITY_NAMES))
    rain = _clean_rain(rainfall_mm)
    return {
        "city": key,
        "rainfall_mm": rain,
        "duration_hours": zones.DURATION_HR,
        "data_note": ZONE_DATA_NOTE,
        "zones": zones.compute_all(rain, key),
    }


@app.get("/zones/at")
async def zone_at(lat: float, lon: float, rainfall_mm: float = 60.0):
    """The zone (in any city) that covers a point, scored for rainfall_mm over 2 hours."""
    rain = _clean_rain(rainfall_mm)
    hit = zones.zone_for_point(lat, lon)
    if hit is None:
        raise HTTPException(status_code=404, detail="No zone covers this point. Zones cover " + ", ".join(zones.CITY_NAMES) + " only.")
    z, dist_m, inside = hit
    return {
        **zones.row_for(z["id"], rain),
        "rainfall_mm": rain,
        "distance_to_zone_centre_m": dist_m,
        "point_inside_zone": inside,
        "data_note": ZONE_DATA_NOTE,
    }


@app.get("/zone-check", response_class=HTMLResponse)
async def zone_check_page():
    """A simple page to check any zone's values with a rainfall slider."""
    path = os.path.join(os.path.dirname(__file__), "zone_check.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/analyze-city")
async def analyze_city(payload: dict):
    """
    Phase 3: Real-time City Analysis Endpoint.
    Fetches live weather and merges with city infrastructure profiles.
    """
    overrides = payload.get("overrides") or {}
    req_lat = overrides.get("lat")
    req_lon = overrides.get("lon")

    # Accept any point on the map: use the named city if known, else the nearest profile.
    city_key, city, profile_km, approximate = resolve_city(payload.get("city", "Bengaluru"), req_lat, req_lon)

    target_lat = req_lat if req_lat is not None else city["lat"]
    target_lon = req_lon if req_lon is not None else city["lon"]

    # Cache per location (rounded to ~1 km) so nearby clicks share one weather lookup.
    cache_key = f"{city_key}_{round(float(target_lat), 2)}_{round(float(target_lon), 2)}"

    # 1. Fetch Live Weather
    weather = ws.fetch_live_weather(target_lat, target_lon, cache_key)
    
    # 2. Merge Data for Engine
    engine_inputs = {
        **city,
        **weather,
        # Allow optional manual overrides from frontend for "Stress Mode"
        # We need to ensure types are correct for the engine
        **{k: float(v) for k, v in overrides.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    }
    
    # 3. Process through Hybrid Risk Engine
    try:
        results = engine.calculate_risk(engine_inputs)
        
        # 4. Add metadata for Frontend
        results["city_metadata"] = {
            "name": city["name"],
            "lat": target_lat,
            "lon": target_lon,
            "profile_used": city_key,
            "profile_distance_km": profile_km,
            "profile_is_approximate": approximate,
            "data_source": "Open-Meteo + UrbanShield Profiles",
            "last_updated": weather["timestamp"],
            "is_live_sync": True
        }
        results["live_weather"] = weather

        # Zone-level view for points inside the Bengaluru zones (uses the same rainfall as the engine).
        hit = zones.zone_for_point(float(target_lat), float(target_lon))
        if hit is not None:
            z, dist_m, inside = hit
            rain_used = float(engine_inputs.get("rainfall_mm", 0.0) or 0.0)
            results["zone"] = {
                "id": z["id"],
                "city": z["city"],
                "name": z["name"],
                "distance_to_zone_centre_m": dist_m,
                "point_inside_zone": inside,
                "rainfall_mm_used": rain_used,
                **zones.assess(z, rain_used),
            }
        
        return results
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Intelligence Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)