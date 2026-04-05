"""Generate embeddings via Ollama."""
import logging

import httpx

from mcp_manager.config import settings

logger = logging.getLogger(__name__)


async def embed_text(text: str) -> list[float] | None:
    """Generate embedding vector for a text using Ollama."""
    url = f"{settings.ollama_base_url}/api/embed"
    payload = {
        "model": "mxbai-embed-large",
        "input": text,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0]
            return None
    except Exception:
        logger.exception("Embedding failed for text of length %d", len(text))
        return None


async def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Generate embeddings for multiple texts."""
    results = []
    for text in texts:
        vec = await embed_text(text)
        results.append(vec)
    return results
