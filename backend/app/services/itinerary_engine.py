"""
Itinerary Engine — Pipeline Smart Multi-City (2.3).

Orchestra l'intera ricerca multi-città in 5 step:
  Step 1: calculate_area()         → raggio, num_stops, aeroporti raggiungibili
  Step 2: generate_with_fallback() → itinerari candidati via AI (JSON)
  Step 3: verifica prezzi reali via FlightProvider (chiamate parallele asincrone)
  Step 4: filtraggio per budget + ranking per prezzo
  Step 5: restituzione top 5 come SmartMultiOut
"""
import asyncio
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ItineraryOut, LegOut, SmartMultiOut
from app.services.area_calculator import AreaResult, calculate_area
from app.services.llm.base import SuggestedItinerary
from app.services.llm.factory import generate_with_fallback
from app.services.providers.base import FlightOffer, Leg
from app.services.providers.factory import get_flight_provider

# Limite aeroporti inviati all'LLM (i più vicini, già ordinati per distanza).
# Evita token overflow con liste molto grandi.
_MAX_AIRPORTS_FOR_LLM = 100

# Massimo task di pricing eseguiti in contemporanea (tutela rate limit API voli).
_MAX_CONCURRENT_PRICING = 5


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

    Esempio: date_from=01/06, trip=12 giorni, 4 tratte
      → [01/06, 04/06, 07/06, 10/06]
    """
    days_per_leg = trip_duration_days // num_legs
    return [date_from + timedelta(days=i * days_per_leg) for i in range(num_legs)]


def _days_per_stop(trip_duration_days: int, num_stops: int) -> list[int]:
    """
    Distribuisce i giorni del viaggio tra le tappe intermedie.
    I giorni rimanenti (modulo) vengono distribuiti sulle prime tappe.

    Esempio: 12 giorni, 3 tappe → [4, 4, 4]
             13 giorni, 3 tappe → [5, 4, 4]
    """
    if num_stops <= 0:
        return []
    base = trip_duration_days // num_stops
    remainder = trip_duration_days % num_stops
    return [base + (1 if i < remainder else 0) for i in range(num_stops)]


def _is_valid_route(route: list[str], origin: str) -> bool:
    """
    Valida la struttura della rotta restituita dall'AI.

    Criteri:
    - Almeno 3 elementi (origine + 1 tappa + ritorno)
    - Inizia e finisce con l'origine
    - Nessuna tappa intermedia duplicata
    """
    if len(route) < 3:
        return False
    if route[0] != origin or route[-1] != origin:
        return False
    # No duplicati nelle tappe intermedie (route[1:-1])
    intermediate = route[1:-1]
    return len(intermediate) == len(set(intermediate))


# ---------------------------------------------------------------------------
# Step 3 helper — pricing di un singolo itinerario
# ---------------------------------------------------------------------------

async def _price_itinerary(
    suggested: SuggestedItinerary,
    origin: str,
    date_from: date,
    trip_duration_days: int,
    direct_only: bool,
    semaphore: asyncio.Semaphore,
) -> tuple[SuggestedItinerary, list[FlightOffer]] | None:
    """
    Recupera il prezzo più basso per ogni tratta dell'itinerario suggerito.

    Restituisce (SuggestedItinerary, lista FlightOffer) se tutte le tratte
    hanno almeno un volo disponibile, None altrimenti.
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
        provider = get_flight_provider()
        offers = await provider.search_multi_city(legs)

    # search_multi_city restituisce una FlightOffer per ogni tratta trovata;
    # se una tratta non ha voli disponibili non viene inclusa → itinerario incompleto.
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

    Args:
        session:               sessione DB asincrona
        origin:                IATA aeroporto di partenza/ritorno (es. "CTA")
        trip_duration_days:    durata totale del viaggio in giorni
        budget_per_person_eur: budget massimo per persona (solo voli)
        travelers:             numero di viaggiatori
        date_from:             data di partenza del primo volo
        date_to:               data entro cui il viaggio deve terminare
        direct_only:           filtra solo voli diretti

    Returns:
        SmartMultiOut con i top 5 itinerari ordinati per prezzo.

    Raises:
        ValueError:   se l'aeroporto di origine non esiste nel DB.
        RuntimeError: se tutti i provider LLM falliscono.
    """

    # ── Step 1: Getting info about the area, contains :origin_iata=origin_iata,radius_km,num_stops,reacheble airports
    explorable_area_details: AreaResult = await calculate_area(session, origin, trip_duration_days)

    # ── Step 2: genereting itineraries with AI 
    allowed_num_legs = explorable_area_details.num_stops + 1 #Adding 1 for the return
    budget_per_leg = budget_per_person_eur / allowed_num_legs
    season = _season_from_date(date_from)

    # Limiting airports for _MAX_AIRPORTS_FOR_LLM (exclude token overflow) the airports are already ordered by 'calculate_area()'
    airports_for_llm = explorable_area_details.airports[:_MAX_AIRPORTS_FOR_LLM]
    available_airports = [f"{a.iata_code} ({a.city})" for a in airports_for_llm]
    #Routing here Calling the orchestrator - generate_itineraries - build_prompt - parsing - returning 'list[SuggestedItinerary]objs'
    suggestions: list[SuggestedItinerary] = await generate_with_fallback(
        origin=origin,
        duration_days=trip_duration_days,
        budget_per_leg=budget_per_leg,
        season=season,
        num_stops=explorable_area_details.num_stops,
        available_airports=available_airports,
    )

    # ── Step 3: verifica prezzi reali (parallelo, con limite concorrenza) ───
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PRICING)
    tasks = [
        _price_itinerary(s, origin, date_from, trip_duration_days, direct_only, semaphore)
        for s in suggestions
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # ── Step 4: filtraggio per budget + ranking ──────────────────────────────
    priced: list[tuple[SuggestedItinerary, list[FlightOffer], float]] = []
    for res in results:
        # Scarta eccezioni (timeout, errori provider) e itinerari incompleti (None)
        if not isinstance(res, tuple):
            continue
        suggested, offers = res
        total_per_person = sum(o.price_eur for o in offers)
        if total_per_person > budget_per_person_eur:
            continue
        priced.append((suggested, offers, total_per_person))

    priced.sort(key=lambda x: x[2])  # prezzo totale per persona, crescente
    top5 = priced[:5]

    # ── Step 5: costruzione risposta ────────────────────────────────────────
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
        # Numero di tappe intermedie = aeroporti della rotta - origine - ritorno
        num_stops_in_route = len(suggested.route) - 2
        itineraries.append(
            ItineraryOut(
                rank=rank,
                route=suggested.route,
                total_price_per_person_eur=round(total_per_person, 2),
                total_price_all_travelers_eur=round(total_per_person * travelers, 2),
                legs=legs_out,
                ai_notes=suggested.reasoning,
                suggested_days_per_stop=_days_per_stop(
                    trip_duration_days, num_stops_in_route
                ),
            )
        )

    return SmartMultiOut(origin=origin, itineraries=itineraries)
