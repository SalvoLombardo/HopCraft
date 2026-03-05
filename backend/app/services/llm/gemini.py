"""
GeminiProvider — Google Gemini 2.5 Flash (primary provider).

Free tier: 10 req/min, 250 req/day, 250K tokens/min.
No credit card required. API key available at aistudio.google.com.

Uses responseMimeType: "application/json" to enforce structured JSON output.
"""
import httpx

from app.services.llm.base import (
    LLMProvider,
    SYSTEM_PROMPT,
    SuggestedItinerary,
    build_user_prompt,
    parse_itineraries,
)

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


class GeminiProvider(LLMProvider):

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate_itineraries(
        self,
        origin: str,
        duration_days: int,
        budget_per_leg: float,
        season: str,
        num_stops: int,
        available_airports: list[str],
        provider_hint: str = "",
    ) -> list[SuggestedItinerary]:
        user_prompt = build_user_prompt(
            origin, duration_days, budget_per_leg, season, num_stops, available_airports,
            provider_hint=provider_hint,
        )

        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _API_URL,
                params={"key": self._api_key},
                json=payload,
            )
            resp.raise_for_status()

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return parse_itineraries(raw)
