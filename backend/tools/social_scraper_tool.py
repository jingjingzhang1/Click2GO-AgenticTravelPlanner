"""
DEPRECATED — Social scraper (removed)
=====================================
Click2GO no longer scrapes Xiaohongshu (Red Note). Place data now comes from
``backend/tools/place_provider.py`` (curated datasets + optional Google Places).

This thin shim remains only so any lingering imports keep working; it simply
delegates to the Place provider and performs no network scraping or login.
"""
from __future__ import annotations

from typing import Dict, List

from .place_provider import get_place_provider


class SocialScraperTool:
    """Backwards-compatible facade over the Place provider (no scraping)."""

    def __init__(self) -> None:
        self._provider = get_place_provider()

    def search_pois(self, keyword: str, max_results: int = 20) -> List[Dict]:
        # Best-effort: treat the keyword as a destination and return curated places.
        return self._provider.get_places(keyword, ["chilling", "photography"], max_results)

    def get_recent_posts(self, poi_name: str, num_posts: int = 5) -> List[Dict]:
        # Social posts are no longer scraped.
        return []
