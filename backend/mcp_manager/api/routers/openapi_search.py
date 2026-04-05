"""Serve OpenAPI spec for the public search API only."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

SEARCH_OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "MCP Manager — Public Search API",
        "description": "Search MCP servers and retrieve installation recipes for any target (Claude Code, VS Code, Cursor, etc.)",
        "version": "1.0.0",
    },
    "servers": [{"url": "/api/v1"}],
    "paths": {
        "/search": {
            "get": {
                "summary": "Search MCP servers",
                "description": "Full-text search with filters. Returns services with descriptions, parameters, and installation recipes.",
                "operationId": "searchServices",
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "Full-text search in name and summaries"},
                    {"name": "transport", "in": "query", "schema": {"type": "string", "enum": ["stdio", "sse", "streamable-http"]}, "description": "Filter by transport type"},
                    {"name": "category", "in": "query", "schema": {"type": "string"}, "description": "Filter by category (database, devops, ai, etc.)"},
                    {"name": "source_type", "in": "query", "schema": {"type": "string", "enum": ["docker_registry", "mcp_registry", "glama", "pulsemcp", "mcp_servers_repo"]}, "description": "Filter by source"},
                    {"name": "repo_status", "in": "query", "schema": {"type": "string", "enum": ["ok", "404"]}, "description": "Filter by repo accessibility"},
                    {"name": "has_summaries", "in": "query", "schema": {"type": "boolean"}, "description": "Filter by summary availability"},
                    {"name": "targets", "in": "query", "schema": {"type": "string"}, "description": "Comma-separated target names (claude_code, cursor, etc.). Filters recipes returned."},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1, "minimum": 1, "maximum": 1000}},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50}},
                ],
                "responses": {
                    "200": {
                        "description": "Search results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SearchResponse"},
                                "example": {
                                    "items": [
                                        {
                                            "id": "b38038e3-a305-4e13-a049-57e70eaefe37",
                                            "name": "mcp-server-fetch",
                                            "description": "MCP server that fetches web content and converts HTML to markdown for LLM consumption.",
                                            "source_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
                                            "doc_url": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
                                            "transport": "stdio",
                                            "category": "reference",
                                            "repo_status": "ok",
                                            "parameters": [],
                                            "recipes": {
                                                "claude_code": {
                                                    "action_type": "cmd",
                                                    "data": "claude mcp add mcp-server-fetch -- uvx mcp-server-fetch"
                                                },
                                                "cursor": {
                                                    "action_type": "insert_in_file",
                                                    "data": "{\"mcpServers\": {\"mcp-server-fetch\": {\"command\": \"uvx\", \"args\": [\"mcp-server-fetch\"]}}}"
                                                }
                                            }
                                        }
                                    ],
                                    "total": 1,
                                    "page": 1,
                                    "per_page": 10
                                },
                            }
                        },
                    }
                },
            }
        }
    },
    "components": {
        "schemas": {
            "SearchResponse": {
                "type": "object",
                "properties": {
                    "items": {"type": "array", "items": {"$ref": "#/components/schemas/ServiceResult"}},
                    "total": {"type": "integer"},
                    "page": {"type": "integer"},
                    "per_page": {"type": "integer"},
                },
            },
            "ServiceResult": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "nullable": True, "description": "English summary if available"},
                    "source_url": {"type": "string", "nullable": True, "description": "GitHub repository URL"},
                    "doc_url": {"type": "string", "nullable": True},
                    "transport": {"type": "string", "enum": ["stdio", "sse", "streamable-http"], "nullable": True},
                    "category": {"type": "string", "nullable": True},
                    "repo_status": {"type": "string", "enum": ["ok", "404"], "nullable": True},
                    "parameters": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Parameter"},
                        "description": "Required environment variables / config parameters",
                    },
                    "recipes": {
                        "type": "object",
                        "additionalProperties": {"$ref": "#/components/schemas/Recipe"},
                        "description": "Installation recipes keyed by target name",
                    },
                },
            },
            "Parameter": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Environment variable name"},
                    "description": {"type": "string", "nullable": True},
                    "is_required": {"type": "boolean"},
                    "is_secret": {"type": "boolean", "description": "True for tokens, keys, passwords"},
                },
            },
            "Recipe": {
                "type": "object",
                "properties": {
                    "action_type": {"type": "string", "enum": ["cmd", "insert_in_file", "docker_run"]},
                    "data": {"type": "string", "description": "The command or config snippet to install the MCP server"},
                },
            },
        }
    },
}


@router.get("/openapi-search.json")
async def get_search_openapi():
    return JSONResponse(content=SEARCH_OPENAPI_SPEC)
