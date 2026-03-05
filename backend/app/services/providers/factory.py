"""
Flight Provider Factory — automatic cascade SerpAPI → Amadeus.

get_providers_in_order() queries Redis for remaining quotas and returns
only providers with available quota, in the predefined order.

Each provider has a separate Redis key (e.g. "serpapi:monthly") with a 30-day TTL:
the counter resets automatically at the start of the next cycle.

Exposed functions:
  get_providers_in_order() → list of (name, provider) with quota > 0
  get_provider_quotas()    → dict {name: remaining_balance} for both providers
  PROVIDER_LIMITS          → dict with monthly limits (with safety margin)
  MONTHLY_WINDOW           → window duration in seconds (30 days)
"""
from app.config import settings
from app.services.providers.base import FlightProvider
from app.services.providers.google_flights import GoogleFlightsProvider
from app.services.providers.amadeus import AmadeusProvider
from app.utils.rate_limiter import get_remaining

# Monthly window in seconds (also used by search_engine and itinerary_engine)
MONTHLY_WINDOW: int = 30 * 24 * 3600

# Monthly limits with safety margin (~10%)
# serpapi:  250 req/month free tier → limit 230
# amadeus:  2000 req/month free tier → limit 1800
PROVIDER_LIMITS: dict[str, int] = {
    "serpapi": 230,
    "amadeus": 1800,
}

# Human-readable notes shown in the frontend badge for each active state
PROVIDER_NOTES: dict[str, str] = {
    "serpapi": (
        "Results from Google Flights (SerpAPI) — includes Wizz Air, easyJet and more. "
        f"{PROVIDER_LIMITS['serpapi']} req/month free tier."
    ),
    "amadeus": (
        "SerpAPI quota exhausted for this month. "
        "Results limited to major carriers (Lufthansa, Air France, Iberia…) — "
        "no Ryanair, easyJet or Wizz Air."
    ),
    "none": "All flight providers exhausted for this month. Try again next month.",
}


def _all_providers() -> list[tuple[str, FlightProvider]]:
    """Builds the full provider list in cascade order."""
    return [
        ("serpapi", GoogleFlightsProvider()),
        ("amadeus", AmadeusProvider(settings.amadeus_api_key, settings.amadeus_api_secret)),
    ]


async def get_providers_in_order() -> list[tuple[str, FlightProvider]]:
    """
    Returns providers with remaining quota in cascade order.

    If settings.flight_provider is set to a known provider ("serpapi" or "amadeus"),
    that provider is moved to the front of the list regardless of the default order.
    Useful in development to force Amadeus (more quota) and preserve SerpAPI credits.

    Example .env:
        FLIGHT_PROVIDER=amadeus   → order [amadeus, serpapi]
        FLIGHT_PROVIDER=serpapi   → order [serpapi, amadeus]  (default)
        FLIGHT_PROVIDER=cascade   → order [serpapi, amadeus]  (automatic cascade)

    Returns an empty list if all providers are exhausted.
    """
    ordered = _all_providers()

    forced = settings.flight_provider
    if forced in PROVIDER_LIMITS:
        ordered = (
            [p for p in ordered if p[0] == forced]
            + [p for p in ordered if p[0] != forced]
        )

    result = []
    for name, provider in ordered:
        remaining = await get_remaining(f"{name}:monthly", PROVIDER_LIMITS[name])
        if remaining > 0:
            result.append((name, provider))
    return result


async def get_provider_quotas() -> dict[str, int]:
    """Remaining balance per provider — included in the API response."""
    return {
        name: await get_remaining(f"{name}:monthly", limit)
        for name, limit in PROVIDER_LIMITS.items()
    }
