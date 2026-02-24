from datetime import datetime
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Airports
# ---------------------------------------------------------------------------

class AirportOut(BaseModel):
    iata_code: str
    name: str
    city: str
    country: str
    latitude: float
    longitude: float
    is_active: bool

    # Permette a Pydantic di leggere i dati direttamente da oggetti SQLAlchemy
    model_config = {"from_attributes": True}


class AirportNearbyOut(AirportOut):
    #distance from airpot as main point
    distance_km: int


# ---------------------------------------------------------------------------
# The result for a single flight(used in the reverse search)
# ---------------------------------------------------------------------------

class FlightOfferOut(BaseModel):
    origin: str
    origin_city: str
    price_eur: float
    airline: str
    departure: datetime
    direct: bool
    duration_minutes: int
    latitude: float
    longitude: float


# ---------------------------------------------------------------------------
# reverse search answer
# ---------------------------------------------------------------------------

class ReverseSearchOut(BaseModel):
    destination: str
    results: list[FlightOfferOut]
    cached: bool
    fetched_at: datetime


# ---------------------------------------------------------------------------
# smart multi-city answere (strutture nidificate)
# ---------------------------------------------------------------------------

class LegOut(BaseModel):
    from_airport: str
    to_airport: str
    price_per_person_eur: float
    airline: str
    departure: datetime
    duration_minutes: int
    direct: bool


class ItineraryOut(BaseModel):
    rank: int
    route: list[str]
    total_price_per_person_eur: float
    total_price_all_travelers_eur: float
    legs: list[LegOut]
    ai_notes: str
    suggested_days_per_stop: list[int]


class SmartMultiOut(BaseModel):
    origin: str
    itineraries: list[ItineraryOut]
