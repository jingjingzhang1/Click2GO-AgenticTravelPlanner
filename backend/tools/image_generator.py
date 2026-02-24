"""
Image Generator Tool
====================
Generates a cartoon-style travel poster for a Click2GO itinerary using
Pollinations AI (free, no API key required).

GET https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux
Returns the image directly — the URL itself is the image source.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

# ── Prompt Templates ──────────────────────────────────────────────────────────

_EN_TEMPLATE = """\
A vibrant cartoon-style travel poster for a trip to {destination}. \
The poster has a clean pastel background with illustrated landmarks and local scenery from {destination}. \
In the upper area, large hand-lettered title text reads "{destination} Travel Guide". \
Below, a colourful illustrated itinerary layout shows {num_days} day{day_plural}, \
with small cartoon icons for each activity. \
Day labels are written as "{day_labels}". \
The key highlights listed are: {poi_labels}. \
At the bottom, decorative text reads "Planned by Click2GO · {personas} style · {num_days}-Day Adventure". \
Art style: flat vector illustration, bright colours, friendly cartoon aesthetic, no photorealism.\
"""

_ZH_TEMPLATE = """\
一张充满活力的卡通风格旅行海报，主题为{destination}之旅。\
海报采用清新的粉彩背景，绘有{destination}当地标志性景点的插画场景。\
上方用醒目的手写体标题文字写着「{destination}旅行指南」。\
海报中央展示一个色彩丰富的{num_days}天行程版式，每项活动配有小巧的卡通图标。\
各天标签分别标注为"{day_labels}"。\
重点推荐地点包括：{poi_labels}。\
底部装饰文字写着「由Click2GO规划 · {personas}风格 · {num_days}天探索之旅」。\
美术风格：扁平矢量插画，色彩明亮，卡通风格友好，非写实风格。\
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_prompt(language: str, itinerary_data: dict) -> str:
    """
    Build a LongCat-compatible prompt from itinerary data.

    itinerary_data keys:
        destination  str
        personas     List[str]
        days         List[dict]  – each {"day_number": int, "pois": List[str]}
    """
    destination = itinerary_data.get("destination", "Unknown Destination")
    personas    = itinerary_data.get("personas", ["travel"])
    days        = itinerary_data.get("days", [])
    num_days    = len(days) if days else 1
    day_plural  = "s" if num_days > 1 else ""

    # Day labels: "Day 1", "Day 2", … / "第1天", "第2天", …
    if language == "zh":
        day_labels = "、".join(f"第{d['day_number']}天" for d in days) if days else "第1天"
        persona_str = " & ".join(personas)
    else:
        day_labels = ", ".join(f"Day {d['day_number']}" for d in days) if days else "Day 1"
        persona_str = " & ".join(p.capitalize() for p in personas)

    # Collect top POI names (up to 6 total across all days)
    all_pois = []
    for day in days:
        all_pois.extend(day.get("pois", []))
    top_pois = all_pois[:6]

    if language == "zh":
        poi_labels = "、".join(f"「{p}」" for p in top_pois) if top_pois else f"「{destination}热门景点」"
        tmpl = _ZH_TEMPLATE
    else:
        poi_labels = ", ".join(f'"{p}"' for p in top_pois) if top_pois else f'"{destination} Top Attractions"'
        tmpl = _EN_TEMPLATE

    return tmpl.format(
        destination = destination,
        num_days    = num_days,
        day_plural  = day_plural,
        day_labels  = day_labels,
        poi_labels  = poi_labels,
        personas    = persona_str,
    )


# ── Main API call ─────────────────────────────────────────────────────────────

def generate_travel_poster(
    language: str,
    itinerary_data: dict,
    width: int = 1024,
    height: int = 1024,
    **_kwargs,
) -> dict:
    """
    Build a Pollinations AI image URL from the itinerary and return it.

    Pollinations AI is free and requires no API key.
    The URL itself serves as the image source — the browser loads it directly.

    Returns:
        {
            "success": bool,
            "image_url": str | None,
            "prompt_used": str,
            "error": str | None,
        }
    """
    prompt = _build_prompt(language, itinerary_data)
    logger.info("Pollinations prompt (%s): %s", language, prompt[:120])

    encoded = quote(prompt, safe="")
    # Use a deterministic seed so re-generating the same itinerary gives the
    # same image; abs() keeps it positive, modulo keeps it reasonable.
    seed = abs(hash(prompt)) % 99991

    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&model=flux&nologo=true&seed={seed}"
    )

    return {
        "success": True,
        "image_url": image_url,
        "prompt_used": prompt,
        "error": None,
    }
