"""
Agent 2: The Route Optimizer
============================
Logistical brain of the operation using a hybrid MCP / Python DB workflow.

Hybrid Workflow:
  - Exploration (Postgres MCP): Read-only mode. Discovers filler POIs
    by querying the database when transit gaps are detected.
  - Computation: K-Means clustering + Greedy Nearest-Neighbor sorting.
  - Execution (ORM): Uses strict SQLAlchemy ORM to safely write the
    finalized itinerary back to PostgreSQL.
"""
import math
from datetime import datetime
from typing import Dict, List, Optional

from ..mcp import get_db_explorer
from ..services.route_optimizer import RouteOptimizer
from ..tools.db_tools import save_session_pois
from ..tools.map_tool import MapTool


# Transit gap threshold in km — if consecutive stops are > this apart,
# look for a filler POI to bridge the gap
TRANSIT_GAP_KM = 3.0


class RouteOptimizerAgent:
    """
    Agent 2 — hybrid MCP/ORM route planner.

    Uses the Postgres MCP server for intelligent read-only exploration
    (finding filler POIs in gaps) and standard ORM for safe writes.
    """

    def __init__(self):
        # In-process engine by default; a real MCP client when DB_MCP_ENABLED.
        # Both expose find_nearby_pois(...) with the same signature.
        self.mcp = get_db_explorer()
        self.optimizer = RouteOptimizer()
        self.map_tool = MapTool()

    def run(self, state: dict) -> dict:
        """
        Execute the Route Optimizer pipeline.

        Reads from state:
            session_id, destination, start_date, end_date,
            verified_pois, max_pois_per_day

        Returns partial state update:
            clustered_days, status
        """
        session_id = state["session_id"]
        destination = state["destination"]
        included = state["verified_pois"]
        max_per_day = state.get("max_pois_per_day", 5)

        hotel = state.get("hotel") or {}
        anchor = ((hotel["lat"], hotel["lng"])
                  if hotel.get("lat") is not None and hotel.get("lng") is not None else None)

        try:
            days = (
                datetime.strptime(state["end_date"], "%Y-%m-%d")
                - datetime.strptime(state["start_date"], "%Y-%m-%d")
            ).days + 1
        except Exception:
            days = 3

        # ── Step 1: K-Means clustering ───────────────────────────────────
        geocoded = [p for p in included if p.get("lat") and p.get("lng")]
        ungeocoded = [p for p in included if not (p.get("lat") and p.get("lng"))]

        if geocoded:
            clustered = self.optimizer.cluster_pois_by_day(
                geocoded, num_days=days, max_per_day=max_per_day, anchor=anchor
            )
        else:
            clustered = self.optimizer.distribute_evenly(
                included, num_days=days, max_per_day=max_per_day
            )

        # Distribute un-geocoded POIs
        for i, poi in enumerate(ungeocoded):
            day_idx = i % max(len(clustered), 1)
            if day_idx < len(clustered):
                clustered[day_idx].append(poi)

        # ── Step 2: Fill transit gaps via MCP exploration ────────────────
        clustered = self._fill_transit_gaps(
            clustered, destination, max_per_day, included
        )

        # ── Step 3: Write finalized itinerary via ORM ────────────────────
        save_session_pois(session_id, clustered)

        return {
            "clustered_days": clustered,
            "status": "routing_complete",
        }

    def _fill_transit_gaps(
        self,
        clustered: List[List[Dict]],
        destination: str,
        max_per_day: int,
        existing_pois: List[Dict],
    ) -> List[List[Dict]]:
        """
        Scan each day for large transit gaps between consecutive stops.
        If found, use the Postgres MCP to discover a filler POI nearby.
        """
        existing_names = {p.get("name") for p in existing_pois}

        for day_idx, day_pois in enumerate(clustered):
            if len(day_pois) >= max_per_day:
                continue

            gaps = self._find_gaps(day_pois)
            for gap in gaps:
                if len(clustered[day_idx]) >= max_per_day:
                    break

                mid_lat = (gap["from"]["lat"] + gap["to"]["lat"]) / 2
                mid_lng = (gap["from"]["lng"] + gap["to"]["lng"]) / 2

                # MCP read-only exploration: find nearby cached POIs
                fillers = self.mcp.find_nearby_pois(
                    destination=destination,
                    lat=mid_lat,
                    lng=mid_lng,
                    radius_km=gap["distance_km"] / 2,
                    exclude_names=list(existing_names),
                    limit=3,
                )

                if fillers:
                    best = fillers[0]
                    filler_poi = {
                        "name": best["name"],
                        "address": best.get("address"),
                        "lat": best.get("lat"),
                        "lng": best.get("lng"),
                        "category": best.get("category", "filler"),
                        "persona_score": best.get("persona_score", 6.0),
                        "agent_note": f"Added to bridge {gap['distance_km']:.1f}km gap.",
                        "recommendation": "INCLUDE",
                        "is_open": True,
                        "likes": 0,
                    }
                    # Insert filler at the gap position
                    insert_idx = gap["insert_after"] + 1
                    clustered[day_idx].insert(insert_idx, filler_poi)
                    existing_names.add(best["name"])

        return clustered

    def _find_gaps(self, day_pois: List[Dict]) -> List[Dict]:
        """Find transit gaps larger than TRANSIT_GAP_KM between consecutive stops."""
        gaps = []
        for i in range(len(day_pois) - 1):
            a, b = day_pois[i], day_pois[i + 1]
            if not (a.get("lat") and a.get("lng") and b.get("lat") and b.get("lng")):
                continue
            dist = self._haversine(a["lat"], a["lng"], b["lat"], b["lng"])
            if dist > TRANSIT_GAP_KM:
                gaps.append({
                    "from": a,
                    "to": b,
                    "distance_km": dist,
                    "insert_after": i,
                })
        return gaps

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lng2 - lng1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))
