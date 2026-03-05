"""
LLM Provider Factory — automatic fallback between providers

I decided to use a strategy pattern, the code will call only generate_with_fallback()
but he doesn't know witch provider he's using.

I created an order wich will be Gemini (primary) → Groq (fallback) → Mistral (fallback).
If the provider doesn't work (for example rate limit)
the factory will call the nex provider until there's no one to call

"""
import logging

from app.config import settings
from app.services.llm.base import SuggestedItinerary
from app.services.llm.gemini import GeminiProvider
from app.services.llm.groq import GroqProvider
from app.services.llm.mistral import MistralProvider

logger = logging.getLogger(__name__)

_PROVIDERS = {
    "gemini":  lambda: GeminiProvider(api_key=settings.gemini_api_key),
    "groq":    lambda: GroqProvider(api_key=settings.groq_api_key),
    "mistral": lambda: MistralProvider(api_key=settings.mistral_api_key),
}

_FALLBACK_ORDER = ["gemini", "groq", "mistral"]


async def generate_with_fallback(
    origin: str,
    duration_days: int,
    budget_per_leg: float,
    season: str,
    num_stops: int,
    available_airports: list[str],
    provider_hint: str = "",
) -> list[SuggestedItinerary]:
    """
    Attempts the provider configured in LLM_PROVIDER; if it fails, falls back to backup providers.

    Args:
    provider_hint: optional constraint for the prompt (e.g., restrictions of the active provider).
                   Empty string = no additional constraint.

    Raises:
        RuntimeError: if all providers fail.
"""
    start = _FALLBACK_ORDER.index(settings.llm_provider)

    for name in _FALLBACK_ORDER[start:]:
        try:
            provider = _PROVIDERS[name]()
            return await provider.generate_itineraries(
                origin=origin,
                duration_days=duration_days,
                budget_per_leg=budget_per_leg,
                season=season,
                num_stops=num_stops,
                available_airports=available_airports,
                provider_hint=provider_hint,
            )
        except Exception as exc:
            logger.warning("LLM provider '%s' failed: %s: %s", name, type(exc).__name__, exc)
            continue

    raise RuntimeError("None of the LLM providers are working.")
