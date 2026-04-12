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

# Valid pipeline keys for the concurrency config block.
PIPELINES = ("mcp", "skill_sources", "skills")


class LLMManager:
    def __init__(self, batch_id: str = "", pipeline: str = ""):
        self.drivers: list = []
        self._current = 0
        self._config = {}
        self._batch_id = batch_id
        self._pipeline = pipeline

    def load(self):
        """Load config and instantiate drivers.

        When `pipeline` is set, reads `config["concurrency"][pipeline]` as a
        mapping of `{provider_id (str): count}` and spawns `count` DockerDriver
        instances per configured docker provider. Ollama providers always get
        exactly one driver (reserved for RAG/embeddings) regardless of pipeline.
        """
        self._config = load_config()
        self.drivers = []

        concurrency = {}
        if self._pipeline:
            concurrency = self._config.get("concurrency", {}).get(self._pipeline, {}) or {}

        for provider in self._config.get("llm", []):
            ptype = provider.get("type")
            args = provider.get("args", {})
            pid = provider.get("id", 0)

            if ptype == "ollama":
                count = 1
                if self._pipeline:
                    try:
                        count = int(concurrency.get(str(pid), 1))
                    except (TypeError, ValueError):
                        count = 1
                count = max(0, count)
                for _ in range(count):
                    self.drivers.append(OllamaDriver(args))
            elif ptype == "docker":
                image = provider.get("image", "claude")
                count = 1
                if self._pipeline:
                    try:
                        count = int(concurrency.get(str(pid), 1))
                    except (TypeError, ValueError):
                        count = 1
                count = max(0, count)
                for i in range(count):
                    driver = DockerDriver(
                        pid, args, image,
                        batch_id=self._batch_id,
                        instance_idx=i,
                    )
                    self.drivers.append(driver)
            else:
                logger.warning("Unknown LLM provider type: %s", ptype)

        logger.info(
            "LLM Manager loaded %d drivers (pipeline=%r)",
            len(self.drivers), self._pipeline or "default",
        )

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
        """Get a driver that can generate text (round-robin across all drivers)."""
        if not self.drivers:
            return None
        driver = self.drivers[self._current % len(self.drivers)]
        self._current += 1
        return driver

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
                stats.append({
                    "type": "docker",
                    "name": d.image,
                    "container": d.container_name,
                    "requests": d.request_count,
                })
        return stats
