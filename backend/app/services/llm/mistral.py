"""
MistralProvider — Mistral via La Plateforme (fallback volume).

Free tier: 1 miliardo di token/mese.
Nessuna carta di credito. Registrazione su console.mistral.ai.

API OpenAI-compatibile: usa response_format json_object per output strutturato.
"""
import httpx

from app.services.llm.base import (
    LLMProvider,
    SYSTEM_PROMPT,
    SuggestedItinerary,
    build_user_prompt,
    parse_itineraries,
)

_API_URL = "https://api.mistral.ai/v1/chat/completions"
_MODEL = "mistral-small-latest"


class MistralProvider(LLMProvider):

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
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                _API_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            resp.raise_for_status()

        raw = resp.json()["choices"][0]["message"]["content"]
        return parse_itineraries(raw)
