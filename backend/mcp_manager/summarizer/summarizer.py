import logging
import os

from mcp_manager.summarizer.cleaner import clean_markdown
from mcp_manager.summarizer.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

CULTURES = {"en", "fr"}

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


def _load_prompt(culture: str) -> str:
    path = os.path.join(PROMPTS_DIR, f"summarize_{culture}.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


async def generate_summary(raw_content: str | None, culture: str) -> str | None:
    if not raw_content or not raw_content.strip():
        return None

    if culture not in CULTURES:
        logger.warning("Unknown culture: %s", culture)
        return None

    cleaned = clean_markdown(raw_content)
    if not cleaned:
        return None

    if len(cleaned) > 8000:
        cleaned = cleaned[:8000] + "\n\n[truncated]"

    template = _load_prompt(culture)
    prompt = template.replace("{content}", cleaned)
    result = await ollama_generate(prompt)
    return result if result else None
