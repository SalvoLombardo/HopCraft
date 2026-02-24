"""
AmadeusProvider — fallback provider (official, stable API).

Uses the Amadeus Self-Service API (free tier: 2,000 requests/month).
LIMITATION: the free tier does NOT include European low-cost airlines
(Ryanair, Wizz Air, easyJet), so prices are incomplete
for HopCraft’s main use case.

Documentation: https://developers.amadeus.com/self-service/category/flights
"""
import re
from datetime import date

import httpx

from app.services.providers.base import FlightOffer, FlightProvider, Leg

_AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
_SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"


def _parse_iso_duration(duration: str) -> int:
    """Converte durata ISO 8601 'PT2H30M' in minuti totali."""
    hours = int(re.search(r"(\d+)H", duration).group(1)) if "H" in duration else 0
    mins = int(re.search(r"(\d+)M", duration).group(1)) if "M" in duration else 0
    return hours * 60 + mins


def _parse_offer(item: dict) -> FlightOffer | None:
    """Normalizza un'offerta Amadeus nel formato FlightOffer."""
    try:
        itinerary = item["itineraries"][0]
        segments = itinerary["segments"]
        first_seg = segments[0]
        last_seg = segments[-1]

        return FlightOffer(
            origin=first_seg["departure"]["iataCode"],
            destination=last_seg["arrival"]["iataCode"],
            departure=first_seg["departure"]["at"],
            price_eur=float(item["price"]["total"]),
            airline=first_seg["carrierCode"],
            direct=(len(segments) == 1),
            duration_minutes=_parse_iso_duration(itinerary["duration"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


class AmadeusProvider(FlightProvider):

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            _AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.api_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        direct_only: bool = False,
        max_results: int = 50,
    ) -> list[FlightOffer]:
        # Amadeus non supporta range di date nativamente:
        # si usa date_from come data di partenza principale
        params: dict = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": date_from.isoformat(),
            "adults": 1,
            "currencyCode": "EUR",
            "max": min(max_results, 250),  # Amadeus max è 250
        }
        if direct_only:
            params["nonStop"] = "true"

        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._get_token(client)
            resp = await client.get(
                _SEARCH_URL,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()

        offers = [_parse_offer(item) for item in resp.json().get("data", [])]
        return [o for o in offers if o is not None]

    async def search_multi_city(
        self,
        legs: list[Leg],
    ) -> list[FlightOffer]:
        """Cerca sequenzialmente ogni tratta e restituisce la più economica per leg."""
        result: list[FlightOffer] = []
        for leg in legs:
            leg_offers = await self.search_one_way(
                leg.origin, leg.destination, leg.date, leg.date, max_results=5
            )
            if leg_offers:
                result.append(min(leg_offers, key=lambda o: o.price_eur))
        return result
