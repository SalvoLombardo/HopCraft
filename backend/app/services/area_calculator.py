"""
Area Calculator — Step 1 della pipeline Smart Multi-City.

Data un'origine e una durata di viaggio:
  1. Calcola il raggio esplorabile (estimate_radius_km)
  2. Stima il numero di tappe intermedie (estimate_stops)
  3. Interroga il DB e filtra gli aeroporti entro quel raggio (Haversine)

Restituisce un AreaResult con tutto il necessario per lo Step 2 (LLM).
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.airport import Airport
from app.utils.geo import estimate_radius_km, estimate_stops, haversine_km


@dataclass
class ReachableAirport:
    iata_code: str
    city: str
    country: str
    latitude: float
    longitude: float
    distance_km: int


@dataclass
class AreaResult:
    origin_iata: str
    radius_km: int
    num_stops: int
    airports: list[ReachableAirport]


async def calculate_area(
    session: AsyncSession,
    origin_iata: str,
    trip_duration_days: int,
) -> AreaResult:
    """
    Calcola l'area esplorabile per la pipeline Smart Multi-City.

    Args:
        session:            sessione DB asincrona
        origin_iata:        codice IATA dell'aeroporto di partenza/ritorno
        trip_duration_days: durata totale del viaggio in giorni

    Returns:
        AreaResult con raggio, numero tappe e lista aeroporti raggiungibili
        (esclude l'origine stessa, ordinati per distanza crescente).

    Raises:
        ValueError: se l'aeroporto di origine non esiste nel DB o non è attivo.
    """
    # Recupera le coordinate dell'origine
    result = await session.execute(
        select(Airport).where(
            Airport.iata_code == origin_iata,
            Airport.is_active.is_(True),
        )
    )
    origin = result.scalar_one_or_none()
    if origin is None:
        raise ValueError(f"Aeroporto di origine '{origin_iata}' non trovato o non attivo.")

    radius_km = estimate_radius_km(trip_duration_days)
    num_stops = estimate_stops(trip_duration_days)

    # Carica tutti gli aeroporti attivi (esclusa l'origine)
    all_result = await session.execute(
        select(Airport).where(
            Airport.is_active.is_(True),
            Airport.iata_code != origin_iata,
        )
    )
    all_airports = all_result.scalars().all()

    # Filtra per raggio e costruisce la lista con distanza
    reachable: list[ReachableAirport] = []
    for airport in all_airports:
        dist = haversine_km(origin.latitude, origin.longitude, airport.latitude, airport.longitude)
        if dist <= radius_km:
            reachable.append(
                ReachableAirport(
                    iata_code=airport.iata_code,
                    city=airport.city,
                    country=airport.country,
                    latitude=airport.latitude,
                    longitude=airport.longitude,
                    distance_km=round(dist),
                )
            )

    reachable.sort(key=lambda a: a.distance_km)

    return AreaResult(
        origin_iata=origin_iata,
        radius_km=radius_km,
        num_stops=num_stops,
        airports=reachable,
    )
