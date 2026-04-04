import pytest

from mcp_manager.connectors.mcp_registry import McpRegistryConnector


@pytest.fixture
def connector():
    return McpRegistryConnector()


def test_source_type(connector):
    assert connector.source_type() == "mcp_registry"


async def test_parse_server_json(connector):
    server_data = {
        "name": "io.github.domdomegg/airtable-mcp-server",
        "description": "Read and write access to Airtable",
        "version": "1.7.2",
        "websiteUrl": "https://github.com/domdomegg/airtable-mcp-server",
        "repository": {
            "url": "https://github.com/domdomegg/airtable-mcp-server",
            "source": "github",
            "subfolder": "packages/server",
        },
        "packages": [
            {
                "registryType": "npm",
                "identifier": "@domdomegg/airtable-mcp-server",
                "version": "1.7.2",
                "runtimeHint": "npx",
                "transport": {"type": "stdio"},
                "environmentVariables": [
                    {"name": "AIRTABLE_API_KEY", "isRequired": True, "isSecret": True}
                ],
            }
        ],
    }
    service = connector._parse_server_json(server_data)
    assert service.name == "io.github.domdomegg/airtable-mcp-server"
    assert service.transport == "stdio"
    assert service.registry_type == "npm"
    assert service.package_identifier == "@domdomegg/airtable-mcp-server"
    assert service.runtime_hint == "npx"
    assert "AIRTABLE_API_KEY" in service.env_vars


async def test_resolve_doc_url_with_subfolder(connector):
    service_data = {
        "name": "test",
        "description": "test",
        "version": "1.0.0",
        "repository": {
            "url": "https://github.com/microsoft/markitdown",
            "source": "github",
            "subfolder": "packages/markitdown-mcp",
        },
        "packages": [],
    }
    service = connector._parse_server_json(service_data)
    assert service.doc_url == "https://github.com/microsoft/markitdown/tree/main/packages/markitdown-mcp"


async def test_parse_remote_server(connector):
    server_data = {
        "name": "com.cloudflare/docs",
        "description": "Cloudflare documentation",
        "version": "1.0.0",
        "remotes": [
            {"type": "sse", "url": "https://docs.mcp.cloudflare.com/sse"}
        ],
    }
    service = connector._parse_server_json(server_data)
    assert service.transport == "sse"
