"""
Flight Provider Factory — cascade automatica SerpAPI → Amadeus.

get_providers_in_order() interroga Redis per i saldi rimanenti e restituisce
solo i provider con quota disponibile, nell'ordine prefissato.

Ogni provider ha una chiave Redis separata (es. "serpapi:monthly") con TTL
di 30 giorni: il contatore si azzera automaticamente al ciclo successivo.

Funzioni esposte:
  get_providers_in_order() → lista (nome, provider) con quota > 0
  get_provider_quotas()    → dict {nome: saldo_rimanente} per entrambi
  PROVIDER_LIMITS          → dict con i limiti mensili (con margine)
  MONTHLY_WINDOW           → durata della finestra in secondi (30 giorni)
"""
from app.config import settings
from app.services.providers.base import FlightProvider
from app.services.providers.google_flights import GoogleFlightsProvider
from app.services.providers.amadeus import AmadeusProvider
from app.utils.rate_limiter import get_remaining

# Finestra mensile in secondi (usata anche da search_engine e itinerary_engine)
MONTHLY_WINDOW: int = 30 * 24 * 3600

# Limiti mensili con margine di sicurezza (~10%)
# serpapi:  250 req/mese free tier → limite 230
# amadeus:  2000 req/mese free tier → limite 1800
PROVIDER_LIMITS: dict[str, int] = {
    "serpapi": 230,
    "amadeus": 1800,
}

# Note human-readable mostrate nel badge frontend per ogni stato attivo
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
    """Costruisce la lista completa nell'ordine cascade."""
    return [
        ("serpapi", GoogleFlightsProvider()),
        ("amadeus", AmadeusProvider(settings.amadeus_api_key, settings.amadeus_api_secret)),
    ]


async def get_providers_in_order() -> list[tuple[str, FlightProvider]]:
    """
    Restituisce i provider con quota residua nell'ordine cascade.

    Se settings.flight_provider è impostato su un provider noto ("serpapi" o "amadeus"),
    quel provider viene messo in testa alla lista indipendentemente dall'ordine di default.
    Utile in sviluppo per forzare Amadeus (più quota) e preservare i crediti SerpAPI.

    Esempio .env:
        FLIGHT_PROVIDER=amadeus   → ordine [amadeus, serpapi]
        FLIGHT_PROVIDER=serpapi   → ordine [serpapi, amadeus]  (default)
        FLIGHT_PROVIDER=cascade   → ordine [serpapi, amadeus]  (cascade automatica)

    Se tutti sono esauriti restituisce lista vuota.
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
    """Saldo rimanente per ogni provider — incluso nella risposta API."""
    return {
        name: await get_remaining(f"{name}:monthly", limit)
        for name, limit in PROVIDER_LIMITS.items()
    }
