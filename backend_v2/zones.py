"""
Zone-level flood risk for five Indian cities: Bengaluru, Mumbai, Delhi, Chennai, Hyderabad.

IMPORTANT: the zone attributes below are ILLUSTRATIVE ESTIMATES made for this prototype.
They are not measured data. Coordinates are approximate (about 1 km). Hospital and school counts are rough
placeholders. Replace them with real data:
  valley       <- terrain model (SRTM / Copernicus DEM): how low-lying the zone is, 0 to 1
  lake         <- OpenStreetMap lakes, rivers and storm drains: nearness to water, 0 to 1
  built_up     <- land cover: share of hard surface, 0 to 1
  drain_mm_hr  <- municipal drain records: rain the drains can carry, mm per hour
  hospitals / schools <- OpenStreetMap facilities inside the zone

The only values taken from reports are the `reported_flooding` labels. Each names an event in which the area
was reported waterlogged or flooded. They are shown for comparison and are NOT used in the score:
  Bengaluru  Sept 2022 floods (news reports)
  Mumbai     19 Aug 2025 heavy rain (news report listing waterlogged areas)
  Delhi      PWD list of critical waterlogging points, Aug 2021 (news report)
  Chennai    2015 floods (Pallikaranai marsh area named as worst hit; Velachery from a news headline)
  Hyderabad  Oct 2020 floods (Ghatkesar and Gurram Cheruvu named)

How the score works (transparent, no trained model):
  1. runoff    = rain_mm * (0.30 + 0.65 * built_up)       rain that reaches the drains
  2. capacity  = drain_mm_hr * 2                          rain the drains carry in 2 hours
  3. load      = runoff / capacity                        1.0 means the drains are exactly full
  4. water     = clamp((load - 0.6) / 2.4, 0, 1)          no flooding until drains are 60% used
  5. score     = 100 * water * (0.45 + 0.55 * susceptibility)
     susceptibility = 0.6 * valley + 0.4 * lake
"""
import math

DURATION_HR = 2
DEFAULT_CITY = "Bengaluru"

CITY_NAMES = ["Bengaluru", "Mumbai", "Delhi", "Chennai", "Hyderabad"]

_DATA = {
    'Bengaluru': [
        dict(id='bellandur', name='Bellandur', lat=12.9257, lng=77.6762, r=1500, valley=0.95, lake=1, built_up=0.85, drain_mm_hr=8, reported_flooding='Sept 2022', hospitals=2, schools=6, note='Sits at the foot of the Bellandur lake outflow.'),
        dict(id='yemalur', name='Yemalur', lat=12.9566, lng=77.6665, r=1100, valley=0.9, lake=0.85, built_up=0.8, drain_mm_hr=9, reported_flooding='Sept 2022', hospitals=1, schools=4, note='Low pocket beside the Yemalur drain.'),
        dict(id='marathahalli', name='Marathahalli and ORR', lat=12.9591, lng=77.6974, r=1300, valley=0.8, lake=0.7, built_up=0.9, drain_mm_hr=10, reported_flooding='Sept 2022', hospitals=3, schools=5, note='Busy junction on the Outer Ring Road.'),
        dict(id='mahadevapura', name='Mahadevapura', lat=12.991, lng=77.696, r=1400, valley=0.75, lake=0.65, built_up=0.85, drain_mm_hr=10, reported_flooding='Sept 2022', hospitals=2, schools=5, note='Tech corridor with many encroached drains.'),
        dict(id='whitefield', name='Whitefield', lat=12.9698, lng=77.75, r=1600, valley=0.6, lake=0.55, built_up=0.75, drain_mm_hr=12, reported_flooding='Sept 2022', hospitals=3, schools=8, note='Lakes overflow into layouts in heavy spells.'),
        dict(id='sarjapur', name='Sarjapur Road', lat=12.904, lng=77.7, r=1500, valley=0.7, lake=0.7, built_up=0.7, drain_mm_hr=9, reported_flooding='Sept 2022', hospitals=1, schools=6, note='Fast-growing layouts, thin drain network.'),
        dict(id='krpuram', name='KR Puram', lat=13.005, lng=77.696, r=1200, valley=0.65, lake=0.5, built_up=0.8, drain_mm_hr=11, reported_flooding=None, hospitals=1, schools=3, note='Low-lying railway and bridge approaches.'),
        dict(id='hsr', name='HSR Layout', lat=12.9116, lng=77.6474, r=1300, valley=0.65, lake=0.55, built_up=0.85, drain_mm_hr=12, reported_flooding='Sept 2022', hospitals=2, schools=7, note='Water collects along the inner roads.'),
        dict(id='silkboard', name='Silk Board Junction', lat=12.9177, lng=77.6228, r=900, valley=0.7, lake=0.45, built_up=0.95, drain_mm_hr=11, reported_flooding='Sept 2022', hospitals=1, schools=1, note='Major junction. A closure here backs up traffic across the city.'),
        dict(id='koramangala', name='Koramangala', lat=12.9352, lng=77.6245, r=1200, valley=0.7, lake=0.6, built_up=0.9, drain_mm_hr=13, reported_flooding='Sept 2022', hospitals=4, schools=6, note='Sits along the valley that drains to Bellandur.'),
        dict(id='hebbal', name='Hebbal', lat=13.0358, lng=77.597, r=1300, valley=0.6, lake=0.7, built_up=0.75, drain_mm_hr=12, reported_flooding=None, hospitals=2, schools=4, note='Flyover approaches and the lake edge.'),
        dict(id='hennur', name='Hennur and Kalyan Nagar', lat=13.028, lng=77.64, r=1300, valley=0.55, lake=0.55, built_up=0.75, drain_mm_hr=11, reported_flooding=None, hospitals=1, schools=5, note='New layouts with partial drain cover.'),
        dict(id='mysoreroad', name='Mysore Road', lat=12.95, lng=77.53, r=1500, valley=0.6, lake=0.5, built_up=0.8, drain_mm_hr=11, reported_flooding='Sept 2022', hospitals=1, schools=4, note='Low stretch near the Vrishabhavathi valley.'),
        dict(id='majestic', name='Majestic and City Market', lat=12.977, lng=77.572, r=1100, valley=0.45, lake=0.3, built_up=0.95, drain_mm_hr=16, reported_flooding=None, hospitals=3, schools=2, note='Dense core, old but better maintained drains.'),
        dict(id='indiranagar', name='Indiranagar', lat=12.9784, lng=77.6408, r=1100, valley=0.35, lake=0.25, built_up=0.85, drain_mm_hr=16, reported_flooding=None, hospitals=2, schools=5, note='Higher ground with decent drain cover.'),
        dict(id='jayanagar', name='Jayanagar', lat=12.925, lng=77.5938, r=1200, valley=0.25, lake=0.2, built_up=0.8, drain_mm_hr=18, reported_flooding=None, hospitals=3, schools=8, note='Planned layout on a gentle ridge.'),
        dict(id='yelahanka', name='Yelahanka', lat=13.1007, lng=77.5963, r=1500, valley=0.3, lake=0.35, built_up=0.55, drain_mm_hr=15, reported_flooding=None, hospitals=1, schools=4, note='Open ground absorbs more water.'),
        dict(id='rajajinagar', name='Rajajinagar', lat=12.991, lng=77.552, r=1200, valley=0.3, lake=0.25, built_up=0.85, drain_mm_hr=16, reported_flooding=None, hospitals=2, schools=6, note='Established grid with working drains.'),
        dict(id='ecity', name='Electronic City', lat=12.8452, lng=77.6602, r=1500, valley=0.5, lake=0.45, built_up=0.7, drain_mm_hr=14, reported_flooding=None, hospitals=1, schools=3, note='Wide roads, planned drainage.'),
    ],
    'Mumbai': [
        dict(id='mum_hindmata', name='Hindmata and Dadar', lat=19.01, lng=72.842, r=1100, valley=0.8, lake=0.4, built_up=0.95, drain_mm_hr=12, reported_flooding='Aug 2025', hospitals=3, schools=4, note='Reported waterlogged in the Aug 2025 rain.'),
        dict(id='mum_sion', name='Sion', lat=19.039, lng=72.8619, r=1100, valley=0.75, lake=0.45, built_up=0.92, drain_mm_hr=13, reported_flooding='Aug 2025', hospitals=2, schools=5, note='Gandhi Market streets reported submerged in Aug 2025.'),
        dict(id='mum_matunga', name="Matunga and King's Circle", lat=19.027, lng=72.856, r=1000, valley=0.7, lake=0.35, built_up=0.93, drain_mm_hr=15, reported_flooding='Aug 2025', hospitals=2, schools=5, note='Reported waterlogged in Aug 2025.'),
        dict(id='mum_kurla', name='Kurla', lat=19.0728, lng=72.8826, r=1300, valley=0.8, lake=0.55, built_up=0.9, drain_mm_hr=12, reported_flooding='Aug 2025', hospitals=2, schools=4, note='Reported waterlogged in Aug 2025. Low-lying, near the Mithi river.'),
        dict(id='mum_chembur', name='Chembur', lat=19.0522, lng=72.8997, r=1300, valley=0.6, lake=0.4, built_up=0.85, drain_mm_hr=15, reported_flooding='Aug 2025', hospitals=2, schools=6, note='Reported waterlogged in Aug 2025.'),
        dict(id='mum_andheri', name='Andheri', lat=19.1197, lng=72.8468, r=1500, valley=0.65, lake=0.45, built_up=0.9, drain_mm_hr=14, reported_flooding='Aug 2025', hospitals=4, schools=8, note='Andheri subway closed in Aug 2025.'),
        dict(id='mum_goregaon', name='Goregaon', lat=19.1663, lng=72.8526, r=1500, valley=0.55, lake=0.35, built_up=0.85, drain_mm_hr=15, reported_flooding='Aug 2025', hospitals=2, schools=6, note='Area under the Mrunaltai Gore flyover reported waterlogged in Aug 2025.'),
        dict(id='mum_kandivali', name='Kandivali and Poisar', lat=19.205, lng=72.8476, r=1400, valley=0.55, lake=0.5, built_up=0.8, drain_mm_hr=15, reported_flooding='Aug 2025', hospitals=1, schools=5, note='Poisar subway closed in Aug 2025.'),
        dict(id='mum_malabar', name='Malabar Hill', lat=18.9548, lng=72.7985, r=1000, valley=0.15, lake=0.1, built_up=0.75, drain_mm_hr=22, reported_flooding=None, hospitals=2, schools=3, note='Higher ground on a ridge (estimate).'),
    ],
    'Delhi': [
        dict(id='del_minto', name='Minto Road and ITO', lat=28.635, lng=77.233, r=1200, valley=0.7, lake=0.45, built_up=0.95, drain_mm_hr=10, reported_flooding='PWD critical point, 2021', hospitals=3, schools=3, note='Minto Road underpass is on the PWD critical waterlogging list.'),
        dict(id='del_pulprahlad', name='Pul Prahladpur', lat=28.5, lng=77.295, r=1200, valley=0.75, lake=0.4, built_up=0.8, drain_mm_hr=9, reported_flooding='PWD critical point, 2021', hospitals=1, schools=3, note='Underpass is on the PWD critical waterlogging list.'),
        dict(id='del_zakhira', name='Zakhira and Moti Nagar', lat=28.659, lng=77.143, r=1200, valley=0.65, lake=0.35, built_up=0.9, drain_mm_hr=10, reported_flooding='PWD critical point, 2021', hospitals=2, schools=5, note='Zakhira underpass is on the PWD critical waterlogging list.'),
        dict(id='del_azadpur', name='Azadpur and Jahangirpuri', lat=28.715, lng=77.17, r=1400, valley=0.65, lake=0.4, built_up=0.88, drain_mm_hr=11, reported_flooding='PWD critical point, 2021', hospitals=2, schools=5, note='Jahangirpuri Metro Station Road is on the PWD list; Azadpur underpass inundated that monsoon.'),
        dict(id='del_yamunabazar', name='Yamuna Bazar', lat=28.664, lng=77.239, r=1100, valley=0.9, lake=0.95, built_up=0.85, drain_mm_hr=9, reported_flooding='PWD, 2021 (Yamuna Bazar underpass)', hospitals=1, schools=2, note='Beside the Yamuna floodplain.'),
        dict(id='del_karala', name='Karala and Kanjhawala', lat=28.735, lng=77.042, r=1500, valley=0.6, lake=0.3, built_up=0.65, drain_mm_hr=8, reported_flooding='PWD critical point, 2021', hospitals=1, schools=4, note='Karala Kanjhawala Road is on the PWD critical waterlogging list.'),
        dict(id='del_loniroad', name='Loni Road and Shahdara', lat=28.675, lng=77.305, r=1300, valley=0.65, lake=0.4, built_up=0.9, drain_mm_hr=11, reported_flooding='PWD critical point, 2021', hospitals=2, schools=5, note='Loni Road Golchakkar is on the PWD critical waterlogging list.'),
        dict(id='del_cp', name='Connaught Place', lat=28.6315, lng=77.2167, r=1000, valley=0.3, lake=0.15, built_up=0.9, drain_mm_hr=18, reported_flooding=None, hospitals=3, schools=3, note='Central planned area (estimate).'),
        dict(id='del_saket', name='Saket', lat=28.5245, lng=77.2066, r=1300, valley=0.35, lake=0.2, built_up=0.8, drain_mm_hr=15, reported_flooding=None, hospitals=3, schools=6, note='South Delhi (estimate).'),
    ],
    'Chennai': [
        dict(id='che_pallikaranai', name='Pallikaranai', lat=12.934, lng=80.215, r=1500, valley=0.95, lake=1.0, built_up=0.7, drain_mm_hr=8, reported_flooding='Dec 2015', hospitals=1, schools=4, note='Localities around the Pallikaranai marsh were the worst hit in 2015.'),
        dict(id='che_velachery', name='Velachery', lat=12.9815, lng=80.218, r=1300, valley=0.9, lake=0.8, built_up=0.85, drain_mm_hr=9, reported_flooding='Dec 2015 (reported)', hospitals=2, schools=5, note='Residents reported flooding in 2015 and again since.'),
        dict(id='che_perungudi', name='Perungudi', lat=12.965, lng=80.2461, r=1200, valley=0.8, lake=0.7, built_up=0.8, drain_mm_hr=11, reported_flooding=None, hospitals=1, schools=4, note='Next to the Pallikaranai marsh (estimate).'),
        dict(id='che_adyar', name='Adyar', lat=13.0067, lng=80.257, r=1200, valley=0.7, lake=0.8, built_up=0.85, drain_mm_hr=11, reported_flooding=None, hospitals=2, schools=5, note='Along the Adyar river (estimate).'),
        dict(id='che_tondiarpet', name='Tondiarpet', lat=13.1256, lng=80.2879, r=1300, valley=0.85, lake=0.5, built_up=0.9, drain_mm_hr=9, reported_flooding=None, hospitals=1, schools=4, note='Low-lying north Chennai (estimate).'),
        dict(id='che_tnagar', name='T. Nagar', lat=13.0418, lng=80.2341, r=1000, valley=0.55, lake=0.3, built_up=0.95, drain_mm_hr=13, reported_flooding=None, hospitals=2, schools=5, note='Dense commercial area (estimate).'),
        dict(id='che_mylapore', name='Mylapore', lat=13.0368, lng=80.2676, r=1000, valley=0.45, lake=0.35, built_up=0.9, drain_mm_hr=14, reported_flooding=None, hospitals=2, schools=5, note='Older core near the coast (estimate).'),
        dict(id='che_annanagar', name='Anna Nagar', lat=13.085, lng=80.2101, r=1400, valley=0.3, lake=0.25, built_up=0.85, drain_mm_hr=16, reported_flooding=None, hospitals=2, schools=8, note='Planned layout on higher ground (estimate).'),
    ],
    'Hyderabad': [
        dict(id='hyd_gurram', name='Gurram Cheruvu and Balapur', lat=17.315, lng=78.51, r=1400, valley=0.85, lake=0.9, built_up=0.6, drain_mm_hr=9, reported_flooding='Oct 2020', hospitals=1, schools=3, note='Over 2,100 families were evacuated near Gurram Cheruvu in Oct 2020.'),
        dict(id='hyd_ghatkesar', name='Ghatkesar', lat=17.451, lng=78.687, r=1600, valley=0.5, lake=0.4, built_up=0.5, drain_mm_hr=12, reported_flooding='Oct 2020 (324 mm rain)', hospitals=1, schools=3, note='Recorded 324 mm of rain in Oct 2020.'),
        dict(id='hyd_lbnagar', name='LB Nagar', lat=17.3457, lng=78.5522, r=1300, valley=0.7, lake=0.55, built_up=0.88, drain_mm_hr=10, reported_flooding=None, hospitals=2, schools=5, note='Low-lying south-east (estimate).'),
        dict(id='hyd_oldcity', name='Old City and Charminar', lat=17.3616, lng=78.4747, r=1200, valley=0.75, lake=0.6, built_up=0.95, drain_mm_hr=9, reported_flooding=None, hospitals=2, schools=5, note='Dense old core near the Musi (estimate).'),
        dict(id='hyd_kukatpally', name='Kukatpally', lat=17.4948, lng=78.3996, r=1400, valley=0.55, lake=0.45, built_up=0.85, drain_mm_hr=11, reported_flooding=None, hospitals=2, schools=8, note='Large residential area with nalas (estimate).'),
        dict(id='hyd_secunderabad', name='Secunderabad', lat=17.4399, lng=78.4983, r=1300, valley=0.4, lake=0.35, built_up=0.9, drain_mm_hr=14, reported_flooding=None, hospitals=3, schools=6, note='Older planned area (estimate).'),
        dict(id='hyd_hitec', name='Hitec City', lat=17.4435, lng=78.3772, r=1400, valley=0.35, lake=0.3, built_up=0.8, drain_mm_hr=15, reported_flooding=None, hospitals=2, schools=4, note='Newer planned drains (estimate).'),
        dict(id='hyd_banjara', name='Banjara Hills', lat=17.4126, lng=78.4482, r=1200, valley=0.2, lake=0.15, built_up=0.8, drain_mm_hr=18, reported_flooding=None, hospitals=3, schools=4, note='Higher rocky ground (estimate).'),
        dict(id='hyd_uppal', name='Uppal', lat=17.4058, lng=78.5591, r=1400, valley=0.55, lake=0.5, built_up=0.85, drain_mm_hr=12, reported_flooding=None, hospitals=1, schools=5, note='Eastern suburb (estimate).'),
    ],
}

# Flat list, each zone tagged with its city.
ZONES = []
for _city, _zs in _DATA.items():
    for _z in _zs:
        ZONES.append({**_z, "city": _city})


def zones_for_city(city):
    return [z for z in ZONES if z["city"] == city]


def resolve_city_name(name):
    """Case-insensitive match to a known city name, or None."""
    if isinstance(name, str):
        for c in CITY_NAMES:
            if c.lower() == name.strip().lower():
                return c
    return None


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def susceptibility(z):
    """How prone the zone is to holding water, regardless of rain (0 to 1)."""
    return 0.6 * z["valley"] + 0.4 * z["lake"]


def assess(z, rain_mm):
    """Flood risk for one zone for rain_mm falling over DURATION_HR hours."""
    runoff = rain_mm * (0.30 + 0.65 * z["built_up"])
    capacity = z["drain_mm_hr"] * DURATION_HR
    load = runoff / capacity
    water = _clamp((load - 0.6) / 2.4, 0, 1)
    s = susceptibility(z)
    score = _clamp(100 * water * (0.45 + 0.55 * s), 0, 100)
    return {
        "score": round(score),
        "level": level(score),
        "rain_reaching_drains_mm": round(runoff, 1),
        "drain_capacity_mm": round(capacity, 1),
        "drain_load_pct": round(load * 100),
        "susceptibility": round(s, 2),
    }


def level(score):
    if score >= 75:
        return "Severe"
    if score >= 55:
        return "High"
    if score >= 30:
        return "Watch"
    return "Low"


def priority(z, score):
    """Response priority: risk weighted by what is exposed (hospitals, schools)."""
    return score * (1 + 0.10 * z["hospitals"] + 0.03 * z["schools"])


def actions(z, a):
    """Plain-language actions for a zone at its assessed level."""
    out = []
    lv, sc = a["level"], a["score"]
    if lv == "Low":
        return out
    if lv == "Severe":
        out.append(f"Pre-position 2 high-capacity pumps at {z['name']} before the rain peaks")
        out.append("Send a crew to clear silt and blockages at the main drain inlets")
    elif lv == "High":
        out.append(f"Pre-position 1 pump and a clearing crew near {z['name']}")
    else:
        out.append(f"Inspect the main drain inlets at {z['name']} before the rain")
    if z["hospitals"] > 0 and sc >= 55:
        n = z["hospitals"]
        out.append(f"Keep an alternate ambulance route open for the {n} hospital{'s' if n != 1 else ''} here")
    if z["schools"] > 0 and sc >= 75:
        out.append(f"Alert {z['schools']} schools to hold early dismissal or shelter in place")
    if z["id"] == "silkboard" and sc >= 55:
        out.append("Warn traffic police: a closure here backs up the Hosur Road and ORR corridors")
    if sc >= 75:
        out.append(f"Send a resident alert for low-lying streets in {z['name']}")
    return out


def _row(z, rain_mm):
    a = assess(z, rain_mm)
    return {
        "id": z["id"], "city": z["city"], "name": z["name"], "lat": z["lat"], "lng": z["lng"], "radius_m": z["r"],
        "note": z["note"],
        "inputs": {
            "low_lying": z["valley"], "near_lake_or_drain": z["lake"], "built_up": z["built_up"],
            "drain_capacity_mm_per_hr": z["drain_mm_hr"], "hospitals": z["hospitals"], "schools": z["schools"],
            "reported_flooding": z["reported_flooding"],
        },
        **a,
        "priority": round(priority(z, a["score"]), 1),
        "actions": actions(z, a),
    }


def compute_all(rain_mm, city=DEFAULT_CITY):
    """Every zone of one city scored, most urgent first."""
    rows = [_row(z, rain_mm) for z in zones_for_city(city)]
    rows.sort(key=lambda r: -r["priority"])
    return rows


def row_for(zone_id, rain_mm):
    for z in ZONES:
        if z["id"] == zone_id:
            return _row(z, rain_mm)
    return None


def _distance_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def zone_for_point(lat, lon, max_m=4000):
    """Nearest zone (any city) to a point. Returns (zone, distance_m, inside) or None if none is within max_m."""
    best, bd = None, float("inf")
    for z in ZONES:
        d = _distance_m(lat, lon, z["lat"], z["lng"])
        if d < bd:
            best, bd = z, d
    if best is None or bd > max_m:
        return None
    return best, round(bd), bd <= best["r"]