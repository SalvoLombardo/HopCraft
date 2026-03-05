"""
RyanairProvider — fallback 1 in the flight provider cascade.

Uses the Flyan library (PyPI) which calls Ryanair's unofficial endpoints
directly without requiring an API key. Covers Ryanair routes only.

Advantages: no declared monthly quota, actively maintained (Jul 2025).
Limitations: Ryanair only, unofficial endpoints (ToS risk, possible instability).

Note: Flyan is a synchronous library — calls are run in a thread pool
via asyncio.to_thread() to avoid blocking the event loop.

Documentation: https://pypi.org/project/Flyan/
"""
import asyncio
import logging
from datetime import date, datetime

from flyan import FlightSearchParams, RyanAir

from app.services.providers.base import FlightOffer, FlightProvider, Leg

logger = logging.getLogger(__name__)

# Reusable instance (thread-safe for concurrent reads)
_client = RyanAir(currency="EUR")


def _sync_search(
    origin: str, destination: str, date_from: date, date_to: date
) -> list[FlightOffer]:
    """Calls Flyan synchronously and normalises results into FlightOffer objects."""
    params = FlightSearchParams(
        from_airport=origin,
        to_airport=destination,
        from_date=datetime(date_from.year, date_from.month, date_from.day),
        to_date=datetime(date_to.year, date_to.month, date_to.day),
    )
    flights = _client.get_oneways(params)

    offers: list[FlightOffer] = []
    for f in flights:
        try:
            dep = f.departure_date
            arr = f.arrival_date
            dep_iso = dep.isoformat() if isinstance(dep, datetime) else str(dep)
            duration = int((arr - dep).total_seconds() / 60) if isinstance(arr, datetime) else 0
            offers.append(FlightOffer(
                origin=f.departure_airport.iata_code,
                destination=f.arrival_airport.iata_code,
                departure=dep_iso,
                price_eur=float(f.price),
                airline="Ryanair",
                direct=True,   # Ryanair does not offer connecting flights via this API
                duration_minutes=duration,
            ))
        except Exception as exc:
            logger.debug("RyanairProvider: error parsing flight: %s", exc)
            continue

    return offers


class RyanairProvider(FlightProvider):

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        direct_only: bool = False,
        max_results: int = 50,
    ) -> list[FlightOffer]:
        try:
            offers = await asyncio.to_thread(_sync_search, origin, destination, date_from, date_to)
        except Exception as exc:
            logger.warning(
                "RyanairProvider %s→%s [%s/%s]: %s",
                origin, destination, date_from, date_to, exc,
            )
            return []
        offers.sort(key=lambda o: o.price_eur)
        return offers[:max_results]

    async def search_multi_city(self, legs: list[Leg]) -> list[FlightOffer]:
        """Searches the cheapest offer for each leg sequentially."""
        result: list[FlightOffer] = []
        for leg in legs:
            leg_offers = await self.search_one_way(
                leg.origin, leg.destination, leg.date, leg.date, max_results=5
            )
            if leg_offers:
                result.append(min(leg_offers, key=lambda o: o.price_eur))
        return result
