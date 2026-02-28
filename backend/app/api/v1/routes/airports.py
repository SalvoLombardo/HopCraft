"""
Endpoint Aeroporti.

GET /api/v1/airports
    Lista di tutti gli aeroporti attivi nel DB.

GET /api/v1/airports/in-radius
    Aeroporti entro un raggio (km) da una coordinata, ordinati per distanza.
    Usato dalla pipeline Smart Multi-City per filtrare le destinazioni raggiungibili.
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
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitudine centro")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitudine centro")],
    radius_km: Annotated[int, Query(ge=1, le=10000, description="Raggio in km")] = 2000,
) -> list[AirportNearbyOut]:
    """
    To get active airports from a starting point to a certain radius (lat, lon) order by distance ASC
    Used by Smart Multi-City to obtain reacheble destination
    """
    result = await session.execute(
        select(Airport).where(Airport.is_active.is_(True))
    )
    all_airports = result.scalars().all()

    nearby: list[AirportNearbyOut] = []
    for airport in all_airports:
        dist = haversine_km(lat, lon, float(airport.latitude), float(airport.longitude))
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
