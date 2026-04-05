import logging

from sqlalchemy import select, delete

from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import McpService

logger = logging.getLogger(__name__)


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    return url.strip().rstrip("/").lower()


def find_name_match(docker_name: str, mcp_name: str) -> bool:
    if not docker_name or not mcp_name:
        return False
    if "/" not in mcp_name:
        return False
    repo_part = mcp_name.split("/", 1)[1]
    return docker_name == repo_part or repo_part.endswith(docker_name) or repo_part.startswith(docker_name)


async def run_dedup() -> dict[str, int]:
    stats = {"merged": 0, "skipped": 0}

    async with SessionLocal() as db:
        docker_result = await db.execute(
            select(McpService).where(McpService.source_type == "docker_registry")
        )
        docker_services = docker_result.scalars().all()

        mcp_result = await db.execute(
            select(McpService).where(McpService.source_type == "mcp_registry")
        )
        mcp_services = mcp_result.scalars().all()

        mcp_by_url: dict[str, list[McpService]] = {}
        for mcp in mcp_services:
            url = normalize_url(mcp.source_url)
            if url:
                mcp_by_url.setdefault(url, []).append(mcp)

        for docker_svc in docker_services:
            docker_url = normalize_url(docker_svc.source_url)
            matches: list[McpService] = []

            if docker_url and docker_url in mcp_by_url:
                matches.extend(mcp_by_url[docker_url])

            if not matches:
                for mcp in mcp_services:
                    if find_name_match(docker_svc.name, mcp.name):
                        matches.append(mcp)

            if not matches:
                stats["skipped"] += 1
                continue

            for mcp_match in matches:
                if mcp_match.branch_hash and (
                    not docker_svc.branch_hash or mcp_match.branch_hash > docker_svc.branch_hash
                ):
                    docker_svc.branch_hash = mcp_match.branch_hash

                if not docker_svc.doc_url and mcp_match.doc_url:
                    docker_svc.doc_url = mcp_match.doc_url

                origins = set(docker_svc.source_origins or [])
                origins.add("docker_registry")
                origins.add("mcp_registry")
                docker_svc.source_origins = list(origins)

                await db.execute(
                    delete(McpService).where(McpService.id == mcp_match.id)
                )
                stats["merged"] += 1

                logger.debug("Merged: %s <- %s", docker_svc.name, mcp_match.name)

        await db.commit()

    logger.info("Dedup done: %d merged, %d skipped", stats["merged"], stats["skipped"])
    return stats
