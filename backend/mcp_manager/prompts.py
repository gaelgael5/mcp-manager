"""Central access to prompt templates and active language codes."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_manager.db.models import Language

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

PROMPT_KINDS = ("summarize", "skill_summary", "source_summary")


class PromptNotFound(FileNotFoundError):
    """Raised when a prompt file is missing on disk."""


def prompt_path(kind: str, language: str) -> Path:
    if kind not in PROMPT_KINDS:
        raise ValueError(f"Unknown prompt kind: {kind!r}")
    return PROMPTS_DIR / language / f"{kind}.md"


def load_prompt(kind: str, language: str) -> str:
    """Read the raw prompt template. Raises PromptNotFound if absent."""
    path = prompt_path(kind, language)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptNotFound(str(path)) from exc


def write_prompt(kind: str, language: str, content: str) -> None:
    """Write a prompt template to disk, creating the language folder if needed."""
    path = prompt_path(kind, language)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def get_active_language_codes(db: AsyncSession) -> list[str]:
    """Return the codes of currently-active languages, ordered by display_order."""
    result = await db.execute(
        select(Language.code)
        .where(Language.is_active.is_(True))
        .order_by(Language.display_order)
    )
    return list(result.scalars().all())


def render_prompt(template: str, content: str) -> str:
    """Replace the {content} placeholder in a prompt template."""
    return template.replace("{content}", content)
