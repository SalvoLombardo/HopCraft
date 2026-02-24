"""
GoogleFlightsProvider — provider primario via SerpAPI.

SerpAPI espone i dati di Google Flights (incluse le low-cost europee:
Ryanair, Wizz Air, easyJet) in JSON strutturato senza scraping diretto.

Free tier: 100 ricerche/mese — sufficiente per sviluppo e demo portfolio.
Registrazione: https://serpapi.com

Documentazione endpoint:
  https://serpapi.com/google-flights-api
"""
import asyncio
from datetime import date, timedelta

import httpx

from app.config import settings
from app.services.providers.base import FlightOffer, FlightProvider, Leg

_SERPAPI_URL = "https://serpapi.com/search.json"

# Massimo giorni nel range da cercare in parallelo
_MAX_DAYS_IN_RANGE = 7


def _parse_offer(item: dict, origin: str, destination: str) -> FlightOffer | None:
    """
    Normalizza un'offerta SerpAPI (best_flights o other_flights) in FlightOffer.

    Struttura SerpAPI:
    {
      "flights": [{"departure_airport": {...}, "arrival_airport": {...},
                   "airline": "Ryanair", "duration": 125, ...}],
      "total_duration": 125,
      "price": 29,
      ...
    }
    """
    try:
        flights = item.get("flights", [])
        if not flights:
            return None

        first_leg = flights[0]
        last_leg = flights[-1]

        departure_time = first_leg.get("departure_airport", {}).get("time", "")
        # SerpAPI restituisce orari come "2026-04-01 07:15" — li convertiamo in ISO
        departure_iso = departure_time.replace(" ", "T") if departure_time else ""

        return FlightOffer(
            origin=first_leg.get("departure_airport", {}).get("id", origin),
            destination=last_leg.get("arrival_airport", {}).get("id", destination),
            departure=departure_iso,
            price_eur=float(item.get("price", 0)),
            airline=first_leg.get("airline", "Unknown"),
            direct=(len(flights) == 1),
            duration_minutes=int(item.get("total_duration", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


async def _fetch_for_date(
    origin: str,
    destination: str,
    search_date: date,
    direct_only: bool,
    max_results: int,
) -> list[FlightOffer]:
    """Chiama SerpAPI per una singola data e restituisce FlightOffer normalizzati."""
    params: dict = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": search_date.isoformat(),
        "currency": "EUR",
        "hl": "en",
        "type": "2",      # 1=andata/ritorno, 2=solo andata
        "adults": "1",
        "api_key": settings.serpapi_api_key,
    }
    if direct_only:
        params["stops"] = "0"   # 0=solo diretti, 1=max 1 scalo, 2=qualsiasi

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_SERPAPI_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    offers: list[FlightOffer] = []
    # SerpAPI suddivide i risultati in best_flights e other_flights
    for section in ("best_flights", "other_flights"):
        for item in data.get(section, []):
            offer = _parse_offer(item, origin, destination)
            if offer:
                offers.append(offer)

    offers.sort(key=lambda o: o.price_eur)
    return offers[:max_results]


class GoogleFlightsProvider(FlightProvider):

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        direct_only: bool = False,
        max_results: int = 50,
    ) -> list[FlightOffer]:
        # Costruisce la lista di date nel range (max _MAX_DAYS_IN_RANGE)
        dates: list[date] = []
        current = date_from
        while current <= date_to and len(dates) < _MAX_DAYS_IN_RANGE:
            dates.append(current)
            current += timedelta(days=1)

        # Chiamate parallele (una per data)
        tasks = [
            _fetch_for_date(origin, destination, d, direct_only, max_results)
            for d in dates
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        offers: list[FlightOffer] = []
        for r in results:
            if isinstance(r, list):
                offers.extend(r)

        offers.sort(key=lambda o: o.price_eur)
        return offers[:max_results]

    async def search_multi_city(
        self,
        legs: list[Leg],
    ) -> list[FlightOffer]:
        """Cerca la tratta più economica per ogni leg in parallelo."""
        tasks = [
            _fetch_for_date(leg.origin, leg.destination, leg.date, False, 5)
            for leg in legs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        offers: list[FlightOffer] = []
        for r in results:
            if isinstance(r, list) and r:
                offers.append(min(r, key=lambda o: o.price_eur))

        return offers
