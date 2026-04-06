"""Ollama LLM driver — HTTP calls to Ollama API."""
import logging

import httpx

logger = logging.getLogger(__name__)


class OllamaDriver:
    def __init__(self, args: dict):
        self.url = args.get("url", "http://localhost:11434")
        self.model = args.get("model", "llama3.1:8b")

    async def generate(self, prompt: str) -> str:
        endpoint = f"{self.url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return text.replace("\x00", "")

    async def embed(self, text: str) -> list[float] | None:
        endpoint = f"{self.url}/api/embed"
        payload = {"model": "mxbai-embed-large", "input": text}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(endpoint, json=payload)
                resp.raise_for_status()
                embeddings = resp.json().get("embeddings", [])
                return embeddings[0] if embeddings else None
        except Exception:
            logger.exception("Ollama embed failed")
            return None

    def start(self):
        """Ollama is always running — nothing to start."""
        pass

    def stop(self):
        """Nothing to stop."""
        pass
