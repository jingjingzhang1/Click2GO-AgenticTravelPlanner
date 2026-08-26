"""
Place Provider
==============
Click2GO's source of attractions, cafés, and hotels — the replacement for the
(removed) Xiaohongshu scraper. Two strategies behind one interface:

  • CuratedPlaceProvider — hand-curated, always-available datasets. Reliable,
    no API keys, and includes the "nanny-level" practical fields: website,
    reservation link, whether a booking is needed.
  • GooglePlacesProvider — live search/enrichment via Google Places when
    GOOGLE_MAPS_API_KEY is set (real hotels, websites, ratings, coordinates).

``get_place_provider()`` returns a HybridPlaceProvider: curated first, topped
up by Google Places when available. Every provider returns the same place dict:

    {
      name, address, lat, lng, category,        # category = persona bucket
      description, persona_score,                # blurb + 0–10 score
      needs_reservation, reservation_url, website,
      likes,
    }
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..config import settings
from .map_tool import _CITY_COORDS

logger = logging.getLogger("click2go.places")

_PERSONA_CATEGORIES = {"photography", "chilling", "foodie", "exercise"}


def _place(name, address, lat, lng, category, description, score,
           needs_reservation=False, reservation_url=None, website=None,
           likes=0) -> Dict:
    return {
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "category": category,
        "description": description,
        "persona_score": score,
        "needs_reservation": needs_reservation,
        "reservation_url": reservation_url,
        "website": website,
        "likes": likes,
    }


# ── Curated datasets ─────────────────────────────────────────────────────────
_CURATED_PLACES: Dict[str, List[Dict]] = {
    "new york": [
        _place("The Metropolitan Museum of Art", "1000 5th Ave, New York, NY",
               40.7794, -73.9632, "photography",
               "Grand staircase, the Temple of Dendur and a rooftop garden — endlessly photogenic.",
               9.4, needs_reservation=False, reservation_url="https://engage.metmuseum.org/tickets",
               website="https://www.metmuseum.org", likes=980),
        _place("Museum of Modern Art (MoMA)", "11 W 53rd St, New York, NY",
               40.7614, -73.9776, "photography",
               "Iconic modern works and clean gallery lines; timed tickets recommended.",
               9.0, needs_reservation=True, reservation_url="https://www.moma.org/tickets/",
               website="https://www.moma.org", likes=870),
        _place("Brooklyn Bridge", "Brooklyn Bridge, New York, NY",
               40.7061, -73.9969, "photography",
               "Gothic stone arches and cables framing the skyline — best at sunrise.",
               9.5, website="https://www.nyc.gov", likes=1200),
        _place("Statue of Liberty", "Liberty Island, New York, NY",
               40.6892, -74.0445, "photography",
               "Harbor icon; ferry tickets sell out, so book the crossing ahead.",
               9.1, needs_reservation=True, reservation_url="https://www.statuecitycruises.com/",
               website="https://www.nps.gov/stli", likes=1100),
        _place("The High Line", "Gansevoort St, New York, NY",
               40.7480, -74.0048, "photography",
               "Elevated rail-park with leading lines and golden-hour light.",
               8.9, website="https://www.thehighline.org", likes=760),
        _place("Central Park", "Central Park, New York, NY",
               40.7812, -73.9665, "photography",
               "Bow Bridge, the Mall and skyline-framed meadows in every season.",
               9.2, website="https://www.centralparknyc.org", likes=1500),
        _place("SoHo", "SoHo, New York, NY",
               40.7233, -74.0020, "chilling",
               "Cast-iron facades, cobblestones and easy boutique browsing.",
               8.6, likes=540),
        _place("Washington Square Park", "Washington Square, New York, NY",
               40.7308, -73.9973, "chilling",
               "Fountain, street musicians and the arch — relaxed people-watching.",
               8.4, website="https://www.nycgovparks.org", likes=610),
        _place("Devoción", "69 Grand St, Brooklyn, NY",
               40.7147, -73.9601, "chilling",
               "Sun-lit Williamsburg roastery with a living green wall; famously fresh beans.",
               9.0, website="https://www.devocion.com", likes=430),
        _place("Watchhouse", "692 Broadway, New York, NY",
               40.7280, -73.9945, "chilling",
               "Minimalist, design-forward space for a calm, slow flat white.",
               8.8, website="https://watchhouse.com", likes=390),
        _place("La Cabra", "152 Second Ave, New York, NY",
               40.7290, -73.9868, "chilling",
               "Danish-style bakery and coffee bar; cardamom buns and a quiet corner.",
               8.9, website="https://lacabra.dk", likes=410),
        _place("Arcane Estate Coffee", "New York, NY",
               40.7212, -73.9968, "chilling",
               "Low-key specialty spot for a pour-over between neighborhoods.",
               8.5, likes=280),
    ],
}

_CURATED_HOTELS: Dict[str, List[Dict]] = {
    "new york": [
        {"name": "The Standard, High Line", "address": "848 Washington St, New York, NY",
         "lat": 40.7409, "lng": -74.0083, "price_level": "$$$",
         "website": "https://www.standardhotels.com/new-york/properties/high-line",
         "reservation_url": "https://www.standardhotels.com/new-york/properties/high-line",
         "note": "Steps from the High Line and Meatpacking cafés."},
        {"name": "Ace Hotel New York", "address": "20 W 29th St, New York, NY",
         "lat": 40.7449, "lng": -73.9882, "price_level": "$$",
         "website": "https://acehotel.com/new-york/",
         "reservation_url": "https://acehotel.com/new-york/",
         "note": "Central NoMad base; easy subway access in every direction."},
        {"name": "The Hoxton, Williamsburg", "address": "97 Wythe Ave, Brooklyn, NY",
         "lat": 40.7220, "lng": -73.9575, "price_level": "$$",
         "website": "https://thehoxton.com/williamsburg/",
         "reservation_url": "https://thehoxton.com/williamsburg/",
         "note": "Right by Devoción and Williamsburg's coffee scene."},
    ],
}

# Generic fallback templates so any city still produces a usable plan.
_GENERIC = {
    "photography": [("Old Town Viewpoint", "Panoramic overlook, best at golden hour.", 8.6),
                    ("Historic Waterfront", "Classic skyline-and-water shot.", 8.3),
                    ("Landmark Square", "The city's signature plaza and architecture.", 8.0)],
    "chilling": [("Riverside Café", "Laid-back spot for a slow coffee.", 8.4),
                 ("Central Park & Gardens", "Green space to read and unwind.", 8.2),
                 ("Specialty Coffee Lane", "Independent roasters on a quiet street.", 8.5)],
    "foodie": [("Central Food Market", "Local specialties and street snacks.", 8.7),
               ("Heritage Restaurant Row", "Time-tested local kitchens.", 8.4)],
    "exercise": [("Riverside Path", "Flat scenic route for a walk or run.", 8.3),
                 ("City Overlook Trail", "Short climb to a rewarding view.", 8.6)],
}


class CuratedPlaceProvider:
    name = "curated"

    @staticmethod
    def _key(destination: str) -> Optional[str]:
        d = destination.lower()
        for key in _CURATED_PLACES:
            if key in d or d in key:
                return key
        return None

    def get_places(self, destination: str, personas: List[str], limit: int = 20) -> List[Dict]:
        key = self._key(destination)
        wanted = {p.lower() for p in personas} or _PERSONA_CATEGORIES
        if key:
            places = [dict(p) for p in _CURATED_PLACES[key]
                      if (p["category"] in wanted or not p["category"])]
            return places[:limit]
        return self._generic(destination, list(wanted), limit)

    def get_hotels(self, destination: str, limit: int = 5) -> List[Dict]:
        key = self._key(destination)
        if key and key in _CURATED_HOTELS:
            return [dict(h) for h in _CURATED_HOTELS[key]][:limit]
        return []

    @staticmethod
    def _generic(destination: str, personas: List[str], limit: int) -> List[Dict]:
        base_lat, base_lng = 40.0, -74.0
        d = destination.lower()
        for city, (clat, clng) in _CITY_COORDS.items():
            if city in d or d in city:
                base_lat, base_lng = clat, clng
                break
        import random as _rnd
        out: List[Dict] = []
        for persona in personas:
            for i, (nm, desc, score) in enumerate(_GENERIC.get(persona, [])):
                out.append(_place(
                    f"{destination} {nm}", destination,
                    base_lat + _rnd.uniform(-0.03, 0.03),
                    base_lng + _rnd.uniform(-0.03, 0.03),
                    persona, desc, score,
                ))
        return out[:limit]


class GooglePlacesProvider:
    name = "google_places"

    def __init__(self):
        self._client = None
        if settings.google_maps_api_key:
            try:
                import googlemaps
                self._client = googlemaps.Client(key=settings.google_maps_api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google Places unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    _PERSONA_QUERY = {
        "photography": "top photo spots and landmarks",
        "chilling": "best specialty coffee shops and relaxed cafés",
        "foodie": "famous local restaurants and food",
        "exercise": "parks trails and outdoor activities",
    }

    def get_places(self, destination: str, personas: List[str], limit: int = 20) -> List[Dict]:
        if not self.available:
            return []
        results: List[Dict] = []
        seen = set()
        for persona in personas:
            query = f"{self._PERSONA_QUERY.get(persona, 'things to do')} in {destination}"
            try:
                resp = self._client.places(query=query)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Places query failed (%s): %s", query, exc)
                continue
            for r in (resp.get("results") or [])[:6]:
                name = r.get("name")
                if not name or name in seen:
                    continue
                seen.add(name)
                loc = (r.get("geometry") or {}).get("location") or {}
                results.append(_place(
                    name, r.get("formatted_address", destination),
                    loc.get("lat"), loc.get("lng"), persona,
                    r.get("types", ["point of interest"])[0].replace("_", " "),
                    min(10.0, (r.get("rating", 4.0) or 4.0) * 2),
                    website=r.get("website"),
                    likes=r.get("user_ratings_total", 0) or 0,
                ))
        return results[:limit]

    def get_hotels(self, destination: str, limit: int = 5) -> List[Dict]:
        if not self.available:
            return []
        try:
            resp = self._client.places(query=f"hotels in {destination}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Places hotel query failed: %s", exc)
            return []
        hotels = []
        for r in (resp.get("results") or [])[:limit]:
            loc = (r.get("geometry") or {}).get("location") or {}
            hotels.append({
                "name": r.get("name"),
                "address": r.get("formatted_address", destination),
                "lat": loc.get("lat"), "lng": loc.get("lng"),
                "price_level": "$" * int(r.get("price_level", 2) or 2),
                "website": r.get("website"),
                "reservation_url": r.get("website"),
                "note": f"{r.get('rating', '')}★ · {r.get('user_ratings_total', 0)} reviews",
            })
        return hotels


class HybridPlaceProvider:
    """Curated first, Google Places to supplement when available."""

    def __init__(self):
        self.curated = CuratedPlaceProvider()
        self.google = GooglePlacesProvider()

    def get_places(self, destination: str, personas: List[str], limit: int = 20) -> List[Dict]:
        places = self.curated.get_places(destination, personas, limit)
        curated_hit = CuratedPlaceProvider._key(destination) is not None
        # Only reach out to Google when we don't have curated coverage.
        if not curated_hit and self.google.available:
            extra = self.google.get_places(destination, personas, limit)
            if extra:
                return extra[:limit]
        return places[:limit]

    def get_hotels(self, destination: str, limit: int = 5) -> List[Dict]:
        hotels = self.curated.get_hotels(destination, limit)
        if hotels:
            return hotels
        return self.google.get_hotels(destination, limit)


_provider: Optional[HybridPlaceProvider] = None


def get_place_provider() -> HybridPlaceProvider:
    global _provider
    if _provider is None:
        _provider = HybridPlaceProvider()
    return _provider
