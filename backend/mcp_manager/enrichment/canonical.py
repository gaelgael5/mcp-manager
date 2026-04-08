"""Canonical ID computation for cross-source service and skill identity."""

import logging
import re

from sqlalchemy import select, or_

from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import McpService, Skill

logger = logging.getLogger(__name__)

# Matches github.com/owner/repo with optional path after
_GITHUB_RE = re.compile(
    r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?(?:/tree/[^/]+(/.*?))?/?$",
    re.IGNORECASE,
)


def compute_canonical_id(
    source_url: str | None,
    package_identifier: str | None = None,
    registry_type: str | None = None,
    source_type: str | None = None,
    name: str | None = None,
) -> str:
    """Compute a canonical identifier for an MCP service.

    Priority:
      1. github:owner/repo[/subpath]  — from source_url
      2. npm:package_identifier       — from package registry
      3. pypi:package_identifier      — from package registry
      4. raw:source_type:name         — last resort
    """
    # 1. Try GitHub URL
    if source_url:
        m = _GITHUB_RE.match(source_url.strip())
        if m:
            owner_repo = m.group(1).lower()
            subpath = m.group(2)
            if subpath:
                return f"github:{owner_repo}{subpath.rstrip('/')}"
            return f"github:{owner_repo}"

    # 2. Try package identifier
    if package_identifier and registry_type:
        if registry_type == "npm":
            return f"npm:{package_identifier}"
        if registry_type == "pypi":
            return f"pypi:{package_identifier.lower()}"

    # 3. Last resort
    return f"raw:{source_type or 'unknown'}:{name or 'unnamed'}"


async def run_canonical_backfill() -> dict[str, int]:
    """Enrichment pass: recompute canonical_id for services missing it or stuck on raw:."""
    stats = {"updated": 0, "skipped": 0}

    async with SessionLocal() as db:
        result = await db.execute(
            select(McpService).where(
                or_(
                    McpService.canonical_id.is_(None),
                    McpService.canonical_id.startswith("raw:"),
                )
            )
        )
        services = result.scalars().all()
        logger.info("Canonical backfill: %d services to process", len(services))

        for svc in services:
            pkg = svc.package_info or {}
            new_cid = compute_canonical_id(
                source_url=svc.source_url,
                package_identifier=pkg.get("package_identifier"),
                registry_type=pkg.get("registry_type"),
                source_type=svc.source_type,
                name=svc.name,
            )
            if new_cid != svc.canonical_id:
                svc.canonical_id = new_cid
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

        await db.commit()

    logger.info("Canonical backfill done: %d updated, %d skipped", stats["updated"], stats["skipped"])
    return stats


def _extract_github_prefix(url: str | None) -> str | None:
    """Extract 'github:owner/repo' from a GitHub URL, or None."""
    if not url:
        return None
    m = _GITHUB_RE.match(url.strip())
    if m:
        return f"github:{m.group(1).lower()}"
    return None


def compute_skill_canonical_id(source_url: str | None, name: str) -> str:
    """Compute a canonical identifier for a skill: github:owner/repo:skill-name or raw:skill:name."""
    prefix = _extract_github_prefix(source_url)
    normalized_name = name.strip().lower()
    if prefix:
        return f"{prefix}:{normalized_name}"
    return f"raw:skill:{normalized_name}"


async def run_skill_canonical_backfill() -> dict[str, int]:
    """Enrichment pass: recompute canonical_id for skills missing it or stuck on raw:."""
    stats = {"updated": 0, "skipped": 0}

    async with SessionLocal() as db:
        result = await db.execute(
            select(Skill).where(
                or_(
                    Skill.canonical_id.is_(None),
                    Skill.canonical_id.startswith("raw:"),
                )
            )
        )
        skills = result.scalars().all()
        logger.info("Skill canonical backfill: %d skills to process", len(skills))

        for skill in skills:
            new_cid = compute_skill_canonical_id(
                source_url=skill.source_url,
                name=skill.name,
            )
            if new_cid != skill.canonical_id:
                skill.canonical_id = new_cid
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

        await db.commit()

    logger.info("Skill canonical backfill done: %d updated, %d skipped", stats["updated"], stats["skipped"])
    return stats
