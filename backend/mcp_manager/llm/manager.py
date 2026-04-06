"""LLM Manager — load providers, start/stop containers, route calls."""
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
    def __init__(self):
        self.drivers: list = []
        self._current = 0
        self._config = {}

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
                driver = DockerDriver(pid, args, image)
                driver.set_rate_limit(rate_limit)
                self.drivers.append(driver)
            else:
                logger.warning("Unknown LLM provider type: %s", ptype)

        logger.info("LLM Manager loaded %d providers", len(self.drivers))

    def start_all(self):
        """Start containers for Docker providers."""
        for driver in self.drivers:
            driver.start()

    def stop_all(self):
        """Stop containers for Docker providers."""
        for driver in self.drivers:
            driver.stop()

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

    @property
    def worker_count(self) -> int:
        return self._config.get("workers", 1)
