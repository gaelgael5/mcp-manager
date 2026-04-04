import uuid

import pytest
import sqlalchemy
from sqlalchemy import select

from mcp_manager.db.models import InstallTarget, McpInstallation, McpService, McpSummary


async def test_create_mcp_service(db):
    service = McpService(
        name="test-server",
        source_url="https://github.com/test/test-mcp",
        source_type="docker_registry",
        transport="stdio",
    )
    db.add(service)
    await db.flush()

    result = await db.execute(select(McpService).where(McpService.name == "test-server"))
    row = result.scalar_one()
    assert row.name == "test-server"
    assert row.source_type == "docker_registry"
    assert row.is_deprecated is False
    assert isinstance(row.id, uuid.UUID)


async def test_create_summary_linked_to_service(db):
    service = McpService(
        name="summary-test",
        source_url="https://github.com/test/test",
        source_type="mcp_registry",
    )
    db.add(service)
    await db.flush()

    summary = McpSummary(
        mcp_service_id=service.id,
        culture="fr",
        summary="Un serveur MCP de test.",
        source_hash="abc123",
    )
    db.add(summary)
    await db.flush()

    result = await db.execute(
        select(McpSummary).where(McpSummary.mcp_service_id == service.id)
    )
    row = result.scalar_one()
    assert row.culture == "fr"
    assert row.summary == "Un serveur MCP de test."


async def test_create_installation_with_target(db):
    service = McpService(
        name="install-test",
        source_url="https://github.com/test/test",
        source_type="docker_registry",
    )
    target = InstallTarget(name="claude_code_test", description="Test target")
    db.add_all([service, target])
    await db.flush()

    install = McpInstallation(
        mcp_service_id=service.id,
        install_target_id=target.id,
        action_type="cmd",
        data="claude mcp add test -- npx @test/mcp@latest",
        env_vars={"TEST_KEY": "test_value"},
    )
    db.add(install)
    await db.flush()

    result = await db.execute(
        select(McpInstallation).where(McpInstallation.mcp_service_id == service.id)
    )
    row = result.scalar_one()
    assert row.action_type == "cmd"
    assert row.env_vars == {"TEST_KEY": "test_value"}


async def test_unique_constraint_source_type_name(db):
    s1 = McpService(name="dup-test", source_url="https://a.com", source_type="docker_registry")
    s2 = McpService(name="dup-test", source_url="https://b.com", source_type="docker_registry")
    db.add(s1)
    await db.flush()
    db.add(s2)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await db.flush()
