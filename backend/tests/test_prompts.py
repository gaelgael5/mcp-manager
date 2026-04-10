"""Tests for mcp_manager.prompts helper module."""
import pytest

from mcp_manager.prompts import (
    PROMPT_KINDS,
    PromptNotFound,
    load_prompt,
    prompt_path,
    render_prompt,
    write_prompt,
)


def test_prompt_kinds_is_tuple():
    assert isinstance(PROMPT_KINDS, tuple)
    assert set(PROMPT_KINDS) == {"summarize", "skill_summary", "source_summary"}


def test_prompt_path_rejects_unknown_kind():
    with pytest.raises(ValueError):
        prompt_path("bogus", "en")


def test_prompt_path_builds_expected_name():
    path = prompt_path("skill_summary", "en")
    assert path.name == "skill_summary.md"
    assert path.parent.name == "en"


def test_load_existing_en_prompt():
    content = load_prompt("summarize", "en")
    assert "{content}" in content


def test_load_missing_language_raises():
    with pytest.raises(PromptNotFound):
        load_prompt("summarize", "xx")


def test_render_substitutes_placeholder():
    assert render_prompt("hello {content}", "world") == "hello world"


def test_render_without_placeholder_returns_as_is():
    assert render_prompt("no placeholder", "ignored") == "no placeholder"


def test_write_and_readback(tmp_path, monkeypatch):
    import mcp_manager.prompts as mod
    monkeypatch.setattr(mod, "PROMPTS_DIR", tmp_path)
    write_prompt("summarize", "xx", "custom {content}")
    assert (tmp_path / "xx" / "summarize.md").read_text(encoding="utf-8") == "custom {content}"
    assert load_prompt("summarize", "xx") == "custom {content}"
