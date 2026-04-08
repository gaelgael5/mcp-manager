"""Serve OpenAPI spec for the public search API only."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

SEARCH_OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "MCP Manager — Public API",
        "description": "Search MCP servers, list install targets, and retrieve installation recipes for any target (Claude Code, VS Code, Cursor, etc.)",
        "version": "1.0.0",
    },
    "servers": [{"url": "/api/v1"}],
    "paths": {
        "/targets": {
            "get": {
                "summary": "List install targets",
                "description": "Returns all available installation targets (Claude Desktop, VS Code, Cursor, etc.) with their configuration modes.",
                "operationId": "listTargets",
                "responses": {
                    "200": {
                        "description": "List of targets",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Target"},
                                },
                                "example": [
                                    {
                                        "id": "a1b2c3d4-...",
                                        "name": "claude_desktop",
                                        "description": "Claude Desktop (claude_desktop_config.json)",
                                        "modes": [{"runtime": "npx", "action_type": "insert_in_file", "template": "..."}],
                                    }
                                ],
                            }
                        },
                    }
                },
            }
        },
        "/search_skill_sources": {
            "get": {
                "summary": "Search skill sources",
                "description": "Search skill source repositories (Claude, Copilot, Gemini, Cursor skills) with text filters and pagination. Returns sources sorted by GitHub stars.",
                "operationId": "searchSkillSources",
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "Search in name, description, summaries, and repo URL"},
                    {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["claude", "copilot", "gemini", "cursor"]}, "description": "Filter by skill type"},
                    {"name": "repo_status", "in": "query", "schema": {"type": "string", "enum": ["ok", "repo_404", "no_skills_dir"]}, "description": "Filter by repo status"},
                    {"name": "has_summary", "in": "query", "schema": {"type": "boolean"}, "description": "Filter by summary availability"},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1, "minimum": 1, "maximum": 1000}},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50}},
                ],
                "responses": {
                    "200": {
                        "description": "Search results",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "items": {"type": "array", "items": {"$ref": "#/components/schemas/SkillSourceResult"}},
                                        "total": {"type": "integer"},
                                        "page": {"type": "integer"},
                                        "per_page": {"type": "integer"},
                                    },
                                },
                            }
                        },
                    }
                },
            }
        },
        "/search_skills": {
            "get": {
                "summary": "Search skills",
                "description": "Search skills (Claude, Copilot, Gemini, Cursor) with text filters and pagination. Returns skills sorted by weekly installs.",
                "operationId": "searchSkills",
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "Search in name, description, and summaries"},
                    {"name": "canonical_id", "in": "query", "schema": {"type": "string"}, "description": "Exact match on canonical_id (e.g. github:owner/repo:skill-name). Bypasses text search."},
                    {"name": "target_type", "in": "query", "schema": {"type": "string", "enum": ["claude", "copilot", "gemini", "cursor"]}, "description": "Filter by target type"},
                    {"name": "category", "in": "query", "schema": {"type": "string"}, "description": "Filter by category"},
                    {"name": "has_summary", "in": "query", "schema": {"type": "boolean"}, "description": "Filter by summary availability"},
                    {"name": "source_id", "in": "query", "schema": {"type": "string", "format": "uuid"}, "description": "Filter by skill source ID"},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1, "minimum": 1, "maximum": 1000}},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50}},
                ],
                "responses": {
                    "200": {
                        "description": "Search results",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "items": {"type": "array", "items": {"$ref": "#/components/schemas/SkillResult"}},
                                        "total": {"type": "integer"},
                                        "page": {"type": "integer"},
                                        "per_page": {"type": "integer"},
                                    },
                                },
                            }
                        },
                    }
                },
            }
        },
        "/search_mcp": {
            "get": {
                "summary": "Search MCP servers",
                "description": "Full-text search with filters. Returns services with descriptions, parameters, and installation recipes.",
                "operationId": "searchServices",
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}, "description": "Full-text search in name and summaries (or semantic query when semantic=true)"},
                    {"name": "canonical_id", "in": "query", "schema": {"type": "string"}, "description": "Exact match on canonical_id (e.g. github:owner/repo). Bypasses text/semantic search."},
                    {"name": "semantic", "in": "query", "schema": {"type": "boolean", "default": False}, "description": "Enable semantic search via pgvector embeddings (requires q). Returns results ranked by similarity."},
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
                                            "stars": 15200,
                                            "canonical_id": "github:modelcontextprotocol/servers/src/fetch",
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
                    "stars": {"type": "integer", "nullable": True, "description": "GitHub stars"},
                    "canonical_id": {"type": "string", "nullable": True, "description": "Canonical identifier (e.g. github:owner/repo, npm:@scope/pkg)"},
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
            "SkillResult": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "nullable": True},
                    "summary_en": {"type": "string", "nullable": True, "description": "English summary"},
                    "target_type": {"type": "string", "enum": ["claude", "copilot", "gemini", "cursor"]},
                    "has_summary": {"type": "boolean"},
                    "category": {"type": "string", "nullable": True},
                    "licence": {"type": "string", "nullable": True},
                    "source_url": {"type": "string", "nullable": True, "description": "GitHub source URL"},
                    "canonical_id": {"type": "string", "nullable": True, "description": "Canonical identifier (e.g. github:owner/repo:skill-name)"},
                    "install_command": {"type": "string", "nullable": True, "description": "Command to install this skill"},
                    "weekly_installs": {"type": "integer", "description": "Number of weekly installs"},
                    "created_at": {"type": "string", "format": "date-time", "nullable": True},
                },
            },
            "SkillSourceResult": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string"},
                    "url": {"type": "string", "description": "Source URL"},
                    "repo_url": {"type": "string", "nullable": True, "description": "GitHub repository URL"},
                    "type": {"type": "string", "enum": ["claude", "copilot", "gemini", "cursor"]},
                    "description": {"type": "string", "nullable": True},
                    "summary_en": {"type": "string", "nullable": True, "description": "English summary"},
                    "has_summary": {"type": "boolean"},
                    "repo_status": {"type": "string", "nullable": True},
                    "stars": {"type": "integer", "nullable": True, "description": "GitHub stars"},
                    "skills_count": {"type": "integer", "description": "Number of skills in this source"},
                    "last_sync": {"type": "string", "format": "date-time", "nullable": True},
                },
            },
            "Target": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string", "description": "Target identifier (claude_desktop, cursor, etc.)"},
                    "description": {"type": "string", "nullable": True},
                    "modes": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/TargetMode"},
                        "description": "Available installation modes for this target",
                    },
                },
            },
            "TargetMode": {
                "type": "object",
                "properties": {
                    "runtime": {"type": "string", "description": "Package manager (npx, uvx, docker, etc.)"},
                    "action_type": {"type": "string", "enum": ["cmd", "insert_in_file", "docker_run"]},
                    "template": {"type": "string", "description": "Template for generating install recipes"},
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
