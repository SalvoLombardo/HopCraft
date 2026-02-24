"""
Core logic per la Reverse Search.

Flusso:
  1. Query efficiente in batch: trova tutte le cache entries valide per
     (qualsiasi_origine → destination) nelle date richieste.
  2. Per gli aeroporti senza cache, chiama il provider (max _MAX_NEW_CALLS_PER_SEARCH).
  3. Salva i nuovi risultati in cache.
  4. Restituisce lista arricchita con coordinate aeroporto + metadati.

Rate limit mensile gestito via Redis: la chiave cambia in base al provider
attivo (es. "amadeus:monthly") per evitare conflitti se si switcha provider.
Amadeus free tier: 2.000 req/mese → limite impostato a 1.800 (10% di margine).
"""
import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.airport import Airport
from app.models.flight_cache import FlightCache
from app.services.cache import save_to_cache
from app.services.providers.base import FlightOffer
from app.services.providers.factory import get_flight_provider
from app.utils.rate_limiter import check_rate_limit

# Nuove chiamate al provider massime per singola ricerca
# Con Amadeus (2000 req/mese) possiamo permetterci batch più grandi.
_MAX_NEW_CALLS_PER_SEARCH = 50
# Limite mensile con margine di sicurezza (Amadeus: 2000 → 1800)
_PROVIDER_MONTHLY_LIMIT = 1800
_MONTHLY_WINDOW = 30 * 24 * 3600


def _cache_cutoff() -> datetime:
    return datetime.utcnow() - timedelta(hours=settings.cache_ttl_hours)


async def reverse_search(
    session: AsyncSession,
    destination: str,
    date_from: date,
    date_to: date,
    direct_only: bool = False,
    max_results: int = 50,
) -> tuple[list[dict], bool, datetime]:
    """
    Reverse search: trova i voli più economici verso destination da tutti gli aeroporti attivi.

    Returns:
        (lista risultati, all_from_cache, fetched_at)
        Ogni elemento della lista è un dict compatibile con FlightOfferOut.
    """
    # --- 1. Carica tutti gli aeroporti attivi (esclusa la destinazione stessa) ---
    stmt_airports = select(Airport).where(
        Airport.is_active.is_(True),
        Airport.iata_code != destination,
    )
    airport_rows = await session.execute(stmt_airports)
    airports: list[Airport] = list(airport_rows.scalars().all())
    airport_map: dict[str, Airport] = {a.iata_code: a for a in airports}

    # --- 2. Costruisce la lista di date nel range (max 7) ---
    date_list: list[date] = []
    current = date_from
    while current <= date_to and len(date_list) < 7:
        date_list.append(current)
        current += timedelta(days=1)

    # --- 3. Batch query cache: tutti i risultati validi per questa destinazione/date ---
    stmt_cache = select(FlightCache).where(
        FlightCache.destination == destination,
        FlightCache.departure_date.in_(date_list),
        FlightCache.fetched_at >= _cache_cutoff(),
    )
    cache_rows = await session.execute(stmt_cache)

    # Per ogni origine, tieni solo l'offerta più economica fra tutte le date in cache
    cache_best: dict[str, tuple[FlightOffer, datetime]] = {}
    for row in cache_rows.scalars():
        offers = [FlightOffer(**item) for item in (row.raw_response or [])]
        if not offers:
            continue
        cheapest = min(offers, key=lambda o: o.price_eur)
        prev = cache_best.get(row.origin)
        if prev is None or cheapest.price_eur < prev[0].price_eur:
            cache_best[row.origin] = (cheapest, row.fetched_at)

    # --- 4. Identifica le origini senza cache ---
    all_origins = set(airport_map.keys())
    cached_origins = set(cache_best.keys())
    missing_origins = list(all_origins - cached_origins)[:_MAX_NEW_CALLS_PER_SEARCH]

    # --- 5. Fetch parallelo per le origini mancanti (con rate limit) ---
    provider = get_flight_provider()
    fresh_best: dict[str, FlightOffer] = {}

    async def _fetch(origin: str) -> None:
        rate_key = f"{settings.flight_provider}:monthly"
        allowed = await check_rate_limit(rate_key, _PROVIDER_MONTHLY_LIMIT, _MONTHLY_WINDOW)
        if not allowed:
            return
        try:
            offers = await provider.search_one_way(
                origin, destination, date_from, date_to,
                direct_only=direct_only, max_results=10,
            )
            if not offers:
                return
            # Salva in cache suddividendo per data
            for d in date_list:
                day_offers = [o for o in offers if o.departure.startswith(d.isoformat())]
                if day_offers:
                    await save_to_cache(session, origin, destination, d, day_offers)
            fresh_best[origin] = min(offers, key=lambda o: o.price_eur)
        except Exception:
            pass

    await asyncio.gather(*[_fetch(o) for o in missing_origins])

    # --- 6. Assembla la risposta con coordinate aeroporto ---
    results: list[dict] = []

    for origin, (offer, fetched_at) in cache_best.items():
        airport = airport_map.get(origin)
        if airport:
            results.append(_build_result(offer, airport, fetched_at))

    now = datetime.utcnow()
    for origin, offer in fresh_best.items():
        airport = airport_map.get(origin)
        if airport:
            results.append(_build_result(offer, airport, now))

    results.sort(key=lambda r: r["price_eur"])
    results = results[:max_results]

    all_from_cache = len(fresh_best) == 0
    fetched_at = results[0]["_fetched_at"] if results else now

    # Rimuove il campo interno _fetched_at prima di restituire
    for r in results:
        r.pop("_fetched_at")

    return results, all_from_cache, fetched_at


def _build_result(offer: FlightOffer, airport: Airport, fetched_at: datetime) -> dict:
    return {
        "origin": offer.origin,
        "origin_city": airport.city,
        "price_eur": float(offer.price_eur),
        "airline": offer.airline,
        "departure": offer.departure,
        "direct": offer.direct,
        "duration_minutes": offer.duration_minutes,
        "latitude": float(airport.latitude),
        "longitude": float(airport.longitude),
        # Campo interno per estrarre fetched_at dal primo risultato
        "_fetched_at": fetched_at,
    }
