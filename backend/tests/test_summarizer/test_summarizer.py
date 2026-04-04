from unittest.mock import AsyncMock, patch

import pytest

from mcp_manager.summarizer.summarizer import generate_summary, CULTURES


def test_cultures_defined():
    assert "en" in CULTURES
    assert "fr" in CULTURES


@patch("mcp_manager.summarizer.summarizer.ollama_generate", new_callable=AsyncMock)
async def test_generate_summary_calls_ollama(mock_ollama):
    mock_ollama.return_value = "This is a test MCP server that does testing."
    result = await generate_summary("# Test Server\nA server for tests.", "en")
    assert result == "This is a test MCP server that does testing."
    mock_ollama.assert_called_once()


@patch("mcp_manager.summarizer.summarizer.ollama_generate", new_callable=AsyncMock)
async def test_generate_summary_french(mock_ollama):
    mock_ollama.return_value = "Un serveur MCP de test."
    result = await generate_summary("# Test Server\nA server for tests.", "fr")
    assert result == "Un serveur MCP de test."


async def test_generate_summary_empty_content():
    result = await generate_summary("", "en")
    assert result is None


async def test_generate_summary_none_content():
    result = await generate_summary(None, "en")
    assert result is None
