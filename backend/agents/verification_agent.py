import json
from typing import List, Optional

from ..config import settings


class VerificationAgent:
    """
    Autonomous agent that verifies POI suitability using recent
    Xiaohongshu posts as evidence.

    Uses Claude to assess three criteria:
      1. Status   – is the place open? any closures / renovations?
      2. Seasonality – does the current vibe match the travel dates?
      3. Persona Alignment – does it fit the traveller's style?
    """

    PERSONA_HINTS = {
        "photography": "scenic views, good lighting, Instagram-worthy spots, unique architecture",
        "chilling":    "relaxed atmosphere, cafes, parks, low-key hangouts, peaceful vibes",
        "foodie":      "authentic cuisine, local specialties, interesting dining experiences",
        "exercise":    "hiking, outdoor activities, sports facilities, wellness centres",
    }

    def __init__(self):
        self._client = None  # lazy-init so the app starts without a key

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client

    def verify(
        self,
        poi_name: str,
        recent_posts: List[str],
        persona: str,
        start_date: str,
        end_date: str,
    ) -> dict:
        """
        Verify a POI using Claude-powered sentiment analysis.

        Returns a dict with keys:
          is_open, status_confidence, seasonal_match, persona_score,
          recommendation ("INCLUDE" | "EXCLUDE"), reasoning, agent_note
        """
        if not recent_posts:
            return self._fallback(poi_name, reason="no_posts")

        key = settings.anthropic_api_key
        if not key or not key.startswith("sk-") or len(key) < 20:
            return self._fallback(poi_name, reason="no_api_key")

        posts_text = "\n\n".join(
            f"--- Post {i + 1} ---\n{post}"
            for i, post in enumerate(recent_posts[:5])
        )
        persona_hint = self.PERSONA_HINTS.get(persona, "general travel experiences")

        prompt = f"""You are a travel verification agent for Click2GO, an intelligent travel planner.

Analyse the recent Xiaohongshu social-media posts below about "{poi_name}" and decide \
whether this location should appear in a personalised travel itinerary.

**Traveller profile**
- Persona: {persona} ({persona_hint})
- Travel dates: {start_date} → {end_date}

**Recent posts**
{posts_text}

**What to check**
1. Status – Is it currently OPEN? Any closures, renovations, or reported issues?
2. Seasonality – Given the travel dates, is the current atmosphere/vibe appropriate \
   (e.g. cherry blossoms in spring, autumn foliage in October)?
3. Persona match – Does it suit a "{persona}" traveller?

**Reply in strict JSON only (no markdown fences, no extra text):**
{{
  "is_open": true | false | null,
  "status_confidence": 0.0–1.0,
  "seasonal_match": true | false | null,
  "persona_score": 0.0–10.0,
  "recommendation": "INCLUDE" | "EXCLUDE",
  "reasoning": "1–2 sentence explanation",
  "agent_note": "Practical tip or note for the traveller"
}}"""

        try:
            client = self._get_client()
            message = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()

            # Strip markdown fences if the model adds them anyway
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

            return json.loads(raw)

        except json.JSONDecodeError:
            return self._fallback(poi_name, reason="parse_error")
        except Exception as e:
            return self._fallback(poi_name, reason=str(e))

    @staticmethod
    def _fallback(poi_name: str, reason: str = "") -> dict:
        notes = {
            "no_posts":    "No recent posts found; including with caution.",
            "no_api_key":  "Anthropic API key not configured; skipping AI verification.",
            "parse_error": "Verification response could not be parsed; including by default.",
        }
        return {
            "is_open": None,
            "status_confidence": 0.5,
            "seasonal_match": None,
            "persona_score": 5.0,
            "recommendation": "INCLUDE",
            "reasoning": notes.get(reason, f"Verification skipped ({reason})."),
            "agent_note": (
                f"Limited verification data for {poi_name}. "
                "Recommend confirming status before visiting."
            ),
        }
