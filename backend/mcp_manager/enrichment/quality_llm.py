"""LLM-based quality scoring for summaries (0-100)."""
import json
import logging
import re

from mcp_manager.summarizer.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

_PROMPT_MCP = """Rate the quality of this MCP server summary on a scale of 0-100.

A good summary should:
- Clearly explain what the server does in 1-2 sentences
- List the key tools or capabilities it exposes
- Mention prerequisites or requirements if any
- Be useful for someone deciding whether to install this server
- Be written in proper English
- NOT contain installation commands, JSON/YAML config, or marketing language

Summary to evaluate:
---
{summary}
---

Reply with ONLY a JSON object: {{"score": <0-100>, "reason": "<one sentence>"}}"""

_PROMPT_SKILL = """Rate the quality of this skill/tool description on a scale of 0-100.

A good description should:
- Clearly explain what the skill does
- Explain when and why to use it
- Be useful for someone deciding whether to install this skill
- Be written in proper English

Description to evaluate:
---
{summary}
---

Reply with ONLY a JSON object: {{"score": <0-100>, "reason": "<one sentence>"}}"""


async def llm_score_summary(summary: str, entity_type: str = "mcp") -> int | None:
    """Score 0-100 via LLM. entity_type = 'mcp' | 'skill'.

    Returns None if LLM call fails or response can't be parsed.
    """
    if not summary or not summary.strip():
        return 0

    template = _PROMPT_MCP if entity_type == "mcp" else _PROMPT_SKILL
    # Truncate very long summaries to avoid wasting tokens
    truncated = summary[:3000] if len(summary) > 3000 else summary
    prompt = template.format(summary=truncated)

    try:
        response = await ollama_generate(prompt)
        if not response:
            return None

        # Extract JSON from response (handle markdown code blocks)
        cleaned = response.strip()
        json_match = re.search(r"\{[^}]+\}", cleaned)
        if not json_match:
            logger.warning("llm_score: no JSON found in response: %s", cleaned[:200])
            return None

        data = json.loads(json_match.group())
        score = int(data.get("score", -1))
        if 0 <= score <= 100:
            return score

        logger.warning("llm_score: score out of range: %d", score)
        return None

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("llm_score: parse error: %s", e)
        return None
    except Exception:
        logger.exception("llm_score: unexpected error")
        return None
