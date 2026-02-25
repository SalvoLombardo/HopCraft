"""
Flight Provider Factory.

Legge FLIGHT_PROVIDER dal .env e restituisce l'istanza corretta.
Il codice applicativo chiama solo get_flight_provider() — non sa
quale provider sta usando (Strategy Pattern).
"""
from app.config import settings
from app.services.providers.base import FlightProvider
from app.services.providers.google_flights import GoogleFlightsProvider
from app.services.providers.amadeus import AmadeusProvider


def get_flight_provider() -> FlightProvider:
    if settings.flight_provider == "google_flights":
        return GoogleFlightsProvider()
    # default: amadeus
    return AmadeusProvider(
        api_key=settings.amadeus_api_key,
        api_secret=settings.amadeus_api_secret,
    )
