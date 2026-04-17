"""
Image Generator Tool
====================
Generates a stylized travel poster using Replicate's FLUX Schnell model.
Falls back to Pollinations AI (free, no auth) when Replicate is unavailable.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import quote

from ..config import settings

logger = logging.getLogger(__name__)

OUTPUTS_DIR = "outputs"

# ── Prompt Templates ─────────────────────────────────────────────────────────

_EN_TEMPLATE = """\
A vibrant cartoon-style travel poster for a trip to {destination}. \
The poster has a clean pastel background with illustrated landmarks and local scenery from {destination}. \
In the upper area, large hand-lettered title text reads "{destination} Travel Guide". \
Below, a colourful illustrated itinerary layout shows {num_days} day{day_plural}, \
with small cartoon icons for each activity. \
Day labels are written as "{day_labels}". \
The key highlights listed are: {poi_labels}. \
At the bottom, decorative text reads "Planned by Click2GO · {personas} style · {num_days}-Day Adventure". \
Art style: {art_style}.\
"""

_ZH_TEMPLATE = """\
一张充满活力的卡通风格旅行海报，主题为{destination}之旅。\
海报采用清新的粉彩背景，绘有{destination}当地标志性景点的插画场景。\
上方用醒目的手写体标题文字写着「{destination}旅行指南」。\
海报中央展示一个色彩丰富的{num_days}天行程版式，每项活动配有小巧的卡通图标。\
各天标签分别标注为"{day_labels}"。\
重点推荐地点包括：{poi_labels}。\
底部装饰文字写着「由Click2GO规划 · {personas}风格 · {num_days}天探索之旅」。\
美术风格：{art_style}。\
"""

# Persona-specific art styles
_PERSONA_STYLES = {
    "photography": "dramatic lighting, cinematic composition, golden-hour palette",
    "chilling": "soft watercolour, warm tones, cozy and relaxed aesthetic",
    "foodie": "rich saturated colours, food illustration style, appetizing warmth",
    "exercise": "bold dynamic lines, energetic composition, nature-forward palette",
}
_DEFAULT_STYLE = "flat vector illustration, bright colours, friendly cartoon aesthetic, no photorealism"


def _build_prompt(language: str, itinerary_data: dict) -> str:
    destination = itinerary_data.get("destination", "Unknown Destination")
    personas = itinerary_data.get("personas", ["travel"])
    days = itinerary_data.get("days", [])
    num_days = len(days) if days else 1
    day_plural = "s" if num_days > 1 else ""

    # Pick art style from primary persona
    primary_persona = personas[0] if personas else "chilling"
    art_style = _PERSONA_STYLES.get(primary_persona, _DEFAULT_STYLE)

    if language == "zh":
        day_labels = "、".join(f"第{d['day_number']}天" for d in days) if days else "第1天"
        persona_str = " & ".join(personas)
    else:
        day_labels = ", ".join(f"Day {d['day_number']}" for d in days) if days else "Day 1"
        persona_str = " & ".join(p.capitalize() for p in personas)

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
        destination=destination,
        num_days=num_days,
        day_plural=day_plural,
        day_labels=day_labels,
        poi_labels=poi_labels,
        personas=persona_str,
        art_style=art_style,
    )


def generate_travel_poster(
    language: str,
    itinerary_data: dict,
    width: int = 1024,
    height: int = 1024,
    **_kwargs,
) -> dict:
    """
    Generate a travel poster image.

    Tries Replicate FLUX Schnell first, falls back to Pollinations.

    Returns:
        {"success": bool, "image_url": str | None, "prompt_used": str, "error": str | None}
    """
    prompt = _build_prompt(language, itinerary_data)
    logger.info("Image gen prompt (%s): %s", language, prompt[:120])

    # Try Replicate first
    if settings.replicate_api_token:
        try:
            result = _generate_replicate(prompt, width, height)
            if result:
                return {
                    "success": True,
                    "image_url": result,
                    "prompt_used": prompt,
                    "error": None,
                }
        except Exception as e:
            logger.warning("Replicate failed, falling back to Pollinations: %s", e)

    # Fallback: Pollinations (free, no auth)
    return _generate_pollinations(prompt, width, height)


def _generate_replicate(prompt: str, width: int, height: int) -> str | None:
    """Generate via Replicate FLUX Schnell."""
    import replicate

    output = replicate.run(
        "black-forest-labs/flux-schnell",
        input={
            "prompt": prompt,
            "go_fast": True,
            "num_outputs": 1,
            "aspect_ratio": "1:1",
            "output_format": "webp",
            "output_quality": 90,
        },
    )
    # output is a list of FileOutput URLs
    if output:
        return str(output[0])
    return None


def _generate_pollinations(prompt: str, width: int, height: int) -> dict:
    """Fallback: Pollinations AI (free, no key)."""
    encoded = quote(prompt, safe="")
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
