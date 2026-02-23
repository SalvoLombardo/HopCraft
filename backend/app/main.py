from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import engine, Base
import app.models  # noqa: F401 — registra tutti i modelli con Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # All'avvio: crea le tabelle nel DB se non esistono ancora.
    # In produzione si userebbe Alembic per le migrazioni;
    # per ora create_all() è sufficiente.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Alla chiusura: nessuna operazione necessaria per ora.


app = FastAPI(
    title="HopCraft API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
