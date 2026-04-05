import asyncio
import logging

from mcp_manager.summarizer.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

CATEGORIES = {
    "database", "devops", "ai", "ai-ml", "security", "monitoring",
    "productivity", "communication", "search", "development",
    "developer-tools", "finance", "analytics", "documentation",
    "web", "blockchain", "commerce", "ecommerce", "infrastructure",
    "automation", "integration", "iot", "games", "media", "video",
    "news", "travel", "healthcare", "geospatial", "maps", "messaging",
    "data-analytics", "data-visualization", "reference", "cloud",
    "testing", "education", "social", "storage", "email",
}

PROMPT_TEMPLATE = """Classify this MCP server into exactly ONE category.

Name: {name}
Description: {description}

Categories: {categories}

Reply with ONLY the category name, nothing else."""


def parse_category_response(response: str) -> str | None:
    if not response:
        return None
    cleaned = response.strip().lower().rstrip(".")
    if cleaned in CATEGORIES:
        return cleaned
    return None


async def categorize_single(name: str, description: str) -> str | None:
    if not description or not description.strip():
        return None
    prompt = PROMPT_TEMPLATE.format(
        name=name,
        description=description,
        categories=", ".join(sorted(CATEGORIES)),
    )
    response = await ollama_generate(prompt)
    return parse_category_response(response)


async def run_categorize() -> dict[str, int]:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService

    stats = {"categorized": 0, "skipped_no_desc": 0, "skipped_invalid": 0}
    semaphore = asyncio.Semaphore(5)

    async with SessionLocal() as db:
        result = await db.execute(
            select(McpService).where(McpService.category.is_(None))
        )
        services = result.scalars().all()
        logger.info("Categorizer: %d services without category", len(services))

        for i, service in enumerate(services):
            desc = service.name

            async with semaphore:
                category = await categorize_single(service.name, desc)

            if category:
                service.category = category
                stats["categorized"] += 1
            else:
                stats["skipped_invalid"] += 1

            if (i + 1) % 100 == 0:
                logger.info("Categorizer progress: %d/%d", i + 1, len(services))
                await db.commit()

        await db.commit()

    logger.info("Categorizer done: %d categorized, %d skipped (no desc), %d skipped (invalid)",
                stats["categorized"], stats["skipped_no_desc"], stats["skipped_invalid"])
    return stats
