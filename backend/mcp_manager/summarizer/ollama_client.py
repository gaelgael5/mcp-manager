"""LLM client — routes calls through the LLM Manager (ollama or docker)."""
import logging

from mcp_manager.llm.manager import LLMManager

logger = logging.getLogger(__name__)

# Global LLM manager instance — loaded lazily
_manager: LLMManager | None = None


def get_llm_manager() -> LLMManager:
    global _manager
    if _manager is None:
        _manager = LLMManager()
        _manager.load()
    return _manager


async def ollama_generate(prompt: str) -> str:
    """Generate text via the configured LLM provider."""
    manager = get_llm_manager()
    driver = manager.get_generate_driver()
    if not driver:
        logger.error("No LLM provider available")
        return ""
    return await driver.generate(prompt)


async def ollama_embed(text: str) -> list[float] | None:
    """Generate embedding via the configured LLM provider (prefers Ollama)."""
    manager = get_llm_manager()
    driver = manager.get_embed_driver()
    if not driver:
        return None
    return await driver.embed(text)
