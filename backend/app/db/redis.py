"""
Connessione Redis asincrona.

Uso come dependency FastAPI:
    redis = Annotated[aioredis.Redis, Depends(get_redis)]

Oppure direttamente:
    redis = await get_redis()
"""
import redis.asyncio as aioredis

from app.config import settings

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Restituisce il client Redis (singleton lazy)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Chiude la connessione Redis. Da chiamare nello shutdown del lifespan."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
