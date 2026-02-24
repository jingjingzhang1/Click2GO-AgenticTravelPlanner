"""
Click2GO – LangGraph Agentic Orchestrator
==========================================
Pipeline:
  START
    └─► scrape_pois      (Xiaohongshu discovery)
          └─► verify_pois    (Claude verification loop)
                └─► filter_pois   (drop rejected/closed POIs)
                      ├─[enough] ─► optimize_route  (K-Means clustering)
                      └─[retry]  ─► scrape_pois      (broader search fallback)
                                        └─► verify_pois → filter_pois
                                                └─► optimize_route
                                                      └─► generate_output
                                                            └─► END
"""
import uuid
from datetime import datetime
from typing import List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from ..tools.social_scraper_tool import SocialScraperTool
from ..tools.map_tool import MapTool
from ..agents.verification_agent import VerificationAgent
from ..services.route_optimizer import RouteOptimizer
from ..tools.itinerary_exporter import ItineraryExporter


# ── State definition ─────────────────────────────────────────────────────────

class PlanningState(TypedDict):
    # Inputs
    session_id: str
    destination: str
    start_date: str
    end_date: str
    personas: List[str]      # one or more: ["photography", "foodie", ...]
    constraints: dict
    max_pois_per_day: int

    # Pipeline data
    raw_pois: List[dict]
    verified_pois: List[dict]
    rejected_pois: List[dict]
    clustered_days: List[List[dict]]

    # Outputs
    pdf_path: Optional[str]
    map_path: Optional[str]

    # Bookkeeping
    scrape_attempts: int
    status: str
    error: Optional[str]
    stats: dict


# ── Orchestrator ──────────────────────────────────────────────────────────────

class TravelPlanningOrchestrator:
    """
    Stateful agentic travel planner implemented as a LangGraph StateGraph.
    """

    PERSONA_KEYWORDS = {
        "photography": ["拍照打卡", "摄影景点", "ins风"],
        "chilling":    ["咖啡厅", "休闲", "氛围感"],
        "foodie":      ["美食推荐", "必吃", "特色小吃"],
        "exercise":    ["徒步", "户外运动", "骑行"],
    }

    def __init__(self):
        self.scraper  = SocialScraperTool()
        self.map_tool = MapTool()
        self.verifier = VerificationAgent()
        self.optimizer = RouteOptimizer()
        self.exporter  = ItineraryExporter()
        self.graph = self._build_graph()

    # ── Graph construction ────────────────────────────────────────────────────

    def _build_graph(self):
        wf = StateGraph(PlanningState)

        wf.add_node("scrape_pois",     self._scrape_pois)
        wf.add_node("verify_pois",     self._verify_pois)
        wf.add_node("filter_pois",     self._filter_pois)
        wf.add_node("optimize_route",  self._optimize_route)
        wf.add_node("generate_output", self._generate_output)

        wf.add_edge(START,            "scrape_pois")
        wf.add_edge("scrape_pois",    "verify_pois")
        wf.add_edge("verify_pois",    "filter_pois")
        wf.add_conditional_edges(
            "filter_pois",
            self._check_sufficiency,
            {
                "ok":    "optimize_route",
                "retry": "scrape_pois",
                "force": "optimize_route",
            },
        )
        wf.add_edge("optimize_route",  "generate_output")
        wf.add_edge("generate_output", END)

        return wf.compile()

    # ── Node implementations ──────────────────────────────────────────────────

    def _scrape_pois(self, state: PlanningState) -> dict:
        destination = state["destination"]
        personas    = state["personas"]          # now a list
        attempt     = state.get("scrape_attempts", 0) + 1

        # Build one general query + one per selected persona
        queries = [f"{destination}旅游攻略"]
        for p in personas:
            kw = self.PERSONA_KEYWORDS.get(p, [""])[0]
            if kw:
                queries.append(f"{destination}{kw}")
        if attempt > 1:
            queries.append(f"{destination}景点推荐")

        raw_pois: List[dict] = []
        seen: set = set()
        for q in queries:
            results = self.scraper.search_pois(q, max_results=15)
            for p in results:
                if p["name"] not in seen:
                    seen.add(p["name"])
                    raw_pois.append(p)

        # Cap at 20 candidates
        raw_pois = raw_pois[:20]

        return {
            "raw_pois":       raw_pois,
            "scrape_attempts": attempt,
            "status":         "scraping_complete",
            "stats": {
                **state.get("stats", {}),
                "total_scraped": len(raw_pois),
            },
        }

    def _verify_pois(self, state: PlanningState) -> dict:
        raw_pois   = state["raw_pois"]
        personas   = state["personas"]
        persona    = " & ".join(personas)        # e.g. "photography & foodie"
        start_date = state["start_date"]
        end_date   = state["end_date"]

        verified: List[dict] = []

        for poi in raw_pois:
            # Fetch 5 most-recent posts for "Reality Check"
            recent = self.scraper.get_recent_posts(poi["name"], num_posts=5)
            posts  = [p.get("content", "") for p in recent if p.get("content")]

            result = self.verifier.verify(
                poi_name=poi["name"],
                recent_posts=posts,
                persona=persona,
                start_date=start_date,
                end_date=end_date,
            )

            # Geocode while we're here
            if poi.get("address") and not poi.get("lat"):
                coords = self.map_tool.geocode(poi["address"])
                if coords:
                    poi["lat"], poi["lng"] = coords

            # Prefer AI-returned score; fall back to score embedded by scraper mock data
            ai_score = result.get("persona_score")
            score = ai_score if (ai_score is not None and ai_score != 5.0) \
                    else poi.get("persona_score", ai_score or 5.0)

            verified.append({
                **poi,
                "is_open":                   result.get("is_open"),
                "seasonal_match":            result.get("seasonal_match"),
                "persona_score":             score,
                "recommendation":            result.get("recommendation", "INCLUDE"),
                "reasoning":                 result.get("reasoning", ""),
                "agent_note":                result.get("agent_note", ""),
            })

        return {
            "verified_pois": verified,
            "status":        "verification_complete",
            "stats": {
                **state.get("stats", {}),
                "total_verified": len(verified),
            },
        }

    def _filter_pois(self, state: PlanningState) -> dict:
        verified = state["verified_pois"]

        included = [
            p for p in verified
            if p.get("recommendation") != "EXCLUDE"
            and p.get("is_open") is not False
        ]
        rejected = [p for p in verified if p not in included]

        # Sort by persona alignment score (descending)
        included.sort(key=lambda p: p.get("persona_score", 0), reverse=True)

        return {
            "verified_pois": included,
            "rejected_pois": rejected,
            "status":        "filtering_complete",
            "stats": {
                **state.get("stats", {}),
                "total_included": len(included),
                "total_rejected": len(rejected),
            },
        }

    def _check_sufficiency(self, state: PlanningState) -> str:
        included = state.get("verified_pois", [])
        try:
            days = (
                datetime.strptime(state["end_date"],   "%Y-%m-%d")
                - datetime.strptime(state["start_date"], "%Y-%m-%d")
            ).days + 1
        except Exception:
            days = 3

        min_needed = max(days * 2, 4)

        if len(included) >= min_needed:
            return "ok"
        if state.get("scrape_attempts", 0) >= 2:
            return "force"          # proceed with whatever we have
        return "retry"

    def _optimize_route(self, state: PlanningState) -> dict:
        included = state["verified_pois"]
        max_per_day = state.get("max_pois_per_day", 5)

        try:
            days = (
                datetime.strptime(state["end_date"],   "%Y-%m-%d")
                - datetime.strptime(state["start_date"], "%Y-%m-%d")
            ).days + 1
        except Exception:
            days = 3

        geocoded   = [p for p in included if p.get("lat") and p.get("lng")]
        ungeocoded = [p for p in included if not (p.get("lat") and p.get("lng"))]

        if geocoded:
            clustered = self.optimizer.cluster_pois_by_day(
                geocoded, num_days=days, max_per_day=max_per_day
            )
        else:
            clustered = self.optimizer.distribute_evenly(included, num_days=days, max_per_day=max_per_day)

        # Append un-geocoded POIs across days
        for i, poi in enumerate(ungeocoded):
            day_idx = i % max(len(clustered), 1)
            if day_idx < len(clustered):
                clustered[day_idx].append(poi)

        return {"clustered_days": clustered, "status": "routing_complete"}

    def _generate_output(self, state: PlanningState) -> dict:
        session_id    = state["session_id"]
        clustered_days = state["clustered_days"]

        personas = state["personas"]
        user_profile = {
            "destination": state["destination"],
            "start_date":  state["start_date"],
            "end_date":    state["end_date"],
            "persona":     " & ".join(p.capitalize() for p in personas),
        }
        itinerary = {
            "session_id": session_id,
            "days":       clustered_days,
            "stats":      state.get("stats", {}),
        }

        pdf_path = self.exporter.generate_pdf(itinerary, user_profile)
        map_path = self.exporter.generate_route_map(itinerary, user_profile)

        return {"pdf_path": pdf_path, "map_path": map_path, "status": "completed"}

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, request: dict) -> dict:
        """
        Execute the full planning pipeline synchronously.

        Args:
            request: dict with keys destination, start_date, end_date,
                     persona, constraints, max_pois_per_day

        Returns:
            Final PlanningState dict
        """
        session_id = request.get("session_id") or str(uuid.uuid4())

        # Accept either new `personas` list or legacy single `persona`
        raw_personas = request.get("personas") or [request.get("persona", "chilling")]
        personas = [raw_personas] if isinstance(raw_personas, str) else raw_personas

        initial: PlanningState = {
            "session_id":      session_id,
            "destination":     request["destination"],
            "start_date":      request["start_date"],
            "end_date":        request["end_date"],
            "personas":        personas,
            "constraints":     request.get("constraints", {}),
            "max_pois_per_day": request.get("max_pois_per_day", 5),
            "raw_pois":        [],
            "verified_pois":   [],
            "rejected_pois":   [],
            "clustered_days":  [],
            "pdf_path":        None,
            "map_path":        None,
            "scrape_attempts": 0,
            "status":          "pending",
            "error":           None,
            "stats":           {},
        }

        try:
            return self.graph.invoke(initial)
        except Exception as exc:
            return {**initial, "status": "failed", "error": str(exc)}
