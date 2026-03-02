# HopCraft

**Intelligent flight search for explorers who don't know where to go (yet).**

HopCraft solves two problems no mainstream flight aggregator addresses well:

- **Reverse Search** — pick a destination, see every cheap flight heading there from all of Europe on a map.
- **Smart Multi-City** — give it a budget, a trip length, and your home airport; AI suggests complete multi-city itineraries with real verified prices.

> Portfolio project · Python / FastAPI · React / Leaflet · PostgreSQL · Redis · Docker · AWS · Terraform

---

## Features

### Reverse Search
Enter a destination (e.g. Catania) and a date range. HopCraft queries all active European airports and shows you the cheapest one-way fares on an interactive map — markers coloured by price tier, sortable list below.

Optional geographic filter: restrict origins to airports within a given radius (useful for hub destinations like London or Dubai that would otherwise scan 1 000+ airports).

### Smart Multi-City (AI-powered)
Enter your home airport, trip duration (5–25 days), and budget per person. The pipeline:

1. **Area calculation** — estimates the reachable radius from trip length (5 days → ~1 000 km, 25 days → ~3 500 km).
2. **AI itinerary generation** — sends the shortlist of reachable airports to Gemini 2.5 Flash and gets back 8–10 geographically sensible multi-city routes in JSON.
3. **Real price verification** — fetches actual flight prices for every leg of every candidate itinerary (async, parallel).
4. **Budget filtering + ranking** — drops itineraries over budget; ranks the rest by total cost.
5. **Top 5 results** — displayed on map with polylines connecting the stops, per-leg prices, and AI travel notes.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | FastAPI (Python 3.12) | Async, ideal for parallel API calls |
| Database | PostgreSQL 16 | Airports, flight cache (TTL 6–12 h), search history |
| Cache / Rate limiting | Redis 7 | Fast cache + monthly quota tracking per provider |
| Flight data (primary) | SerpAPI — Google Flights | 250 req/month free, covers Wizz Air, easyJet |
| Flight data (fallback) | Amadeus Self-Service | 2 000 req/month free, major carriers only |
| LLM (primary) | Google Gemini 2.5 Flash | 250 req/day free, no credit card |
| LLM (fallback 1) | Groq — Llama 3.3 70B | Free, >300 tok/sec |
| LLM (fallback 2) | Mistral | 1B tokens/month free |
| Frontend | React 18 + Vite + react-leaflet | Interactive map with routes and price markers |
| Infrastructure | AWS EC2 t3.micro + S3 + CloudFront | Terraform, HTTPS via CloudFront (no domain needed) |
| CI/CD | GitHub Actions | Lint (ruff) → test (pytest) → deploy on push to main |

---

## Quick Start (local)

**Prerequisites:** Docker + Docker Compose, plus API keys (see below).

```bash
# 1. Clone
git clone https://github.com/your-username/hopcraft.git
cd hopcraft

# 2. Configure environment
cp .env.example .env
# Edit .env and fill in your API keys (see docs/SETUP.md)

# 3. Start everything
docker compose up --build

# 4. Seed the airport database (~1 174 European airports)
docker compose exec backend python -m app.db.seed_airports

# 5. Open the app
open http://localhost:3000

# API docs (Swagger UI)
open http://localhost:8000/docs
```

That's it. The frontend proxies `/api/` to the backend automatically.

---

## API Keys Required

All free tiers, no credit card needed:

| Service | Where to sign up | Used for |
|---|---|---|
| SerpAPI | [serpapi.com](https://serpapi.com) | Google Flights data (primary, 250 req/month) |
| Amadeus | [developers.amadeus.com](https://developers.amadeus.com) | Flight data fallback (2 000 req/month) |
| Google AI Studio | [aistudio.google.com](https://aistudio.google.com) | Gemini LLM (itinerary generation) |
| Groq | [console.groq.com](https://console.groq.com) | LLM fallback |
| Mistral | [console.mistral.ai](https://console.mistral.ai) | LLM fallback |

> **During development** set `FLIGHT_PROVIDER=amadeus` in your `.env` to use Amadeus first and preserve the 250 SerpAPI monthly credits for production. See [docs/SETUP.md](docs/SETUP.md) for the full variable reference.

---

## Project Structure

```
hopcraft/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/       # search.py, airports.py
│   │   ├── services/
│   │   │   ├── providers/       # Flight Provider Layer (Strategy Pattern)
│   │   │   │   ├── base.py      # FlightProvider ABC, FlightOffer, Leg
│   │   │   │   ├── google_flights.py  # SerpAPI (primary)
│   │   │   │   ├── amadeus.py   # Amadeus (fallback)
│   │   │   │   └── factory.py   # Cascade: get_providers_in_order()
│   │   │   ├── llm/             # LLM Provider Layer (Strategy Pattern)
│   │   │   │   ├── gemini.py    # Gemini 2.5 Flash (primary)
│   │   │   │   ├── groq.py      # Llama 3.3 70B (fallback)
│   │   │   │   ├── mistral.py   # Mistral (fallback)
│   │   │   │   └── factory.py   # generate_with_fallback()
│   │   │   ├── search_engine.py     # Reverse search logic
│   │   │   ├── area_calculator.py   # Radius from trip duration
│   │   │   └── itinerary_engine.py  # Smart Multi-City pipeline
│   │   ├── models/              # SQLAlchemy models + Pydantic schemas
│   │   ├── db/                  # DB connection, Redis, cache layer, seed
│   │   └── utils/               # Haversine geo, rate limiter
│   └── tests/                   # 76 unit tests (all mocked, no real APIs)
├── frontend/
│   └── src/
│       ├── components/          # SearchForm, SmartSearchForm, Map, ResultsList, ItineraryCard
│       └── services/api.js      # HTTP client
├── infra/                       # Terraform (EC2, S3, CloudFront, Security Groups)
├── docker-compose.yml           # Local dev
├── docker-compose.prod.yml      # Production
└── nginx.prod.conf              # Reverse proxy (port 80 → FastAPI:8000)
```

---

## Architecture Overview

```
CloudFront (*.cloudfront.net — HTTPS, no domain needed)
  ├── /*      → S3 (React SPA)
  └── /api/*  → EC2 t3.micro :80 (Nginx → FastAPI :8000)

EC2 (eu-south-1 — Milan)
  └── docker-compose.prod.yml
      ├── nginx   :80
      ├── backend :8000
      ├── postgres (persistent volume)
      └── redis

Flight data cascade:  SerpAPI → Amadeus
LLM cascade:          Gemini  → Groq → Mistral
```

For the full architectural breakdown see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, Strategy Pattern, cascade logic, database schema, caching, CI/CD |
| [docs/SETUP.md](docs/SETUP.md) | Local dev setup, env variables reference, production deploy, first-deploy checklist |
| [docs/API.md](docs/API.md) | Complete API reference with request/response examples |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
# 76/76 PASSED — all external APIs are mocked
```

---

## Roadmap

- [ ] Additional flight providers (Kiwi Tequila if B2B access becomes available, RapidAPI aggregators)
- [ ] OpenAI GPT-4o-mini as LLM option for production traffic
- [ ] Itinerary caching (same origin + season + duration returns cached AI suggestions)
- [ ] Expand airport database beyond Europe (North Africa already seeded)
- [ ] Radius filter UI in Reverse Search form (browser geolocation)

---

## License

MIT
