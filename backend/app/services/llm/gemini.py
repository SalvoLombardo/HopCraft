"""
GeminiProvider — Google Gemini 2.5 Flash (provider primario).

Free tier: 10 req/min, 250 req/giorno, 250K token/min.
Nessuna carta di credito. API key su aistudio.google.com.

Usa responseMimeType: "application/json" per forzare output JSON strutturato.
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
    ) -> list[SuggestedItinerary]:
        user_prompt = build_user_prompt(
            origin, duration_days, budget_per_leg, season, num_stops, available_airports
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

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _API_URL,
                params={"key": self._api_key},
                json=payload,
            )
            resp.raise_for_status()

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return parse_itineraries(raw)
