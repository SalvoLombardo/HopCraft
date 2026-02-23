FlySpy — Project Specification
Overview
FlySpy è un'applicazione web per la ricerca intelligente di voli che risolve due problemi non coperti dai motori di ricerca esistenti:

Reverse Search: cercare voli da ovunque verso una destinazione specifica (solo andata)
Smart Multi-City: dato un budget, una durata e un'origine, il sistema propone autonomamente itinerari multi-città ottimizzati

Target: progetto portfolio production-ready.

Funzionalità
Feature 1 — Reverse Search (solo andata)
L'utente inserisce una destinazione (es. Catania) e un range di date. Il sistema mostra su mappa i voli disponibili da aeroporti europei (e potenzialmente mondiali) verso quella destinazione, ordinati per prezzo.
Input utente:

Destinazione (aeroporto/città)
Range date (partenza)
Filtro opzionale: solo voli diretti sì/no

Output:

Mappa interattiva con marker sugli aeroporti di partenza, colorati per fascia di prezzo
Lista ordinabile per prezzo, durata, numero scali

Note tecniche:

Database di ~300 aeroporti europei principali (espandibile)
Cache risultati con TTL 6-12 ore per rispettare rate limit API
Chiamate asincrone parallele per performance


Feature 2 — Smart Multi-City (killer feature)
L'utente inserisce origine, durata viaggio, budget per persona e numero viaggiatori. Il sistema propone autonomamente itinerari multi-città completi e ottimizzati.
Input utente:

Aeroporto/città di origine (e ritorno)
Durata viaggio (5-25 giorni)
Budget per persona (solo voli)
Numero viaggiatori
Filtro opzionale: solo voli diretti sì/no

Output:

Top 5 itinerari proposti, visualizzati su mappa con rotte
Per ogni itinerario: prezzo totale, prezzo per tratta, tempi, note AI sulle destinazioni

Vincoli:

Massimo 4 aeroporti intermedi (quindi max 5 tratte: origine → 4 tappe → origine)
Il numero di tappe si adatta alla durata: 5-7 giorni → 1-2 tappe, 8-15 giorni → 2-3 tappe, 16-25 giorni → 3-4 tappe
Il budget viene diviso per il numero di tratte per filtrare le opzioni

Flusso interno (pipeline):
Step 1 — Calcolo area esplorabile
  Dalla durata del viaggio si stima un raggio massimo dal punto di partenza.
  Esempi indicativi:
    5 giorni  → raggio ~1000 km → area ~3M km²
    12 giorni → raggio ~2000 km → area ~12M km²
    25 giorni → raggio ~3500 km → area ~38M km²
  Si filtrano solo gli aeroporti dentro quel raggio.
  Questo riduce drasticamente lo spazio di ricerca.

Step 2 — Generazione itinerari (Claude API)
  Si invia a Claude Sonnet una richiesta strutturata con:
    - Origine
    - Durata e stagione
    - Budget per tratta (budget totale / numero tratte stimato)
    - Lista aeroporti disponibili nel raggio
    - Numero tappe desiderato
  Claude restituisce 8-10 itinerari plausibili in formato JSON.
  Esempio output:
    [
      {"route": ["CTA", "ATH", "SOF", "BUD", "CTA"], "reasoning": "..."},
      {"route": ["CTA", "BCN", "LIS", "MRS", "CTA"], "reasoning": "..."},
      ...
    ]
  Questo riduce le combinazioni da migliaia a ~30-40 rotte verificabili.

Step 3 — Verifica prezzi reali
  Per ogni itinerario suggerito, si interroga l'API voli per ogni tratta.
  Con 10 itinerari da ~4 tratte = ~40 chiamate API (gestibile).
  Si usano chiamate asincrone parallele.

Step 4 — Filtraggio e ranking
  Si eliminano itinerari che sforano il budget.
  Si ordina per:
    - Prezzo totale (peso principale)
    - Rapporto qualità/prezzo
    - Varietà destinazioni
    - Tempo di viaggio complessivo

Step 5 — Presentazione
  Top 5 itinerari su mappa con rotte tracciate.
  Per ogni itinerario: dettaglio tratte, prezzi, orari.
  Note AI opzionali su ogni destinazione (stagione, consigli).

Architettura
┌─────────────────┐     ┌────────────────────┐     ┌──────────────────┐
│   Frontend      │────▶│   FastAPI Backend   │────▶│  Tequila API     │
│   React +       │     │                    │     │  (Kiwi.com)      │
│   Leaflet       │◀────│  - Search engine    │◀────│  Dati voli       │
│   (Mappa)       │     │  - Cache layer      │     └──────────────────┘
└─────────────────┘     │  - Area calculator  │
                        │  - Itinerary engine │     ┌──────────────────┐
                        │                    │────▶│  Claude API      │
                        │                    │     │  (Sonnet)        │
                        └────────┬───────────┘     │  Suggerimento    │
                                 │                 │  itinerari       │
                        ┌────────▼───────────┐     └──────────────────┘
                        │   PostgreSQL       │
                        │  - Aeroporti       │
                        │  - Cache voli      │
                        │  - Storico ricerche│
                        └────────────────────┘
                        ┌────────────────────┐
                        │   Redis            │
                        │  - Cache veloce    │
                        │  - Rate limiting   │
                        └────────────────────┘

Stack Tecnico
ComponenteTecnologiaNoteBackendFastAPI (Python)Asincrono, ideale per chiamate parallele APIDatabasePostgreSQLAeroporti, cache prezzi (TTL 6-12h), storicoCacheRedisCache risultati recenti, rate limitingAPI VoliTequila API (Kiwi.com)Gratuita, ben documentata, ricerche flessibiliAPI AIClaude API (Sonnet)Generazione itinerari intelligentiFrontendReact + LeafletMappa interattiva con rotte e prezziDeployDocker + AWS (ECS o EC2)ContainerizzatoCI/CDGitHub ActionsTest + deploy automatico

Modello Dati (PostgreSQL)
Tabella airports
sqlCREATE TABLE airports (
    iata_code VARCHAR(3) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 6) NOT NULL,
    longitude DECIMAL(10, 6) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
-- Indice spaziale per query per raggio
CREATE INDEX idx_airports_coords ON airports (latitude, longitude);
Tabella flight_cache
sqlCREATE TABLE flight_cache (
    id SERIAL PRIMARY KEY,
    origin VARCHAR(3) NOT NULL,
    destination VARCHAR(3) NOT NULL,
    departure_date DATE NOT NULL,
    price_eur DECIMAL(10, 2),
    airline VARCHAR(100),
    direct_flight BOOLEAN,
    flight_duration_minutes INTEGER,
    fetched_at TIMESTAMP DEFAULT NOW(),
    raw_response JSONB,
    UNIQUE(origin, destination, departure_date)
);
CREATE INDEX idx_cache_lookup ON flight_cache (destination, departure_date, fetched_at);
CREATE INDEX idx_cache_expiry ON flight_cache (fetched_at);
Tabella search_history
sqlCREATE TABLE search_history (
    id SERIAL PRIMARY KEY,
    search_type VARCHAR(20) NOT NULL, -- 'reverse' o 'smart_multi'
    params JSONB NOT NULL,
    results JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

API Endpoints (FastAPI)
Reverse Search
GET /api/v1/search/reverse
  ?destination=CTA
  &date_from=2025-04-01
  &date_to=2025-04-07
  &direct_only=false
  &max_results=50

Response: {
  "destination": "CTA",
  "results": [
    {
      "origin": "BER",
      "origin_city": "Berlin",
      "price_eur": 29.99,
      "airline": "Ryanair",
      "departure": "2025-04-03T06:30:00",
      "direct": true,
      "duration_minutes": 165,
      "latitude": 52.3667,
      "longitude": 13.5033
    },
    ...
  ],
  "cached": true,
  "fetched_at": "2025-03-20T14:30:00"
}
Smart Multi-City
POST /api/v1/search/smart-multi
Body: {
  "origin": "CTA",
  "trip_duration_days": 12,
  "budget_per_person_eur": 350,
  "travelers": 2,
  "date_from": "2025-06-01",
  "date_to": "2025-06-15",
  "direct_only": false
}

Response: {
  "origin": "CTA",
  "itineraries": [
    {
      "rank": 1,
      "route": ["CTA", "ATH", "SOF", "BUD", "CTA"],
      "total_price_per_person_eur": 187.50,
      "total_price_all_travelers_eur": 375.00,
      "legs": [
        {
          "from": "CTA",
          "to": "ATH",
          "price_per_person_eur": 45.00,
          "airline": "Ryanair",
          "departure": "2025-06-01T08:00:00",
          "duration_minutes": 120,
          "direct": true
        },
        ...
      ],
      "ai_notes": "Rotta balcanica economica. Atene a giugno ha clima ideale...",
      "suggested_days_per_stop": [3, 3, 3, 3]
    },
    ...
  ]
}
Endpoint ausiliari
GET  /api/v1/airports                     -- Lista aeroporti
GET  /api/v1/airports/in-radius           -- Aeroporti in un raggio
     ?lat=37.47&lon=15.06&radius_km=2000
GET  /api/v1/health                       -- Health check

Integrazione Tequila API (Kiwi.com)
Endpoint principale: https://api.tequila.kiwi.com/v2/search
python# Esempio chiamata
params = {
    "fly_from": "BER",          # o "EU" per tutta Europa
    "fly_to": "CTA",
    "date_from": "01/04/2025",
    "date_to": "07/04/2025",
    "one_for_city": 1,          # un risultato per città
    "curr": "EUR",
    "locale": "it",
    "max_stopovers": 0,         # solo diretti (opzionale)
    "limit": 50
}
headers = {"apikey": TEQUILA_API_KEY}
Note:

Rate limit: ~100 richieste/minuto (piano gratuito)
Il parametro fly_from accetta codici IATA, "EU", o raggi tipo "49.2-16.6-250km"
Registrazione gratuita su https://tequila.kiwi.com/


Integrazione Claude API
Utilizzata nello Step 2 della pipeline Smart Multi-City.
python# Prompt strutturato per generazione itinerari
system_prompt = """
Sei un esperto di viaggi e rotte aeree low-cost in Europa.
Dato un punto di partenza, una durata, un budget per tratta e una lista
di aeroporti raggiungibili, genera 8-10 itinerari multi-città ottimizzati.

Rispondi SOLO in JSON, senza preambolo né markdown.
Formato:
[
  {
    "route": ["CTA", "ATH", "SOF", "BUD", "CTA"],
    "reasoning": "Rotta balcanica con ottime connessioni low-cost",
    "estimated_difficulty": "easy",
    "best_season": ["apr", "mag", "giu", "set", "ott"]
  }
]

Criteri:
- Privilegia rotte con connessioni low-cost note (Ryanair, Wizz Air, easyJet)
- Ogni tappa deve avere senso geografico (no zig-zag)
- Considera la stagionalità
- Rispetta il budget per tratta indicato
- L'ultimo volo deve tornare all'origine
"""

user_prompt = f"""
Origine: {origin}
Durata viaggio: {duration} giorni
Budget per tratta per persona: {budget_per_leg}€
Stagione: {season}
Numero tappe intermedie: {num_stops}
Aeroporti disponibili nel raggio: {airport_list}
"""

Calcolo Area/Raggio
pythonimport math

def estimate_radius_km(trip_duration_days: int) -> int:
    """
    Stima il raggio esplorabile in base alla durata del viaggio.
    Logica: più giorni = raggio più ampio, ma con rendimenti decrescenti.
    """
    # Base: ~200km per giorno, con scala logaritmica per viaggi lunghi
    base_km_per_day = 200
    if trip_duration_days <= 7:
        radius = trip_duration_days * base_km_per_day
    elif trip_duration_days <= 15:
        radius = 1400 + (trip_duration_days - 7) * 150
    else:
        radius = 2600 + (trip_duration_days - 15) * 100
    
    return min(radius, 5000)  # Cap a 5000km


def estimate_stops(trip_duration_days: int) -> int:
    """Numero di tappe intermedie suggerite."""
    if trip_duration_days <= 7:
        return min(2, trip_duration_days // 3)
    elif trip_duration_days <= 15:
        return min(3, trip_duration_days // 4)
    else:
        return min(4, trip_duration_days // 5)


def airports_in_radius(
    origin_lat: float, origin_lon: float,
    radius_km: int, airports: list
) -> list:
    """Filtra aeroporti dentro il raggio usando formula Haversine."""
    R = 6371  # Raggio terra in km
    results = []
    for airport in airports:
        dlat = math.radians(airport['lat'] - origin_lat)
        dlon = math.radians(airport['lon'] - origin_lon)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(origin_lat)) *
             math.cos(math.radians(airport['lat'])) *
             math.sin(dlon/2)**2)
        distance = R * 2 * math.asin(math.sqrt(a))
        if distance <= radius_km:
            airport['distance_km'] = round(distance)
            results.append(airport)
    return results

Struttura Progetto
flyspy/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app + CORS
│   │   ├── config.py                # Settings (env vars)
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── routes/
│   │   │   │   │   ├── search.py    # Reverse search + smart multi
│   │   │   │   │   └── airports.py  # Airport endpoints
│   │   │   │   └── router.py
│   │   ├── services/
│   │   │   ├── tequila.py           # Kiwi Tequila API client
│   │   │   ├── claude.py            # Claude API integration
│   │   │   ├── search_engine.py     # Core search logic
│   │   │   ├── area_calculator.py   # Raggio/area da durata
│   │   │   └── itinerary_engine.py  # Pipeline smart multi-city
│   │   ├── models/
│   │   │   ├── airport.py           # SQLAlchemy models
│   │   │   ├── flight_cache.py
│   │   │   └── schemas.py           # Pydantic schemas
│   │   ├── db/
│   │   │   ├── database.py          # DB connection
│   │   │   ├── redis.py             # Redis connection
│   │   │   └── seed_airports.py     # Script popolamento aeroporti
│   │   └── utils/
│   │       ├── geo.py               # Haversine, calcoli geo
│   │       └── rate_limiter.py      # Rate limiting per API esterne
│   ├── tests/
│   │   ├── test_search.py
│   │   ├── test_itinerary.py
│   │   └── test_geo.py
│   ├── alembic/                     # Migrazioni DB
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Map.jsx              # Mappa Leaflet
│   │   │   ├── SearchForm.jsx       # Form reverse search
│   │   │   ├── SmartSearchForm.jsx  # Form smart multi-city
│   │   │   ├── ResultsList.jsx      # Lista risultati
│   │   │   └── ItineraryCard.jsx    # Card singolo itinerario
│   │   ├── hooks/
│   │   │   └── useFlightSearch.js
│   │   └── services/
│   │       └── api.js               # Client API
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml               # App + Postgres + Redis
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions CI/CD
├── .env.example
└── README.md

Docker Compose
yamlversion: "3.8"
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: flyspy
      POSTGRES_USER: flyspy
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:

Variabili d'Ambiente (.env.example)
# Database
DATABASE_URL=postgresql+asyncpg://flyspy:password@db:5432/flyspy
DB_PASSWORD=your_secure_password

# Redis
REDIS_URL=redis://redis:6379/0

# Tequila API (Kiwi.com)
TEQUILA_API_KEY=your_tequila_api_key
TEQUILA_BASE_URL=https://api.tequila.kiwi.com/v2

# Claude API (Anthropic)
ANTHROPIC_API_KEY=your_anthropic_api_key
CLAUDE_MODEL=claude-sonnet-4-20250514

# App
APP_ENV=development
CACHE_TTL_HOURS=6
MAX_AIRPORTS_SEARCH=300

Roadmap di Sviluppo
Fase 1 — Fondamenta + Reverse Search (2-3 settimane)

 Setup progetto (Docker Compose, FastAPI boilerplate, DB)
 Database aeroporti europei con coordinate (seed da OpenFlights)
 Integrazione Tequila API con client asincrono
 Cache layer PostgreSQL + Redis
 Endpoint reverse search
 Frontend minimale: form + mappa Leaflet con risultati
 Rate limiter per API esterne

Fase 2 — Smart Multi-City (3-4 settimane)

 Area calculator (raggio da durata)
 Endpoint aeroporti in raggio
 Integrazione Claude API per suggerimento itinerari
 Pipeline completa: area → AI → verifica prezzi → ranking
 Vincolo budget funzionante
 Frontend: form smart search + visualizzazione itinerari su mappa

Fase 3 — Polish & Deploy (1-2 settimane)

 UI professionale (design system coerente)
 Error handling robusto (API down, no results, timeout)
 Test suite (unit + integration)
 GitHub Actions CI/CD
 Deploy AWS (ECS o EC2)
 README completo con screenshot
 Demo video per portfolio


Note Importanti

Rate limiting Tequila: ~100 req/min su piano gratuito. Il caching è essenziale.
Costo Claude API: Sonnet è economico (~$3/1M token input). Una ricerca smart usa ~1000 token → costo trascurabile.
Dati aeroporti: OpenFlights (https://openflights.org/data.html) fornisce CSV gratuito con IATA, coordinate, città per ~7000 aeroporti mondiali.
Scalabilità: la pipeline smart multi-city è il collo di bottiglia. Se il prodotto crescesse, si potrebbe pre-calcolare e cacheare itinerari popolari.




NOTE POST: Aggiungoqueste note successive per modificare delle informazioni: l'app si chiamerà HopCraft e non FlySpy e come modello AI dobbiamo usare qualche cosa di gratuito, magari lo cambiaremo in un secondo momento