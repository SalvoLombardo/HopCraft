"""
Cache layer per i risultati di volo (PostgreSQL flight_cache).

Flusso di utilizzo:
    1. get_cached()  → hit? restituisce (offerte, fetched_at) senza chiamare il provider
    2. save_to_cache() → dopo ogni chiamata al provider, salva i risultati
    3. Il TTL è definito da CACHE_TTL_HOURS nel .env (default 6h)

La tabella flight_cache ha UNIQUE su (origin, destination, departure_date):
ogni tuple ha un solo record, aggiornato in-place quando la cache scade.
"""
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.flight_cache import FlightCache
from app.services.providers.base import FlightOffer


def _cutoff() -> datetime:
    """I'm using this to set the cutoff separately and having this allow to verify 
    if the FlightCache.fetched_at(see below async def get_cached ) is later of our cutoff 
    In this way if FlightCache.fetched_at >= _cutoff() it will means that the data is still valueable and usable
    """
    return (datetime.now(timezone.utc) - timedelta(hours=settings.cache_ttl_hours)).replace(tzinfo=None)





########################################################################
#       TO GET CACHE
########################################################################
async def get_cached(
    session: AsyncSession,
    origin: str,
    destination: str,
    departure_date: date,
) -> tuple[list[FlightOffer], datetime] | None:
    """
    Used for searching a valid result in cache.

    Returns:
        (list of FlightOffer, fetched_at) if the cache is valid or
        None if doesn't exist or expired.
    """
    stmt = select(FlightCache).where(
        FlightCache.origin == origin,
        FlightCache.destination == destination,
        FlightCache.departure_date == departure_date,
        FlightCache.fetched_at >= _cutoff(),
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none() #scalar_one_or_none used to get only one result (simple cache logic)

    if row is None:
        return None
    

    offers = []
    data = row.raw_response or []
    for item in data:
        offer = FlightOffer(**item)#expecting k v pair
        offers.append(offer)
    #Convert cached DICTs back to FlightOffer obj



    return offers, row.fetched_at




########################################################################
#       TO SAVE CACHE
########################################################################
async def save_to_cache(
    session: AsyncSession,
    origin: str,
    destination: str,
    departure_date: date,
    offers: list[FlightOffer],
) -> None:
    """
    Salva i risultati in cache.
    Se esiste già un record per (origin, destination, departure_date), lo sovrascrive.
    """
    if not offers:
        return

    cheapest = min(offers, key=lambda o: o.price_eur)
    raw = [asdict(o) for o in offers]
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    stmt = (
        insert(FlightCache)
        .values(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            price_eur=cheapest.price_eur,
            airline=cheapest.airline,
            direct_flight=cheapest.direct,
            flight_duration_minutes=cheapest.duration_minutes,
            fetched_at=now,
            raw_response=raw,
        )
        .on_conflict_do_update(
            index_elements=["origin", "destination", "departure_date"],
            set_={
                "price_eur": cheapest.price_eur,
                "airline": cheapest.airline,
                "direct_flight": cheapest.direct,
                "flight_duration_minutes": cheapest.duration_minutes,
                "fetched_at": now,
                "raw_response": raw,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
