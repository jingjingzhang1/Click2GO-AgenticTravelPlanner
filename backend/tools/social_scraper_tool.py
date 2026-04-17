"""
Social Scraper Tool
===================
MCP-based wrapper around the existing XiaohongshuAPI.
Converts raw note content into structured POI dicts and handles
graceful degradation (mock data) when the MCP server is unavailable.
"""
import os
import re
import sys
from typing import Dict, List, Optional

# Add the project root to sys.path so we can import xiaohongshu_api.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ..config import settings


class SocialScraperTool:
    """
    Wraps XiaohongshuAPI and exposes two high-level methods:

    - search_pois(keyword, max_results)  →  List[POI dict]
    - get_recent_posts(poi_name, n)       →  List[post dict]
    """

    def __init__(self):
        self._api = None           # lazy-init
        self._login_ok = False
        self._login_checked = False

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_api(self):
        if self._api is None:
            try:
                from xiaohongshu_api import XiaohongshuAPI
                self._api = XiaohongshuAPI(mcp_url=settings.mcp_server_url)
            except ImportError:
                pass
        return self._api

    def _ensure_login(self) -> bool:
        if self._login_checked:
            return self._login_ok
        api = self._get_api()
        if api is None:
            self._login_checked = True
            return False
        try:
            self._login_ok = api.check_login()
        except Exception:
            self._login_ok = False
        self._login_checked = True
        return self._login_ok

    # ── Public interface ──────────────────────────────────────────────────────

    def search_pois(self, keyword: str, max_results: int = 20) -> List[Dict]:
        """
        Search Xiaohongshu for travel content and extract POI candidates.

        Falls back to mock data when the MCP server is unreachable.
        """
        if not self._ensure_login():
            return self._mock_pois(keyword, max_results)

        api = self._get_api()
        try:
            notes = api.search_and_extract(keyword, max_notes=max_results, delay=1.0)
        except Exception:
            return self._mock_pois(keyword, max_results)

        pois: List[Dict] = []
        for note in notes:
            pois.extend(self._extract_pois_from_note(note))

        return pois[:max_results]

    def get_recent_posts(self, poi_name: str, num_posts: int = 5) -> List[Dict]:
        """
        Fetch the most-recent posts mentioning a specific POI.
        Used by the Verification Agent for the "Reality Check".
        """
        if not self._ensure_login():
            return self._mock_recent_posts(poi_name, num_posts)

        api = self._get_api()
        feeds = api.search(poi_name, max_results=num_posts)

        posts: List[Dict] = []
        for feed in feeds[:num_posts]:
            try:
                content = api.get_note_content(feed["id"], feed["xsecToken"])
                if content:
                    posts.append({
                        "title":   content.get("title", ""),
                        "content": content.get("content", ""),
                        "id":      feed.get("id", ""),
                        "likes":   feed.get("liked_count", 0),
                    })
            except Exception:
                continue

        return posts

    # ── POI extraction helpers ────────────────────────────────────────────────

    def _extract_pois_from_note(self, note: Dict) -> List[Dict]:
        """
        Parse a Xiaohongshu note and extract individual POI entries.
        Looks for numbered / bullet-style location lists inside travel guides.
        """
        title   = note.get("title", "")
        content = note.get("content", "")
        text    = f"{title}\n{content}"

        pois: List[Dict] = []

        # Match numbered/bulleted list items (e.g. "1.", "①", "📍")
        pattern = r"(?:^|\n)[①②③④⑤⑥⑦⑧⑨⑩📍\d]+[\.、\s]+([^\n]{3,60})"
        matches = re.findall(pattern, text)

        for raw_name in matches:
            name = raw_name.strip().rstrip("：:，,。.")
            if len(name) < 3 or name.isdigit():
                continue
            pois.append({
                "name":        name[:120],
                "address":     self._extract_address(text, name),
                "raw_content": text[:500],
                "source_url":  note.get("url", ""),
                "likes":       note.get("likes", 0),
            })

        # Fallback: treat the note title itself as one POI
        if not pois and title:
            pois.append({
                "name":        title[:120],
                "address":     None,
                "raw_content": content[:500],
                "source_url":  note.get("url", ""),
                "likes":       note.get("likes", 0),
            })

        return pois[:5]     # cap at 5 per note to avoid duplicates

    @staticmethod
    def _extract_address(text: str, poi_name: str) -> Optional[str]:
        """Look for an address pattern in the text near a POI name."""
        patterns = [
            r"[〒][\d\-]+\s+[^\n]{5,80}",   # Japanese postal code
            r"地址[：:]([^\n]{5,80})",
            r"🏠[：:]?\s*([^\n]{5,80})",
            r"位于([^\n]{5,60})",
            r"在([^\n的]{3,40})[附近]",
        ]
        pos = text.find(poi_name)
        search = text[pos:pos + 500] if pos != -1 else text[:500]

        for pat in patterns:
            m = re.search(pat, search)
            if m:
                return (m.group(1) if m.lastindex else m.group(0)).strip()
        return None

    # ── Mock data (development / offline) ────────────────────────────────────

    # Persona-specific POI templates (name, description, score hint)
    _PERSONA_TEMPLATES = {
        "photography": [
            ("{dest} Golden Hour Viewpoint",   "Famous for stunning sunset photography. Best light at 6–7pm.", 9.2),
            ("{dest} Street Art District",      "Colourful murals and instagrammable walls around every corner.", 8.8),
            ("{dest} Misty Mountain Overlook",  "Cloud-level panorama perfect for landscape shots.", 9.5),
            ("{dest} Old Architecture Quarter", "Preserved historic facades with excellent natural lighting.", 8.5),
            ("{dest} Reflection Pool Garden",   "Symmetrical reflections ideal for mirror photography.", 8.0),
            ("{dest} Abandoned Factory Loft",   "Urban-decay aesthetic popular with portrait photographers.", 7.8),
            ("{dest} Lantern Festival Square",  "Glowing lanterns make for magical long-exposure shots.", 9.0),
            ("{dest} Cliffside Café",           "Glass-floor café perched on a cliff with unobstructed views.", 8.6),
        ],
        "chilling": [
            ("{dest} Riverside Café Row",       "Laid-back waterside cafés with hammocks and slow WiFi.", 9.0),
            ("{dest} Secret Garden Park",       "Hidden green space locals use to read and nap.", 8.7),
            ("{dest} Rooftop Lounge Bar",        "Sunset cocktails with zero dress code.", 8.3),
            ("{dest} Specialty Coffee Alley",   "Tiny independent roasters tucked in a cobblestone lane.", 9.1),
            ("{dest} Floating Library Barge",   "Books, tea, and gentle river waves.", 8.0),
            ("{dest} Night Market Food Court",  "Low-key evening street food with plastic stools.", 8.5),
            ("{dest} Lakeside Hammock Spot",    "Free hammock zone, no booking needed.", 7.9),
            ("{dest} Cat Café & Bookstore",     "Resident cats, vintage paperbacks, and homemade cake.", 8.8),
        ],
        "foodie": [
            ("{dest} Morning Wet Market",       "Where locals shop at 6am — freshest produce in the city.", 9.3),
            ("{dest} Night Street Food Strip",  "Sizzling skewers and mystery noodles under neon signs.", 9.5),
            ("{dest} Heritage Dumpling Shop",   "Family recipe unchanged for 80 years. Cash only.", 9.0),
            ("{dest} Spice Bazaar",             "Sensory overload of local spices, dried fruits and nuts.", 8.6),
            ("{dest} Rooftop Farm-to-Table",    "Chef grows 40% of ingredients on the roof.", 8.4),
            ("{dest} Craft Brewery & Taproom",  "Regional ales brewed on-site, free tasting flights on Fridays.", 8.0),
            ("{dest} Michelin Bib Gourmand Stall", "Cheap eats that made the Michelin list — 2-hour queue typical.", 9.2),
            ("{dest} Dessert Alley",            "Eight dessert shops in a row, try the signature soft-serve.", 8.3),
        ],
        "exercise": [
            ("{dest} Coastal Hiking Trail",     "8km cliffside trail with ocean views, moderate difficulty.", 9.4),
            ("{dest} Sunrise Yoga Deck",        "Outdoor platform overlooking the valley, free drop-in class.", 8.5),
            ("{dest} Kayak Launch Point",       "Rentals available, guides tours through mangrove channels.", 9.0),
            ("{dest} Volcano Summit Trek",      "Strenuous 4-hour ascent rewarded with 360° crater views.", 9.6),
            ("{dest} Urban Cycling Circuit",    "16km signed cycle loop through parks and riverside paths.", 8.2),
            ("{dest} Rock Climbing Crag",       "Natural limestone face with routes for all skill levels.", 8.8),
            ("{dest} Open-Water Swimming Cove", "Calm sheltered bay, regular early-morning swim club.", 8.0),
            ("{dest} Forest Canopy Walkway",    "Suspension bridges 40m above the jungle floor.", 9.1),
        ],
    }

    @staticmethod
    def _mock_pois(keyword: str, n: int) -> List[Dict]:
        import random as _rnd
        from ..tools.map_tool import _CITY_COORDS

        # Detect persona from keyword suffixes before stripping them
        persona = "chilling"  # default
        if any(k in keyword for k in ["拍照", "摄影", "photography"]):
            persona = "photography"
        elif any(k in keyword for k in ["美食", "必吃", "小吃", "foodie"]):
            persona = "foodie"
        elif any(k in keyword for k in ["徒步", "户外", "运动", "exercise"]):
            persona = "exercise"
        elif any(k in keyword for k in ["咖啡", "休闲", "chill"]):
            persona = "chilling"

        # Strip Chinese travel/persona suffixes to get clean destination name
        dest = keyword
        for suffix in ["旅游攻略", "攻略", "旅游", "景点推荐", "景点", "打卡",
                       "美食推荐", "美食", "咖啡", "拍照打卡", "拍照", "摄影",
                       "徒步", "户外运动", "休闲", "必吃", "特色小吃"]:
            dest = dest.split(suffix)[0]
        dest = dest.strip()

        # Resolve city centre coords for mock lat/lng (fuzzy match)
        base_lat, base_lng = 35.6762, 139.6503  # default Tokyo
        dest_lower = dest.lower()
        for city, (clat, clng) in _CITY_COORDS.items():
            # Fuzzy: check if either string contains the other
            if city.lower() in dest_lower or dest_lower in city.lower():
                base_lat, base_lng = clat, clng
                break

        templates = SocialScraperTool._PERSONA_TEMPLATES.get(
            persona, SocialScraperTool._PERSONA_TEMPLATES["chilling"]
        )

        return [
            {
                "name":        tpl[0].format(dest=dest),
                "address":     f"{dest}",
                "raw_content": tpl[1],
                "persona_score": tpl[2],
                "category":    persona,
                "source_url":  "",
                "likes":       max(10, 200 - i * 15),
                "lat":         base_lat + _rnd.uniform(-0.03, 0.03),
                "lng":         base_lng + _rnd.uniform(-0.03, 0.03),
            }
            for i, tpl in enumerate(templates[:n])
        ]

    @staticmethod
    def _mock_recent_posts(poi_name: str, n: int) -> List[Dict]:
        descriptions = [
            f"Just visited {poi_name} — still open and absolutely worth it! No renovation signs.",
            f"{poi_name} was great this weekend. Crowds are manageable on weekday mornings.",
            f"Went to {poi_name} yesterday. Highly recommend, place is thriving.",
        ]
        return [
            {
                "title":   f"My visit to {poi_name}",
                "content": descriptions[i % len(descriptions)],
                "id":      f"mock_{i}",
                "likes":   50 + i * 10,
            }
            for i in range(min(3, n))
        ]
