"""
Click2GO — LangGraph Multi-Agent Supervisor
============================================
Orchestrates three specialized autonomous agents via the Supervisor pattern:

  Supervisor
    ├── Agent 1: Knowledge Manager   (scrape → verify → cache)
    ├── Agent 2: Route Optimizer     (cluster → fill gaps → write)
    └── Agent 3: Design & UI Agent   (map → PDF → cover image)

Flow:
  START → supervisor → knowledge_manager → supervisor → check_sufficiency
       → route_optimizer → supervisor → design_agent → supervisor → END
"""
import uuid
from datetime import datetime
from typing import List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from ..agents.knowledge_agent import KnowledgeManagerAgent
from ..agents.route_agent import RouteOptimizerAgent
from ..agents.design_agent import DesignAgent


# ── Shared state across all agents ──────────────────────────────────────────

class SupervisorState(TypedDict):
    # Inputs
    session_id: str
    destination: str
    start_date: str
    end_date: str
    personas: List[str]
    constraints: dict
    hotel: dict
    max_pois_per_day: int
    language: str

    # Agent 1 outputs
    raw_pois: List[dict]
    verified_pois: List[dict]
    rejected_pois: List[dict]
    scrape_attempts: int

    # Agent 2 outputs
    clustered_days: List[List[dict]]

    # Agent 3 outputs
    pdf_path: Optional[str]
    map_path: Optional[str]
    cover_image_url: Optional[str]
    map_config: dict

    # Bookkeeping
    current_agent: str
    status: str
    error: Optional[str]
    stats: dict


# ── Multi-Agent Supervisor ──────────────────────────────────────────────────

class MultiAgentSupervisor:
    """
    LangGraph Multi-Agent Supervisor that coordinates the three
    specialized agents in a structured pipeline with conditional routing.
    """

    def __init__(self):
        self.knowledge_agent = KnowledgeManagerAgent()
        self.route_agent = RouteOptimizerAgent()
        self.design_agent = DesignAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        wf = StateGraph(SupervisorState)

        # Agent nodes
        wf.add_node("knowledge_manager", self._run_knowledge_manager)
        wf.add_node("route_optimizer", self._run_route_optimizer)
        wf.add_node("design_agent", self._run_design_agent)

        # Routing node
        wf.add_node("check_sufficiency", self._check_sufficiency_node)

        # Flow: START → knowledge → check → route/retry → design → END
        wf.add_edge(START, "knowledge_manager")
        wf.add_edge("knowledge_manager", "check_sufficiency")
        wf.add_conditional_edges(
            "check_sufficiency",
            self._sufficiency_router,
            {
                "ok": "route_optimizer",
                "retry": "knowledge_manager",
                "force": "route_optimizer",
            },
        )
        wf.add_edge("route_optimizer", "design_agent")
        wf.add_edge("design_agent", END)

        return wf.compile()

    # ── Agent runner nodes ───────────────────────────────────────────────

    def _run_knowledge_manager(self, state: SupervisorState) -> dict:
        """Delegate to Agent 1: Knowledge Manager."""
        result = self.knowledge_agent.run(state)
        return {
            **result,
            "current_agent": "knowledge_manager",
        }

    def _run_route_optimizer(self, state: SupervisorState) -> dict:
        """Delegate to Agent 2: Route Optimizer."""
        result = self.route_agent.run(state)
        return {
            **result,
            "current_agent": "route_optimizer",
        }

    def _run_design_agent(self, state: SupervisorState) -> dict:
        """Delegate to Agent 3: Design & UI Agent."""
        result = self.design_agent.run(state)
        return {
            **result,
            "current_agent": "design_agent",
        }

    # ── Sufficiency check ────────────────────────────────────────────────

    def _check_sufficiency_node(self, state: SupervisorState) -> dict:
        """Evaluate whether we have enough POIs to proceed."""
        return {"status": "checking_sufficiency"}

    def _sufficiency_router(self, state: SupervisorState) -> str:
        """Route based on POI count vs. trip length."""
        included = state.get("verified_pois", [])
        try:
            days = (
                datetime.strptime(state["end_date"], "%Y-%m-%d")
                - datetime.strptime(state["start_date"], "%Y-%m-%d")
            ).days + 1
        except Exception:
            days = 3

        min_needed = max(days * 2, 4)

        if len(included) >= min_needed:
            return "ok"
        if state.get("scrape_attempts", 0) >= 2:
            return "force"
        return "retry"

    # ── Public entry point ───────────────────────────────────────────────

    def run(self, request: dict) -> dict:
        """
        Execute the full multi-agent planning pipeline.

        Args:
            request: dict with destination, start_date, end_date,
                     personas, constraints, max_pois_per_day, language

        Returns:
            Final SupervisorState dict
        """
        session_id = request.get("session_id") or str(uuid.uuid4())

        raw_personas = request.get("personas") or [request.get("persona", "chilling")]
        personas = [raw_personas] if isinstance(raw_personas, str) else raw_personas

        initial: SupervisorState = {
            "session_id": session_id,
            "destination": request["destination"],
            "start_date": request["start_date"],
            "end_date": request["end_date"],
            "personas": personas,
            "constraints": request.get("constraints", {}),
            "hotel": request.get("hotel") or {},
            "max_pois_per_day": request.get("max_pois_per_day", 5),
            "language": request.get("language", "en"),
            "raw_pois": [],
            "verified_pois": [],
            "rejected_pois": [],
            "scrape_attempts": 0,
            "clustered_days": [],
            "pdf_path": None,
            "map_path": None,
            "cover_image_url": None,
            "map_config": {},
            "current_agent": "",
            "status": "pending",
            "error": None,
            "stats": {},
        }

        try:
            return self.graph.invoke(initial)
        except Exception as exc:
            return {**initial, "status": "failed", "error": str(exc)}
