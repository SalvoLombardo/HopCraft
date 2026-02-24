"""
TequilaProvider — placeholder per uso futuro.

Tequila (Kiwi.com) non è più accessibile gratuitamente.
Questo provider è predisposto per una futura reintegrazione.
"""
from app.services.providers.base import FlightOffer, FlightProvider, Leg


class TequilaProvider(FlightProvider):

    async def search_one_way(self, *args, **kwargs) -> list[FlightOffer]:
        raise NotImplementedError(
            "TequilaProvider non è implementato: Tequila API non è accessibile gratuitamente."
        )

    async def search_multi_city(self, legs: list[Leg]) -> list[FlightOffer]:
        raise NotImplementedError(
            "TequilaProvider non è implementato: Tequila API non è accessibile gratuitamente."
        )
