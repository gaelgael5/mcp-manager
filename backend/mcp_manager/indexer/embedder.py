"""Generate embeddings via the LLM Manager."""
import logging

from mcp_manager.summarizer.ollama_client import ollama_embed

logger = logging.getLogger(__name__)


async def embed_text(text: str) -> list[float] | None:
    """Generate embedding vector using the configured LLM provider."""
    try:
        return await ollama_embed(text)
    except Exception:
        logger.exception("Embedding failed for text of length %d", len(text))
        return None
