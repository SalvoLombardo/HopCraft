# HopCraft — Architecture

## Table of Contents

1. [System Overview](#system-overview)
2. [Backend Structure](#backend-structure)
3. [Flight Provider Layer](#flight-provider-layer)
4. [LLM Provider Layer](#llm-provider-layer)
5. [Smart Multi-City Pipeline](#smart-multi-city-pipeline)
6. [Reverse Search Logic](#reverse-search-logic)
7. [Database Schema](#database-schema)
8. [Caching Strategy](#caching-strategy)
9. [Geo Utilities](#geo-utilities)
10. [CI/CD Pipeline](#cicd-pipeline)
11. [Infrastructure (AWS)](#infrastructure-aws)
12. [Monitoring & Observability](#monitoring--observability)

---

## System Overview

```
┌─────────────────────────┐
│   React + Leaflet       │
│   (Vite, port 3000)     │
│                         │
│  SearchForm             │
│  SmartSearchForm        │
│  Map (Leaflet)          │
│  ResultsList            │
│  ItineraryCard          │
│  ProviderBadge          │
└────────────┬────────────┘
             │ HTTP (proxied via Vite in dev / Nginx in prod)
             ▼
┌─────────────────────────┐
│   FastAPI Backend       │
│   (uvicorn, port 8000)  │
│                         │
│  /api/v1/search/reverse │──► search_engine.py
│  /api/v1/search/smart-  │──► itinerary_engine.py
│  /api/v1/airports       │──► airports.py
│  /api/v1/health         │
└──────┬──────────────────┘
       │
       ├──► Flight Provider Layer (SerpAPI → Amadeus)
       ├──► LLM Provider Layer    (Gemini → Groq → Mistral)
       ├──► PostgreSQL            (airports, flight_cache, search_history)
       └──► Redis                 (rate limiting, monthly quota counters)
```

---

## Backend Structure

```
backend/app/
├── main.py              # FastAPI app, CORS, lifespan (create_all tables)
├── config.py            # pydantic-settings: reads .env
├── api/v1/
│   ├── router.py        # Aggregates all routes
│   └── routes/
│       ├── search.py    # GET /search/reverse, POST /search/smart-multi
│       └── airports.py  # GET /airports, GET /airports/in-radius
├── services/
│   ├── providers/       # Flight Provider Layer (see below)
│   ├── llm/             # LLM Provider Layer (see below)
│   ├── search_engine.py     # Reverse search core logic
│   ├── area_calculator.py   # Reachable area from trip duration
│   └── itinerary_engine.py  # Smart Multi-City 5-step pipeline
├── models/
│   ├── airport.py       # SQLAlchemy model: Airport
│   ├── flight_cache.py  # SQLAlchemy model: FlightCache
│   └── schemas.py       # Pydantic schemas (all API input/output)
├── db/
│   ├── database.py      # Async SQLAlchemy engine + session factory
│   ├── redis.py         # Redis connection (aioredis)
│   ├── cache.py         # Flight cache read/write helpers
│   └── seed_airports.py # Populates airports from OpenFlights CSV
└── utils/
    ├── geo.py           # haversine_km, estimate_radius_km, estimate_stops
    └── rate_limiter.py  # check_rate_limit, get_remaining (Redis-backed)
```

---

## Flight Provider Layer

### Design: Strategy Pattern + Automatic Cascade

The application code (`search_engine.py`, `itinerary_engine.py`) never knows which flight provider it is using. The layer exposes a single abstract interface; providers are selected and rotated automatically at runtime based on remaining quota.

```
providers/
├── base.py         # FlightProvider (ABC), FlightOffer, Leg
├── google_flights.py  # GoogleFlightsProvider — SerpAPI (primary)
├── amadeus.py      # AmadeusProvider — Amadeus Self-Service (fallback)
├── tequila.py      # TequilaProvider — stub only (Kiwi.com is B2B only)
└── factory.py      # get_providers_in_order(), get_provider_quotas()
```

### Abstract Interface (`base.py`)

```python
@dataclass
class Leg:
    origin: str        # IATA code
    destination: str
    date: date

@dataclass
class FlightOffer:
    origin: str
    destination: str
    departure: str     # ISO datetime string
    price_eur: float
    airline: str
    direct: bool
    duration_minutes: int

class FlightProvider(ABC):
    @abstractmethod
    async def search_one_way(
        self, origin, destination, date_from, date_to,
        direct_only=False, max_results=50
    ) -> list[FlightOffer]: ...

    @abstractmethod
    async def search_multi_city(
        self, legs: list[Leg]
    ) -> list[FlightOffer]: ...
```

### Cascade Logic (`factory.py`)

```python
PROVIDER_LIMITS = {
    "serpapi":  230,   # free tier 250, safety margin 20
    "amadeus":  1800,  # free tier 2000, safety margin 200
}

async def get_providers_in_order() -> list[tuple[str, FlightProvider]]:
    """
    Returns providers with quota remaining, in cascade order.
    If settings.flight_provider is set to a known provider name,
    that provider is moved to the front of the list.
    """
```

Monthly quotas are tracked in Redis (`serpapi:monthly`, `amadeus:monthly`). Each time a provider is called successfully, `check_rate_limit` increments the counter. When a provider's counter reaches its limit, it is skipped.

#### Forcing a provider via `FLIGHT_PROVIDER`

The `FLIGHT_PROVIDER` environment variable lets you override the default cascade order without touching the quota counters:

| `FLIGHT_PROVIDER` | Effective order | Typical use |
|---|---|---|
| `cascade` | SerpAPI → Amadeus (auto by quota) | Production |
| `amadeus` | Amadeus → SerpAPI | Local dev — preserves the 250 SerpAPI req/month |
| `serpapi` | SerpAPI → Amadeus | Force SerpAPI explicitly |

If the forced provider has exhausted its quota, the system falls through to the next provider in the list automatically. The `FLIGHT_PROVIDER` only controls the *starting order*, not hard exclusion.

### Provider Characteristics

| Provider | Coverage | Quota | Notes |
|---|---|---|---|
| SerpAPI (GoogleFlightsProvider) | Wizz Air, easyJet, Ryanair (partial) | 250 req/month | Primary. Structured JSON from Google Flights. |
| Amadeus (AmadeusProvider) | Major carriers only (no EU low-cost) | 2 000 req/month | Fallback. OAuth2 token cached 30 min to save quota. When Amadeus is the only active provider, the LLM prompt receives a `provider_hint` that steers it toward hub airports covered by major carriers. |

### ProviderStatus in every response

Every API response includes a `provider_status` field:

```json
{
  "provider_status": {
    "active_provider": "serpapi",
    "serpapi_remaining": 187,
    "amadeus_remaining": 1800,
    "note": "SerpAPI attivo — Wizz Air, easyJet, Ryanair (parziale)"
  }
}
```

The frontend renders this as a coloured badge (🟢 SerpAPI / 🔴 Amadeus-only).

---

## LLM Provider Layer

### Design: Strategy Pattern + Automatic Fallback

Used in Step 2 of the Smart Multi-City pipeline to generate candidate itineraries. Same pattern as the flight layer.

```
llm/
├── base.py      # LLMProvider (ABC), SuggestedItinerary, system prompt, parse_itineraries()
├── gemini.py    # GeminiProvider — Gemini 2.5 Flash (primary)
├── groq.py      # GroqProvider  — Llama 3.3 70B (fast fallback)
├── mistral.py   # MistralProvider — Mistral (volume fallback)
└── factory.py   # generate_with_fallback()
```

### Fallback Factory (`factory.py`)

```python
_FALLBACK_ORDER = ["gemini", "groq", "mistral"]

async def generate_with_fallback(*args, **kwargs) -> list[SuggestedItinerary]:
    start = _FALLBACK_ORDER.index(settings.llm_provider)
    for name in _FALLBACK_ORDER[start:]:
        try:
            return await _PROVIDERS[name]().generate_itineraries(*args, **kwargs)
        except Exception:
            continue  # try next provider
    raise RuntimeError("All LLM providers failed")
```

`LLM_PROVIDER` in `.env` is used as a **start index** into `_FALLBACK_ORDER`. The factory slices the list from that position and attempts each remaining provider in order until one succeeds:

| `LLM_PROVIDER` | `_FALLBACK_ORDER[start:]` | Behaviour |
|---|---|---|
| `gemini` | `["gemini", "groq", "mistral"]` | Tries all three in order |
| `groq` | `["groq", "mistral"]` | Skips Gemini entirely |
| `mistral` | `["mistral"]` | Tries Mistral only, no further fallback |

This differs from the flight provider: here "skipped" providers are **never tried**, even if the chosen one fails. Setting `LLM_PROVIDER=groq` means Gemini is out of the picture for that run. If Groq fails, the factory falls through to Mistral automatically.

### Prompt Engineering

The prompt is defined once in `base.py` and used identically across all providers. A structured system prompt requests JSON-only output; `parse_itineraries()` handles both raw JSON and markdown-wrapped code blocks.

The `provider_hint` parameter is injected into the user prompt when Amadeus is the only active flight provider, guiding the AI to avoid secondary airports (BGY, STN, etc.) that Amadeus cannot price.

### LLM Provider Limits (free tier, as of early 2026)

| Provider | Model | Free Limit | Card required |
|---|---|---|---|
| Gemini | 2.5 Flash | 250 req/day | No |
| Groq | Llama 3.3 70B | ~14 400 req/day (1M tok/min) | No |
| Mistral | mistral-small-latest | ~1B tokens/month | No |

---

## Smart Multi-City Pipeline

Implemented in `itinerary_engine.py` → `run_smart_multi()`.

```
Step 1: calculate_area(session, origin, trip_duration_days)
        ├─ Queries DB for all active airports
        ├─ Computes Haversine distance from origin to each
        ├─ Returns AreaResult: radius_km, num_stops, sorted airport list
        └─ Example: 12 days → radius ~2 000 km, num_stops = 3

Step 2: generate_with_fallback(origin, duration, budget_per_leg, season,
                               num_stops, available_airports, provider_hint)
        ├─ Sends request to Gemini (→ Groq → Mistral on error)
        ├─ Receives 8–10 JSON itineraries
        └─ Each: { route: ["CTA","ATH","SOF","BUD","CTA"], reasoning, difficulty, best_season }

Step 3: _price_itinerary() × N  (asyncio.gather, semaphore=3 concurrent)
        ├─ For each candidate itinerary:
        │   ├─ Validates route structure (starts and ends at origin, no duplicate stops)
        │   ├─ Distributes departure dates evenly across the trip
        │   └─ Calls provider cascade to price every leg
        └─ Returns (SuggestedItinerary, list[FlightOffer]) or None

Step 4: Budget filter + rank
        ├─ Drop itineraries where sum(leg prices) > budget_per_person_eur
        ├─ Sort by total_per_person ascending
        └─ Keep top 5

Step 5: Build SmartMultiOut
        └─ ItineraryOut × 5: rank, route, total prices, legs, ai_notes,
           suggested_days_per_stop, provider_status
```

### Radius / Stops Estimation

```python
def estimate_radius_km(days: int) -> int:
    if days <= 7:   return days * 200           # up to 1 400 km
    if days <= 15:  return 1400 + (days-7)*150  # up to 2 600 km
    return min(2600 + (days-15)*100, 5000)      # capped at 5 000 km

def estimate_stops(days: int) -> int:
    if days <= 7:   return min(2, days // 3)
    if days <= 15:  return min(3, days // 4)
    return min(4, days // 5)
```

---

## Reverse Search Logic

Implemented in `search_engine.py` → `reverse_search()`.

```
1. Load all active airports from DB (exclude destination)
2. Optional: filter by radius from origin_lat/origin_lon (Haversine)
3. Build date list: date_from → date_to (max 7 days)
4. Batch query flight_cache for valid entries (fetched_at within TTL)
   → cache_best: {origin: (cheapest_offer, fetched_at)}
5. Identify missing_origins (no cache hit)
   → take first _MAX_NEW_CALLS_PER_SEARCH = 50
6. For each missing origin: asyncio.gather(_fetch)
   _fetch: tries SerpAPI first; if quota exhausted, tries Amadeus
   → saves new results to cache
7. Merge cache results + fresh results
8. Sort by price_eur, cap at max_results
9. Attach provider_status
```

---

## Database Schema

### `airports`

```sql
CREATE TABLE airports (
    iata_code   VARCHAR(3)   PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    city        VARCHAR(255) NOT NULL,
    country     VARCHAR(100) NOT NULL,
    continent   VARCHAR(2),            -- ISO: EU, AF, AS, NA, SA, OC
    latitude    FLOAT        NOT NULL,
    longitude   FLOAT        NOT NULL,
    is_active   BOOLEAN      DEFAULT TRUE
);
CREATE INDEX idx_airports_coords ON airports (latitude, longitude);
```

Seeded from OpenFlights (`airports.dat`), filtered to Europe + North Africa (~1 174 airports). The `continent` field was added post-seed; use `seed_airports.py` (idempotent via `on_conflict_do_update`) to populate it on existing data.

### `flight_cache`

```sql
CREATE TABLE flight_cache (
    id                    SERIAL PRIMARY KEY,
    origin                VARCHAR(3)   NOT NULL,
    destination           VARCHAR(3)   NOT NULL,
    departure_date        DATE         NOT NULL,
    price_eur             DECIMAL(10,2),
    airline               VARCHAR(100),
    direct_flight         BOOLEAN,
    flight_duration_minutes INTEGER,
    fetched_at            TIMESTAMP    DEFAULT NOW(),
    raw_response          JSONB,       -- full list of FlightOffer dicts
    UNIQUE(origin, destination, departure_date)
);
CREATE INDEX idx_cache_lookup ON flight_cache (destination, departure_date, fetched_at);
CREATE INDEX idx_cache_expiry ON flight_cache (fetched_at);
```

TTL is controlled by `CACHE_TTL_HOURS` (default 6). `cache.py` stores the full raw response as JSONB so the same cache entry can be re-parsed and re-filtered.

### `search_history`

```sql
CREATE TABLE search_history (
    id          SERIAL PRIMARY KEY,
    search_type VARCHAR(20) NOT NULL,  -- 'reverse' or 'smart_multi'
    params      JSONB       NOT NULL,
    results     JSONB,
    created_at  TIMESTAMP   DEFAULT NOW()
);
```

### Migrations

No Alembic in use. Tables are created via `create_all()` in the FastAPI lifespan handler. New columns require a manual `ALTER TABLE` (see `SETUP.md`).

---

## Caching Strategy

Two-level cache:

| Layer | Technology | What it caches | TTL |
|---|---|---|---|
| PostgreSQL (`flight_cache`) | SQL JSONB | Full `FlightOffer` lists per origin/destination/date | 6–12 h |
| Redis | In-memory key/value | Monthly API call counters per provider | Rolling 30-day window |

The PostgreSQL cache is read in a single batch query at the start of each search (one `SELECT … WHERE destination = ? AND date IN (…) AND fetched_at >= cutoff`). Cache hits avoid all external API calls. Cache misses trigger provider cascade calls and immediately write results back.

Redis is used exclusively for rate limiting. The key `serpapi:monthly` holds the count of SerpAPI calls in the current 30-day window; `amadeus:monthly` does the same for Amadeus.

---

## Geo Utilities

`utils/geo.py` implements:

```python
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two points on Earth."""

def estimate_radius_km(trip_duration_days: int) -> int:
    """Reachable radius from trip length (used in area_calculator)."""

def estimate_stops(trip_duration_days: int) -> int:
    """Suggested number of intermediate stops."""
```

`area_calculator.py` queries the DB, applies `haversine_km` to filter airports in range, and returns an `AreaResult` with the sorted airport list ready to be sent to the LLM.

---

## CI/CD Pipeline

`.github/workflows/ci.yml` — triggered on every push and PR to `main`.

```
Job: lint  (ruff)
  └─ ruff check --select E,F --line-length 100 backend/app backend/tests

Job: test  (pytest)  — needs: lint
  └─ pytest tests/ -v
     All 76 tests pass with mocked external services
     (DB, Redis, SerpAPI, Amadeus, Gemini, Groq, Mistral)

Job: deploy  — needs: test, only on push to main
  ├─ Build backend Docker image → push to GHCR
  ├─ Build React frontend → upload to S3 → invalidate CloudFront
  └─ SSH into EC2 → docker pull → docker compose up -d --no-deps backend nginx
```

The deploy job requires GitHub Secrets:
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `CLOUDFRONT_DISTRIBUTION_ID`, `EC2_HOST`, `EC2_SSH_KEY`.

---

## Infrastructure (AWS)

Managed with Terraform in `infra/`. Region: `eu-south-1` (Milan).

```
infra/
├── main.tf            # Provider config, optional remote state (S3 backend)
├── variables.tf       # aws_region, ec2_ami, instance_type, key_pair_name, …
├── outputs.tf         # ec2_public_ip, s3_bucket_name, cloudfront_distribution_id
├── ec2.tf             # t3.micro, Amazon Linux 2023, user_data (Docker install)
├── security_groups.tf # SG: ports 22, 80, 443 inbound; all outbound
├── s3.tf              # Private bucket for React SPA static files
├── cloudfront.tf      # Distribution: S3 origin + EC2 /api/* origin
└── terraform.tfvars.example
```

### Architecture

```
Internet users
      │
      ▼
CloudFront (*.cloudfront.net — HTTPS free, no custom domain needed)
  ├─ GET /*       → S3 bucket (React SPA, versioned deploys)
  └─ GET /api/*   → EC2 :80 (Nginx)
                          └─ FastAPI :8000

EC2 t3.micro (docker-compose.prod.yml)
  ├─ nginx       :80  → backend:8000
  ├─ backend     :8000
  ├─ postgres    (persistent EBS volume)
  └─ redis       (persistent volume)
```

HTTPS is provided by CloudFront at no cost. The EC2 instance only needs port 80 open (CloudFront → EC2 traffic is plain HTTP over AWS internal network).

---

## Monitoring & Observability

### CloudWatch Logs

Backend logs are shipped to **AWS CloudWatch Logs** via the Docker `awslogs` driver (built into Docker Engine — no agent required).

```
Log group:  hopcraft/backend
Log stream: backend
Region:     eu-south-1
```

The driver uses the EC2 instance IAM role (`hopcraft-ec2-role`) for credentials via the EC2 metadata service. The role has `CloudWatchLogsFullAccess` attached.

> **Note:** IAM resources are managed manually via the AWS console (root account). The `hopcraft-deploy` Terraform user does not have IAM permissions, so `infra/iam.tf` is documentation-only.

> **Side effect:** with `awslogs` active, `docker logs backend` does not work on the EC2 instance. Use the CloudWatch Logs console or Logs Insights to read logs.

### Structured Timing Logs

`itinerary_engine.py` emits one structured JSON log line per Smart Multi-City request, immediately before returning the response:

```json
{
  "event": "smart_multi_timing",
  "origin": "CTA",
  "trip_duration_days": 12,
  "budget_eur": 300.0,
  "travelers": 1,
  "provider": "amadeus",
  "step_area_ms": 87,
  "step_llm_ms": 4231,
  "step_pricing_ms": 22847,
  "routes_suggested": 10,
  "routes_no_data": 2,
  "routes_over_budget": 3,
  "routes_returned": 5,
  "result": "success",
  "total_ms": 27165
}
```

| Field | Description |
|---|---|
| `step_area_ms` | DB query + Haversine filtering (Step 1) |
| `step_llm_ms` | LLM call (Step 2) — main variable cost |
| `step_pricing_ms` | Provider pricing, all routes, parallel with semaphore=3 (Step 3) |
| `routes_suggested` | Number of candidate routes returned by the AI |
| `routes_no_data` | Routes dropped because the provider returned no flights |
| `routes_over_budget` | Routes dropped because total price exceeded budget |
| `routes_returned` | Final itineraries returned to the user (max 5) |

The log is written even when `routes_returned = 0` (before the `ValueError` is raised), so failed requests are also observable.

### CloudWatch Logs Insights Queries

**Recent requests — timing breakdown:**
```
fields @timestamp, step_llm_ms, step_pricing_ms, total_ms, routes_suggested, routes_returned
| filter event = "smart_multi_timing"
| sort @timestamp desc
| limit 20
```

**Average time per step:**
```
filter event = "smart_multi_timing"
| stats avg(step_llm_ms) as avg_llm,
        avg(step_pricing_ms) as avg_pricing,
        avg(total_ms) as avg_total,
        count() as requests
```

**Requests with low yield (many routes suggested, few returned):**
```
filter event = "smart_multi_timing"
| filter routes_returned < 2 and routes_suggested >= 8
| fields @timestamp, origin, provider, routes_no_data, routes_over_budget, total_ms
```

### Migration Note (June 2026)

AWS free tier expires June 2026. Planned migration to **Oracle Cloud Always Free** (Ampere A1, 4 OCPU / 24 GB RAM, permanently free):

- Terraform: swap `hashicorp/aws` provider → `oracle/oci`, same resource structure.
- GitHub Actions: update `EC2_HOST` secret only.
- S3 + CloudFront: evaluate Cloudflare Pages (free) as replacement.
