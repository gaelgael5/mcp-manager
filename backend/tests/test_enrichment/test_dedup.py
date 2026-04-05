from mcp_manager.enrichment.dedup import normalize_url, find_name_match


def test_normalize_url_trailing_slash():
    assert normalize_url("https://github.com/test/repo/") == "https://github.com/test/repo"


def test_normalize_url_uppercase():
    assert normalize_url("https://GitHub.com/Test/Repo") == "https://github.com/test/repo"


def test_normalize_url_empty():
    assert normalize_url("") == ""
    assert normalize_url(None) == ""


def test_find_name_match_suffix():
    assert find_name_match("brave", "io.github.brave/brave-search-mcp-server") is True


def test_find_name_match_exact_suffix():
    assert find_name_match("docker", "io.github.Dave-London/docker") is True


def test_find_name_match_no_match():
    assert find_name_match("brave", "io.github.appium/appium-mcp") is False


def test_find_name_match_empty():
    assert find_name_match("", "io.github.test/test") is False
    assert find_name_match("test", "") is False
