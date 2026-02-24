"""
Map Tool
========
MCP Tool wrapping Google Maps (global) and a Haversine fallback.
Provides geocoding and distance utilities for the route optimizer.
"""
import math
import random
from typing import Dict, List, Optional, Tuple

from ..config import settings

# Approximate city centres for offline/mock geocoding
_CITY_COORDS: Dict[str, Tuple[float, float]] = {
    # Asia
    "tokyo":       (35.6762,  139.6503),
    "東京":         (35.6762,  139.6503),
    "osaka":       (34.6937,  135.5023),
    "大阪":         (34.6937,  135.5023),
    "kyoto":       (35.0116,  135.7681),
    "京都":         (35.0116,  135.7681),
    "beijing":     (39.9042,  116.4074),
    "北京":         (39.9042,  116.4074),
    "shanghai":    (31.2304,  121.4737),
    "上海":         (31.2304,  121.4737),
    "chengdu":     (30.5728,  104.0668),
    "成都":         (30.5728,  104.0668),
    "chongqing":   (29.5630,  106.5516),
    "重庆":         (29.5630,  106.5516),
    "guangzhou":   (23.1291,  113.2644),
    "广州":         (23.1291,  113.2644),
    "shenzhen":    (22.5431,  114.0579),
    "深圳":         (22.5431,  114.0579),
    "hangzhou":    (30.2741,  120.1551),
    "杭州":         (30.2741,  120.1551),
    "xian":        (34.3416,  108.9398),
    "西安":         (34.3416,  108.9398),
    "singapore":   ( 1.3521,  103.8198),
    "bangkok":     (13.7563,  100.5018),
    "seoul":       (37.5665,  126.9780),
    "서울":         (37.5665,  126.9780),
    "hong kong":   (22.3193,  114.1694),
    "香港":         (22.3193,  114.1694),
    "taipei":      (25.0330,  121.5654),
    "台北":         (25.0330,  121.5654),
    "bali":        (-8.3405,  115.0920),
    "kuala lumpur":(3.1390,   101.6869),
    # Europe
    "london":      (51.5074,   -0.1278),
    "paris":       (48.8566,    2.3522),
    "rome":        (41.9028,   12.4964),
    "barcelona":   (41.3851,    2.1734),
    "amsterdam":   (52.3676,    4.9041),
    "berlin":      (52.5200,   13.4050),
    "vienna":      (48.2082,   16.3738),
    "prague":      (50.0755,   14.4378),
    "lisbon":      (38.7223,   -9.1393),
    "istanbul":    (41.0082,   28.9784),
    # Americas
    "new york":    (40.7128,  -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago":     (41.8781,  -87.6298),
    "miami":       (25.7617,  -80.1918),
    "san francisco":(37.7749,-122.4194),
    "las vegas":   (36.1699, -115.1398),
    "toronto":     (43.6532,  -79.3832),
    "vancouver":   (49.2827, -123.1207),
    "mexico city": (19.4326,  -99.1332),
    "rio de janeiro":(-22.9068,-43.1729),
    # US states / regions (so "Alaska trip" resolves correctly)
    "alaska":      (64.2008, -153.4937),
    "hawaii":      (20.7967, -156.3319),
    "florida":     (27.9944,  -81.7603),
    "california":  (36.7783, -119.4179),
    "texas":       (31.9686,  -99.9018),
    "colorado":    (39.5501, -105.7821),
    # Oceania
    "sydney":      (-33.8688, 151.2093),
    "melbourne":   (-37.8136, 144.9631),
    "auckland":    (-36.8485, 174.7633),
    # Middle East / Africa
    "dubai":       (25.2048,   55.2708),
    "cairo":       (30.0444,   31.2357),
    "cape town":   (-33.9249,  18.4241),
}


class MapTool:
    """
    Geocoding and routing utilities.

    Uses the Google Maps Python client when GOOGLE_MAPS_API_KEY is set;
    otherwise falls back to a city-lookup table + small random jitter so
    that the route-optimiser still gets plausible lat/lng values.
    """

    def __init__(self):
        self._gmaps = None
        if settings.google_maps_api_key:
            try:
                import googlemaps
                self._gmaps = googlemaps.Client(key=settings.google_maps_api_key)
            except ImportError:
                pass

    # ── Public interface ──────────────────────────────────────────────────────

    def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Convert an address string to (lat, lng).

        Returns None if geocoding fails.
        """
        if self._gmaps:
            try:
                results = self._gmaps.geocode(address)
                if results:
                    loc = results[0]["geometry"]["location"]
                    return (loc["lat"], loc["lng"])
            except Exception:
                pass

        return self._mock_geocode(address)

    def calculate_distance(self, poi1: dict, poi2: dict) -> Optional[float]:
        """
        Haversine distance (km) between two POIs.
        """
        if not (poi1.get("lat") and poi1.get("lng")
                and poi2.get("lat") and poi2.get("lng")):
            return None
        return self._haversine(poi1["lat"], poi1["lng"], poi2["lat"], poi2["lng"])

    def get_directions_url(self, pois: List[dict]) -> Optional[str]:
        """
        Build a Google Maps directions URL for an ordered list of POIs.
        """
        geo = [p for p in pois if p.get("lat") and p.get("lng")]
        if len(geo) < 2:
            return None

        pts = [f"{p['lat']},{p['lng']}" for p in geo]
        origin, dest = pts[0], pts[-1]
        if len(pts) > 2:
            wps = "|".join(pts[1:-1])
            return f"https://www.google.com/maps/dir/{origin}/{dest}?waypoints={wps}"
        return f"https://www.google.com/maps/dir/{origin}/{dest}"

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6371.0
        φ1, φ2 = math.radians(lat1), math.radians(lat2)
        dφ = math.radians(lat2 - lat1)
        dλ = math.radians(lng2 - lng1)
        a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    @staticmethod
    def _mock_geocode(address: str) -> Optional[Tuple[float, float]]:
        """
        Return approximate city-centre coords + small jitter.
        Enables route-optimiser testing without a live Maps API.
        """
        addr_lower = address.lower()
        for city, (lat, lng) in _CITY_COORDS.items():
            if city.lower() in addr_lower:
                offset = 0.015
                return (
                    lat + random.uniform(-offset, offset),
                    lng + random.uniform(-offset, offset),
                )
        # Unknown location — return None so the orchestrator skips geocoding
        # rather than silently placing the POI in the wrong city.
        return None
