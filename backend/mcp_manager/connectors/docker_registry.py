import hashlib
import logging

import httpx
import yaml

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.registry import register_connector
from mcp_manager.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPO_OWNER = "docker"
REPO_NAME = "mcp-registry"
SERVERS_PATH = "servers"


@register_connector
class DockerRegistryConnector(AbstractConnector):
    def source_type(self) -> str:
        return "docker_registry"

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

        logger.info("Docker registry: fetched %d services", len(services))
        return services

    async def _fetch_server(
        self, client: httpx.AsyncClient, server_name: str
    ) -> RawMcpService | None:
        url = (
            f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}"
            f"/main/{SERVERS_PATH}/{server_name}/server.yaml"
        )
        resp = await client.get(url, headers=self._github_headers())
        if resp.status_code != 200:
            return None
        yaml_content = resp.text
        service = self._parse_server_yaml(server_name, yaml_content)
        service.doc_hash = hashlib.sha256(yaml_content.encode()).hexdigest()
        return service

    def _parse_server_yaml(self, server_name: str, yaml_content: str) -> RawMcpService:
        data = yaml.safe_load(yaml_content) or {}
        meta = data.get("meta", {})
        source = data.get("source", {})
        remote = data.get("remote", {})

        transport = "stdio"
        if data.get("type") == "remote":
            transport = remote.get("transport_type", "sse")

        return RawMcpService(
            name=data.get("name", server_name),
            source_url=source.get("project", ""),
            source_type="docker_registry",
            doc_url=data.get("readme") or data.get("upstream") or source.get("project"),
            transport=transport,
            category=meta.get("category"),
            tags=meta.get("tags", []),
            branch_hash=source.get("commit"),
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

        # Fallback: try root README
        if "/tree/" in (service.doc_url or ""):
            root_url = service.doc_url.rsplit("/tree/", 1)[0]
            root_readme = root_url.replace(
                "github.com", "raw.githubusercontent.com"
            ) + "/main/README.md"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(root_readme, headers=self._github_headers())
                if resp.status_code == 200:
                    return resp.text

        return None
