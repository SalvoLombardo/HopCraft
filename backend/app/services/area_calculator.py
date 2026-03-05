"""
Area Calculator — Step 1 of the Smart Multi-City pipeline.

Given an origin and a trip duration:
  1. Computes the explorable radius (estimate_radius_km)
  2. Estimates the number of intermediate stops (estimate_stops)
  3. Queries the DB and filters airports within that radius (Haversine)

Returns an AreaResult with everything needed for Step 2 (LLM).
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
    Computes the explorable area for the Smart Multi-City pipeline.

    Args:
        session:            async DB session
        origin_iata:        IATA code of the departure/return airport
        trip_duration_days: total trip duration in days

    Returns:
        AreaResult with radius, number of stops, and list of reachable airports
        (origin excluded, sorted by distance ascending).

    Raises:
        ValueError: if the origin airport does not exist in the DB or is inactive.
    """
    # Fetch the coordinates of the origin airport
    result = await session.execute(
        select(Airport).where(
            Airport.iata_code == origin_iata,
            Airport.is_active.is_(True),
        )
    )
    origin = result.scalar_one_or_none()
    if origin is None:
        raise ValueError(f"Origin airport '{origin_iata}' not found or inactive.")

    radius_km = estimate_radius_km(trip_duration_days)
    num_stops = estimate_stops(trip_duration_days)

    # Load all active airports (excluding the origin)
    all_result = await session.execute(
        select(Airport).where(
            Airport.is_active.is_(True),
            Airport.iata_code != origin_iata,
        )
    )
    all_airports = all_result.scalars().all()

    # Filter by radius and build the list with distances
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
