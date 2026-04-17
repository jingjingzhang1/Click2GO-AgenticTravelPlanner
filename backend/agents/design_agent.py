"""
Agent 3: The Design & UI Agent
===============================
Bridges the gap between raw data and beautiful user experience.

Responsibilities:
  - Generate interactive Folium maps with configurable styling
  - Handle user chat messages to restyle maps on the fly
  - Generate persona-specific cover photos via image generation API
  - Export final styled PDF itinerary
"""
import json
import logging
import os
from typing import Dict, List, Optional

from ..config import settings
from ..tools.itinerary_exporter import ItineraryExporter

logger = logging.getLogger(__name__)

OUTPUTS_DIR = "outputs"

# Available Folium tile layers for user customization
TILE_LAYERS = {
    "default": {"tiles": "CartoDB positron", "label": "Clean Light"},
    "dark": {"tiles": "CartoDB dark_matter", "label": "Dark Mode"},
    "satellite": {"tiles": "Esri.WorldImagery", "label": "Satellite"},
    "openstreetmap": {"tiles": "OpenStreetMap", "label": "Street Map"},
}

# Persona category colors and icons
PERSONA_STYLES = {
    "foodie":      {"color": "#FF6B35", "icon": "🍜", "label": "Foodie"},
    "photography": {"color": "#FFD700", "icon": "📷", "label": "Photography"},
    "chilling":    {"color": "#7FDBFF", "icon": "☕", "label": "Chilling"},
    "exercise":    {"color": "#2ECC71", "icon": "🥾", "label": "Exercise"},
}


class DesignAgent:
    """
    Agent 3 — dynamic frontend developer.

    Generates and iterates on maps, PDFs, and cover images based on
    user chat messages.
    """

    def __init__(self):
        self.exporter = ItineraryExporter()
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    # ── Initial generation (called by supervisor) ────────────────────────

    def run(self, state: dict) -> dict:
        """
        Generate initial outputs: PDF, map, and cover image.

        Reads from state:
            session_id, destination, start_date, end_date, personas,
            clustered_days, stats, language

        Returns partial state update:
            pdf_path, map_path, cover_image_url, status
        """
        session_id = state["session_id"]
        clustered_days = state["clustered_days"]
        personas = state["personas"]
        language = state.get("language", "en")

        user_profile = {
            "destination": state["destination"],
            "start_date": state["start_date"],
            "end_date": state["end_date"],
            "persona": " & ".join(p.capitalize() for p in personas),
        }
        itinerary = {
            "session_id": session_id,
            "days": clustered_days,
            "stats": state.get("stats", {}),
        }

        # Generate PDF
        pdf_path = self.exporter.generate_pdf(itinerary, user_profile)

        # Generate interactive map
        map_config = state.get("map_config", {})
        map_path = self._generate_styled_map(
            itinerary, user_profile, map_config
        )

        return {
            "pdf_path": pdf_path,
            "map_path": map_path,
            "cover_image_url": None,
            "status": "completed",
        }

    # ── Chat-driven iteration ────────────────────────────────────────────

    def handle_chat(
        self,
        session_id: str,
        user_message: str,
        itinerary: dict,
        user_profile: dict,
        chat_history: List[Dict],
        current_map_config: Optional[Dict] = None,
    ) -> Dict:
        """
        Process a user chat message and apply design changes.

        Uses Claude to interpret the user's styling request, then
        applies the changes to the map/PDF.

        Returns:
            {"response": str, "map_updated": bool, "pdf_updated": bool,
             "map_url": str|None, "pdf_url": str|None, "new_map_config": dict}
        """
        map_config = current_map_config or {}

        # Use Claude to interpret the design request
        interpretation = self._interpret_request(
            user_message, chat_history, map_config
        )

        map_updated = False
        pdf_updated = False
        map_url = None
        pdf_url = None

        # Apply map changes
        if interpretation.get("map_changes"):
            new_config = {**map_config, **interpretation["map_changes"]}
            map_path = self._generate_styled_map(
                itinerary, user_profile, new_config
            )
            map_config = new_config
            map_updated = True
            map_url = f"/outputs/{os.path.basename(map_path)}"

        # Apply PDF changes
        if interpretation.get("pdf_regenerate"):
            pdf_path = self.exporter.generate_pdf(itinerary, user_profile)
            pdf_updated = True
            pdf_url = f"/outputs/{os.path.basename(pdf_path)}"

        return {
            "response": interpretation.get("response", "Changes applied."),
            "map_updated": map_updated,
            "pdf_updated": pdf_updated,
            "map_url": map_url,
            "pdf_url": pdf_url,
            "new_map_config": map_config,
        }

    def _interpret_request(
        self,
        user_message: str,
        chat_history: List[Dict],
        current_config: Dict,
    ) -> Dict:
        """Use OpenAI to interpret a design chat message into actionable changes."""
        key = settings.openai_api_key
        if not key or len(key.strip()) < 10:
            return self._rule_based_interpret(user_message, current_config)

        history_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in chat_history[-6:]
        )

        available_tiles = ", ".join(
            f'"{k}" ({v["label"]})' for k, v in TILE_LAYERS.items()
        )

        prompt = f"""You are the Design Agent for Click2GO, a travel planner.
The user wants to customize their travel map and itinerary outputs.

Current map configuration: {json.dumps(current_config)}

Available tile layers: {available_tiles}

Note: POI markers are automatically colored by category (foodie, photography, chilling, exercise). This cannot be changed by the user.

Recent chat:
{history_text}

User request: "{user_message}"

Interpret this request and return a JSON object with these keys:
- "response": A friendly message explaining what you did. If you CAN make the change, say what changed. If you CANNOT (the feature doesn't exist), honestly say so and suggest what you CAN do instead.
- "map_changes": dict of config changes to apply (or null if no map changes). Valid keys:
  - "tile_layer": one of the available tile layer keys
  - "show_routes": boolean (show/hide route lines)
  - "show_distances": boolean (show distance labels between stops)
- "pdf_regenerate": boolean (true if PDF needs regenerating)

IMPORTANT: If the user asks for something you cannot do, set map_changes to null and explain honestly in "response". Never pretend you made changes when you didn't.

Reply in strict JSON only (no markdown fences)."""

        try:
            client = self._get_client()
            completion = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content.strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning("OpenAI interpretation failed: %s", e)
            return self._rule_based_interpret(user_message, current_config)

    def _rule_based_interpret(self, message: str, config: Dict) -> Dict:
        """Fallback: keyword-based interpretation when Claude is unavailable."""
        msg = message.lower()
        changes = {}
        response_parts = []

        # Tile layer changes
        if "dark" in msg:
            changes["tile_layer"] = "dark"
            response_parts.append("Switching to dark mode")
        elif "satellite" in msg:
            changes["tile_layer"] = "satellite"
            response_parts.append("Switching to satellite view")
        elif "street" in msg and "map" in msg:
            changes["tile_layer"] = "openstreetmap"
            response_parts.append("Switching to street map view")
        elif "light" in msg or "default" in msg or "clean" in msg:
            changes["tile_layer"] = "default"
            response_parts.append("Switching to clean light mode")

        # Route lines
        if "hide route" in msg or "no route" in msg or "remove route" in msg:
            changes["show_routes"] = False
            response_parts.append("Hiding route lines")
        elif "show route" in msg:
            changes["show_routes"] = True
            response_parts.append("Showing route lines")

        # Distance labels
        if "distance" in msg or "km" in msg or "commute" in msg or "transit" in msg or "transport" in msg:
            changes["show_distances"] = True
            response_parts.append("Adding distance labels between stops")

        # Honest response when nothing matched
        if not changes and "pdf" not in msg and "regenerate" not in msg:
            return {
                "response": (
                    "I'm not sure how to make that change. Here's what I can do: "
                    "change map style (dark, satellite, street map), "
                    "show/hide route lines, show distances between stops, "
                    "or regenerate the PDF."
                ),
                "map_changes": None,
                "pdf_regenerate": False,
            }

        return {
            "response": ". ".join(response_parts) + "." if response_parts
                        else "Regenerating the PDF.",
            "map_changes": changes if changes else None,
            "pdf_regenerate": "pdf" in msg or "regenerate" in msg,
        }

    # ── Map generation with styling ──────────────────────────────────────

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine distance in km between two points."""
        import math
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lng2 - lng1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    @staticmethod
    def _estimate_transit(dist_km: float) -> str:
        """Estimate transit method and time based on distance."""
        if dist_km < 0.8:
            mins = int(dist_km / 0.08)  # ~5 km/h walking
            return f"Walk ~{max(mins, 1)} min"
        elif dist_km < 4.0:
            mins = int(dist_km / 0.25)  # ~15 km/h cycling/bus
            return f"Bus/bike ~{max(mins, 3)} min"
        elif dist_km < 20.0:
            mins = int(dist_km / 0.5)   # ~30 km/h urban driving
            return f"Taxi/metro ~{max(mins, 5)} min"
        else:
            mins = int(dist_km / 1.2)   # ~72 km/h intercity
            return f"Drive ~{max(mins, 10)} min"

    def _generate_styled_map(
        self,
        itinerary: dict,
        user_profile: dict,
        config: Dict,
    ) -> str:
        """Generate a Folium map with configurable styling."""
        try:
            import folium
        except ImportError:
            return self.exporter.generate_route_map(itinerary, user_profile)

        sid = itinerary.get("session_id", "unknown")
        out_path = os.path.join(OUTPUTS_DIR, f"map_{sid[:8]}.html")
        days = itinerary.get("days", [])
        dest = user_profile.get("destination", "Destination")

        # Map centre
        all_geo = [p for day in days for p in day if p.get("lat") and p.get("lng")]
        if all_geo:
            c_lat = sum(p["lat"] for p in all_geo) / len(all_geo)
            c_lng = sum(p["lng"] for p in all_geo) / len(all_geo)
        else:
            c_lat, c_lng = 35.6762, 139.6503

        # Tile layer from config
        tile_key = config.get("tile_layer", "default")
        tile_info = TILE_LAYERS.get(tile_key, TILE_LAYERS["default"])
        tiles = tile_info["tiles"]

        m = folium.Map(location=[c_lat, c_lng], zoom_start=13, tiles=tiles)

        DAY_COLORS = [
            "#E8335D", "#3498DB", "#2ECC71", "#9B59B6",
            "#F39C12", "#1ABC9C", "#E74C3C", "#34495E",
        ]

        show_routes = config.get("show_routes", True)
        show_distances = config.get("show_distances", False)

        for di, day_pois in enumerate(days):
            day_color = DAY_COLORS[di % len(DAY_COLORS)]
            day_geo = [p for p in day_pois if p.get("lat") and p.get("lng")]

            for si, poi in enumerate(day_pois):
                if not (poi.get("lat") and poi.get("lng")):
                    continue

                # Color and icon by POI category (persona type)
                cat = (poi.get("category") or "").lower()
                style = PERSONA_STYLES.get(cat)
                if style:
                    marker_color = style["color"]
                    label = style["icon"]
                else:
                    marker_color = day_color
                    label = f"D{di+1}"

                marker_size = 32

                icon_html = (
                    f'<div style="background:{marker_color};color:white;'
                    f'border-radius:50%;width:{marker_size}px;height:{marker_size}px;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-weight:bold;font-size:13px;'
                    f'box-shadow:0 2px 6px rgba(0,0,0,.3);">'
                    f'{label}</div>'
                )

                popup_html = (
                    f'<div style="font-family:sans-serif;min-width:190px;">'
                    f'<h4 style="color:{marker_color};margin:0 0 4px 0">'
                    f'Day {di+1} · Stop {si+1}</h4>'
                    f'<b>{poi.get("name","")}</b>'
                    + (f'<br><small>📍 {poi["address"]}</small>' if poi.get("address") else "")
                    + (f'<br><small>⭐ {poi["persona_score"]:.1f}/10</small>'
                       if poi.get("persona_score") else "")
                    + (f'<br><i style="color:#666">{poi["agent_note"][:100]}</i>'
                       if poi.get("agent_note") else "")
                    + "</div>"
                )

                folium.Marker(
                    [poi["lat"], poi["lng"]],
                    popup=folium.Popup(popup_html, max_width=240),
                    tooltip=f"Day {di+1}: {poi.get('name', '')}",
                    icon=folium.DivIcon(
                        html=icon_html,
                        icon_size=(marker_size, marker_size),
                        icon_anchor=(marker_size//2, marker_size//2),
                    ),
                ).add_to(m)

            # Route polyline
            if show_routes and len(day_geo) > 1:
                folium.PolyLine(
                    [[p["lat"], p["lng"]] for p in day_geo],
                    color=day_color, weight=3, opacity=0.75,
                    tooltip=f"Day {di+1} route",
                ).add_to(m)

            # Distance labels between consecutive stops
            if show_distances and len(day_geo) > 1:
                for j in range(len(day_geo) - 1):
                    a, b = day_geo[j], day_geo[j + 1]
                    dist = self._haversine(a["lat"], a["lng"], b["lat"], b["lng"])
                    transit = self._estimate_transit(dist)
                    mid_lat = (a["lat"] + b["lat"]) / 2
                    mid_lng = (a["lng"] + b["lng"]) / 2

                    dist_html = (
                        f'<div style="background:rgba(255,255,255,0.92);'
                        f'padding:3px 8px;border-radius:12px;font-size:11px;'
                        f'font-weight:600;color:#333;white-space:nowrap;'
                        f'box-shadow:0 1px 4px rgba(0,0,0,.15);'
                        f'border:1px solid {day_color};">'
                        f'{dist:.1f} km · {transit}</div>'
                    )

                    folium.Marker(
                        [mid_lat, mid_lng],
                        icon=folium.DivIcon(
                            html=dist_html,
                            icon_size=(140, 24),
                            icon_anchor=(70, 12),
                        ),
                    ).add_to(m)

        # Legend — show persona categories + day colors
        category_items = "".join(
            f'<div style="margin-top:5px;">'
            f'<span style="background:{s["color"]};color:white;'
            f'padding:2px 8px;border-radius:10px;font-size:11px;">'
            f'{s["icon"]} {s["label"]}</span></div>'
            for s in PERSONA_STYLES.values()
        )
        day_items = "".join(
            f'<div style="margin-top:4px;">'
            f'<span style="color:{DAY_COLORS[i % len(DAY_COLORS)]};'
            f'font-size:11px;font-weight:600;">━━ Day {i+1}</span> '
            f'<span style="font-size:10px;color:#888;">{len(days[i])} stops</span></div>'
            for i in range(len(days))
        )
        tile_label = TILE_LAYERS.get(tile_key, {}).get("label", "")
        m.get_root().html.add_child(folium.Element(
            f'<div style="position:fixed;bottom:30px;right:30px;background:white;'
            f'padding:14px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.2);'
            f'font-family:sans-serif;z-index:1000;">'
            f'<div style="font-weight:bold;font-size:13px;color:#E8335D;margin-bottom:6px;">'
            f'🗺️ Click2GO Route</div>'
            f'<div style="font-size:11px;color:#888">{dest} · {tile_label}</div>'
            f'{category_items}'
            f'<div style="margin-top:8px;border-top:1px solid #eee;padding-top:6px;">'
            f'{day_items}</div></div>'
        ))

        m.save(out_path)
        return out_path

