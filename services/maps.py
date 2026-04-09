"""
Google Maps API integration + transport mode estimations.
Falls back to Haversine formula when no API key is provided.
"""
from __future__ import annotations

import math
import requests
import streamlit as st
from typing import Optional

# ── Base URL ──────────────────────────────────────────────────────────────────
GOOGLE_BASE = "https://maps.googleapis.com/maps/api"

# ── Fallback city coordinates (lat, lon) ─────────────────────────────────────
FALLBACK_COORDS: dict[str, tuple[float, float]] = {
    "london":         (51.5074,  -0.1278),
    "paris":          (48.8566,   2.3522),
    "berlin":         (52.5200,  13.4050),
    "amsterdam":      (52.3676,   4.9041),
    "rome":           (41.9028,  12.4964),
    "madrid":         (40.4168,  -3.7038),
    "barcelona":      (41.3851,   2.1734),
    "lisbon":         (38.7169,  -9.1395),
    "vienna":         (48.2082,  16.3738),
    "prague":         (50.0755,  14.4378),
    "budapest":       (47.4979,  19.0402),
    "warsaw":         (52.2297,  21.0122),
    "brussels":       (50.8503,   4.3517),
    "zurich":         (47.3769,   8.5417),
    "geneva":         (46.2044,   6.1432),
    "milan":          (45.4654,   9.1859),
    "luxembourg":     (49.6116,   6.1319),
    "new york":       (40.7128,  -74.0060),
    "los angeles":    (34.0522, -118.2437),
    "san francisco":  (37.7749, -122.4194),
    "chicago":        (41.8781,  -87.6298),
    "toronto":        (43.6532,  -79.3832),
    "dubai":          (25.2048,  55.2708),
    "singapore":      ( 1.3521, 103.8198),
    "tokyo":          (35.6762, 139.6503),
    "hong kong":      (22.3193, 114.1694),
    "bangkok":        (13.7563, 100.5018),
    "sydney":         (-33.8688, 151.2093),
    "mumbai":         (19.0760,  72.8777),
    "bangalore":      (12.9716,  77.5946),
    "delhi":          (28.7041,  77.1025),
    "cairo":          (30.0444,  31.2357),
    "istanbul":       (41.0082,  28.9784),
    "johannesburg":   (-26.2041, 28.0473),
    "sao paulo":      (-23.5505, -46.6333),
    "mexico city":    (19.4326,  -99.1332),
    "seoul":          (37.5665, 126.9780),
    "beijing":        (39.9042, 116.4074),
    "shanghai":       (31.2304, 121.4737),
    "kuala lumpur":   ( 3.1390, 101.6869),
    "jakarta":        (-6.2088, 106.8456),
    "manila":         (14.5995, 120.9842),
    "lagos":          ( 6.5244,   3.3792),
    "nairobi":        (-1.2921,  36.8219),
    "buenos aires":   (-34.6037, -58.3816),
    "bogota":         ( 4.7110,  -74.0721),
    "lima":           (-12.0464, -77.0428),
    "santiago":       (-33.4489, -70.6693),
}

# ── Transport mode parameters (from Soul Spark implementation) ────────────────
TRANSPORT_MODES = {
    "car": {
        "label": "🚗 Car",
        "speed_kmh":    90,
        "cost_per_km":  0.112,   # 7 L/100km * EUR 1.60/L
        "co2_per_km":   0.162,   # 7 L/100km * 2.31 kg CO2/L / 100
        "base_cost":    0,
        "overhead_h":   0,
        "min_km":       0,
        "color":        "#f59e0b",
    },
    "train": {
        "label": "🚂 Train",
        "speed_kmh":    120,
        "cost_per_km":  0.15,
        "co2_per_km":   0.041,
        "base_cost":    0,
        "overhead_h":   0.5,     # station arrival buffer
        "min_km":       0,
        "color":        "#3b82f6",
    },
    "bus": {
        "label": "🚌 Bus",
        "speed_kmh":    70,
        "cost_per_km":  0.08,
        "co2_per_km":   0.068,
        "base_cost":    0,
        "overhead_h":   0.25,
        "min_km":       0,
        "color":        "#22c55e",
    },
    "flight": {
        "label": "✈️ Flight",
        "speed_kmh":    700,
        "cost_per_km":  0.10,
        "co2_per_km":   0.255,
        "base_cost":    80,
        "overhead_h":   2.5,     # check-in + security + boarding
        "min_km":       300,     # only offered for routes > 300 km
        "color":        "#8b5cf6",
    },
}


# ── Haversine ─────────────────────────────────────────────────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Geocoding ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def geocode(location: str, api_key: str = "") -> Optional[tuple[float, float]]:
    """
    Return (lat, lon) for a location string.
    Uses Google Geocoding API when api_key is provided;
    falls back to FALLBACK_COORDS dict.
    """
    key = location.strip().lower()
    if api_key:
        try:
            r = requests.get(
                f"{GOOGLE_BASE}/geocode/json",
                params={"address": location, "key": api_key},
                timeout=8,
            )
            if r.ok:
                results = r.json().get("results", [])
                if results:
                    loc = results[0]["geometry"]["location"]
                    return loc["lat"], loc["lng"]
        except Exception:
            pass

    # Fallback: try exact match then partial match
    if key in FALLBACK_COORDS:
        return FALLBACK_COORDS[key]
    for city, coords in FALLBACK_COORDS.items():
        if city in key or key in city:
            return coords
    return None


# ── Google Distance Matrix ─────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def get_driving_data(origin: str, destination: str, api_key: str) -> Optional[dict]:
    """
    Returns {"distance_km": float, "duration_h": float} from Google Distance Matrix.
    Returns None if unavailable.
    """
    if not api_key:
        return None
    try:
        r = requests.get(
            f"{GOOGLE_BASE}/distancematrix/json",
            params={
                "origins": origin,
                "destinations": destination,
                "mode": "driving",
                "key": api_key,
            },
            timeout=8,
        )
        if r.ok:
            data = r.json()
            rows = data.get("rows", [])
            if rows:
                element = rows[0].get("elements", [{}])[0]
                if element.get("status") == "OK":
                    dist_m  = element["distance"]["value"]
                    dur_s   = element["duration"]["value"]
                    return {
                        "distance_km": dist_m / 1000,
                        "duration_h":  dur_s  / 3600,
                    }
    except Exception:
        pass
    return None


# ── Distance Matrix for multiple pairs ───────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def get_distance_matrix_multi(
    locations: list[str], api_key: str
) -> Optional[list[list[float]]]:
    """
    For N locations, return an NxN matrix of driving distances in km.
    Falls back to Haversine if API unavailable.
    """
    n = len(locations)
    coords = [geocode(loc, api_key) for loc in locations]

    if api_key and all(c is not None for c in coords):
        try:
            pipe = "|".join(f"{c[0]},{c[1]}" for c in coords)
            r = requests.get(
                f"{GOOGLE_BASE}/distancematrix/json",
                params={"origins": pipe, "destinations": pipe,
                        "mode": "driving", "key": api_key},
                timeout=12,
            )
            if r.ok:
                data = r.json()
                rows = data.get("rows", [])
                matrix = []
                for row in rows:
                    matrix_row = []
                    for elem in row.get("elements", []):
                        if elem.get("status") == "OK":
                            matrix_row.append(elem["distance"]["value"] / 1000)
                        else:
                            matrix_row.append(float("inf"))
                    matrix.append(matrix_row)
                if len(matrix) == n:
                    return matrix
        except Exception:
            pass

    # Haversine fallback
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(0.0)
            elif coords[i] and coords[j]:
                row.append(haversine_km(*coords[i], *coords[j]))
            else:
                row.append(float("inf"))
        matrix.append(row)
    return matrix


# ── Transport mode estimation ─────────────────────────────────────────────────
def estimate_modes(
    distance_km: float,
    driving_override: Optional[dict] = None,
) -> dict[str, dict]:
    """
    Return transport mode estimates for a given distance.
    driving_override: {"distance_km": x, "duration_h": y} from Google API.

    Returns:
        {
          "car":    {"time_h": ..., "cost_eur": ..., "co2_kg": ..., "label": ..., "color": ...},
          "train":  {...},
          "bus":    {...},
          "flight": {...},  # only if distance_km >= 300
        }
    """
    results = {}
    for mode_key, cfg in TRANSPORT_MODES.items():
        if distance_km < cfg["min_km"]:
            continue
        if mode_key == "car" and driving_override:
            time_h    = driving_override["duration_h"]
            drive_km  = driving_override["distance_km"]
            cost_eur  = drive_km * cfg["cost_per_km"] + cfg["base_cost"]
            co2_kg    = drive_km * cfg["co2_per_km"]
        else:
            time_h   = distance_km / cfg["speed_kmh"] + cfg["overhead_h"]
            cost_eur = distance_km * cfg["cost_per_km"] + cfg["base_cost"]
            co2_kg   = distance_km * cfg["co2_per_km"]

        results[mode_key] = {
            "time_h":   round(time_h, 2),
            "cost_eur": round(cost_eur, 2),
            "co2_kg":   round(co2_kg, 2),
            "label":    cfg["label"],
            "color":    cfg["color"],
        }
    return results


def format_duration(hours: float) -> str:
    """Format fractional hours to 'Xh Ym'."""
    h = int(hours)
    m = int(round((hours - h) * 60))
    if h == 0:
        return f"{m}m"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


# ── Multi-stop optimisation (greedy nearest-neighbour) ────────────────────────
def optimize_route(
    origin: str,
    waypoints: list[str],
    destination: str,
    api_key: str = "",
) -> dict:
    """
    Given an origin, list of waypoints, and destination, find the optimal
    order to visit all waypoints using a greedy nearest-neighbour algorithm.

    Returns:
        {
            "ordered_stops": [origin, wp1, wp2, ..., destination],
            "segments": [
                {"from": ..., "to": ..., "distance_km": ..., "duration_h": ...},
                ...
            ],
            "total_km": float,
            "total_h": float,
            "used_google": bool,
        }
    """
    all_stops = [origin] + waypoints + [destination]
    n = len(all_stops)

    matrix = get_distance_matrix_multi(all_stops, api_key)
    used_google = api_key and matrix is not None

    if matrix is None:
        # Compute haversine matrix
        coords = [geocode(s, api_key) for s in all_stops]
        matrix = []
        for i in range(n):
            row = []
            for j in range(n):
                if i == j:
                    row.append(0.0)
                elif coords[i] and coords[j]:
                    row.append(haversine_km(*coords[i], *coords[j]))
                else:
                    row.append(float("inf"))
            matrix.append(row)

    # Greedy nearest-neighbour on waypoints only
    waypoint_indices = list(range(1, n - 1))  # indices in all_stops for waypoints
    ordered_indices  = [0]                     # start with origin
    remaining        = set(waypoint_indices)

    current = 0
    while remaining:
        nearest      = min(remaining, key=lambda j: matrix[current][j])
        ordered_indices.append(nearest)
        remaining.remove(nearest)
        current = nearest
    ordered_indices.append(n - 1)  # destination last

    ordered_stops = [all_stops[i] for i in ordered_indices]

    segments = []
    total_km = 0.0
    total_h  = 0.0
    for a, b in zip(ordered_indices, ordered_indices[1:]):
        km = matrix[a][b] if matrix[a][b] != float("inf") else 0.0
        h  = km / TRANSPORT_MODES["car"]["speed_kmh"]
        segments.append({
            "from":        all_stops[a],
            "to":          all_stops[b],
            "distance_km": round(km, 1),
            "duration_h":  round(h, 2),
        })
        total_km += km
        total_h  += h

    return {
        "ordered_stops": ordered_stops,
        "segments":      segments,
        "total_km":      round(total_km, 1),
        "total_h":       round(total_h, 2),
        "used_google":   bool(used_google),
    }
