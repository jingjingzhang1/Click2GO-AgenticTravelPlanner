"""
Agent 1: The Knowledge Manager
==============================
Autonomous data-engineering agent that keeps the destination database fresh.

Responsibilities:
  - Check POI cache freshness for the requested destination
  - If stale / missing → scrape Xiaohongshu via the MCP server
  - Validate each POI with Claude (open? seasonal? persona match?)
  - Geocode addresses
  - Upsert clean, verified POIs into the PostgreSQL poi_cache table
  - Filter by recommendation and return qualified POIs
"""
from datetime import datetime
from typing import Dict, List

from ..tools.social_scraper_tool import SocialScraperTool
from ..tools.map_tool import MapTool
from ..agents.verification_agent import VerificationAgent
from ..tools.db_tools import get_cached_pois, upsert_poi_cache


PERSONA_KEYWORDS = {
    "photography": ["拍照打卡", "摄影景点", "ins风"],
    "chilling":    ["咖啡厅", "休闲", "氛围感"],
    "foodie":      ["美食推荐", "必吃", "特色小吃"],
    "exercise":    ["徒步", "户外运动", "骑行"],
}

# Maximum age (hours) before cached data triggers a background refresh
CACHE_MAX_AGE_HOURS = 72


class KnowledgeManagerAgent:
    """
    Agent 1 — proactive data engineer.

    If a user queries a popular city, data is served instantly from the
    cache. If data is stale or missing, it triggers scraping + validation.
    """

    def __init__(self):
        self.scraper = SocialScraperTool()
        self.map_tool = MapTool()
        self.verifier = VerificationAgent()

    def run(self, state: dict) -> dict:
        """
        Execute the Knowledge Manager pipeline.

        Reads from state:
            destination, personas, start_date, end_date, scrape_attempts

        Returns partial state update:
            verified_pois, stats, status
        """
        destination = state["destination"]
        personas = state["personas"]
        start_date = state["start_date"]
        end_date = state["end_date"]
        attempt = state.get("scrape_attempts", 0) + 1

        # ── Step 1: Check cache ──────────────────────────────────────────
        cached = get_cached_pois(destination, max_age_hours=CACHE_MAX_AGE_HOURS)
        if cached and attempt <= 1:
            filtered = self._filter_by_persona(cached, personas)
            # Check that ALL requested personas are represented in cache
            cached_categories = {p.get("category", "").lower() for p in filtered}
            missing_personas = [p for p in personas if p not in cached_categories]
            if not missing_personas and len(filtered) >= 4:
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

        # ── Step 2: Scrape fresh data ────────────────────────────────────
        raw_pois = self._scrape(destination, personas, attempt)

        # ── Step 3: Verify each POI with Claude ──────────────────────────
        persona_label = " & ".join(personas)
        verified = []
        for poi in raw_pois:
            recent = self.scraper.get_recent_posts(poi["name"], num_posts=5)
            posts = [p.get("content", "") for p in recent if p.get("content")]

            result = self.verifier.verify(
                poi_name=poi["name"],
                recent_posts=posts,
                persona=persona_label,
                start_date=start_date,
                end_date=end_date,
            )

            # Geocode
            if poi.get("address") and not poi.get("lat"):
                coords = self.map_tool.geocode(poi["address"])
                if coords:
                    poi["lat"], poi["lng"] = coords

            # Prefer AI score over scraper hint score
            ai_score = result.get("persona_score")
            score = (
                ai_score
                if (ai_score is not None and ai_score != 5.0)
                else poi.get("persona_score", ai_score or 5.0)
            )

            verified.append({
                **poi,
                "is_open": result.get("is_open"),
                "seasonal_match": result.get("seasonal_match"),
                "persona_score": score,
                "recommendation": result.get("recommendation", "INCLUDE"),
                "reasoning": result.get("reasoning", ""),
                "agent_note": result.get("agent_note", ""),
                "persona_tags": personas,
                "seasonal_info": result.get("reasoning", ""),
            })

        # ── Step 4: Filter ───────────────────────────────────────────────
        included = [
            p for p in verified
            if p.get("recommendation") != "EXCLUDE"
            and p.get("is_open") is not False
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
                "total_scraped": len(raw_pois),
                "total_verified": len(verified),
                "total_included": len(included),
                "total_rejected": len(rejected),
                "cache_hit": False,
            },
        }

    def _scrape(self, destination: str, personas: List[str], attempt: int) -> List[Dict]:
        """Build persona-specific queries and scrape POIs."""
        # General query — tagged as first persona or "chilling"
        queries = [(f"{destination}旅游攻略", personas[0] if personas else "chilling")]
        for p in personas:
            kw = PERSONA_KEYWORDS.get(p, [""])[0]
            if kw:
                queries.append((f"{destination}{kw}", p))
        if attempt > 1:
            queries.append((f"{destination}景点推荐", personas[0] if personas else "chilling"))

        raw_pois: List[Dict] = []
        seen: set = set()
        for q, persona in queries:
            results = self.scraper.search_pois(q, max_results=15)
            for p in results:
                if p["name"] not in seen:
                    seen.add(p["name"])
                    # Tag with the persona that sourced this POI
                    p.setdefault("category", persona)
                    raw_pois.append(p)

        return raw_pois[:20]

    @staticmethod
    def _filter_by_persona(pois: List[Dict], personas: List[str]) -> List[Dict]:
        """Filter cached POIs by category (persona type)."""
        filtered = []
        personas_lower = [p.lower() for p in personas]
        for p in pois:
            cat = (p.get("category") or "").lower()
            # Include if category matches a requested persona, or if no category
            if not cat or cat in personas_lower:
                filtered.append(p)
        # Sort by score
        filtered.sort(key=lambda x: x.get("persona_score", 0), reverse=True)
        return filtered
