"""LLM Manager — load providers, start/stop containers, route calls."""
import asyncio
import logging

from mcp_manager.llm.config import load_config
from mcp_manager.llm.driver_ollama import OllamaDriver
from mcp_manager.llm.driver_docker import DockerDriver

logger = logging.getLogger(__name__)

DRIVER_TYPES = {
    "ollama": OllamaDriver,
    "docker": DockerDriver,
}


class LLMManager:
    def __init__(self, batch_id: str = ""):
        self.drivers: list = []
        self._current = 0
        self._config = {}
        self._batch_id = batch_id

    def load(self):
        """Load config and instantiate drivers."""
        self._config = load_config()
        self.drivers = []

        rate_limit = self._config.get("claude_rate_limit_per_second", 1)

        for provider in self._config.get("llm", []):
            ptype = provider.get("type")
            args = provider.get("args", {})
            pid = provider.get("id", 0)

            if ptype == "ollama":
                driver = OllamaDriver(args)
                self.drivers.append(driver)
            elif ptype == "docker":
                image = provider.get("image", "claude")
                driver = DockerDriver(pid, args, image, batch_id=self._batch_id)
                driver.set_rate_limit(rate_limit)
                self.drivers.append(driver)
            else:
                logger.warning("Unknown LLM provider type: %s", ptype)

        logger.info("LLM Manager loaded %d providers", len(self.drivers))

    async def start_all(self):
        """Start containers for Docker providers."""
        for driver in self.drivers:
            result = driver.start()
            if asyncio.iscoroutine(result):
                await result

    async def stop_all(self):
        """Stop containers for Docker providers."""
        for driver in self.drivers:
            result = driver.stop()
            if asyncio.iscoroutine(result):
                await result

    def get_driver(self):
        """Round-robin across available drivers."""
        if not self.drivers:
            return None
        driver = self.drivers[self._current % len(self.drivers)]
        self._current += 1
        return driver

    def get_generate_driver(self):
        """Get a driver that can generate text."""
        return self.get_driver()

    def get_embed_driver(self):
        """Get a driver that can embed (prefer Ollama)."""
        for d in self.drivers:
            if isinstance(d, OllamaDriver):
                return d
        return self.get_driver()

    def get_driver_stats(self) -> list[dict]:
        """Return request counts per driver."""
        stats = []
        for d in self.drivers:
            if isinstance(d, OllamaDriver):
                stats.append({"type": "ollama", "name": "ollama", "requests": d.request_count})
            elif isinstance(d, DockerDriver):
                stats.append({"type": "docker", "name": d.image, "container": d.container_name, "requests": d.request_count})
        return stats

    @property
    def worker_count(self) -> int:
        return self._config.get("workers", 1)
