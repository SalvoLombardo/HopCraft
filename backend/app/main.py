from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import engine, Base
from app.db.redis import get_redis, close_redis
from app.api.v1.router import api_router
import app.models  # noqa: F401 — registra tutti i modelli con Base

###############---############
# REMEMBER TO SWITCH TO Alembic migrations IN PROD
###############---############
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    redis = await get_redis()
    await redis.ping()  # verifica connessione Redis all'avvio

    yield

    # Shutdown
    await close_redis()


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


app.include_router(api_router)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
