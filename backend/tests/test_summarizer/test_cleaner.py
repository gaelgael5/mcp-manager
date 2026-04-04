from mcp_manager.summarizer.cleaner import clean_markdown


def test_removes_badges():
    md = "# Server\n[![Build](https://img.shields.io/badge.svg)](url)\nContent here."
    result = clean_markdown(md)
    assert "img.shields.io" not in result
    assert "Content here." in result


def test_removes_image_lines():
    md = "# Server\n![screenshot](https://example.com/img.png)\nUseful text."
    result = clean_markdown(md)
    assert "screenshot" not in result
    assert "Useful text." in result


def test_removes_contributing_section():
    md = "# Server\nMain content.\n## Contributing\nPlease submit PRs.\n## License\nMIT"
    result = clean_markdown(md)
    assert "Main content." in result
    assert "Please submit PRs" not in result
    assert "MIT" not in result


def test_preserves_code_blocks():
    md = "# Usage\n```bash\nnpx @test/mcp\n```\nDone."
    result = clean_markdown(md)
    assert "npx @test/mcp" in result


def test_empty_input():
    assert clean_markdown("") == ""
    assert clean_markdown(None) == ""
