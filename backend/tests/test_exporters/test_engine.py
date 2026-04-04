from mcp_manager.exporters.engine import generate_installation_data


def test_npm_stdio_claude_code():
    result = generate_installation_data(
        registry_type="npm", package_identifier="@playwright/mcp",
        runtime_hint="npx", transport="stdio", target_name="claude_code",
        service_name="playwright", env_vars={"PLAYWRIGHT_HEADLESS": "Run headless"},
    )
    assert result["action_type"] == "cmd"
    assert "claude mcp add" in result["data"]
    assert "@playwright/mcp" in result["data"]


def test_npm_stdio_langgraph():
    result = generate_installation_data(
        registry_type="npm", package_identifier="@playwright/mcp",
        runtime_hint="npx", transport="stdio", target_name="langgraph",
        service_name="playwright", env_vars={},
    )
    assert result["action_type"] == "insert_in_file"
    assert '"command": "npx"' in result["data"]


def test_pypi_stdio_claude_code():
    result = generate_installation_data(
        registry_type="pypi", package_identifier="mcp-server-git",
        runtime_hint="uvx", transport="stdio", target_name="claude_code",
        service_name="git", env_vars={},
    )
    assert result["action_type"] == "cmd"
    assert "uvx" in result["data"]


def test_oci_docker_stdio():
    result = generate_installation_data(
        registry_type="oci", package_identifier="mcp/playwright:latest",
        runtime_hint="docker", transport="stdio", target_name="docker_stdio",
        service_name="playwright", env_vars={},
    )
    assert result["action_type"] == "docker_run"
    assert "docker run" in result["data"]


def test_unknown_target_returns_none():
    result = generate_installation_data(
        registry_type="npm", package_identifier="test",
        runtime_hint="npx", transport="stdio", target_name="unknown_target",
        service_name="test", env_vars={},
    )
    assert result is None
