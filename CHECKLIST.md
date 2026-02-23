# HopCraft — Checklist di Sviluppo

> Riferimento: [Structure.md](Structure.md)
> Aggiorna questo file ad ogni sessione di lavoro.
> Legenda: `[ ]` da fare · `[x]` completato · `[~]` in corso · `[-]` saltato/rimandato

---

## FASE 1 — Fondamenta + Reverse Search

### 1.1 Setup progetto
- [x] Creare struttura cartelle come da Structure.md
- [ ] Inizializzare repo Git
- [x] Creare `docker-compose.yml` (backend + frontend + postgres + redis)
- [x] Creare `.env.example` con tutte le variabili necessarie
- [ ] Creare `.env` locale con i valori reali (non committare)
- [ ] Verificare che `docker compose up` avvii tutti i servizi senza errori

### 1.2 Backend — Boilerplate FastAPI
- [ ] Creare `backend/requirements.txt` con le dipendenze base
- [ ] Creare `backend/Dockerfile`
- [ ] Scrivere `app/main.py` con FastAPI + CORS
- [ ] Scrivere `app/config.py` con lettura variabili d'ambiente
- [ ] Endpoint `/api/v1/health` funzionante
- [ ] Verificare che il backend risponda su `localhost:8000`

### 1.3 Database — PostgreSQL
- [ ] Scrivere `app/db/database.py` con connessione asincrona (asyncpg)
- [ ] Scrivere i modelli SQLAlchemy per `airports`, `flight_cache`, `search_history`
- [ ] Scrivere `app/models/schemas.py` con Pydantic schemas
- [ ] Setup Alembic per migrazioni
- [ ] Eseguire prima migrazione (crea le tabelle)
- [ ] Verificare le tabelle nel database con un client (es. TablePlus o psql)

### 1.4 Seed aeroporti
- [ ] Scaricare CSV da OpenFlights (`airports.dat`)
- [ ] Scrivere `app/db/seed_airports.py` per popolare la tabella `airports`
- [ ] Filtrare solo gli aeroporti europei principali (~300)
- [ ] Eseguire lo script e verificare i dati nel DB

### 1.5 Redis
- [ ] Scrivere `app/db/redis.py` con connessione Redis
- [ ] Verificare connessione Redis con un ping

### 1.6 Tequila API (Kiwi.com)
- [ ] Registrarsi su tequila.kiwi.com e ottenere API key
- [ ] Scrivere `app/services/tequila.py` — client asincrono
- [ ] Testare una chiamata manuale all'API (es. voli da Milano a Catania)
- [ ] Gestire errori e timeout

### 1.7 Cache layer
- [ ] Implementare logica cache in PostgreSQL (`flight_cache`) con TTL 6-12h
- [ ] Prima di ogni chiamata Tequila, controllare se il risultato è in cache
- [ ] Scrivere in cache dopo ogni chiamata API
- [ ] Scrivere `app/utils/rate_limiter.py` per rispettare i 100 req/min

### 1.8 Endpoint Reverse Search
- [ ] Scrivere `app/services/search_engine.py` — logica core reverse search
- [ ] Scrivere `app/api/v1/routes/search.py` — endpoint `GET /api/v1/search/reverse`
- [ ] Testare endpoint manualmente con Swagger UI (`localhost:8000/docs`)
- [ ] Risposta include: origine, prezzo, compagnia, orario, lat/lon

### 1.9 Endpoint Aeroporti
- [ ] Scrivere `app/api/v1/routes/airports.py`
- [ ] `GET /api/v1/airports` — lista tutti gli aeroporti attivi
- [ ] `GET /api/v1/airports/in-radius` — aeroporti in un raggio dato lat/lon/km

### 1.10 Frontend minimale — Reverse Search
- [ ] Inizializzare progetto React (Vite)
- [ ] Creare `frontend/Dockerfile`
- [ ] Scrivere `src/services/api.js` — client HTTP verso il backend
- [ ] Scrivere `SearchForm.jsx` — form con destinazione, date, filtro diretto
- [ ] Scrivere `Map.jsx` con Leaflet — mappa con marker colorati per prezzo
- [ ] Scrivere `ResultsList.jsx` — lista ordinabile per prezzo/durata
- [ ] Collegare form → API → mappa + lista
- [ ] Verificare il flusso completo end-to-end

---

## FASE 2 — Smart Multi-City

### 2.1 Area Calculator
- [ ] Scrivere `app/utils/geo.py` con funzione Haversine
- [ ] Scrivere `app/services/area_calculator.py` — `estimate_radius_km()` e `estimate_stops()`
- [ ] Testare con diversi valori di durata (5, 12, 25 giorni)

### 2.2 AI per suggerimento itinerari
- [ ] Scegliere il modello AI gratuito da usare (decidere con il prossimo lavoro)
- [ ] Scrivere `app/services/claude.py` (o rinominare in base al modello scelto)
- [ ] Implementare il prompt strutturato come da Structure.md
- [ ] Testare che l'output sia JSON valido con rotte plausibili

### 2.3 Pipeline Smart Multi-City
- [ ] Scrivere `app/services/itinerary_engine.py`
  - [ ] Step 1: calcolo raggio e filtraggio aeroporti
  - [ ] Step 2: chiamata AI → lista itinerari candidati
  - [ ] Step 3: verifica prezzi reali (chiamate Tequila parallele asincronie)
  - [ ] Step 4: filtraggio per budget + ranking
  - [ ] Step 5: preparazione risposta top 5

### 2.4 Endpoint Smart Multi-City
- [ ] Scrivere endpoint `POST /api/v1/search/smart-multi`
- [ ] Testare con Swagger UI
- [ ] Gestire casi: nessun itinerario trovato, budget troppo basso, API non disponibile

### 2.5 Frontend Smart Search
- [ ] Scrivere `SmartSearchForm.jsx` — form con origine, durata, budget, viaggiatori
- [ ] Scrivere `ItineraryCard.jsx` — card con rotta, prezzi per tratta, note AI
- [ ] Aggiornare `Map.jsx` per disegnare rotte (polyline tra tappe)
- [ ] Integrare il flusso completo Smart Multi-City nel frontend

---

## FASE 3 — Polish & Deploy

### 3.1 UI
- [ ] Definire un design system coerente (colori, font, componenti base)
- [ ] Rendere il layout responsive (mobile-friendly)
- [ ] Aggiungere stati di caricamento (skeleton/spinner) e messaggi di errore utente

### 3.2 Error Handling
- [ ] Gestire API Tequila down (fallback, messaggio chiaro)
- [ ] Gestire risultati vuoti (zero voli trovati)
- [ ] Gestire timeout su chiamate lente
- [ ] Gestire errori AI (risposta non JSON, rotte invalide)

### 3.3 Test
- [ ] Scrivere `tests/test_geo.py` — test funzioni Haversine e raggio
- [ ] Scrivere `tests/test_search.py` — test reverse search (mock API)
- [ ] Scrivere `tests/test_itinerary.py` — test pipeline smart multi-city
- [ ] Tutti i test passano (`pytest`)

### 3.4 CI/CD
- [ ] Creare `.github/workflows/ci.yml`
- [ ] Pipeline: lint + test su ogni push
- [ ] Aggiungere deploy automatico (da decidere: AWS ECS o EC2)

### 3.5 Deploy
- [ ] Scegliere e configurare ambiente cloud (AWS ECS o EC2)
- [ ] Configurare variabili d'ambiente in produzione
- [ ] Deploy Docker Compose in produzione
- [ ] Verificare l'app funzionante su dominio pubblico

### 3.6 Portfolio
- [ ] Scrivere `README.md` completo con screenshot
- [ ] Registrare demo video
- [ ] Aggiungere al portfolio

---

## Note di sessione

> Usa questa sezione per annotare decisioni prese, problemi incontrati, cose da riprendere.

| Data | Nota |
|------|------|
| 2026-02-23 | Creazione checklist. Progetto ancora vuoto. Nome app: HopCraft. AI model da decidere (deve essere gratuito). |
| 2026-02-23 | Creata struttura cartelle completa, docker-compose.yml (con PostgreSQL + Redis), .gitignore, .env.example. Redis mantenuto per ora su richiesta. Prossimo passo: boilerplate FastAPI (1.2). |
