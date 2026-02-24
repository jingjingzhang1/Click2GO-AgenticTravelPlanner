"""
Itinerary Exporter
==================
MCP Tool that produces two output artefacts:
  1. A styled PDF report (via ReportLab)
  2. An interactive HTML route map (via Folium)

Both tools degrade gracefully: plain-text / GeoJSON fallbacks are
used when the optional dependencies are not installed.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List

OUTPUTS_DIR = "outputs"


class ItineraryExporter:

    def __init__(self):
        os.makedirs(OUTPUTS_DIR, exist_ok=True)

    # ── PDF ───────────────────────────────────────────────────────────────────

    def generate_pdf(self, itinerary: dict, user_profile: dict) -> str:
        """
        Generate a branded PDF itinerary.

        Returns the path to the created file.
        """
        try:
            return self._build_pdf(itinerary, user_profile)
        except ImportError:
            return self._text_fallback(itinerary, user_profile)

    def _build_pdf(self, itinerary: dict, user_profile: dict) -> str:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )

        session_id  = itinerary.get("session_id", "unknown")
        out_path    = os.path.join(OUTPUTS_DIR, f"itinerary_{session_id[:8]}.pdf")

        doc    = SimpleDocTemplate(out_path, pagesize=A4,
                                   leftMargin=2*cm, rightMargin=2*cm,
                                   topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        RED    = colors.HexColor("#E8335D")

        # ── Custom styles
        def ps(name, parent="Normal", **kw):
            return ParagraphStyle(name, parent=styles[parent], **kw)

        title_sty   = ps("Title2",   "Title",   fontSize=28, textColor=RED, spaceAfter=4)
        sub_sty     = ps("Sub",      fontSize=11, textColor=colors.HexColor("#666666"), spaceAfter=18)
        day_sty     = ps("Day",      "Heading1", fontSize=17, textColor=RED, spaceBefore=14, spaceAfter=6)
        poi_sty     = ps("POI",      "Heading2", fontSize=12, textColor=colors.HexColor("#222222"),
                         spaceBefore=7, spaceAfter=3)
        note_sty    = ps("Note",     fontSize=9,  textColor=colors.HexColor("#555555"),
                         leftIndent=16)
        footer_sty  = ps("Footer",   fontSize=8,  textColor=colors.HexColor("#AAAAAA"), alignment=1)

        story = []

        # ── Header
        dest       = user_profile.get("destination", "Your Destination")
        start_date = user_profile.get("start_date", "")
        end_date   = user_profile.get("end_date", "")
        persona    = user_profile.get("persona", "chilling").capitalize()

        story.append(Paragraph("Click2GO", title_sty))
        story.append(Paragraph(
            f"{dest} &nbsp;·&nbsp; {start_date} → {end_date} &nbsp;·&nbsp; {persona} Style",
            sub_sty,
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=RED))
        story.append(Spacer(1, 10))

        # ── Stats table
        stats = itinerary.get("stats", {})
        if stats:
            tbl = Table(
                [
                    ["POIs Discovered", "POIs Verified", "POIs Included"],
                    [
                        str(stats.get("total_scraped", "–")),
                        str(stats.get("total_verified", "–")),
                        str(stats.get("total_included", "–")),
                    ],
                ],
                colWidths=[5*cm, 5*cm, 5*cm],
            )
            tbl.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (-1, 0), RED),
                ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
                ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE",     (0, 0), (-1, 0), 10),
                ("FONTSIZE",     (0, 1), (-1, 1), 18),
                ("FONTNAME",     (0, 1), (-1, 1), "Helvetica-Bold"),
                ("BACKGROUND",   (0, 1), (-1, 1), colors.HexColor("#FFF5F7")),
                ("BOX",          (0, 0), (-1, -1), 1, RED),
                ("INNERGRID",    (0, 0), (-1, -1), 0.5, colors.HexColor("#FFCCCC")),
                ("TOPPADDING",   (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 18))

        # ── Daily itinerary
        days = itinerary.get("days", [])
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except Exception:
            start_dt = None

        for day_num, day_pois in enumerate(days, 1):
            if not day_pois:
                continue
            date_str = ""
            if start_dt:
                d = start_dt + timedelta(days=day_num - 1)
                date_str = f" — {d.strftime('%A, %B %d')}"

            story.append(Paragraph(f"Day {day_num}{date_str}", day_sty))
            story.append(HRFlowable(width="100%", thickness=0.5,
                                     color=colors.HexColor("#FFAAAA")))
            story.append(Spacer(1, 5))

            for stop_num, poi in enumerate(day_pois, 1):
                name = poi.get("name", "Unknown Location")
                story.append(Paragraph(f"{stop_num}. {name}", poi_sty))

                details = []
                if poi.get("address"):
                    details.append(f"📍 {poi['address']}")
                if poi.get("category"):
                    details.append(f"🏷️ {poi['category']}")
                score = poi.get("persona_score")
                if score is not None:
                    stars = "★" * int(score / 2) + "☆" * (5 - int(score / 2))
                    details.append(f"⭐ {stars} ({score:.1f}/10)")
                if details:
                    story.append(Paragraph(" &nbsp;|&nbsp; ".join(details), note_sty))

                if poi.get("agent_note"):
                    story.append(Paragraph(f"🤖 {poi['agent_note']}", note_sty))

                story.append(Spacer(1, 5))

            story.append(Spacer(1, 8))

        # ── Footer
        story.append(HRFlowable(width="100%", thickness=1,
                                  color=colors.HexColor("#CCCCCC")))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"Generated by Click2GO · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            footer_sty,
        ))
        story.append(Paragraph(
            "Powered by Xiaohongshu social intelligence + Claude AI verification",
            footer_sty,
        ))

        doc.build(story)
        return out_path

    def _text_fallback(self, itinerary: dict, user_profile: dict) -> str:
        """Plain-text itinerary when ReportLab is not installed."""
        sid      = itinerary.get("session_id", "unknown")
        out_path = os.path.join(OUTPUTS_DIR, f"itinerary_{sid[:8]}.txt")
        dest     = user_profile.get("destination", "")
        lines    = [
            "=" * 60, "CLICK2GO TRAVEL ITINERARY", "=" * 60,
            f"Destination : {dest}",
            f"Dates       : {user_profile.get('start_date', '')} → {user_profile.get('end_date', '')}",
            f"Persona     : {user_profile.get('persona', 'chilling').capitalize()}",
            "",
        ]
        for day_num, day_pois in enumerate(itinerary.get("days", []), 1):
            lines.append(f"\n--- DAY {day_num} ---")
            for i, poi in enumerate(day_pois, 1):
                lines.append(f"  {i}. {poi.get('name', 'Unknown')}")
                if poi.get("address"):
                    lines.append(f"     📍 {poi['address']}")
                if poi.get("agent_note"):
                    lines.append(f"     🤖 {poi['agent_note']}")
        lines += ["", "=" * 60, "Generated by Click2GO", "=" * 60]
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return out_path

    # ── Map ───────────────────────────────────────────────────────────────────

    def generate_route_map(self, itinerary: dict, user_profile: dict) -> str:
        """
        Generate an interactive HTML route map.

        Returns the path to the created file.
        """
        try:
            return self._build_map(itinerary, user_profile)
        except ImportError:
            return self._geojson_fallback(itinerary)

    def _build_map(self, itinerary: dict, user_profile: dict) -> str:
        import folium

        sid      = itinerary.get("session_id", "unknown")
        out_path = os.path.join(OUTPUTS_DIR, f"map_{sid[:8]}.html")
        days     = itinerary.get("days", [])
        dest     = user_profile.get("destination", "Destination")

        # Map centre
        all_geo = [p for day in days for p in day if p.get("lat") and p.get("lng")]
        if all_geo:
            c_lat = sum(p["lat"] for p in all_geo) / len(all_geo)
            c_lng = sum(p["lng"] for p in all_geo) / len(all_geo)
        else:
            c_lat, c_lng = 35.6762, 139.6503   # default Tokyo

        m = folium.Map(location=[c_lat, c_lng], zoom_start=13, tiles="CartoDB positron")

        DAY_COLORS = ["#E8335D", "#3498DB", "#2ECC71", "#9B59B6",
                      "#F39C12", "#1ABC9C", "#E74C3C", "#34495E"]

        for di, day_pois in enumerate(days):
            color    = DAY_COLORS[di % len(DAY_COLORS)]
            day_geo  = [p for p in day_pois if p.get("lat") and p.get("lng")]

            for si, poi in enumerate(day_pois):
                if not (poi.get("lat") and poi.get("lng")):
                    continue

                icon_html = (
                    f'<div style="background:{color};color:white;border-radius:50%;'
                    f'width:30px;height:30px;display:flex;align-items:center;'
                    f'justify-content:center;font-weight:bold;font-size:11px;'
                    f'box-shadow:0 2px 6px rgba(0,0,0,.3);">D{di+1}</div>'
                )
                popup_html = (
                    f'<div style="font-family:sans-serif;min-width:190px;">'
                    f'<h4 style="color:{color};margin:0 0 4px 0">'
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
                    icon=folium.DivIcon(html=icon_html, icon_size=(30, 30), icon_anchor=(15, 15)),
                ).add_to(m)

            # Route polyline
            if len(day_geo) > 1:
                folium.PolyLine(
                    [[p["lat"], p["lng"]] for p in day_geo],
                    color=color, weight=3, opacity=0.75,
                    tooltip=f"Day {di+1} route",
                ).add_to(m)

        # Legend
        legend_items = "".join(
            f'<div style="margin-top:5px;">'
            f'<span style="background:{DAY_COLORS[i % len(DAY_COLORS)]};color:white;'
            f'padding:2px 8px;border-radius:10px;font-size:11px;">Day {i+1}</span> '
            f'{len(days[i])} stops</div>'
            for i in range(len(days))
        )
        m.get_root().html.add_child(folium.Element(
            f'<div style="position:fixed;bottom:30px;right:30px;background:white;'
            f'padding:14px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.2);'
            f'font-family:sans-serif;z-index:1000;">'
            f'<div style="font-weight:bold;font-size:13px;color:#E8335D;margin-bottom:6px;">'
            f'🗺️ Click2GO Route</div>'
            f'<div style="font-size:11px;color:#888">{dest}</div>'
            f'{legend_items}</div>'
        ))

        m.save(out_path)
        return out_path

    def _geojson_fallback(self, itinerary: dict) -> str:
        sid      = itinerary.get("session_id", "unknown")
        out_path = os.path.join(OUTPUTS_DIR, f"map_{sid[:8]}.geojson")
        features = []
        for di, day_pois in enumerate(itinerary.get("days", [])):
            for poi in day_pois:
                if poi.get("lat") and poi.get("lng"):
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point",
                                     "coordinates": [poi["lng"], poi["lat"]]},
                        "properties": {
                            "name": poi.get("name", ""),
                            "day":  di + 1,
                            "note": poi.get("agent_note", ""),
                        },
                    })
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": features},
                      fh, ensure_ascii=False, indent=2)
        return out_path
