"""
Endpoint Reverse Search.

GET /api/v1/search/reverse
  ?destination=CTA
  &date_from=2026-04-01
  &date_to=2026-04-03
  &direct_only=false
  &max_results=50
"""
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.schemas import FlightOfferOut, ReverseSearchOut
from app.services.search_engine import reverse_search

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/reverse", response_model=ReverseSearchOut)
async def search_reverse(
    session: SessionDep,
    destination: Annotated[str, Query(min_length=3, max_length=3, description="Codice IATA destinazione")],
    date_from: Annotated[date, Query(description="Data partenza minima (YYYY-MM-DD)")],
    date_to: Annotated[date, Query(description="Data partenza massima (YYYY-MM-DD)")],
    direct_only: Annotated[bool, Query(description="Solo voli diretti")] = False,
    max_results: Annotated[int, Query(ge=1, le=200, description="Numero massimo risultati")] = 50,
) -> ReverseSearchOut:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from deve essere <= date_to")
    if (date_to - date_from).days > 6:
        raise HTTPException(status_code=422, detail="Il range massimo è 7 giorni")

    results, cached, fetched_at = await reverse_search(
        session=session,
        destination=destination.upper(),
        date_from=date_from,
        date_to=date_to,
        direct_only=direct_only,
        max_results=max_results,
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
    )
