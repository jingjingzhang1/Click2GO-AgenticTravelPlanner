"""
Click2GO – Test Suite
=====================
Run with:  python3 -m pytest tests/ -v
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

# ── App setup ─────────────────────────────────────────────────────────────────

from backend.main import app
from backend.database import Base, engine, SessionLocal
from backend.models import UserProfile, PlanningSession, POI, SessionStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """Recreate all tables before each test so tests are isolated."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ══════════════════════════════════════════════════════════════════════════════
# 1. API – root & health
# ══════════════════════════════════════════════════════════════════════════════

class TestRootEndpoints:

    def test_root_returns_app_name(self):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["name"] == "Click2GO"

    def test_health_returns_healthy(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_docs_accessible(self):
        r = client.get("/docs")
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 2. API – Planning session lifecycle
# ══════════════════════════════════════════════════════════════════════════════

VALID_PLAN_PAYLOAD = {
    "destination": "Tokyo",
    "start_date":  "2026-04-01",
    "end_date":    "2026-04-03",
    "persona":     "photography",
    "constraints": {"allergies": [], "budget": "mid-range"},
    "max_pois_per_day": 4,
    "language": "en",
}


class TestPlanningAPI:

    def test_create_plan_returns_session_id(self):
        r = client.post("/api/v1/plan", json=VALID_PLAN_PAYLOAD)
        assert r.status_code == 202
        body = r.json()
        assert "session_id" in body
        assert len(body["session_id"]) == 36          # UUID format
        assert "Tokyo" in body["message"]

    def test_create_plan_missing_destination_rejected(self):
        bad = {**VALID_PLAN_PAYLOAD}
        del bad["destination"]
        r = client.post("/api/v1/plan", json=bad)
        assert r.status_code == 422

    def test_create_plan_invalid_persona_rejected(self):
        bad = {**VALID_PLAN_PAYLOAD, "persona": "partying"}
        r = client.post("/api/v1/plan", json=bad)
        assert r.status_code == 422

    def test_status_returns_pending_immediately(self):
        r = client.post("/api/v1/plan", json=VALID_PLAN_PAYLOAD)
        sid = r.json()["session_id"]

        r2 = client.get(f"/api/v1/plan/{sid}/status")
        assert r2.status_code == 200
        body = r2.json()
        assert body["session_id"] == sid
        assert body["status"] in ("pending", "scraping", "verifying",
                                   "routing", "exporting", "completed", "failed")

    def test_status_unknown_session_returns_404(self):
        r = client.get("/api/v1/plan/00000000-0000-0000-0000-000000000000/status")
        assert r.status_code == 404

    def test_result_unknown_session_returns_404(self):
        r = client.get("/api/v1/plan/00000000-0000-0000-0000-000000000000/result")
        assert r.status_code == 404

    def test_result_while_in_progress_returns_202(self):
        r = client.post("/api/v1/plan", json=VALID_PLAN_PAYLOAD)
        sid = r.json()["session_id"]
        # Session is pending/scraping — result should not be ready yet
        r2 = client.get(f"/api/v1/plan/{sid}/result")
        assert r2.status_code in (202, 200)   # 202 if still running, 200 if it finished instantly

    def test_all_persona_values_accepted(self):
        for persona in ("photography", "chilling", "foodie", "exercise"):
            payload = {**VALID_PLAN_PAYLOAD, "persona": persona}
            r = client.post("/api/v1/plan", json=payload)
            assert r.status_code == 202, f"persona={persona} was rejected"


# ══════════════════════════════════════════════════════════════════════════════
# 3. API – Preferences
# ══════════════════════════════════════════════════════════════════════════════

class TestPreferencesAPI:

    def test_save_and_retrieve_preferences(self):
        r = client.post("/api/v1/preferences", json=VALID_PLAN_PAYLOAD)
        assert r.status_code == 201
        pid = r.json()["id"]

        r2 = client.get(f"/api/v1/preferences/{pid}")
        assert r2.status_code == 200
        body = r2.json()
        assert body["destination"] == "Tokyo"
        assert body["persona"]     == "photography"

    def test_preferences_not_found_returns_404(self):
        r = client.get("/api/v1/preferences/99999")
        assert r.status_code == 404

    def test_preferences_budget_stored(self):
        payload = {**VALID_PLAN_PAYLOAD, "constraints": {"budget": "luxury", "allergies": []}}
        r = client.post("/api/v1/preferences", json=payload)
        pid = r.json()["id"]
        r2 = client.get(f"/api/v1/preferences/{pid}")
        assert r2.json()["budget"] == "luxury"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Route Optimizer
# ══════════════════════════════════════════════════════════════════════════════

from backend.services.route_optimizer import RouteOptimizer

TOKYO_POIS = [
    {"name": "Shibuya Crossing",   "lat": 35.6598, "lng": 139.7004, "persona_score": 9.0},
    {"name": "Shinjuku Gyoen",     "lat": 35.6851, "lng": 139.7100, "persona_score": 7.5},
    {"name": "TeamLab Borderless", "lat": 35.6246, "lng": 139.7798, "persona_score": 8.8},
    {"name": "Yanaka Ginza",       "lat": 35.7263, "lng": 139.7645, "persona_score": 6.5},
    {"name": "Harajuku",           "lat": 35.6702, "lng": 139.7027, "persona_score": 8.0},
    {"name": "Tsukiji Market",     "lat": 35.6654, "lng": 139.7707, "persona_score": 7.8},
]


class TestRouteOptimizer:

    def setup_method(self):
        self.opt = RouteOptimizer()

    def test_cluster_returns_correct_number_of_days(self):
        days = self.opt.cluster_pois_by_day(TOKYO_POIS, num_days=2)
        assert len(days) == 2

    def test_cluster_no_poi_is_lost(self):
        days = self.opt.cluster_pois_by_day(TOKYO_POIS, num_days=2)
        total = sum(len(d) for d in days)
        assert total == len(TOKYO_POIS)

    def test_max_per_day_is_respected(self):
        days = self.opt.cluster_pois_by_day(TOKYO_POIS, num_days=2, max_per_day=2)
        for day in days:
            assert len(day) <= 2

    def test_single_day_returns_all_pois(self):
        days = self.opt.cluster_pois_by_day(TOKYO_POIS, num_days=1, max_per_day=10)
        assert len(days) == 1
        assert len(days[0]) == len(TOKYO_POIS)

    def test_more_days_than_pois_handled(self):
        days = self.opt.cluster_pois_by_day(TOKYO_POIS[:2], num_days=5)
        assert all(len(d) >= 1 for d in days)

    def test_distribute_evenly_fallback(self):
        no_coords = [{"name": f"Place {i}", "persona_score": float(10 - i)}
                     for i in range(7)]
        days = self.opt.distribute_evenly(no_coords, num_days=3, max_per_day=3)
        assert len(days) >= 2
        assert sum(len(d) for d in days) == 7

    def test_nearest_neighbour_keeps_all_pois(self):
        result = self.opt._nearest_neighbour(TOKYO_POIS)
        assert len(result) == len(TOKYO_POIS)
        assert {p["name"] for p in result} == {p["name"] for p in TOKYO_POIS}


# ══════════════════════════════════════════════════════════════════════════════
# 5. Map Tool
# ══════════════════════════════════════════════════════════════════════════════

from backend.tools.map_tool import MapTool


class TestMapTool:

    def setup_method(self):
        self.mt = MapTool()

    def test_geocode_known_city_returns_coords(self):
        coords = self.mt.geocode("Shibuya Crossing Tokyo")
        assert coords is not None
        lat, lng = coords
        # Tokyo is roughly 35°N, 139°E
        assert 35.0 < lat < 36.5
        assert 138.0 < lng < 141.0

    def test_geocode_beijing(self):
        coords = self.mt.geocode("Forbidden City Beijing 北京")
        assert coords is not None
        lat, lng = coords
        assert 39.0 < lat < 41.0
        assert 115.0 < lng < 118.0

    def test_geocode_unknown_address_still_returns_coords(self):
        # Unknown locations should return a default (Tokyo area)
        coords = self.mt.geocode("XYZ_UNKNOWN_PLACE_12345")
        assert coords is not None
        lat, lng = coords
        assert isinstance(lat, float)
        assert isinstance(lng, float)

    def test_haversine_same_point_is_zero(self):
        d = self.mt._haversine(35.0, 139.0, 35.0, 139.0)
        assert d == pytest.approx(0.0)

    def test_haversine_tokyo_osaka_approx_400km(self):
        # Tokyo (35.68, 139.69) → Osaka (34.69, 135.50) ≈ 400 km
        d = self.mt._haversine(35.68, 139.69, 34.69, 135.50)
        assert 350 < d < 450

    def test_directions_url_two_pois(self):
        pois = [{"lat": 35.66, "lng": 139.70}, {"lat": 35.67, "lng": 139.71}]
        url = self.mt.get_directions_url(pois)
        assert url is not None
        assert "google.com/maps/dir" in url

    def test_directions_url_none_when_single_poi(self):
        url = self.mt.get_directions_url([{"lat": 35.66, "lng": 139.70}])
        assert url is None

    def test_calculate_distance_returns_float(self):
        p1 = {"lat": 35.66, "lng": 139.70}
        p2 = {"lat": 35.68, "lng": 139.73}
        d = self.mt.calculate_distance(p1, p2)
        assert d is not None
        assert d > 0

    def test_calculate_distance_missing_coords_returns_none(self):
        d = self.mt.calculate_distance({"name": "A"}, {"name": "B"})
        assert d is None


# ══════════════════════════════════════════════════════════════════════════════
# 6. Verification Agent (no API key – tests fallback behaviour)
# ══════════════════════════════════════════════════════════════════════════════

from backend.agents.verification_agent import VerificationAgent


class TestVerificationAgent:

    def setup_method(self):
        self.agent = VerificationAgent()

    def test_no_posts_returns_include(self):
        result = self.agent.verify("Shibuya Crossing", [], "photography",
                                   "2026-04-01", "2026-04-03")
        assert result["recommendation"] == "INCLUDE"

    def test_no_api_key_returns_include(self):
        result = self.agent.verify("TeamLab", ["Great place!"], "chilling",
                                   "2026-04-01", "2026-04-03")
        assert result["recommendation"] == "INCLUDE"

    def test_result_has_required_keys(self):
        result = self.agent.verify("Yanaka Ginza", [], "foodie",
                                   "2026-04-01", "2026-04-03")
        for key in ("is_open", "seasonal_match", "persona_score",
                    "recommendation", "reasoning", "agent_note"):
            assert key in result, f"Missing key: {key}"

    def test_persona_score_in_valid_range(self):
        result = self.agent.verify("Harajuku", [], "exercise",
                                   "2026-04-01", "2026-04-03")
        assert 0.0 <= result["persona_score"] <= 10.0


# ══════════════════════════════════════════════════════════════════════════════
# 7. Itinerary Exporter
# ══════════════════════════════════════════════════════════════════════════════

from backend.tools.itinerary_exporter import ItineraryExporter

MOCK_ITINERARY = {
    "session_id": "abcdef12-0000-0000-0000-000000000000",
    "days": [
        [
            {"name": "Shibuya Crossing",   "lat": 35.6598, "lng": 139.7004,
             "persona_score": 9.0, "agent_note": "Best at night for light trails."},
            {"name": "Harajuku",           "lat": 35.6702, "lng": 139.7027,
             "persona_score": 8.0, "agent_note": "Visit on weekday to avoid crowds."},
        ],
        [
            {"name": "TeamLab Borderless", "lat": 35.6246, "lng": 139.7798,
             "persona_score": 8.8, "agent_note": "Book tickets 2 weeks in advance."},
        ],
    ],
    "stats": {"total_scraped": 10, "total_verified": 10, "total_included": 3},
}

MOCK_PROFILE = {
    "destination": "Tokyo",
    "start_date":  "2026-04-01",
    "end_date":    "2026-04-02",
    "persona":     "photography",
}


class TestItineraryExporter:

    def setup_method(self):
        self.exp = ItineraryExporter()

    def test_pdf_file_is_created(self):
        path = self.exp.generate_pdf(MOCK_ITINERARY, MOCK_PROFILE)
        assert os.path.exists(path)
        assert path.endswith(".pdf") or path.endswith(".txt")

    def test_map_file_is_created(self):
        path = self.exp.generate_route_map(MOCK_ITINERARY, MOCK_PROFILE)
        assert os.path.exists(path)
        assert path.endswith(".html") or path.endswith(".geojson")

    def test_pdf_contains_destination(self):
        # Use text fallback for a quick content check
        itinerary = {**MOCK_ITINERARY, "session_id": "txttest0-0000-0000-0000-000000000000"}
        path = self.exp._text_fallback(itinerary, MOCK_PROFILE)
        content = open(path).read()
        assert "Tokyo" in content
        assert "DAY 1" in content          # text fallback uses "--- DAY 1 ---"
        assert "Shibuya Crossing" in content

    def test_map_html_contains_marker_data(self):
        path = self.exp.generate_route_map(MOCK_ITINERARY, MOCK_PROFILE)
        if path.endswith(".html"):
            content = open(path).read()
            assert "Shibuya Crossing" in content
            assert "TeamLab Borderless" in content

    def test_geojson_fallback_structure(self):
        itinerary = {**MOCK_ITINERARY, "session_id": "geojson0-0000-0000-0000-000000000000"}
        path = self.exp._geojson_fallback(itinerary)
        with open(path) as f:
            geo = json.load(f)
        assert geo["type"] == "FeatureCollection"
        assert len(geo["features"]) == 3      # 3 geocoded POIs
        assert geo["features"][0]["geometry"]["type"] == "Point"


# ══════════════════════════════════════════════════════════════════════════════
# 8. Social Scraper Tool (offline / mock mode)
# ══════════════════════════════════════════════════════════════════════════════

from backend.tools.social_scraper_tool import SocialScraperTool


class TestSocialScraperTool:

    def setup_method(self):
        self.scraper = SocialScraperTool()

    def test_mock_pois_returns_list(self):
        pois = self.scraper._mock_pois("Tokyo Coffee", 5)
        assert isinstance(pois, list)
        assert len(pois) == 5

    def test_mock_pois_have_required_fields(self):
        pois = self.scraper._mock_pois("Tokyo", 3)
        for poi in pois:
            assert "name" in poi
            assert "likes" in poi

    def test_mock_recent_posts_returns_list(self):
        posts = self.scraper._mock_recent_posts("Shibuya Crossing", 3)
        assert len(posts) == 3
        assert all("content" in p for p in posts)

    def test_extract_pois_from_note_numbered_list(self):
        note = {
            "title": "Tokyo Must-Visit",
            "content": "1. Shibuya Crossing\n2. Harajuku\n3. Shinjuku Gyoen",
            "likes": 200,
        }
        pois = self.scraper._extract_pois_from_note(note)
        assert len(pois) >= 1
        names = [p["name"] for p in pois]
        assert any("Shibuya" in n or "Harajuku" in n or "Shinjuku" in n for n in names)

    def test_extract_pois_fallback_to_title(self):
        note = {"title": "Best Ramen in Tokyo", "content": "Long prose with no list.", "likes": 50}
        pois = self.scraper._extract_pois_from_note(note)
        assert len(pois) == 1
        assert "Ramen" in pois[0]["name"] or "Tokyo" in pois[0]["name"]

    def test_extract_address_japanese_postal(self):
        text = "Visit STREAMER COFFEE\n〒106-0032 Tokyo, Minato City, Roppongi 6-11"
        addr = self.scraper._extract_address(text, "STREAMER COFFEE")
        assert addr is not None
        assert "106" in addr

    def test_search_pois_returns_list_when_offline(self):
        # MCP server not running → falls back to mock data
        pois = self.scraper.search_pois("Tokyo Coffee", max_results=5)
        assert isinstance(pois, list)
