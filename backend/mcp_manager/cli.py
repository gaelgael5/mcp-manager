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


def _build_package_info(raw) -> dict:
    """Build package_info dict from RawMcpService fields."""
    info = {}
    if raw.registry_type:
        info["registry_type"] = raw.registry_type
    if raw.package_identifier:
        info["package_identifier"] = raw.package_identifier
    if raw.runtime_hint:
        info["runtime_hint"] = raw.runtime_hint
    if raw.env_vars:
        info["env_vars"] = raw.env_vars
    return info


async def _run_sync(source: str | None = None) -> dict[str, int]:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService
    from mcp_manager.connectors.registry import get_all_connectors, get_connector
    from mcp_manager.enrichment.canonical import compute_canonical_id

    import mcp_manager.connectors  # noqa: F401 — registers all connectors

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
                pkg_info = _build_package_info(raw)
                cid = compute_canonical_id(
                    source_url=raw.source_url,
                    package_identifier=raw.package_identifier,
                    registry_type=raw.registry_type,
                    source_type=raw.source_type,
                    name=raw.name,
                )

                if not existing:
                    db.add(McpService(
                        name=raw.name, source_url=raw.source_url,
                        source_type=raw.source_type, doc_url=raw.doc_url,
                        doc_hash=raw.doc_hash, branch_hash=raw.branch_hash,
                        transport=raw.transport, category=raw.category,
                        tags=raw.tags, is_deprecated=raw.is_deprecated,
                        package_info=pkg_info,
                        canonical_id=cid,
                    ))
                    stats["new"] += 1
                elif existing.doc_hash != raw.doc_hash or existing.branch_hash != raw.branch_hash:
                    existing.doc_url = raw.doc_url
                    existing.doc_hash = raw.doc_hash
                    existing.branch_hash = raw.branch_hash
                    existing.transport = raw.transport
                    existing.category = raw.category
                    existing.tags = raw.tags
                    existing.canonical_id = cid
                    if pkg_info:
                        existing.package_info = pkg_info
                    stats["updated"] += 1
                elif not existing.package_info and pkg_info:
                    existing.package_info = pkg_info
                    existing.canonical_id = cid
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
    from mcp_manager.summarizer.summarizer import generate_summary
    from mcp_manager.prompts import get_active_language_codes
    from mcp_manager.connectors.registry import get_connector
    from mcp_manager.connectors.base import RawMcpService


    count = 0
    async with SessionLocal() as db:
        cultures = await get_active_language_codes(db)
        result = await db.execute(select(McpService))
        services = result.scalars().all()

        for service in services:
            connector = get_connector(service.source_type)
            if not connector:
                continue

            for culture in cultures:
                if not force:
                    existing = await db.execute(
                        select(McpSummary).where(
                            McpSummary.parent_id == service._id,
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
                        McpSummary.parent_id == service._id,
                        McpSummary.culture == culture,
                    )
                )
                from mcp_manager.summarizer.ollama_client import get_current_llm_name
                llm_name = get_current_llm_name()
                summary_row = existing.scalar_one_or_none()
                if summary_row:
                    summary_row.summary = summary_text
                    summary_row.source_hash = service.doc_hash
                    summary_row.llm = llm_name
                else:
                    db.add(McpSummary(
                        parent_id=service._id, culture=culture,
                        summary=summary_text, source_hash=service.doc_hash,
                        llm=llm_name,
                    ))
                count += 1
        await db.commit()
    return count


@app.command()
def export(
    target: str = typer.Option("all", help="Target name or 'all' for all targets"),
):
    """Generate installation recipes for services using target modes."""
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_export(target=target))
    typer.echo(f"Export complete: {result}")


async def _run_export(target: str) -> dict[str, int]:
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService, McpInstallation, InstallTarget
    from mcp_manager.exporters.engine import generate_from_modes, generate_installation_data

    stats: dict[str, int] = {}

    async with SessionLocal() as db:
        # Get targets
        if target == "all":
            targets_result = await db.execute(select(InstallTarget))
            targets = targets_result.scalars().all()
        else:
            targets_result = await db.execute(select(InstallTarget).where(InstallTarget.name == target))
            t = targets_result.scalar_one_or_none()
            if not t:
                typer.echo(f"Unknown target: {target}", err=True)
                raise typer.Exit(1)
            targets = [t]

        # Get all active services with package_info
        services_result = await db.execute(
            select(McpService).where(McpService.is_deprecated == False)
        )
        services = services_result.scalars().all()

        for t in targets:
            count = 0
            for service in services:
                pkg = service.package_info or {}

                # Use DB modes if available
                if t.modes:
                    data = generate_from_modes(
                        modes=t.modes,
                        runtime_hint=pkg.get("runtime_hint"),
                        package_identifier=pkg.get("package_identifier"),
                        service_name=service.name,
                        env_vars=pkg.get("env_vars", {}),
                    )
                else:
                    data = generate_installation_data(
                        registry_type=pkg.get("registry_type"),
                        package_identifier=pkg.get("package_identifier"),
                        runtime_hint=pkg.get("runtime_hint"),
                        transport=service.transport,
                        target_name=t.name,
                        service_name=service.name,
                        env_vars=pkg.get("env_vars", {}),
                    )

                if not data:
                    continue

                existing = await db.execute(
                    select(McpInstallation).where(
                        McpInstallation.parent_id == service._id,
                        McpInstallation.install_target_id == t.id,
                    )
                )
                install_row = existing.scalar_one_or_none()
                if install_row:
                    install_row.action_type = data["action_type"]
                    install_row.data = data["data"]
                else:
                    db.add(McpInstallation(
                        parent_id=service._id, install_target_id=t.id,
                        action_type=data["action_type"], data=data["data"],
                    ))
                count += 1

            stats[t.name] = count
            logger.info("Export %s: %d recipes", t.name, count)

        await db.commit()
    return stats


@app.command()
def enrich(
    pass_name: str | None = typer.Option(None, "--pass", help="Run a specific pass: url-resolve, dedup, categorize"),
):
    """Enrich service data: resolve URLs, deduplicate, auto-categorize."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_enrich(pass_name=pass_name))


async def _run_enrich(pass_name: str | None = None) -> None:
    from mcp_manager.enrichment.url_resolver import run_url_resolve
    from mcp_manager.enrichment.dedup import run_dedup
    from mcp_manager.enrichment.categorizer import run_categorize
    from mcp_manager.enrichment.repo_checker import run_repo_check, run_stars_update
    from mcp_manager.enrichment.canonical import run_canonical_backfill

    passes = {
        "url-resolve": ("URL Resolve", run_url_resolve),
        "canonical": ("Canonical ID", run_canonical_backfill),
        "dedup": ("Deduplication", run_dedup),
        "repo-check": ("Repo Check", run_repo_check),
        "stars": ("Stars Update", run_stars_update),
        "categorize": ("Auto-categorize", run_categorize),
    }

    if pass_name:
        if pass_name not in passes:
            typer.echo(f"Unknown pass: {pass_name}. Available: {', '.join(passes.keys())}", err=True)
            raise typer.Exit(1)
        label, func = passes[pass_name]
        typer.echo(f"Running {label}...")
        result = await func()
        typer.echo(f"{label} complete: {result}")
    else:
        for name, (label, func) in passes.items():
            typer.echo(f"\n=== {label} ===")
            result = await func()
            typer.echo(f"{label}: {result}")
        typer.echo("\nEnrichment complete.")


@app.command("fetch-branch-shas")
def fetch_branch_shas(
    concurrency: int = typer.Option(10, help="Max parallel GitHub API calls"),
):
    """Batch: fetch HEAD SHA of default branch for each service with
    needs_reindex=true and store it in mcp_services.branch_hash. Does not
    touch any other column, does not reset needs_reindex."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_fetch_branch_shas(concurrency=concurrency))


async def _fetch_branch_shas(concurrency: int):
    """Fetch branch SHAs for flagged services, deduplicating by source_url so
    repos shared by multiple services are only queried once."""
    from collections import defaultdict
    from sqlalchemy import select, update as sa_update
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService
    from mcp_manager.connectors.github_readme import fetch_branch_sha
    from mcp_manager.connectors.token_pool import load_tokens

    await load_tokens()

    async with SessionLocal() as db:
        result = await db.execute(
            select(McpService.id, McpService.source_url, McpService.branch_hash)
            .where(McpService.needs_reindex == True)
            .where(McpService.source_url.ilike("%github.com%"))
        )
        rows = result.all()

    total_services = len(rows)

    # Group services by source_url so one HTTP call covers all duplicates.
    by_url: dict[str, list[tuple]] = defaultdict(list)
    for svc_id, source_url, current_hash in rows:
        by_url[source_url].append((svc_id, current_hash))

    unique_urls = list(by_url.keys())
    total_urls = len(unique_urls)
    typer.echo(
        f"Fetching branch SHAs for {total_services} services "
        f"across {total_urls} unique repos (concurrency={concurrency})"
    )

    stats = {
        "processed_urls": 0,
        "services_updated": 0,
        "services_unchanged": 0,
        "services_failed": 0,
    }
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(url: str) -> tuple[str, str | None]:
        async with semaphore:
            sha = await fetch_branch_sha(url)
            return url, sha

    chunk_size = 100
    for i in range(0, total_urls, chunk_size):
        chunk = unique_urls[i:i + chunk_size]
        results = await asyncio.gather(*(_one(u) for u in chunk))

        async with SessionLocal() as db:
            for url, new_hash in results:
                stats["processed_urls"] += 1
                services_for_url = by_url[url]
                if new_hash is None:
                    stats["services_failed"] += len(services_for_url)
                    continue
                for svc_id, current_hash in services_for_url:
                    if new_hash == current_hash:
                        stats["services_unchanged"] += 1
                        continue
                    await db.execute(
                        sa_update(McpService)
                        .where(McpService.id == svc_id)
                        .values(branch_hash=new_hash)
                    )
                    stats["services_updated"] += 1
            await db.commit()

        typer.echo(
            f"  [urls={stats['processed_urls']}/{total_urls}] "
            f"updated={stats['services_updated']} "
            f"unchanged={stats['services_unchanged']} "
            f"failed={stats['services_failed']}"
        )

    typer.echo(f"Done: {stats}")


@app.command()
def index(
    limit: int = typer.Option(100, help="Max number of services to index per run"),
):
    """Run indexation pipeline on services flagged needs_reindex."""
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_index(limit=limit))
    typer.echo(f"Index complete: {result}")


async def _run_index(limit: int) -> dict:
    from mcp_manager.indexer.pipeline import run_index
    from mcp_manager.llm.manager import LLMManager

    manager = LLMManager(batch_id="mcp", pipeline="mcp")
    manager.load()
    typer.echo(f"LLM providers: {len(manager.drivers)} loaded")
    await manager.start_all()
    try:
        return await run_index(limit=limit, manager=manager)
    finally:
        await manager.stop_all()
        typer.echo("LLM providers stopped")


@app.command()
def sync_instances():
    """Sync services from all active MCP Manager instances."""
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_sync_instances())
    typer.echo(f"Instance sync complete: {result}")


async def _run_sync_instances() -> dict[str, int]:
    from sqlalchemy import select
    from datetime import datetime, timezone
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import McpService, McpInstance
    from mcp_manager.connectors.mcp_manager_instance import McpManagerInstanceConnector

    stats = {"new": 0, "updated": 0, "instances": 0}

    async with SessionLocal() as db:
        result = await db.execute(
            select(McpInstance).where(McpInstance.is_active == True)
        )
        instances = result.scalars().all()

        for instance in instances:
            logger.info("Syncing instance: %s (%s)", instance.name, instance.url)
            connector = McpManagerInstanceConnector(
                instance_url=instance.url,
                api_key=instance.api_key,
                last_sync=instance.last_sync.isoformat() if instance.last_sync else None,
            )
            try:
                services = await connector.fetch_services()
                count = 0
                for raw in services:
                    existing = await db.execute(
                        select(McpService).where(
                            McpService.source_type == "mcp_instance",
                            McpService.name == raw.name,
                        )
                    )
                    existing_svc = existing.scalar_one_or_none()
                    if not existing_svc:
                        db.add(McpService(
                            name=raw.name, source_url=raw.source_url,
                            source_type="mcp_instance", doc_url=raw.doc_url,
                            transport=raw.transport, category=raw.category,
                        ))
                        stats["new"] += 1
                        count += 1
                    else:
                        stats["updated"] += 1

                instance.last_sync = datetime.now(timezone.utc)
                instance.last_sync_count = count
                stats["instances"] += 1
                await db.commit()
                logger.info("Instance %s: %d new services", instance.name, count)
            except Exception:
                logger.exception("Failed to sync instance %s", instance.name)

    return stats


@app.command()
def scrape_skills(
    limit: int | None = typer.Option(None, help="Max number of skills to scrape"),
    skip_summaries: bool = typer.Option(False, help="Skip summary generation"),
):
    """Scrape skills.sh catalog into SkillSources + Skills."""
    logging.basicConfig(level=logging.INFO)
    from scripts.scrape_skills_sh import scrape_skills_sh
    asyncio.run(scrape_skills_sh(limit=limit, skip_summaries=skip_summaries))
    typer.echo("Scrape complete.")


if __name__ == "__main__":
    app()
