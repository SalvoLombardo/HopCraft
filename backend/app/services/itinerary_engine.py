"""
Itinerary Engine — Pipeline Smart Multi-City (2.3).

Orchestra l'intera ricerca multi-città in 5 step:
  Step 1: calculate_area()         → raggio, num_stops, aeroporti raggiungibili
  Step 2: generate_with_fallback() → itinerari candidati via AI (JSON)
  Step 3: verifica prezzi reali via FlightProvider cascade (chiamate parallele asincrone)
  Step 4: filtraggio per budget + ranking per prezzo
  Step 5: restituzione top 5 come SmartMultiOut
"""
import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ItineraryOut, LegOut, ProviderStatus, SmartMultiOut
from app.services.area_calculator import AreaResult, calculate_area
from app.services.llm.base import SuggestedItinerary
from app.services.llm.factory import generate_with_fallback
from app.services.providers.base import FlightOffer, Leg
from app.services.providers.factory import (
    MONTHLY_WINDOW,
    PROVIDER_LIMITS,
    PROVIDER_NOTES,
    get_provider_quotas,
    get_providers_in_order,
)
from app.utils.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

# Hint iniettato nel prompt LLM solo quando Amadeus è l'unico provider disponibile.
# Amadeus free tier non copre le low-cost europee (Ryanair, easyJet, Wizz Air):
# serve guidare l'AI verso aeroporti principali coperti dalle major carriers.
_AMADEUS_PROVIDER_HINT = (
    "Il provider di voli attivo copre solo major carriers (Air France, Lufthansa, "
    "Iberia, BA, KLM, ITA, SAS, TAP, Finnair). Usa ESCLUSIVAMENTE aeroporti principali: "
    "CDG/ORY per Parigi, FCO per Roma, LHR/LGW per Londra, MXP/LIN per Milano, "
    "AMS per Amsterdam, BRU per Bruxelles, MAD per Madrid, BCN per Barcellona, "
    "FRA per Francoforte, MUC per Monaco, VIE per Vienna, ZRH per Zurigo. "
    "Evita aeroporti secondari: BGY, CIA, STN, BVA, CRL, HHN, EIN, MST, SXB, GDN."
)

# Limite aeroporti inviati all'LLM (i più vicini, già ordinati per distanza).
_MAX_AIRPORTS_FOR_LLM = 100

# Massimo task di pricing eseguiti in contemporanea.
_MAX_CONCURRENT_PRICING = 3


# ---------------------------------------------------------------------------
# Utility interne
# ---------------------------------------------------------------------------

def _season_from_date(d: date) -> str:
    """Restituisce la stagione italiana per la data di partenza."""
    month = d.month
    if month in (3, 4, 5):
        return "primavera"
    if month in (6, 7, 8):
        return "estate"
    if month in (9, 10, 11):
        return "autunno"
    return "inverno"


def _leg_dates(date_from: date, trip_duration_days: int, num_legs: int) -> list[date]:
    """
    Distribuisce le date di partenza di ogni tratta in modo uniforme
    sull'arco del viaggio.
    """
    days_per_leg = trip_duration_days // num_legs
    return [date_from + timedelta(days=i * days_per_leg) for i in range(num_legs)]


def _days_per_stop(trip_duration_days: int, num_stops: int) -> list[int]:
    """Distribuisce i giorni del viaggio tra le tappe intermedie."""
    if num_stops <= 0:
        return []
    base = trip_duration_days // num_stops
    remainder = trip_duration_days % num_stops
    return [base + (1 if i < remainder else 0) for i in range(num_stops)]


def _is_valid_route(route: list[str], origin: str) -> bool:
    """Valida la struttura della rotta restituita dall'AI."""
    if len(route) < 3:
        return False
    if route[0] != origin or route[-1] != origin:
        return False
    intermediate = route[1:-1]
    return len(intermediate) == len(set(intermediate))


# ---------------------------------------------------------------------------
# Step 3 helper — pricing di un singolo itinerario con cascade provider
# ---------------------------------------------------------------------------

async def _price_itinerary(
    suggested: SuggestedItinerary,
    origin: str,
    date_from: date,
    trip_duration_days: int,
    direct_only: bool,
    semaphore: asyncio.Semaphore,
    providers_in_order: list,
) -> tuple[SuggestedItinerary, list[FlightOffer]] | None:
    """
    Recupera il prezzo più basso per ogni tratta dell'itinerario suggerito,
    usando la cascade provider (SerpAPI → Ryanair → Amadeus).
    """
    if not _is_valid_route(suggested.route, origin):
        return None

    route = suggested.route
    num_legs = len(route) - 1
    dates = _leg_dates(date_from, trip_duration_days, num_legs)

    legs = [
        Leg(origin=route[i], destination=route[i + 1], date=dates[i])
        for i in range(num_legs)
    ]

    async with semaphore:
        offers: list[FlightOffer] = []
        for provider_name, provider in providers_in_order:
            rate_key = f"{provider_name}:monthly"
            allowed = await check_rate_limit(rate_key, PROVIDER_LIMITS[provider_name], MONTHLY_WINDOW)
            if not allowed:
                continue
            try:
                offers = await provider.search_multi_city(legs)
                if offers:
                    break
            except Exception as exc:
                logger.warning("Provider %s fallito per itinerario %s: %s", provider_name, route, exc)
                continue

    if len(offers) < num_legs:
        return None

    return (suggested, offers)


# ---------------------------------------------------------------------------
# Entry point pubblico
# ---------------------------------------------------------------------------

async def run_smart_multi(
    session: AsyncSession,
    origin: str,
    trip_duration_days: int,
    budget_per_person_eur: float,
    travelers: int,
    date_from: date,
    date_to: date,
    direct_only: bool = False,
) -> SmartMultiOut:
    """
    Pipeline completa Smart Multi-City.

    Returns:
        SmartMultiOut con i top 5 itinerari ordinati per prezzo + provider_status.
    """

    # ── Step 1: area esplorabile
    explorable_area_details: AreaResult = await calculate_area(session, origin, trip_duration_days)

    # ── Cascade provider setup (fatto prima dello Step 2 per calcolare il provider_hint)
    providers_in_order = await get_providers_in_order()
    provider_names = [name for name, _ in providers_in_order]
    active_provider = provider_names[0] if provider_names else "none"

    # Il provider_hint guida l'AI solo quando Amadeus è l'unico disponibile
    only_amadeus = provider_names == ["amadeus"]
    provider_hint = _AMADEUS_PROVIDER_HINT if only_amadeus else ""

    # ── Step 2: generazione itinerari via AI
    allowed_num_legs = explorable_area_details.num_stops + 1
    budget_per_leg = budget_per_person_eur / allowed_num_legs
    season = _season_from_date(date_from)

    airports_for_llm = explorable_area_details.airports[:_MAX_AIRPORTS_FOR_LLM]
    available_airports = [f"{a.iata_code} ({a.city})" for a in airports_for_llm]

    suggestions: list[SuggestedItinerary] = await generate_with_fallback(
        origin=origin,
        duration_days=trip_duration_days,
        budget_per_leg=budget_per_leg,
        season=season,
        num_stops=explorable_area_details.num_stops,
        available_airports=available_airports,
        provider_hint=provider_hint,
    )

    # ── Step 3: verifica prezzi reali (parallelo, con limite concorrenza)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PRICING)
    tasks = [
        _price_itinerary(s, origin, date_from, trip_duration_days, direct_only, semaphore, providers_in_order)
        for s in suggestions
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # ── Step 4: filtraggio per budget + ranking
    n_no_data = 0
    n_over_budget = 0

    priced: list[tuple[SuggestedItinerary, list[FlightOffer], float]] = []
    for res in results:
        if res is None or isinstance(res, Exception):
            n_no_data += 1
            continue
        suggested, offers = res
        total_per_person = sum(o.price_eur for o in offers)
        if total_per_person > budget_per_person_eur:
            n_over_budget += 1
            continue
        priced.append((suggested, offers, total_per_person))

    priced.sort(key=lambda x: x[2])
    top5 = priced[:5]

    if not top5:
        if n_no_data > 0 and n_over_budget == 0:
            raise ValueError(
                f"Il provider non ha trovato voli per le rotte suggerite dall'AI "
                f"({n_no_data} itinerari senza copertura). "
                "Prova con date diverse, un'origine con più connessioni, o cambia il provider voli."
            )
        if n_over_budget > 0 and n_no_data == 0:
            raise ValueError(
                f"Trovati {n_over_budget} itinerari ma tutti oltre il budget di "
                f"€{budget_per_person_eur:.0f}/persona. "
                "Prova ad aumentare il budget o la durata del viaggio."
            )
        if n_no_data > 0 and n_over_budget > 0:
            raise ValueError(
                f"Nessun itinerario valido: {n_no_data} senza copertura voli, "
                f"{n_over_budget} oltre il budget di €{budget_per_person_eur:.0f}/persona. "
                "Prova con date diverse o aumenta il budget."
            )
        raise ValueError(
            "L'AI non ha generato itinerari validi per i parametri forniti. "
            "Prova con un'origine diversa o date diverse."
        )

    # ── Step 5: costruzione risposta
    itineraries: list[ItineraryOut] = []
    for rank, (suggested, offers, total_per_person) in enumerate(top5, start=1):
        legs_out = [
            LegOut(
                from_airport=o.origin,
                to_airport=o.destination,
                price_per_person_eur=o.price_eur,
                airline=o.airline,
                departure=o.departure,
                duration_minutes=o.duration_minutes,
                direct=o.direct,
            )
            for o in offers
        ]
        num_stops_in_route = len(suggested.route) - 2
        itineraries.append(
            ItineraryOut(
                rank=rank,
                route=suggested.route,
                total_price_per_person_eur=round(total_per_person, 2),
                total_price_all_travelers_eur=round(total_per_person * travelers, 2),
                legs=legs_out,
                ai_notes=suggested.reasoning,
                suggested_days_per_stop=_days_per_stop(trip_duration_days, num_stops_in_route),
            )
        )

    quotas = await get_provider_quotas()
    provider_status = ProviderStatus(
        active_provider=active_provider,
        serpapi_remaining=quotas.get("serpapi", 0),
        amadeus_remaining=quotas.get("amadeus", 0),
        note=PROVIDER_NOTES.get(active_provider, ""),
    )

    return SmartMultiOut(origin=origin, itineraries=itineraries, provider_status=provider_status)
