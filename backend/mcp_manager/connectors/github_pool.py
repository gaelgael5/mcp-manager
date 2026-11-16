"""GitHub token pool — uses token_pool for domain-based rate-limited tokens, with env var fallback.

Il n'existe volontairement pas de variante synchrone. Respecter un quota
suppose de pouvoir attendre, ce qu'une fonction synchrone ne sait pas faire
dans une boucle asyncio. L'ancienne version envoyait a la place une requete
qu'elle savait condamnee ("use first one anyway") ; GitHub repondait 403, et
repo_checker interpretait tout code different de 200 comme un repo disparu.
Resultat mesure le 2026-11-15 : 87% des services marques repo_status='404'
avaient en realite un depot vivant. Cf. docs/repo-check.md.
"""
import os
import logging

logger = logging.getLogger(__name__)


async def get_github_headers_async() -> dict:
    """Get HTTP headers with a GitHub token (uses token_pool with rate limiting)."""
    from mcp_manager.connectors.token_pool import get_headers_for_domain, _loaded, _pools
    if not _loaded:
        from mcp_manager.connectors.token_pool import load_tokens
        await load_tokens()

    if "github.com" in _pools and _pools["github.com"]:
        return await get_headers_for_domain("github.com")

    # Fallback to env var
    return _get_env_headers()


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
