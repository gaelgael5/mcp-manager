"""LLM client — routes calls through the LLM Manager (ollama or docker)."""
import contextvars
import logging

from mcp_manager.llm.manager import LLMManager

logger = logging.getLogger(__name__)

# Context-local LLM manager — each async task can have its own
_manager_var: contextvars.ContextVar[LLMManager | None] = contextvars.ContextVar("llm_manager", default=None)

# Fallback global for non-batch code
_fallback_manager: LLMManager | None = None


def get_llm_manager() -> LLMManager:
    global _fallback_manager
    # Check context-local first (set by batch jobs)
    manager = _manager_var.get(None)
    if manager is not None:
        return manager
    # Fallback to global singleton
    if _fallback_manager is None:
        _fallback_manager = LLMManager()
        _fallback_manager.load()
    return _fallback_manager


def set_llm_manager(manager: LLMManager | None):
    """Set the LLM manager for the current async context (batch job)."""
    _manager_var.set(manager)


def get_current_llm_name() -> str:
    """Return the name of the current generate LLM driver."""
    manager = get_llm_manager()
    driver = manager.get_generate_driver()
    if not driver:
        return "unknown"
    from mcp_manager.llm.driver_docker import DockerDriver
    from mcp_manager.llm.driver_ollama import OllamaDriver
    if isinstance(driver, DockerDriver):
        return f"docker:{driver.image}"
    if isinstance(driver, OllamaDriver):
        return f"ollama:{driver.model}"
    return type(driver).__name__


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
