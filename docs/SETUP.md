# HopCraft — Setup Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Environment Variables Reference](#environment-variables-reference)
4. [Running Tests](#running-tests)
5. [Production Deploy (AWS)](#production-deploy-aws)
6. [First Deploy Checklist](#first-deploy-checklist)
7. [Database Operations](#database-operations)
8. [Common Operations](#common-operations)

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker | ≥ 24 | With Docker Compose plugin |
| Git | any | |
| Python | 3.12 | Only needed for local tests outside Docker |
| Node.js | 20 | Only needed for frontend outside Docker |
| Terraform | ≥ 1.6 | Only for production infrastructure |
| AWS CLI | ≥ 2 | Only for production |

**API keys required (all free, no credit card):**

| Service | Sign up | Variable |
|---|---|---|
| SerpAPI | [serpapi.com](https://serpapi.com) | `SERPAPI_API_KEY` |
| Amadeus | [developers.amadeus.com](https://developers.amadeus.com) | `AMADEUS_API_KEY` + `AMADEUS_API_SECRET` |
| Google AI Studio | [aistudio.google.com](https://aistudio.google.com) | `GEMINI_API_KEY` |
| Groq | [console.groq.com](https://console.groq.com) | `GROQ_API_KEY` |
| Mistral | [console.mistral.ai](https://console.mistral.ai) | `MISTRAL_API_KEY` |

> Groq and Mistral are optional (used only as LLM fallbacks). If you only have a Gemini key the app works fine for normal load.

---

## Local Development

### 1. Clone and configure

```bash
git clone https://github.com/your-username/hopcraft.git
cd hopcraft

cp .env.example .env
# Fill in your API keys in .env (see reference below)
```

### 2. Start all services

```bash
docker compose up --build
```

This starts:
- `backend` — FastAPI on `localhost:8000`
- `frontend` — React (served by nginx) on `localhost:3000`
- `db` — PostgreSQL 16 on `localhost:5432`
- `redis` — Redis 7 on `localhost:6379`

The backend waits for PostgreSQL and Redis to be healthy before starting (health checks configured in `docker-compose.yml`). SQLAlchemy `create_all()` creates the tables on first startup.

### 3. Seed airports

```bash
docker compose exec backend python -m app.db.seed_airports
```

Loads ~1 174 European + North Africa airports from OpenFlights into the `airports` table. The script is idempotent — safe to run multiple times.

### 4. Open the app

- App: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs
- API docs (ReDoc): http://localhost:8000/redoc

### 5. Stop

```bash
docker compose down           # stop containers, keep volumes
docker compose down -v        # stop containers AND delete volumes (fresh start)
```

---

## Environment Variables Reference

Copy `.env.example` to `.env` and fill in the values below.

### Database

| Variable | Example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://hopcraft:password@db:5432/hopcraft` | Full async DSN. The host `db` is the Docker service name. |
| `DB_PASSWORD` | `your_secure_password` | Used by the `db` service in `docker-compose.yml`. |

### Redis

| Variable | Example | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | The host `redis` is the Docker service name. |

### Flight Providers (cascade: SerpAPI → Amadeus)

| Variable | Default | Description |
|---|---|---|
| `FLIGHT_PROVIDER` | `cascade` | Controls provider order. See table below. |
| `SERPAPI_API_KEY` | — | SerpAPI key. Get it at serpapi.com. |
| `AMADEUS_API_KEY` | — | Amadeus client ID. |
| `AMADEUS_API_SECRET` | — | Amadeus client secret. |

**`FLIGHT_PROVIDER` values:**

| Value | Cascade order | When to use |
|---|---|---|
| `cascade` | SerpAPI → Amadeus (auto by quota) | Production default |
| `serpapi` | SerpAPI first, Amadeus fallback | Force SerpAPI (e.g. testing coverage) |
| `amadeus` | Amadeus first, SerpAPI fallback | **Recommended for local dev** — Amadeus has 2 000 req/month vs 250 for SerpAPI, preserves SerpAPI credits for production |

> Quota checks still apply in all modes. If the forced provider has exhausted its quota, the system falls through to the next one automatically.

### LLM Providers (cascade: Gemini → Groq → Mistral)

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | Starting point of the fallback chain. Options: `gemini`, `groq`, `mistral`. |
| `GEMINI_API_KEY` | — | Google AI Studio key. |
| `GROQ_API_KEY` | — | Groq console key. |
| `MISTRAL_API_KEY` | — | Mistral La Plateforme key. |

**`LLM_PROVIDER` values:**

| Value | Providers attempted in order | When to use |
|---|---|---|
| `gemini` | Gemini → Groq → Mistral | Default — Gemini is the highest quality option |
| `groq` | Groq → Mistral | Skip Gemini entirely (e.g. Gemini key unavailable or quota hit) |
| `mistral` | Mistral only | Last resort / testing Mistral specifically |

> Unlike `FLIGHT_PROVIDER`, this is a *start index* into the fixed chain `[gemini, groq, mistral]`. Setting `LLM_PROVIDER=groq` means "start from Groq and cascade downward" — Gemini is skipped, not just deprioritised. If Groq also fails, Mistral is tried automatically.

### App Settings

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` or `production`. |
| `CACHE_TTL_HOURS` | `6` | How long flight cache entries stay valid. |
| `MAX_AIRPORTS_SEARCH` | `300` | Max airports passed to the frontend airport list endpoint. |

---

## Running Tests

Tests use pytest. All external services (DB, Redis, SerpAPI, Amadeus, Gemini) are mocked — no real API calls are made.

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Expected output: **76 passed**.

### Test files

| File | What it tests |
|---|---|
| `tests/test_geo.py` | Haversine distance, radius estimation, stop count estimation |
| `tests/test_search.py` | Reverse search flow: cache hits, cache misses, provider cascade, radius filter |
| `tests/test_itinerary.py` | Smart multi-city pipeline, budget filtering, ranking, `parse_itineraries()`, route validation |

### Lint

```bash
ruff check --select E,F --line-length 100 app/ tests/
```

---

## Production Deploy (AWS)

### EC2 Bootstrap — Docker Compose on Amazon Linux 2023

Amazon Linux 2023 ships with Docker but **not** the Compose plugin. Install it manually after provisioning the instance (Terraform `user_data` can automate this):

```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL \
  "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version   # verify
```

Also add `ec2-user` to the `docker` group so you don't need `sudo`:

```bash
sudo usermod -aG docker ec2-user
newgrp docker
```

### Infrastructure with Terraform

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: aws_region, key_pair_name, your_ip_cidr

terraform init
terraform plan
terraform apply
```

After `apply`, note the outputs:
```
ec2_public_ip              = "x.x.x.x"
s3_bucket_name             = "hopcraft-frontend-xxxx"
cloudfront_distribution_id = "EXXXXXXXXXXXXX"
cloudfront_domain_name     = "dxxxxxxxxxxxx.cloudfront.net"
```

### GitHub Secrets

Add these in the repository: **Settings → Secrets and variables → Actions**.

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user with S3 + CloudFront + EC2 permissions |
| `AWS_SECRET_ACCESS_KEY` | Corresponding secret |
| `S3_BUCKET_NAME` | From `terraform output s3_bucket_name` |
| `CLOUDFRONT_DISTRIBUTION_ID` | From `terraform output cloudfront_distribution_id` |
| `EC2_HOST` | From `terraform output ec2_public_ip` |
| `EC2_SSH_KEY` | Full content of your private SSH key (`~/.ssh/hopcraft`) |

### GHCR Package Visibility

The deploy job pulls the Docker image without authentication. Make the package public:

GitHub → Your profile → Packages → `hopcraft-backend` → Package settings → Change visibility → Public

---

## First Deploy Checklist

Run these steps **once** after `terraform apply` and before the first automated deploy.

```bash
EC2_IP=$(terraform -chdir=infra output -raw ec2_public_ip)

# 1. Upload production compose file, nginx config, and .env
scp -i ~/.ssh/hopcraft \
    docker-compose.prod.yml \
    nginx.prod.conf \
    ec2-user@$EC2_IP:/opt/hopcraft/

# 2. Upload production environment (create .env.prod from .env.prod.example)
cp .env.prod.example .env.prod
# Fill in .env.prod with real production values
scp -i ~/.ssh/hopcraft .env.prod ec2-user@$EC2_IP:/opt/hopcraft/.env

# 3. SSH in and start services
ssh -i ~/.ssh/hopcraft ec2-user@$EC2_IP
cd /opt/hopcraft
docker compose -f docker-compose.prod.yml up -d

# 4. Seed the database
docker compose -f docker-compose.prod.yml exec backend \
    python -m app.db.seed_airports

# 5. Deactivate non-civil airports (military/naval bases from OpenFlights)
docker compose -f docker-compose.prod.yml exec db \
    psql -U hopcraft -d hopcraft -c "
    UPDATE airports SET is_active = FALSE
    WHERE name ILIKE '%naval%'
       OR name ILIKE '%air base%'
       OR name ILIKE '%air force%'
       OR name ILIKE '%military%';
    "

# 6. Verify
curl http://$EC2_IP/api/v1/health
```

After this, push any commit to `main` to trigger the automated CI/CD pipeline.

---

## Database Operations

### Re-run seed (idempotent)

```bash
docker compose exec backend python -m app.db.seed_airports
```

Safe to run on existing data — uses `INSERT … ON CONFLICT DO UPDATE` to refresh the `continent` field without losing other data.

### Add a new column (no Alembic)

Since the project uses `create_all()` instead of Alembic, new columns need a manual ALTER:

```bash
docker compose exec db psql -U hopcraft -d hopcraft -c \
    "ALTER TABLE airports ADD COLUMN IF NOT EXISTS my_column VARCHAR(50);"
```

Then update the SQLAlchemy model and re-run the seed if the column needs populating.

### Connect directly to the database

```bash
# Local dev
docker compose exec db psql -U hopcraft -d hopcraft

# Production
ssh -i ~/.ssh/hopcraft ec2-user@$EC2_IP
docker compose -f /opt/hopcraft/docker-compose.prod.yml exec db \
    psql -U hopcraft -d hopcraft
```

### Inspect Redis quota counters

```bash
docker compose exec redis redis-cli
> GET serpapi:monthly
> GET amadeus:monthly
> TTL serpapi:monthly    # seconds until monthly reset
```

---

## Common Operations

### Rebuild only the backend

```bash
docker compose up --build backend
```

### View logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Reset flight cache (force fresh API calls)

```bash
docker compose exec db psql -U hopcraft -d hopcraft -c \
    "DELETE FROM flight_cache;"
```

### Reset provider quota counters (testing only)

```bash
docker compose exec redis redis-cli DEL serpapi:monthly
docker compose exec redis redis-cli DEL amadeus:monthly
```

### Update production after a change (manual)

```bash
EC2_IP=your.ec2.ip
ssh -i ~/.ssh/hopcraft ec2-user@$EC2_IP
cd /opt/hopcraft
docker compose -f docker-compose.prod.yml pull backend
docker compose -f docker-compose.prod.yml up -d --no-deps backend nginx
docker image prune -f
```
