"""
Rate limiter Redis-based per proteggere le API esterne.

Uso tipico:
    allowed = await check_rate_limit("serpapi:monthly", max_calls=90, window_seconds=2_592_000)
    if not allowed:
        raise HTTPException(429, "Rate limit SerpAPI raggiunto")

Note:
- Il contatore è incrementato ad ogni chiamata.
- Il TTL viene impostato solo alla prima chiamata nella finestra (incr → 1).
- Non è atomico al 100% su race condition estreme, ma è sufficiente per questo use case.
"""
from app.db.redis import get_redis


async def check_rate_limit(
    key: str,
    max_calls: int,
    window_seconds: int,
) -> bool:
    """
    Verifica e incrementa il contatore per la chiave data.

    Args:
        key:            Chiave Redis (es. "serpapi:monthly").
        max_calls:      Numero massimo di chiamate permesse nella finestra.
        window_seconds: Durata della finestra in secondi.

    Returns:
        True se la chiamata è permessa, False se il limite è raggiunto.
    """
    redis = await get_redis()
    count = await redis.incr(key)
    if count == 1:
        # Prima chiamata nella finestra: imposta il TTL
        await redis.expire(key, window_seconds)
    return count <= max_calls


async def get_remaining(key: str, max_calls: int) -> int:
    """Restituisce il numero di chiamate rimanenti per la chiave."""
    redis = await get_redis()
    count = int(await redis.get(key) or 0)
    return max(0, max_calls - count)


#asd