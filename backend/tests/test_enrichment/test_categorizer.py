from unittest.mock import AsyncMock, patch

import pytest
from mcp_manager.enrichment.categorizer import CATEGORIES, parse_category_response


def test_categories_defined():
    assert "database" in CATEGORIES
    assert "devops" in CATEGORIES
    assert "ai" in CATEGORIES
    assert len(CATEGORIES) > 20


def test_parse_valid_category():
    assert parse_category_response("database") == "database"


def test_parse_category_with_whitespace():
    assert parse_category_response("  devops  \n") == "devops"


def test_parse_category_case_insensitive():
    assert parse_category_response("DevOps") == "devops"


def test_parse_invalid_category():
    assert parse_category_response("not-a-real-category") is None


def test_parse_empty():
    assert parse_category_response("") is None


def test_parse_sentence_response():
    assert parse_category_response("The category is database.") is None


@patch("mcp_manager.enrichment.categorizer.ollama_generate", new_callable=AsyncMock)
async def test_categorize_single(mock_ollama):
    from mcp_manager.enrichment.categorizer import categorize_single
    mock_ollama.return_value = "database"
    result = await categorize_single("postgres-mcp", "PostgreSQL database access")
    assert result == "database"
    mock_ollama.assert_called_once()


@patch("mcp_manager.enrichment.categorizer.ollama_generate", new_callable=AsyncMock)
async def test_categorize_single_empty_description(mock_ollama):
    from mcp_manager.enrichment.categorizer import categorize_single
    result = await categorize_single("test", "")
    assert result is None
    mock_ollama.assert_not_called()
