"""
Flight Provider Layer — interfaccia astratta (Strategy Pattern).

Il codice applicativo (search_engine, itinerary_engine) usa solo queste classi.
Il provider concreto viene scelto dalla factory tramite FLIGHT_PROVIDER nel .env.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class Leg:
    """Una singola tratta per la ricerca multi-city."""
    origin: str       # codice IATA (es. "CTA")
    destination: str  # codice IATA (es. "ATH")
    date: date


@dataclass
class FlightOffer:
    """Risultato normalizzato indipendente dal provider."""
    origin: str
    destination: str
    departure: str          # ISO datetime string (es. "2025-04-03T06:30:00")
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
        Cerca voli one-way da origin a destination nel range di date.
        Restituisce lista di FlightOffer ordinata per prezzo crescente.
        """
        ...

    @abstractmethod
    async def search_multi_city(
        self,
        legs: list[Leg],
    ) -> list[FlightOffer]:
        """
        Cerca voli per ogni tratta di un itinerario multi-city.
        Restituisce una FlightOffer per ogni tratta (la più economica trovata).
        """
        ...
