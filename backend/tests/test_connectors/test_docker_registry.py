import pytest

from mcp_manager.connectors.docker_registry import DockerRegistryConnector


@pytest.fixture
def connector():
    return DockerRegistryConnector()


def test_source_type(connector):
    assert connector.source_type() == "docker_registry"


async def test_parse_server_yaml(connector):
    yaml_content = """
name: playwright
type: server
title: Playwright MCP Server
description: Browser automation and web scraping
image: mcp/playwright:latest
meta:
  category: Development
  tags:
    - browser
    - testing
source:
  project: https://github.com/playwright/playwright-mcp
  commit: abc123
"""
    service = connector._parse_server_yaml("playwright", yaml_content)
    assert service.name == "playwright"
    assert service.source_type == "docker_registry"
    assert service.category == "Development"
    assert "browser" in service.tags
    assert "testing" in service.tags
    assert service.source_url == "https://github.com/playwright/playwright-mcp"


async def test_parse_server_yaml_remote_type(connector):
    yaml_content = """
name: cloudflare-docs
type: remote
title: Cloudflare Docs
description: Access Cloudflare documentation
remote:
  transport_type: sse
  url: https://docs.mcp.cloudflare.com/sse
"""
    service = connector._parse_server_yaml("cloudflare-docs", yaml_content)
    assert service.name == "cloudflare-docs"
    assert service.transport == "sse"


async def test_parse_server_yaml_missing_source(connector):
    yaml_content = """
name: minimal
type: server
title: Minimal Server
description: A minimal server
"""
    service = connector._parse_server_yaml("minimal", yaml_content)
    assert service.name == "minimal"
    assert service.source_url == ""
