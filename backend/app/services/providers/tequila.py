"""
TequilaProvider — placeholder for future use.

Tequila (Kiwi.com) is no longer freely accessible.
This provider is scaffolded for a potential future reintegration.
"""
from app.services.providers.base import FlightOffer, FlightProvider, Leg


class TequilaProvider(FlightProvider):

    async def search_one_way(self, *args, **kwargs) -> list[FlightOffer]:
        raise NotImplementedError(
            "TequilaProvider is not implemented: Tequila API is no longer freely accessible."
        )

    async def search_multi_city(self, legs: list[Leg]) -> list[FlightOffer]:
        raise NotImplementedError(
            "TequilaProvider is not implemented: Tequila API is no longer freely accessible."
        )
