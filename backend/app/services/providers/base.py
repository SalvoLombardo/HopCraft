"""
Flight Provider Layer — abstract interface (Strategy Pattern).

Application code (search_engine, itinerary_engine) depends only on these classes.
The concrete provider is selected by the factory based on FLIGHT_PROVIDER in .env.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class Leg:
    """A single leg for multi-city search."""
    origin: str       # IATA code (e.g. "CTA")
    destination: str  # IATA code (e.g. "ATH")
    date: date


@dataclass
class FlightOffer:
    """Normalised flight result, provider-agnostic."""
    origin: str
    destination: str
    departure: str          # ISO datetime string (e.g. "2025-04-03T06:30:00")
    price_eur: float
    airline: str
    direct: bool
    duration_minutes: int


class FlightProvider(ABC):

    @abstractmethod
    async def search_one_way(
        self,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        direct_only: bool = False,
        max_results: int = 50,
    ) -> list[FlightOffer]:
        """
        Search one-way flights from origin to destination within the date range.
        Returns a list of FlightOffer sorted by price ascending.
        """
        ...

    @abstractmethod
    async def search_multi_city(
        self,
        legs: list[Leg],
    ) -> list[FlightOffer]:
        """
        Search flights for each leg of a multi-city itinerary.
        Returns one FlightOffer per leg (the cheapest found).
        """
        ...
