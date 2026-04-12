"""Serve OpenAPI spec for the public search API only."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

SEARCH_OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "MCP Manager — API",
        "description": "Search MCP servers, list install targets, retrieve installation recipes, and manage preference groups. Authentication via Google OAuth (JWT) or API key.",
        "version": "1.1.0",
    },
    "servers": [{"url": "/api/v1"}],
    "security": [{"bearerAuth": []}],
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
                    {"name": "source_id", "in": "query", "schema": {"type": "integer"}, "description": "Filter by skill source ID"},
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
        },
        "/services/{service_id}": {
            "get": {
                "summary": "Get MCP service detail",
                "description": "Returns a single MCP service with all its data: metadata, summaries per language, parameters, and installation recipes per target.",
                "operationId": "getService",
                "tags": ["MCP Services"],
                "parameters": [{"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {
                    "200": {
                        "description": "Service detail",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ServiceDetail"}}},
                    },
                    "404": {"description": "Service not found"},
                },
            },
        },
        "/summaries": {
            "get": {
                "summary": "List summaries",
                "description": "Returns summaries with optional filters. Use service_id to get summaries for a specific service.",
                "operationId": "listSummaries",
                "tags": ["Summaries"],
                "parameters": [
                    {"name": "service_id", "in": "query", "schema": {"type": "integer"}, "description": "Filter by MCP service ID"},
                    {"name": "culture", "in": "query", "schema": {"type": "string"}, "description": "Filter by language code (en, fr, ...)"},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 50}},
                ],
                "responses": {
                    "200": {
                        "description": "List of summaries",
                        "content": {"application/json": {"schema": {"type": "object", "properties": {
                            "items": {"type": "array", "items": {"$ref": "#/components/schemas/Summary"}},
                            "total": {"type": "integer"},
                        }}}},
                    },
                },
            },
        },
        "/parameters/{service_id}": {
            "get": {
                "summary": "Get service parameters",
                "description": "Returns detected parameters (env vars, secrets, config) for a service.",
                "operationId": "getParameters",
                "tags": ["Parameters"],
                "parameters": [{"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {
                    "200": {
                        "description": "List of parameters",
                        "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Parameter"}}}},
                    },
                },
            },
        },
        "/installations": {
            "get": {
                "summary": "List installations",
                "description": "Returns installation recipes. Use service_id to get recipes for a specific service.",
                "operationId": "listInstallations",
                "tags": ["Installations"],
                "parameters": [
                    {"name": "service_id", "in": "query", "schema": {"type": "integer"}, "description": "Filter by MCP service ID"},
                    {"name": "target_id", "in": "query", "schema": {"type": "integer"}, "description": "Filter by install target ID"},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 50}},
                ],
                "responses": {
                    "200": {
                        "description": "List of installations",
                        "content": {"application/json": {"schema": {"type": "object", "properties": {
                            "items": {"type": "array", "items": {"$ref": "#/components/schemas/Installation"}},
                            "total": {"type": "integer"},
                        }}}},
                    },
                },
            },
        },
        "/preference-groups": {
            "get": {
                "summary": "List my preference groups",
                "description": "Returns all preference groups for the authenticated user, with service and skill counts. Requires Google login (JWT).",
                "operationId": "listPreferenceGroups",
                "tags": ["Preference Groups"],
                "responses": {
                    "200": {
                        "description": "List of groups",
                        "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/PreferenceGroup"}}}},
                    },
                    "403": {"description": "API keys not supported — requires Google login"},
                },
            },
            "post": {
                "summary": "Create a preference group",
                "description": "Create a new preference group for the authenticated user. Requires Google login (JWT).",
                "operationId": "createPreferenceGroup",
                "tags": ["Preference Groups"],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "description": {"type": "string", "nullable": True}}}}},
                },
                "responses": {
                    "200": {"description": "Created group", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/GroupRef"}}}},
                },
            },
        },
        "/preference-groups/{group_id}": {
            "get": {
                "summary": "Get preference group detail",
                "description": "Returns group with its associated services and skills.",
                "operationId": "getPreferenceGroup",
                "tags": ["Preference Groups"],
                "parameters": [{"name": "group_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {
                    "200": {"description": "Group detail", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PreferenceGroupDetail"}}}},
                    "404": {"description": "Group not found or not owned by user"},
                },
            },
            "put": {
                "summary": "Update a preference group",
                "operationId": "updatePreferenceGroup",
                "tags": ["Preference Groups"],
                "parameters": [{"name": "group_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string", "nullable": True}}}}},
                },
                "responses": {"200": {"description": "Updated"}},
            },
            "delete": {
                "summary": "Delete a preference group",
                "operationId": "deletePreferenceGroup",
                "tags": ["Preference Groups"],
                "parameters": [{"name": "group_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "Deleted"}},
            },
        },
        "/preference-groups/{group_id}/services/{service_id}": {
            "post": {
                "summary": "Add a service to a group",
                "operationId": "addServiceToGroup",
                "tags": ["Preference Groups"],
                "parameters": [
                    {"name": "group_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "Added"}},
            },
            "delete": {
                "summary": "Remove a service from a group",
                "operationId": "removeServiceFromGroup",
                "tags": ["Preference Groups"],
                "parameters": [
                    {"name": "group_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "Removed"}},
            },
        },
        "/preference-groups/{group_id}/skills/{skill_id}": {
            "post": {
                "summary": "Add a skill to a group",
                "operationId": "addSkillToGroup",
                "tags": ["Preference Groups"],
                "parameters": [
                    {"name": "group_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "skill_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "Added"}},
            },
            "delete": {
                "summary": "Remove a skill from a group",
                "operationId": "removeSkillFromGroup",
                "tags": ["Preference Groups"],
                "parameters": [
                    {"name": "group_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "skill_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "Removed"}},
            },
        },
        "/services/{service_id}/groups": {
            "get": {
                "summary": "List groups containing a service",
                "description": "Returns the current user's groups that contain this service.",
                "operationId": "getServiceGroups",
                "tags": ["Preference Groups"],
                "parameters": [{"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "List of groups", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/GroupRef"}}}}}},
            },
        },
        "/skills/{skill_id}/groups": {
            "get": {
                "summary": "List groups containing a skill",
                "description": "Returns the current user's groups that contain this skill.",
                "operationId": "getSkillGroups",
                "tags": ["Preference Groups"],
                "parameters": [{"name": "skill_id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "List of groups", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/GroupRef"}}}}}},
            },
        },
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
                    "id": {"type": "integer"},
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
            "Translation": {
                "type": "object",
                "description": "A summary translated into one culture",
                "properties": {
                    "culture": {"type": "string", "enum": ["en", "fr"]},
                    "summary": {"type": "string"},
                },
            },
            "SkillResult": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "nullable": True},
                    "translations": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Translation"},
                        "description": "Summaries per culture",
                    },
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
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "url": {"type": "string", "description": "Source URL"},
                    "repo_url": {"type": "string", "nullable": True, "description": "GitHub repository URL"},
                    "type": {"type": "string", "enum": ["claude", "copilot", "gemini", "cursor"]},
                    "description": {"type": "string", "nullable": True},
                    "translations": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Translation"},
                        "description": "Summaries per culture",
                    },
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
                    "id": {"type": "integer"},
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
            "ServiceDetail": {
                "type": "object",
                "description": "Full MCP service with metadata, summaries, parameters, and installations",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "source_url": {"type": "string"},
                    "doc_url": {"type": "string", "nullable": True},
                    "source_type": {"type": "string"},
                    "transport": {"type": "string", "nullable": True},
                    "category": {"type": "string", "nullable": True},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "repo_status": {"type": "string", "nullable": True},
                    "stars": {"type": "integer", "nullable": True},
                    "canonical_id": {"type": "string", "nullable": True},
                    "is_deprecated": {"type": "boolean"},
                    "has_summaries": {"type": "boolean"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "updated_at": {"type": "string", "format": "date-time"},
                },
            },
            "Summary": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "mcp_service_id": {"type": "integer"},
                    "culture": {"type": "string", "description": "Language code (en, fr, ...)"},
                    "summary": {"type": "string"},
                    "source_hash": {"type": "string", "nullable": True},
                    "created_at": {"type": "string", "format": "date-time"},
                    "updated_at": {"type": "string", "format": "date-time"},
                },
            },
            "Installation": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "mcp_service_id": {"type": "integer"},
                    "install_target_id": {"type": "integer"},
                    "target_name": {"type": "string"},
                    "action_type": {"type": "string", "enum": ["cmd", "insert_in_file", "docker_run"]},
                    "data": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "PreferenceGroup": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "nullable": True},
                    "service_count": {"type": "integer"},
                    "skill_count": {"type": "integer"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "PreferenceGroupDetail": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "nullable": True},
                    "created_at": {"type": "string", "format": "date-time"},
                    "updated_at": {"type": "string", "format": "date-time"},
                    "services": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "source_type": {"type": "string"},
                                "category": {"type": "string", "nullable": True},
                            },
                        },
                    },
                    "skills": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "target_type": {"type": "string"},
                                "category": {"type": "string", "nullable": True},
                            },
                        },
                    },
                },
            },
            "GroupRef": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                },
            },
        },
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT or API key (mcp_...)",
                "description": "JWT from Google OAuth login, or API key (prefix mcp_). Preference groups require JWT (Google login).",
            },
        },
    },
}


@router.get("/openapi-search.json")
async def get_search_openapi():
    return JSONResponse(content=SEARCH_OPENAPI_SPEC)
