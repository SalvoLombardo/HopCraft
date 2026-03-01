"""
RyanairProvider — fallback 1 nella cascade flight provider.

Usa la libreria Flyan (PyPI) che chiama direttamente gli endpoint non ufficiali
di Ryanair senza richiedere API key. Copre esclusivamente le rotte Ryanair.

Vantaggi: nessuna quota mensile dichiarata, attivamente mantenuto (lug 2025).
Limiti: solo Ryanair, endpoint non ufficiali (rischio ToS, possibile instabilità).

Nota: Flyan è una libreria sincrona → le chiamate vengono eseguite in un thread
pool separato via asyncio.to_thread() per non bloccare l'event loop.

Documentazione: https://pypi.org/project/Flyan/
"""
import asyncio
import logging
from datetime import date, datetime

from flyan import FlightSearchParams, RyanAir

from app.services.providers.base import FlightOffer, FlightProvider, Leg

logger = logging.getLogger(__name__)

# Istanza riusabile (thread-safe per letture concorrenti)
_client = RyanAir(currency="EUR")


def _sync_search(origin: str, destination: str, date_from: date, date_to: date) -> list[FlightOffer]:
    """Chiama Flyan in modo sincrono e normalizza i risultati in FlightOffer."""
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
                direct=True,   # Ryanair non offre voli con scalo tramite questa API
                duration_minutes=duration,
            ))
        except Exception as exc:
            logger.debug("RyanairProvider: errore parsing volo: %s", exc)
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
            logger.warning("RyanairProvider %s→%s [%s/%s]: %s", origin, destination, date_from, date_to, exc)
            return []
        offers.sort(key=lambda o: o.price_eur)
        return offers[:max_results]

    async def search_multi_city(self, legs: list[Leg]) -> list[FlightOffer]:
        """Cerca la tratta più economica per ogni leg in modo sequenziale."""
        result: list[FlightOffer] = []
        for leg in legs:
            leg_offers = await self.search_one_way(
                leg.origin, leg.destination, leg.date, leg.date, max_results=5
            )
            if leg_offers:
                result.append(min(leg_offers, key=lambda o: o.price_eur))
        return result
