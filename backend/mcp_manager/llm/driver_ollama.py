"""Ollama LLM driver — HTTP calls to Ollama API."""
import logging

import httpx

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Retire un suffixe /v1 de l'URL d'Ollama.

    Ollama expose deux surfaces : l'API native a la racine (/api/generate,
    /api/embed), que ce driver utilise, et une surface compatible OpenAI sous
    /v1. C'est /v1 que la plupart des interfaces affichent, donc ce qu'on colle
    naturellement dans la configuration — on obtenait alors
    /v1/api/generate et un 404 sans explication.
    """
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith("/v1"):
        logger.info(
            "Ollama: suffixe /v1 retire de %r, ce driver parle l'API native", url,
        )
        cleaned = cleaned[: -len("/v1")]
    return cleaned


class OllamaError(RuntimeError):
    """Erreur d'appel a Ollama, porteuse du corps de la reponse."""


class OllamaDriver:
    def __init__(self, args: dict):
        self.url = _normalize_url(args.get("url", "http://localhost:11434"))
        self.model = args.get("model", "llama3.1:8b")
        self.request_count = 0

    async def generate(self, prompt: str) -> str:
        self.request_count += 1
        endpoint = f"{self.url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code >= 400:
                # Le corps porte la cause reelle — typiquement
                # {"error":"model 'x' not found"} — la ou le message de
                # raise_for_status() ne cite que le code et l'URL. Un 404
                # d'endpoint et un 404 de modele absent devenaient ainsi
                # indistinguables depuis l'interface.
                raise OllamaError(
                    f"POST {endpoint} (model={self.model!r}) -> HTTP "
                    f"{resp.status_code}: {resp.text[:500]}"
                )
            text = resp.json().get("response", "").strip()
            return text.replace("\x00", "")

    async def embed(self, text: str, max_retries: int = 3) -> list[float] | None:
        import asyncio
        if not text or not text.strip():
            return None
        text = text.replace("\x00", "").strip()
        if not text:
            return None
        endpoint = f"{self.url}/api/embed"
        payload = {"model": "mxbai-embed-large", "input": text}
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(endpoint, json=payload)
                    if resp.status_code == 429 or resp.status_code >= 500:
                        wait = 2 ** attempt * 5
                        logger.warning("Ollama embed %d, retrying in %ds (attempt %d/%d)", resp.status_code, wait, attempt + 1, max_retries)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    embeddings = resp.json().get("embeddings", [])
                    return embeddings[0] if embeddings else None
            except httpx.TimeoutException:
                wait = 2 ** attempt * 5
                logger.warning("Ollama embed timeout, retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
            except Exception:
                logger.exception("Ollama embed failed")
                return None
        logger.error("Ollama embed failed after %d retries", max_retries)
        return None

    def start(self):
        """Ollama is always running — nothing to start."""
        pass

    def stop(self):
        """Nothing to stop."""
        pass
