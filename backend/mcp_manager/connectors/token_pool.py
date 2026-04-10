"""Token pool — round-robin distribution with per-token rate limiting."""
import asyncio
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# In-memory state: domain -> list of {token, rate_limit_per_min, timestamps[]}
_pools: dict[str, list[dict]] = {}
_pool_index: dict[str, int] = defaultdict(int)
_lock = asyncio.Lock()
_loaded = False


async def load_tokens():
    """Load tokens from database into memory."""
    global _pools, _loaded
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import ApiToken
    from sqlalchemy import select

    pools: dict[str, list[dict]] = defaultdict(list)

    try:
        async with SessionLocal() as db:
            result = await db.execute(select(ApiToken).order_by(ApiToken.created_at))
            tokens = result.scalars().all()
            for t in tokens:
                pools[t.domain].append({
                    "id": str(t.id),
                    "token": t.token,
                    "rate_limit_per_min": t.rate_limit_per_min,
                    "timestamps": [],
                })
    except Exception:
        logger.exception("Failed to load API tokens from database")

    _pools = dict(pools)
    _loaded = True
    total = sum(len(v) for v in _pools.values())
    logger.info("Token pool loaded: %d tokens across %d domains", total, len(_pools))


async def get_headers_for_domain(domain: str) -> dict:
    """Get HTTP headers with a token from the pool for the given domain.

    Respects per-token rate limits. Waits if all tokens are exhausted.
    Returns headers dict with Authorization if a token is available.
    """
    if not _loaded:
        await load_tokens()

    pool = _pools.get(domain, [])
    if not pool:
        return {}

    # Try each token in round-robin, find one under rate limit
    now = time.monotonic()
    pool_size = len(pool)

    for attempt in range(pool_size):
        async with _lock:
            idx = _pool_index[domain] % pool_size
            _pool_index[domain] += 1
            entry = pool[idx]

        # Clean old timestamps (older than 60s)
        cutoff = now - 60.0
        entry["timestamps"] = [ts for ts in entry["timestamps"] if ts > cutoff]

        if len(entry["timestamps"]) < entry["rate_limit_per_min"]:
            entry["timestamps"].append(now)
            return {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {entry['token']}",
            }

    # All tokens exhausted — wait for the oldest to expire
    earliest_free = min(
        entry["timestamps"][0] + 60.0
        for entry in pool
        if entry["timestamps"]
    )
    wait_time = max(0, earliest_free - now + 0.1)
    logger.warning("Token pool exhausted for %s, waiting %.1fs", domain, wait_time)
    await asyncio.sleep(wait_time)

    # Retry after wait
    async with _lock:
        idx = _pool_index[domain] % pool_size
        _pool_index[domain] += 1
        entry = pool[idx]

    now = time.monotonic()
    entry["timestamps"] = [ts for ts in entry["timestamps"] if ts > now - 60.0]
    entry["timestamps"].append(now)
    return {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {entry['token']}",
    }


def get_pool_stats() -> dict:
    """Return current pool stats per domain."""
    now = time.monotonic()
    stats = {}
    for domain, pool in _pools.items():
        tokens = []
        for entry in pool:
            recent = [ts for ts in entry["timestamps"] if ts > now - 60.0]
            tokens.append({
                "rate_limit": entry["rate_limit_per_min"],
                "used_last_min": len(recent),
            })
        stats[domain] = {
            "token_count": len(pool),
            "tokens": tokens,
        }
    return stats


def invalidate_cache():
    """Force reload on next call."""
    global _loaded
    _loaded = False
