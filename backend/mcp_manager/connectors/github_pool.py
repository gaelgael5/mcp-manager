"""GitHub token pool — uses token_pool for domain-based rate-limited tokens, with env var fallback."""
import os
import time
import logging

logger = logging.getLogger(__name__)


async def get_github_headers_async() -> dict:
    """Get HTTP headers with a GitHub token (async, uses token_pool with rate limiting)."""
    from mcp_manager.connectors.token_pool import get_headers_for_domain, _loaded, _pools
    if not _loaded:
        from mcp_manager.connectors.token_pool import load_tokens
        await load_tokens()

    if "github.com" in _pools and _pools["github.com"]:
        return await get_headers_for_domain("github.com")

    # Fallback to env var
    return _get_env_headers()


def get_github_headers() -> dict:
    """Get HTTP headers with a GitHub token (sync, uses pool if loaded, else env var)."""
    from mcp_manager.connectors.token_pool import _loaded, _pools

    if _loaded and "github.com" in _pools and _pools["github.com"]:
        return _get_pool_headers_sync(_pools["github.com"])

    return _get_env_headers()


def _get_pool_headers_sync(pool: list[dict]) -> dict:
    """Sync round-robin from in-memory pool with rate limiting."""
    global _pool_sync_index
    now = time.monotonic()
    pool_size = len(pool)

    for _ in range(pool_size):
        idx = _pool_sync_index % pool_size
        _pool_sync_index += 1
        entry = pool[idx]

        # Clean old timestamps
        entry["timestamps"] = [ts for ts in entry["timestamps"] if ts > now - 60.0]

        if len(entry["timestamps"]) < entry["rate_limit_per_min"]:
            entry["timestamps"].append(now)
            return {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {entry['token']}",
            }

    # All exhausted — use first one anyway (will be rate limited by GitHub)
    entry = pool[0]
    entry["timestamps"].append(now)
    logger.warning("GitHub token pool exhausted, using token anyway")
    return {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {entry['token']}",
    }


def _get_env_headers() -> dict:
    """Fallback: use GITHUB_TOKEN env var (supports comma-separated)."""
    raw = os.environ.get("GITHUB_TOKEN", "")
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    headers = {"Accept": "application/vnd.github.v3+json"}
    if tokens:
        global _env_index
        token = tokens[_env_index % len(tokens)]
        _env_index += 1
        headers["Authorization"] = f"token {token}"
    return headers


_env_index = 0
_pool_sync_index = 0
