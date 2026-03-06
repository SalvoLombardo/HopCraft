"""
ApifyProvider — tertiary provider via Apify Google Flights Search Scraper.

Output format identical to SerpAPI Google Flights engine — includes low-cost
carriers (Ryanair, Wizz Air, easyJet). No proxy required.

Free tier: $5 platform credits/month (~200 searches depending on actor runtime).
Registration: https://apify.com

HOW TO FIND THE ACTOR ID:
  Open the actor page in your browser. The URL is:
    https://apify.com/USERNAME/ACTOR-NAME
  Set _ACTOR_ID below as "USERNAME~ACTOR-NAME" (replace / with ~).

Confirmed input parameters (from README):
  departure_id  → IATA string, comma-separated for multiple (e.g. "CTA" or "CDG,ORY")
  arrival_id    → IATA string, comma-separated for multiple (e.g. "ATH")
  outbound_date → "YYYY-MM-DD"  (omit return_date → one-way)
  adults        → int
  currency      → "EUR"
  hl            → language code ("en")
  gl            → country code ("it" for Italy)
  max_stops     → 0 = direct only, null = no limit
  max_pages     → int, use 1 to limit cost
  multi_city_json → JSON string for multi-city (see search_multi_city below)

Confirmed output structure (per dataset item = one page):
  {
    "best_flights":  [ { "flights": [...], "total_duration": N, "price": N }, ... ],
    "other_flights": [ ... ]
  }
  Each flight entry in flights[]:
  {
    "departure_airport": { "id": "DUB", "time": "2026-05-05 20:25" },
    "arrival_airport":   { "id": "LHR", "time": "2026-05-05 21:40" },
    "duration": 75,
    "airline": "British Airways"
  }
"""
import asyncio
import json
import logging
from datetime import date, timedelta

import httpx

from app.config import settings
from app.services.providers.base import FlightOffer, FlightProvider, Leg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CONFIGURE THIS: actor URL → https://apify.com/USERNAME/ACTOR-NAME
#                 set as   → "USERNAME~ACTOR-NAME"
# ---------------------------------------------------------------------------
_ACTOR_ID = "1dYHRKkEBHBPd0JM7"
# ---------------------------------------------------------------------------

_RUN_SYNC_URL = f"https://api.apify.com/v2/acts/{_ACTOR_ID}/run-sync-get-dataset-items"

# Actor timeout in seconds (Apify max is 300s)
_ACTOR_TIMEOUT_SECONDS = 120

# Limit concurrent runs to avoid exhausting the free-tier credit budget
_MAX_CONCURRENT = 3
_APIFY_SEMAPHORE: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _APIFY_SEMAPHORE
    if _APIFY_SEMAPHORE is None:
        _APIFY_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENT)
    return _APIFY_SEMAPHORE


def _parse_flight_entry(item: dict, origin: str, destination: str) -> FlightOffer | None:
    """
    Normalises one entry from best_flights / other_flights into a FlightOffer.

    Handles the confirmed nested-flights format (same as SerpAPI):
    {
      "flights": [
        {
          "departure_airport": { "id": "DUB", "time": "2026-05-05 20:25" },
          "arrival_airport":   { "id": "LHR", "time": "2026-05-05 21:40" },
          "duration": 75,
          "airline": "British Airways"
        }
      ],
      "total_duration": 75,
      "price": 95
    }
    Direct = flights has 1 element; connecting = 2+ elements.
    """
    try:
        price = item.get("price")
        if price is None:
            return None

        flights = item.get("flights", [])
        if not flights:
            return None

        first_leg = flights[0]
        last_leg = flights[-1]

        # "2026-05-05 20:25" → "2026-05-05T20:25"
        raw_time = first_leg.get("departure_airport", {}).get("time", "")
        departure_iso = raw_time.replace(" ", "T") if raw_time else ""

        return FlightOffer(
            origin=first_leg.get("departure_airport", {}).get("id", origin),
            destination=last_leg.get("arrival_airport", {}).get("id", destination),
            departure=departure_iso,
            price_eur=float(price),
            airline=first_leg.get("airline", "Unknown"),
            direct=(len(flights) == 1),
            duration_minutes=int(item.get("total_duration", 0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("Apify _parse_flight_entry skipped: %s", exc)
        return None


def _offers_from_pages(pages: list[dict], origin: str, destination: str) -> list[FlightOffer]:
    """Extracts all FlightOffers from the actor's dataset (list of page objects)."""
    offers: list[FlightOffer] = []
    for page in pages:
        for section in ("best_flights", "other_flights"):
            for item in page.get(section, []):
                offer = _parse_flight_entry(item, origin, destination)
                if offer:
                    offers.append(offer)
    return offers


async def _run_actor(actor_input: dict) -> list[dict]:
    """
    Calls the Apify run-sync-get-dataset-items endpoint and returns the raw list.
    Returns [] on any error (timeout, HTTP error, unexpected format).
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.apify_api_token}",
    }
    params = {"format": "json", "timeout": _ACTOR_TIMEOUT_SECONDS}

    async with _get_semaphore():
        try:
            async with httpx.AsyncClient(timeout=_ACTOR_TIMEOUT_SECONDS + 10) as client:
                resp = await client.post(
                    _RUN_SYNC_URL,
                    json=actor_input,
                    headers=headers,
                    params=params,
                )
        except httpx.TimeoutException:
            logger.warning("Apify actor timeout after %ds (input: %s)", _ACTOR_TIMEOUT_SECONDS, actor_input)
            return []

    if resp.status_code == 400:
        logger.warning("Apify HTTP 400 — check actor input: %s", resp.text[:300])
        return []
    if resp.status_code == 402:
        logger.warning("Apify HTTP 402 — credit limit reached")
        return []

    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Apify HTTP %d — %s", exc.response.status_code, exc.response.text[:300])
        return []

    data = resp.json()
    if not isinstance(data, list):
        logger.warning("Apify unexpected response format: %s", str(data)[:200])
        return []

    return data


class ApifyProvider(FlightProvider):

    async def search_one_way(
        self,
        origin: str,
        destination: str,
        date_from: date,
        date_to: date,
        direct_only: bool = False,
        max_results: int = 50,
    ) -> list[FlightOffer]:
        # Max 3 dates to preserve free-tier credits
        dates: list[date] = []
        current = date_from
        while current <= date_to and len(dates) < 3:
            dates.append(current)
            current += timedelta(days=1)

        async def fetch_date(d: date) -> list[FlightOffer]:
            actor_input: dict = {
                "departure_id": origin,
                "arrival_id": destination,
                "outbound_date": d.isoformat(),
                "adults": 1,
                "currency": "EUR",
                "hl": "en",
                "gl": "it",
                "max_pages": 1,
            }
            if direct_only:
                actor_input["max_stops"] = 0

            pages = await _run_actor(actor_input)
            return _offers_from_pages(pages, origin, destination)

        results = await asyncio.gather(*[fetch_date(d) for d in dates], return_exceptions=True)

        offers: list[FlightOffer] = []
        for r in results:
            if isinstance(r, list):
                offers.extend(r)

        offers.sort(key=lambda o: o.price_eur)
        return offers[:max_results]

    async def search_multi_city(
        self,
        legs: list[Leg],
    ) -> list[FlightOffer]:
        """
        Searches all legs in a SINGLE actor call using multi_city_json.
        Much more efficient than N separate calls.

        multi_city_json format:
        [{"departure_id":"CTA","arrival_id":"ATH","date":"2026-04-01"}, ...]
        """
        multi_city_data = [
            {
                "departure_id": leg.origin,
                "arrival_id": leg.destination,
                "date": leg.date.isoformat(),
            }
            for leg in legs
        ]

        actor_input: dict = {
            "multi_city_json": json.dumps(multi_city_data),
            "adults": 1,
            "currency": "EUR",
            "hl": "en",
            "gl": "it",
            "max_pages": 1,
        }

        pages = await _run_actor(actor_input)

        # With multi-city the actor returns results grouped by leg.
        # Extract cheapest offer per leg by matching origin/destination.
        all_offers = _offers_from_pages(pages, "", "")

        result: list[FlightOffer] = []
        for leg in legs:
            leg_offers = [
                o for o in all_offers
                if o.origin == leg.origin and o.destination == leg.destination
            ]
            if leg_offers:
                result.append(min(leg_offers, key=lambda o: o.price_eur))

        return result
