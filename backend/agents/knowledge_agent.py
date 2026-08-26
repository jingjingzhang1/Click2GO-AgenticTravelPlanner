"""
Agent 1: The Knowledge Manager
==============================
Curates the destination's places (attractions, cafés, viewpoints) and keeps a
fresh, verified cache. Data now comes from the **Place provider** (curated
datasets + optional Google Places) instead of social-media scraping.

Responsibilities:
  - Check the POI cache for the destination
  - If stale / missing → fetch places from the Place provider
  - Score / sanity-check each place with the LLM (optional; degrades to the
    curated score when no key)
  - Geocode anything missing coordinates
  - Carry practical info (website, reservation link, needs-reservation)
  - Upsert verified places into poi_cache and return qualified places
"""
from typing import Dict, List

from ..agents.verification_agent import VerificationAgent
from ..tools.db_tools import get_cached_pois, upsert_poi_cache
from ..tools.map_tool import MapTool
from ..tools.place_provider import get_place_provider

CACHE_MAX_AGE_HOURS = 72


class KnowledgeManagerAgent:
    """Agent 1 — proactive data curator (curated + Google Places)."""

    def __init__(self):
        self.places = get_place_provider()
        self.map_tool = MapTool()
        self.verifier = VerificationAgent()

    def run(self, state: dict) -> dict:
        destination = state["destination"]
        personas = state["personas"]
        start_date = state["start_date"]
        end_date = state["end_date"]
        attempt = state.get("scrape_attempts", 0) + 1

        # ── Step 1: Cache check ──────────────────────────────────────────
        cached = get_cached_pois(destination, max_age_hours=CACHE_MAX_AGE_HOURS)
        if cached and attempt <= 1:
            filtered = self._filter_by_persona(cached, personas)
            cached_categories = {p.get("category", "").lower() for p in filtered}
            missing = [p for p in personas if p not in cached_categories]
            if not missing and len(filtered) >= 4:
                return {
                    "verified_pois": filtered,
                    "scrape_attempts": attempt,
                    "status": "knowledge_complete",
                    "stats": {
                        "total_scraped": len(cached),
                        "total_verified": len(cached),
                        "total_included": len(filtered),
                        "cache_hit": True,
                    },
                }

        # ── Step 2: Fetch places from the provider ───────────────────────
        raw = self.places.get_places(destination, personas, limit=20)

        # ── Step 3: Score / sanity-check each place ──────────────────────
        persona_label = " & ".join(personas)
        verified = []
        for place in raw:
            evidence = [place.get("description", "")] if place.get("description") else []
            result = self.verifier.verify(
                poi_name=place["name"],
                recent_posts=evidence,
                persona=persona_label,
                start_date=start_date,
                end_date=end_date,
            )

            if not place.get("lat") and place.get("address"):
                coords = self.map_tool.geocode(place["address"])
                if coords:
                    place["lat"], place["lng"] = coords

            used_llm = result.get("source") == "llm"
            ai_score = result.get("persona_score")
            own_score = place.get("persona_score")
            if used_llm and ai_score is not None:
                score = ai_score
            elif own_score is not None:
                score = own_score
            else:
                score = ai_score if ai_score is not None else 6.5

            note = result.get("agent_note", "") if used_llm else (
                place.get("description") or result.get("agent_note", ""))

            verified.append({
                **place,
                "is_open": result.get("is_open"),
                "seasonal_match": result.get("seasonal_match"),
                "persona_score": score,
                "recommendation": result.get("recommendation", "INCLUDE"),
                "reasoning": result.get("reasoning", ""),
                "agent_note": note,
                "persona_tags": personas,
                "seasonal_info": result.get("reasoning", ""),
                "raw_content": place.get("description", ""),
            })

        # ── Step 4: Filter + sort ────────────────────────────────────────
        included = [
            p for p in verified
            if p.get("recommendation") != "EXCLUDE" and p.get("is_open") is not False
        ]
        included.sort(key=lambda p: p.get("persona_score", 0), reverse=True)
        rejected = [p for p in verified if p not in included]

        # ── Step 5: Upsert to cache ──────────────────────────────────────
        upsert_poi_cache(destination, included)

        return {
            "verified_pois": included,
            "rejected_pois": rejected,
            "scrape_attempts": attempt,
            "status": "knowledge_complete",
            "stats": {
                "total_scraped": len(raw),
                "total_verified": len(verified),
                "total_included": len(included),
                "total_rejected": len(rejected),
                "cache_hit": False,
            },
        }

    @staticmethod
    def _filter_by_persona(pois: List[Dict], personas: List[str]) -> List[Dict]:
        """Filter cached places by category (persona type)."""
        filtered = []
        personas_lower = [p.lower() for p in personas]
        for p in pois:
            cat = (p.get("category") or "").lower()
            if not cat or cat in personas_lower:
                filtered.append(p)
        filtered.sort(key=lambda x: x.get("persona_score", 0), reverse=True)
        return filtered
