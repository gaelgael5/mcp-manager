import asyncio
import logging

import typer

app = typer.Typer(name="mcp-manager", help="MCP Server Reference Manager")
logger = logging.getLogger(__name__)


@app.command()
def sync(source: str | None = typer.Option(None, help="Sync a specific source only")):
    """Sync MCP services from all registered sources."""
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_sync(source=source))
    typer.echo(f"Sync complete: {result['new']} new, {result['updated']} updated, {result['unchanged']} unchanged")


async def _run_sync(source: str | None = None) -> dict[str, int]:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService
    from mcp_manager.connectors.registry import get_all_connectors, get_connector

    # Import connector modules to trigger registration
    import mcp_manager.connectors.docker_registry  # noqa: F401
    import mcp_manager.connectors.mcp_registry  # noqa: F401

    if source:
        connector = get_connector(source)
        connectors = [connector] if connector else []
    else:
        connectors = get_all_connectors()

    stats = {"new": 0, "updated": 0, "unchanged": 0}
    for conn in connectors:
        services = await conn.fetch_services()
        async with SessionLocal() as db:
            for raw in services:
                result = await db.execute(
                    select(McpService).where(
                        McpService.source_type == raw.source_type,
                        McpService.name == raw.name,
                    )
                )
                existing = result.scalar_one_or_none()
                if not existing:
                    db.add(McpService(
                        name=raw.name, source_url=raw.source_url,
                        source_type=raw.source_type, doc_url=raw.doc_url,
                        doc_hash=raw.doc_hash, branch_hash=raw.branch_hash,
                        transport=raw.transport, category=raw.category,
                        tags=raw.tags, is_deprecated=raw.is_deprecated,
                    ))
                    stats["new"] += 1
                elif existing.doc_hash != raw.doc_hash or existing.branch_hash != raw.branch_hash:
                    existing.doc_url = raw.doc_url
                    existing.doc_hash = raw.doc_hash
                    existing.branch_hash = raw.branch_hash
                    existing.transport = raw.transport
                    existing.category = raw.category
                    existing.tags = raw.tags
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1
            await db.commit()
    return stats


@app.command()
def summarize(force: bool = typer.Option(False, help="Regenerate all summaries")):
    """Generate AI summaries for outdated or missing services."""
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(_run_summarize(force=force))
    typer.echo(f"Summaries generated: {count}")


async def _run_summarize(force: bool = False) -> int:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService, McpSummary
    from mcp_manager.summarizer.summarizer import generate_summary, CULTURES
    from mcp_manager.connectors.registry import get_connector
    from mcp_manager.connectors.base import RawMcpService

    import mcp_manager.connectors.docker_registry  # noqa: F401
    import mcp_manager.connectors.mcp_registry  # noqa: F401

    count = 0
    async with SessionLocal() as db:
        result = await db.execute(select(McpService))
        services = result.scalars().all()

        for service in services:
            connector = get_connector(service.source_type)
            if not connector:
                continue

            for culture in CULTURES:
                if not force:
                    existing = await db.execute(
                        select(McpSummary).where(
                            McpSummary.mcp_service_id == service.id,
                            McpSummary.culture == culture,
                        )
                    )
                    summary_row = existing.scalar_one_or_none()
                    if summary_row and summary_row.source_hash == service.doc_hash:
                        continue

                raw = RawMcpService(
                    name=service.name, source_url=service.source_url,
                    source_type=service.source_type, doc_url=service.doc_url,
                )
                doc_content = await connector.fetch_doc_content(raw)
                if not doc_content:
                    continue

                summary_text = await generate_summary(doc_content, culture)
                if not summary_text:
                    continue

                existing = await db.execute(
                    select(McpSummary).where(
                        McpSummary.mcp_service_id == service.id,
                        McpSummary.culture == culture,
                    )
                )
                summary_row = existing.scalar_one_or_none()
                if summary_row:
                    summary_row.summary = summary_text
                    summary_row.source_hash = service.doc_hash
                else:
                    db.add(McpSummary(
                        mcp_service_id=service.id, culture=culture,
                        summary=summary_text, source_hash=service.doc_hash,
                    ))
                count += 1
        await db.commit()
    return count


@app.command()
def export(
    target: str = typer.Option(..., help="Target name (claude_code, langgraph, docker_stdio)"),
    output: str | None = typer.Option(None, help="Output file path"),
):
    """Export installation recipes for a target."""
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_export(target=target, output=output))
    typer.echo(f"Exported {result} installations for {target}")


async def _run_export(target: str, output: str | None = None) -> int:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService, McpInstallation, InstallTarget
    from mcp_manager.exporters.engine import generate_installation_data

    count = 0
    async with SessionLocal() as db:
        target_result = await db.execute(select(InstallTarget).where(InstallTarget.name == target))
        target_row = target_result.scalar_one_or_none()
        if not target_row:
            typer.echo(f"Unknown target: {target}", err=True)
            raise typer.Exit(1)

        services_result = await db.execute(select(McpService).where(McpService.is_deprecated == False))
        services = services_result.scalars().all()

        for service in services:
            data = generate_installation_data(
                registry_type=None, package_identifier=None,
                runtime_hint=None, transport=service.transport,
                target_name=target, service_name=service.name, env_vars={},
            )
            if not data:
                continue

            existing = await db.execute(
                select(McpInstallation).where(
                    McpInstallation.mcp_service_id == service.id,
                    McpInstallation.install_target_id == target_row.id,
                )
            )
            install_row = existing.scalar_one_or_none()
            if install_row:
                install_row.action_type = data["action_type"]
                install_row.data = data["data"]
            else:
                db.add(McpInstallation(
                    mcp_service_id=service.id, install_target_id=target_row.id,
                    action_type=data["action_type"], data=data["data"],
                ))
            count += 1
        await db.commit()
    return count


if __name__ == "__main__":
    app()
