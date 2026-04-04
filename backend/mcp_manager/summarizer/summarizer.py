import logging

from mcp_manager.summarizer.cleaner import clean_markdown
from mcp_manager.summarizer.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

CULTURES = {
    "en": "English",
    "fr": "French",
}

PROMPT_TEMPLATE = """Summarize this MCP (Model Context Protocol) server documentation in {language}.

Include:
- What the server does
- Key tools/capabilities it exposes
- Prerequisites and requirements
- Typical use cases

Be concise: maximum 300 words. No marketing language. No badges or links.

Documentation:
---
{content}
---

Summary in {language}:"""


async def generate_summary(raw_content: str | None, culture: str) -> str | None:
    if not raw_content or not raw_content.strip():
        return None

    language = CULTURES.get(culture, culture)
    cleaned = clean_markdown(raw_content)

    if not cleaned:
        return None

    if len(cleaned) > 8000:
        cleaned = cleaned[:8000] + "\n\n[truncated]"

    prompt = PROMPT_TEMPLATE.format(language=language, content=cleaned)
    result = await ollama_generate(prompt)
    return result if result else None
