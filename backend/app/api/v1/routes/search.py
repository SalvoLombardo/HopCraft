from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.schemas import FlightOfferOut, ReverseSearchOut, SmartMultiIn, SmartMultiOut
from app.services.search_engine import reverse_search
from app.services.itinerary_engine import run_smart_multi

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]





"""
Endpoint Reverse Search.-----------------------------------------------------------------------------------

GET /api/v1/search/reverse
  ?destination=CTA
  &date_from=2026-04-01
  &date_to=2026-04-03
  &direct_only=false
  &max_results=50
  &origin_lat=52.3     
  &origin_lon=4.9
  &radius_km=600
"""
@router.get("/reverse", response_model=ReverseSearchOut)
async def search_reverse(
    session: SessionDep,
    destination: Annotated[str, Query(min_length=3, max_length=3, description="Codice IATA destinazione")],
    date_from: Annotated[date, Query(description="Data partenza minima (YYYY-MM-DD)")],
    date_to: Annotated[date, Query(description="Data partenza massima (YYYY-MM-DD)")],
    direct_only: Annotated[bool, Query(description="Solo voli diretti")] = False,
    max_results: Annotated[int, Query(ge=1, le=200, description="Numero massimo risultati")] = 50,
    origin_lat: Annotated[float | None, Query(ge=-90, le=90, description="Latitudine area di partenza")] = None,
    origin_lon: Annotated[float | None, Query(ge=-180, le=180, description="Longitudine area di partenza")] = None,
    radius_km: Annotated[int | None, Query(ge=50, le=5000, description="Raggio in km dall'area di partenza")] = None,
) -> ReverseSearchOut:
    
    #Validation area -------------------------------------------
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from deve essere <= date_to")
    if (date_to - date_from).days > 6:
        raise HTTPException(status_code=422, detail="Il range massimo è 7 giorni")
    if (origin_lat is None) != (origin_lon is None):
        raise HTTPException(status_code=422, detail="origin_lat e origin_lon devono essere forniti insieme")
    #Validation area -------------------------------------------


    results, cached, fetched_at, provider_status = await reverse_search(
        session=session,
        destination=destination.upper(),
        date_from=date_from,
        date_to=date_to,
        direct_only=direct_only,
        max_results=max_results,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        radius_km=radius_km,
    )

    if not results:
        raise HTTPException(status_code=404, detail=f"Nessun volo trovato verso {destination}")

    offers = [
        FlightOfferOut(
            origin=r["origin"],
            origin_city=r["origin_city"],
            price_eur=r["price_eur"],
            airline=r["airline"],
            departure=datetime.fromisoformat(r["departure"]),
            direct=r["direct"],
            duration_minutes=r["duration_minutes"],
            latitude=r["latitude"],
            longitude=r["longitude"],
        )
        for r in results
    ]

    return ReverseSearchOut(
        destination=destination.upper(),
        results=offers,
        cached=cached,
        fetched_at=fetched_at,
        provider_status=provider_status,
    )


@router.post("/smart-multi", response_model=SmartMultiOut)
async def search_smart_multi(
    session: SessionDep,
    body: SmartMultiIn,
) -> SmartMultiOut:
    """
    Smart Multi-City: dato origine, durata, budget e date restituisce
    i top 5 itinerari multi-città ottimizzati con prezzi reali.
    """
    #Validation area -------------------------------------------
    if body.trip_duration_days < 5 or body.trip_duration_days > 25:
        raise HTTPException(status_code=422, detail="trip_duration_days deve essere tra 5 e 25")
    if body.budget_per_person_eur <= 0:
        raise HTTPException(status_code=422, detail="budget_per_person_eur deve essere positivo")
    if body.travelers < 1:
        raise HTTPException(status_code=422, detail="travelers deve essere almeno 1")
    if body.date_from >= body.date_to:
        raise HTTPException(status_code=422, detail="date_from deve essere < date_to")
    #Validation area -------------------------------------------




    try:
        result = await run_smart_multi(
            session=session,
            origin=body.origin.upper(),
            trip_duration_days=body.trip_duration_days,
            budget_per_person_eur=body.budget_per_person_eur,
            travelers=body.travelers,
            date_from=body.date_from,
            date_to=body.date_to,
            direct_only=body.direct_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return result
