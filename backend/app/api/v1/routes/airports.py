"""
Airports Endpoint 

GET /api/v1/airports
    The list of all airports in the db

GET /api/v1/airports/in-radius
    Endpoint used to get airports inside a specific radius (in km) ordered by distance
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.airport import Airport
from app.models.schemas import AirportNearbyOut, AirportOut
from app.utils.geo import haversine_km

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[AirportOut])
async def list_airports(session: SessionDep) -> list[AirportOut]:
    """To get all airports"""
    result = await session.execute(
        select(Airport).where(Airport.is_active.is_(True)).order_by(Airport.iata_code)
    )
    return list(result.scalars().all())


@router.get("/in-radius", response_model=list[AirportNearbyOut])
async def airports_in_radius(
    session: SessionDep,
    origin_lat: Annotated[float, Query(ge=-90, le=90, description="Latitude of the origin airport")],
    origin_lon: Annotated[float, Query(ge=-180, le=180, description="longitude of the origin airport")],
    radius_km: Annotated[int, Query(ge=1, le=10000, description="Radius in km")] = 2000,
) -> list[AirportNearbyOut]:
    """
    Get active airports within a given radius from the origin airport, ordered by distance ASC.
    """
    result = await session.execute(
        select(Airport).where(Airport.is_active.is_(True))
    )
    all_airports = result.scalars().all()

    nearby: list[AirportNearbyOut] = []
    for airport in all_airports:
        #checking if current airport is in the radius of th origin airport (where the travel is based)
        dist = haversine_km(origin_lat, origin_lon, float(airport.latitude), float(airport.longitude))
        if dist <= radius_km:
            nearby.append(
                AirportNearbyOut(
                    iata_code=airport.iata_code,
                    name=airport.name,
                    city=airport.city,
                    country=airport.country,
                    latitude=float(airport.latitude),
                    longitude=float(airport.longitude),
                    is_active=airport.is_active,
                    distance_km=round(dist),
                )
            )

    nearby.sort(key=lambda a: a.distance_km)
    return nearby
