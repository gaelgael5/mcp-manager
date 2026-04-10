import logging

from mcp_manager.prompts import PROMPT_KINDS, PromptNotFound, load_prompt, render_prompt
from mcp_manager.summarizer.cleaner import clean_markdown
from mcp_manager.summarizer.ollama_client import ollama_generate

logger = logging.getLogger(__name__)


async def generate_summary(raw_content: str | None, culture: str) -> str | None:
    if not raw_content or not raw_content.strip():
        return None

    cleaned = clean_markdown(raw_content)
    if not cleaned:
        return None

    if len(cleaned) > 8000:
        cleaned = cleaned[:8000] + "\n\n[truncated]"

    try:
        template = load_prompt("summarize", culture)
    except PromptNotFound:
        logger.warning("No summarize prompt for culture %s", culture)
        return None

    prompt = render_prompt(template, cleaned)
    result = await ollama_generate(prompt)
    return result if result else None
