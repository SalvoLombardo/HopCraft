# HopCraft — API Reference

Base URL (local): `http://localhost:8000/api/v1`
Base URL (production): `https://dxxxxxxxxxxxx.cloudfront.net/api/v1`

Interactive docs: `/docs` (Swagger UI) · `/redoc` (ReDoc)

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/airports` | List all active airports |
| GET | `/airports/in-radius` | Airports within a radius |
| GET | `/search/reverse` | Reverse flight search |
| POST | `/search/smart-multi` | AI-powered multi-city search |

---

## GET `/health`

Returns service status.

**Response `200`**
```json
{
  "status": "ok"
}
```

---

## GET `/airports`

Returns all active airports in the database.

> **Scope:** Europe + North Africa (Morocco, Tunisia, Egypt). The airport dataset is seeded from [OpenFlights](https://openflights.org/data) and filtered by the `COUNTRY_CONTINENT` mapping in `seed_airports.py`. Adding a country to that mapping and re-running the seed is enough to extend coverage.

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 500 | Max airports to return |

**Response `200`**
```json
[
  {
    "iata_code": "CTA",
    "name": "Catania-Fontanarossa Airport",
    "city": "Catania",
    "country": "Italy",
    "continent": "EU",
    "latitude": 37.4668,
    "longitude": 15.0664,
    "is_active": true
  },
  ...
]
```

---

## GET `/airports/in-radius`

Returns airports within a given radius from a coordinate.

**Query parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `origin_lat` | float | Yes | Latitude of the origin airport |
| `origin_lon` | float | Yes | Longitude of the origin airport |
| `radius_km` | int | Yes | Radius in kilometres |

**Example**
```
GET /api/v1/airports/in-radius?origin_lat=37.47&origin_lon=15.06&radius_km=2000
```

**Response `200`**
```json
[
  {
    "iata_code": "PMO",
    "name": "Palermo Falcone Borsellino Airport",
    "city": "Palermo",
    "country": "Italy",
    "continent": "EU",
    "latitude": 38.1759,
    "longitude": 13.0910,
    "distance_km": 180
  },
  ...
]
```

---

## GET `/search/reverse`

Finds the cheapest one-way flights from European airports to a given destination.

Returns up to `max_results` results ordered by price. Results come from cache when available (TTL 6–12 h); cache misses trigger live API calls via the provider cascade (SerpAPI → Amadeus).

**Query parameters**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `destination` | string | Yes | — | IATA airport code (e.g. `CTA`) |
| `date_from` | date | Yes | — | Earliest departure date (`YYYY-MM-DD`) |
| `date_to` | date | Yes | — | Latest departure date (`YYYY-MM-DD`, max 7 days range) |
| `direct_only` | bool | No | `false` | Return only direct flights |
| `max_results` | int | No | `50` | Max results to return |
| `origin_lat` | float | No | — | Filter: latitude of origin point |
| `origin_lon` | float | No | — | Filter: longitude of origin point (required if `origin_lat` set) |
| `radius_km` | int | No | — | Filter: max radius from origin point in km |

> The geographic filter (`origin_lat` / `origin_lon` / `radius_km`) restricts the search to airports within the given radius. Useful for hub destinations (LHR, DXB, …) that would otherwise scan all ~1 174 airports.

**Example — all origins**
```
GET /api/v1/search/reverse?destination=CTA&date_from=2025-06-01&date_to=2025-06-07
```

**Example — origins within 600 km of Amsterdam**
```
GET /api/v1/search/reverse
  ?destination=CTA
  &date_from=2025-06-01
  &date_to=2025-06-07
  &origin_lat=52.31
  &origin_lon=4.76
  &radius_km=600
```

**Response `200`**
```json
{
  "destination": "CTA",
  "results": [
    {
      "origin": "BER",
      "origin_city": "Berlin",
      "price_eur": 29.99,
      "airline": "Ryanair",
      "departure": "2025-06-03T06:30:00",
      "direct": true,
      "duration_minutes": 165,
      "latitude": 52.3667,
      "longitude": 13.5033
    },
    {
      "origin": "WAW",
      "origin_city": "Warsaw",
      "price_eur": 34.50,
      "airline": "Wizz Air",
      "departure": "2025-06-02T14:15:00",
      "direct": true,
      "duration_minutes": 180,
      "latitude": 52.1657,
      "longitude": 20.9671
    }
  ],
  "cached": false,
  "fetched_at": "2025-04-15T10:22:00Z",
  "provider_status": {
    "active_provider": "serpapi",
    "serpapi_remaining": 187,
    "amadeus_remaining": 1800,
    "note": "SerpAPI attivo — Wizz Air, easyJet, Ryanair (parziale)"
  }
}
```

**Response fields**

| Field | Type | Description |
|---|---|---|
| `destination` | string | IATA code of the destination |
| `results` | array | List of cheapest flights per origin airport |
| `results[].origin` | string | IATA code of the departure airport |
| `results[].origin_city` | string | City name |
| `results[].price_eur` | float | Cheapest price found in the date range |
| `results[].airline` | string | Airline name |
| `results[].departure` | string | ISO datetime of the cheapest departure |
| `results[].direct` | bool | Whether the flight is direct |
| `results[].duration_minutes` | int | Flight duration |
| `results[].latitude` | float | Departure airport latitude (for map) |
| `results[].longitude` | float | Departure airport longitude (for map) |
| `cached` | bool | `true` if all results came from cache |
| `fetched_at` | string | Timestamp of the most recent data |
| `provider_status` | object | See [ProviderStatus](#providerstatus-schema) |

**Error responses**

| Status | Condition |
|---|---|
| `422` | Missing or invalid query parameters |
| `503` | All flight providers exhausted / unavailable |

---

## POST `/search/smart-multi`

AI-powered multi-city itinerary search. Generates candidate routes with an LLM, verifies real prices for every leg, filters by budget, and returns the top 5 cheapest itineraries.

This endpoint is slow by design (5–45 s depending on provider latency). The frontend shows a step-by-step progress indicator.

**Request body (`application/json`)**

```json
{
  "origin": "CTA",
  "trip_duration_days": 12,
  "budget_per_person_eur": 350,
  "travelers": 2,
  "date_from": "2025-06-01",
  "date_to": "2025-06-15",
  "direct_only": false
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `origin` | string | Yes | IATA code of origin/return airport |
| `trip_duration_days` | int | Yes | Total trip length in days (5–25) |
| `budget_per_person_eur` | float | Yes | Max total flight cost per person in EUR |
| `travelers` | int | Yes | Number of passengers |
| `date_from` | date | Yes | Trip start date (`YYYY-MM-DD`) |
| `date_to` | date | Yes | Trip end date (used to define the departure window) |
| `direct_only` | bool | No | Restrict to direct flights only (default `false`) |

**Response `200`**

```json
{
  "origin": "CTA",
  "itineraries": [
    {
      "rank": 1,
      "route": ["CTA", "ATH", "SOF", "BUD", "CTA"],
      "total_price_per_person_eur": 187.50,
      "total_price_all_travelers_eur": 375.00,
      "legs": [
        {
          "from_airport": "CTA",
          "to_airport": "ATH",
          "price_per_person_eur": 45.00,
          "airline": "Ryanair",
          "departure": "2025-06-01T08:00:00",
          "duration_minutes": 120,
          "direct": true
        },
        {
          "from_airport": "ATH",
          "to_airport": "SOF",
          "price_per_person_eur": 38.50,
          "airline": "Wizz Air",
          "departure": "2025-06-04T11:30:00",
          "duration_minutes": 90,
          "direct": true
        },
        {
          "from_airport": "SOF",
          "to_airport": "BUD",
          "price_per_person_eur": 52.00,
          "airline": "Ryanair",
          "departure": "2025-06-08T09:15:00",
          "duration_minutes": 100,
          "direct": true
        },
        {
          "from_airport": "BUD",
          "to_airport": "CTA",
          "price_per_person_eur": 52.00,
          "airline": "Wizz Air",
          "departure": "2025-06-12T16:00:00",
          "duration_minutes": 135,
          "direct": true
        }
      ],
      "ai_notes": "Balkan route with excellent low-cost connections. Athens in June is ideal. Sofia and Budapest are affordable and culturally rich stops.",
      "suggested_days_per_stop": [3, 3, 3]
    },
    {
      "rank": 2,
      "route": ["CTA", "BCN", "LIS", "MRS", "CTA"],
      "total_price_per_person_eur": 210.00,
      "total_price_all_travelers_eur": 420.00,
      "legs": [ ... ],
      "ai_notes": "Western Mediterranean loop. Barcelona and Lisbon in June are vibrant.",
      "suggested_days_per_stop": [3, 3, 3]
    }
  ],
  "provider_status": {
    "active_provider": "serpapi",
    "serpapi_remaining": 145,
    "amadeus_remaining": 1800,
    "note": "SerpAPI attivo — Wizz Air, easyJet, Ryanair (parziale)"
  }
}
```

**Response fields**

| Field | Type | Description |
|---|---|---|
| `origin` | string | IATA code of origin |
| `itineraries` | array | Up to 5 itineraries, sorted by total price |
| `itineraries[].rank` | int | 1 = cheapest |
| `itineraries[].route` | array of strings | Ordered IATA codes. First and last are always `origin`. |
| `itineraries[].total_price_per_person_eur` | float | Sum of all leg prices |
| `itineraries[].total_price_all_travelers_eur` | float | `total_per_person × travelers` |
| `itineraries[].legs` | array | One entry per flight segment |
| `itineraries[].legs[].from_airport` | string | IATA departure |
| `itineraries[].legs[].to_airport` | string | IATA arrival |
| `itineraries[].legs[].price_per_person_eur` | float | Cheapest fare found for this leg |
| `itineraries[].legs[].airline` | string | Airline name |
| `itineraries[].legs[].departure` | string | ISO datetime |
| `itineraries[].legs[].duration_minutes` | int | Flight duration |
| `itineraries[].legs[].direct` | bool | Direct flight |
| `itineraries[].ai_notes` | string | LLM reasoning / travel tips for the route |
| `itineraries[].suggested_days_per_stop` | array of ints | Suggested days at each intermediate stop |
| `provider_status` | object | See [ProviderStatus](#providerstatus-schema) |

**Error responses**

| Status | Body | Condition |
|---|---|---|
| `422` | Validation error detail | Missing or invalid request fields |
| `400` | `{"detail": "…"}` | No valid itineraries found (all over budget, no coverage, or AI returned no routes) |

Error detail messages (localized in Italian in the current version):

| Scenario | Message pattern |
|---|---|
| All itineraries have no flight coverage | `"Il provider non ha trovato voli per le rotte suggerite…"` |
| All itineraries over budget | `"Trovati N itinerari ma tutti oltre il budget di €X/persona…"` |
| Mixed (some no coverage, some over budget) | `"Nessun itinerario valido: N senza copertura, M oltre il budget…"` |
| AI returned no valid routes | `"L'AI non ha generato itinerari validi…"` |

---

## ProviderStatus Schema

Included in every `/search/reverse` and `/search/smart-multi` response.

```json
{
  "active_provider": "serpapi",
  "serpapi_remaining": 187,
  "amadeus_remaining": 1800,
  "note": "SerpAPI attivo — Wizz Air, easyJet, Ryanair (parziale)"
}
```

| Field | Type | Description |
|---|---|---|
| `active_provider` | string | Provider currently in use: `"serpapi"`, `"amadeus"`, or `"none"` |
| `serpapi_remaining` | int | SerpAPI monthly calls remaining (resets after 30-day rolling window) |
| `amadeus_remaining` | int | Amadeus monthly calls remaining |
| `note` | string | Human-readable status message shown in the frontend badge |

When `active_provider` is `"amadeus"`, the Smart Multi-City LLM prompt automatically adapts to suggest only hub airports covered by major carriers.

---

## Notes on Rate Limits

Monthly quotas are tracked in Redis with a 30-day rolling window. Soft limits (with safety margins) are:

| Provider | Free tier | Soft limit used |
|---|---|---|
| SerpAPI | 250 req/month | 230 |
| Amadeus | 2 000 req/month | 1 800 |

Each Reverse Search call may consume up to 50 provider API calls (one per uncached origin airport). Each Smart Multi-City call may consume up to 30 provider calls (one per itinerary leg).

When both providers are exhausted, the API returns an error. Reset the Redis counters to restore functionality (development only):

```bash
docker compose exec redis redis-cli DEL serpapi:monthly
docker compose exec redis redis-cli DEL amadeus:monthly
```
