import pytest
from mcp_manager.enrichment.url_resolver import parse_reverse_dns_to_github_url


def test_io_github_pattern():
    url = parse_reverse_dns_to_github_url("io.github.appium/appium-mcp")
    assert url == "https://github.com/appium/appium-mcp"


def test_io_github_dotted_owner():
    url = parse_reverse_dns_to_github_url("io.github.some.user/my-repo")
    assert url == "https://github.com/some.user/my-repo"


def test_com_domain_pattern():
    url = parse_reverse_dns_to_github_url("com.example/my-server")
    assert url == "https://github.com/example/my-server"


def test_ai_domain_pattern():
    url = parse_reverse_dns_to_github_url("ai.smithery/brave")
    assert url == "https://github.com/smithery/brave"


def test_no_slash_returns_none():
    url = parse_reverse_dns_to_github_url("just-a-name")
    assert url is None


def test_empty_returns_none():
    url = parse_reverse_dns_to_github_url("")
    assert url is None


def test_already_has_github_in_name():
    url = parse_reverse_dns_to_github_url("io.github.brave/brave-search-mcp-server")
    assert url == "https://github.com/brave/brave-search-mcp-server"
