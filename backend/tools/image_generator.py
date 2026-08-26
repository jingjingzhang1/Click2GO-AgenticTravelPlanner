"""
Travel-poster prompt builder + provider orchestration
=====================================================
Builds a tight, art-directed prompt describing the finished trip, then
delegates rendering to the provider chain (Gemini → OpenAI → Replicate →
Pollinations).

Design philosophy: image models garble large amounts of text, so the prompt
asks for **one clean headline** (the destination) plus a short tagline, and
folds the top POIs into the artwork as *visual scene elements* rather than
printed labels. This yields a poster-grade result instead of a cluttered card
full of misspelled captions.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from .image_providers import ImageResult, ordered_providers

logger = logging.getLogger(__name__)

# ── Persona-driven art direction ─────────────────────────────────────────────
_PERSONA_ART = {
    "photography": {
        "style": "cinematic travel-poster art, dramatic golden-hour lighting, sweeping vistas",
        "palette": "warm gold, deep teal and sunset amber",
        "mood": "awe-inspiring and cinematic",
        "tagline_en": "Chase the Light",
        "tagline_zh": "追光而行",
    },
    "chilling": {
        "style": "soft flat-vector illustration, cozy minimalist poster design",
        "palette": "warm pastels, cream, dusty sage and blush",
        "mood": "calm, cozy and unhurried",
        "tagline_en": "Slow Down & Savor",
        "tagline_zh": "慢享时光",
    },
    "foodie": {
        "style": "vibrant appetizing illustration, playful modern poster design",
        "palette": "rich reds, warm orange and golden cream",
        "mood": "lively, warm and delicious",
        "tagline_en": "Taste the City",
        "tagline_zh": "品味之旅",
    },
    "exercise": {
        "style": "bold dynamic vector art with energetic linework",
        "palette": "fresh greens, crisp sky blue and sunlit yellow",
        "mood": "active, fresh and adventurous",
        "tagline_en": "Explore the Outdoors",
        "tagline_zh": "户外探索",
    },
}
_DEFAULT_ART = {
    "style": "elegant flat-vector travel-poster illustration with a vintage feel",
    "palette": "balanced, harmonious travel-poster colors",
    "mood": "inviting and adventurous",
    "tagline_en": "Plan Perfectly. Arrive Curious.",
    "tagline_zh": "完美规划 · 好奇出发",
}


def _scene_pois(itinerary_data: dict) -> List[str]:
    """Top few POI names, used as visual scene inspiration (not printed text)."""
    names: List[str] = []
    for day in itinerary_data.get("days", []):
        names.extend(day.get("pois", []))
    # De-dupe, keep order, cap at 3 so the artwork stays focused.
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
        if len(out) == 3:
            break
    return out


def _join_en(items: List[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _day_lines(days: list, language: str) -> str:
    """Enumerate each day and its numbered stops for the route-map art."""
    lines = []
    for i, d in enumerate(days):
        stops = [s for s in d.get("pois", []) if s]
        if not stops:
            continue
        n = d.get("day_number", i + 1)
        if language == "zh":
            numbered = "  ".join(f"{j + 1})「{s}」" for j, s in enumerate(stops))
            lines.append(f"第{n}天（一条独立颜色的路线）：{numbered}")
        else:
            numbered = "  ".join(f'{j + 1}) "{s}"' for j, s in enumerate(stops))
            lines.append(f"Day {n} (its own colored route): {numbered}")
    return "\n".join(lines)


def _build_prompt(language: str, itinerary_data: dict) -> str:
    destination = itinerary_data.get("destination", "a lovely destination")
    days = itinerary_data.get("days", [])
    num_days = len(days) if days else 1
    day_block = _day_lines(days, language)

    if language == "zh":
        return (
            f"一张色彩鲜艳的手绘旅行路线图，小红书「手绘攻略」风格，画在浅色方格本（格子纸）背景上，"
            f"主题是 {destination} {num_days} 天行程。"
            f"顶部用夸张俏皮的手写大标题，把「{destination}」放在一个印章式方框里，并写上「{num_days}日游」。"
            f"把每一天画成一条独立颜色的路线：用一种马克笔颜色的手绘曲线，按顺序把当天的站点连起来，"
            f"每个站点标上圆圈数字（①②③…）和手绘小箭头表示游览方向；不同天用不同颜色区分。"
            f"每个站点画一个可爱的彩色小涂鸦图标（地标 / 博物馆 / 大桥 / 公园 / 咖啡杯等），"
            f"旁边用工整清晰的小字手写地点名称。行程如下（每天一种颜色的路线）：\n"
            f"{day_block}\n"
            f"页面四周点缀可爱的小涂鸦（小人、相机、咖啡、花朵、星星、地铁标志、动物等）。"
            f"用彩色铅笔 / 马克笔上色，干净的白色方格背景，随性可爱的手绘风。"
            f"所有文字简短、手写工整、拼写正确、清晰可读。无写实照片风，无水印。"
        )

    return (
        f"A colorful hand-drawn travel route map in the cute Xiaohongshu illustrated-guide style, "
        f"drawn on a light grid / graph-paper background. A {num_days}-day trip to {destination}. "
        f'Big playful hand-lettered title at the top with "{destination}" inside a stamp-like box '
        f'and "{num_days}-Day Trip". '
        f"Draw each day as its OWN color-coded route: a looping hand-drawn marker line in a "
        f"distinct color that connects that day's stops in order, with circled numbers (1, 2, 3 …) "
        f"and little hand-drawn arrows showing the walking direction. Use a different color per day. "
        f"For every stop, draw a small cute colored doodle icon of the place (landmark, museum, "
        f"bridge, park, coffee cup, etc.) with its name hand-written neatly beside it. "
        f"Itinerary (each day is a different colored route):\n"
        f"{day_block}\n"
        f"Scatter kawaii doodles around the page (little people, a camera, coffee, flowers, stars, "
        f"a subway sign). Bright colored-pencil / marker coloring, clean white grid background, "
        f"casual and charming hand-drawn aesthetic. Keep every label short, correctly spelled and "
        f"clearly legible. No photorealism, no watermark."
    )


def generate_travel_poster(
    language: str,
    itinerary_data: dict,
    width: int = 1024,
    height: int = 1024,
    **_kwargs,
) -> dict:
    """
    Render a travel poster by walking the configured provider chain.

    Returns a dict (backward-compatible keys preserved):
        success, image_url, image_bytes, provider, mime_type, prompt_used, error
    """
    prompt = _build_prompt(language, itinerary_data)
    logger.info("image gen prompt (%s): %s", language, prompt[:160])

    last_error: Optional[str] = None
    for provider in ordered_providers():
        if not provider.is_available():
            logger.debug("skipping image provider %s (not configured)", provider.name)
            continue
        try:
            result = provider.generate(prompt, width, height)
            if result.success:
                logger.info("image generated via %s", provider.name)
                return _to_dict(result)
            last_error = result.error
            logger.warning("provider %s returned no image: %s", provider.name, result.error)
        except Exception as exc:  # noqa: BLE001 — try the next provider
            last_error = f"{provider.name}: {exc}"
            logger.warning("image provider %s failed: %s", provider.name, exc)

    return {
        "success": False,
        "image_url": None,
        "image_bytes": None,
        "provider": None,
        "mime_type": None,
        "prompt_used": prompt,
        "error": last_error or "All image providers failed.",
    }


def _to_dict(result: ImageResult) -> dict:
    return {
        "success": result.success,
        "image_url": result.image_url,
        "image_bytes": result.image_bytes,
        "provider": result.provider,
        "mime_type": result.mime_type,
        "prompt_used": result.prompt_used,
        "error": result.error,
    }
