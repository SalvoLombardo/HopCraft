"""
LLM Provider Factory — fallback automatico tra provider.

Ordine: Gemini (primario) → Groq (fallback veloce) → Mistral (fallback volume).
Se il provider configurato in LLM_PROVIDER fallisce (es. 429 rate limit o errore rete),
la factory tenta automaticamente il successivo nell'ordine fino ad esaurirli.

Il codice applicativo chiama solo generate_with_fallback() — non sa quale
provider sta usando (Strategy Pattern).
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
    Tenta il provider configurato in LLM_PROVIDER; in caso di errore scala ai fallback.

    Args:
        provider_hint: vincolo opzionale per il prompt (es. restrizioni del flight provider attivo).
                       Stringa vuota = nessun vincolo aggiuntivo.

    Raises:
        RuntimeError: se tutti i provider falliscono.
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
            logger.warning("LLM provider '%s' fallito: %s: %s", name, type(exc).__name__, exc)
            continue

    raise RuntimeError("Tutti i provider LLM hanno fallito.")
