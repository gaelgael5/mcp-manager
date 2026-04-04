import hashlib
import json
import logging

import httpx

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.registry import register_connector
from mcp_manager.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPO_OWNER = "modelcontextprotocol"
REPO_NAME = "servers"
SERVERS_PATH = "src"


@register_connector
class McpServersRepoConnector(AbstractConnector):
    def source_type(self) -> str:
        return "mcp_servers_repo"

    def _github_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        return headers

    async def fetch_services(self) -> list[RawMcpService]:
        services: list[RawMcpService] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{SERVERS_PATH}"
            resp = await client.get(url, headers=self._github_headers())
            resp.raise_for_status()
            entries = resp.json()

            for entry in entries:
                if entry.get("type") != "dir":
                    continue
                server_name = entry["name"]
                try:
                    service = await self._fetch_server(client, server_name)
                    if service:
                        services.append(service)
                except Exception:
                    logger.exception("Failed to fetch server %s", server_name)

        logger.info("MCP servers repo: fetched %d services", len(services))
        return services

    async def _fetch_server(
        self, client: httpx.AsyncClient, server_name: str
    ) -> RawMcpService | None:
        base_raw = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{SERVERS_PATH}/{server_name}"
        source_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/main/{SERVERS_PATH}/{server_name}"

        # Try pyproject.toml first (Python servers)
        resp = await client.get(f"{base_raw}/pyproject.toml", headers=self._github_headers())
        if resp.status_code == 200:
            return self._parse_pyproject(server_name, resp.text, source_url)

        # Then package.json (Node servers)
        resp = await client.get(f"{base_raw}/package.json", headers=self._github_headers())
        if resp.status_code == 200:
            return self._parse_package_json(server_name, resp.text, source_url)

        return None

    def _parse_pyproject(self, server_name: str, content: str, source_url: str) -> RawMcpService:
        import tomllib
        data = tomllib.loads(content)
        project = data.get("project", {})
        name = project.get("name", server_name)
        description = project.get("description", "")
        version = project.get("version", "")
        keywords = project.get("keywords", [])

        return RawMcpService(
            name=name,
            source_url=source_url,
            source_type="mcp_servers_repo",
            doc_url=source_url,
            doc_hash=hashlib.sha256(content.encode()).hexdigest(),
            branch_hash=version,
            transport="stdio",
            category="reference",
            tags=keywords,
            registry_type="pypi",
            package_identifier=name,
            runtime_hint="uvx",
        )

    def _parse_package_json(self, server_name: str, content: str, source_url: str) -> RawMcpService:
        data = json.loads(content)
        name = data.get("name", server_name)
        description = data.get("description", "")
        version = data.get("version", "")
        keywords = data.get("keywords", [])

        return RawMcpService(
            name=name,
            source_url=source_url,
            source_type="mcp_servers_repo",
            doc_url=source_url,
            doc_hash=hashlib.sha256(content.encode()).hexdigest(),
            branch_hash=version,
            transport="stdio",
            category="reference",
            tags=keywords,
            registry_type="npm",
            package_identifier=name,
            runtime_hint="npx",
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        if not service.doc_url:
            return None
        readme_url = service.doc_url.replace(
            "github.com", "raw.githubusercontent.com"
        ).replace("/tree/", "/") + "/README.md"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(readme_url, headers=self._github_headers())
            if resp.status_code == 200:
                return resp.text
        return None
