import hashlib
import json
import logging

import httpx

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.registry import register_connector
from mcp_manager.config import settings

logger = logging.getLogger(__name__)

REGISTRY_API = "https://registry.modelcontextprotocol.io/v0.1"


@register_connector
class McpRegistryConnector(AbstractConnector):
    def source_type(self) -> str:
        return "mcp_registry"

    def _github_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        return headers

    async def fetch_services(self) -> list[RawMcpService]:
        services: list[RawMcpService] = []
        cursor: str | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: dict[str, str] = {"limit": "96", "version": "latest"}
                if cursor:
                    params["cursor"] = cursor

                resp = await client.get(f"{REGISTRY_API}/servers", params=params)
                resp.raise_for_status()
                data = resp.json()

                servers = data.get("servers", [])
                if not servers:
                    break

                for entry in servers:
                    try:
                        server_data = entry.get("server", entry)
                        service = self._parse_server_json(server_data)
                        if not service.name:
                            continue
                        raw_json = json.dumps(server_data, sort_keys=True)
                        service.doc_hash = hashlib.sha256(raw_json.encode()).hexdigest()
                        services.append(service)
                    except Exception:
                        logger.exception(
                            "Failed to parse server %s",
                            entry.get("server", entry).get("name", "unknown"),
                        )

                cursor = data.get("metadata", {}).get("nextCursor")
                if not cursor:
                    break

        logger.info("MCP registry: fetched %d services", len(services))
        return services

    def _parse_server_json(self, data: dict) -> RawMcpService:
        name = data.get("name", "")
        version = data.get("version", "")
        repository = data.get("repository", {})

        # Resolve doc URL: subfolder in repo takes priority
        doc_url = data.get("websiteUrl") or repository.get("url")
        if repository.get("url") and repository.get("subfolder"):
            doc_url = f"{repository['url']}/tree/main/{repository['subfolder']}"

        # Extract first package info
        packages = data.get("packages", [])
        registry_type = None
        package_identifier = None
        runtime_hint = None
        transport = None
        env_vars: dict[str, str] = {}

        if packages:
            pkg = packages[0]
            registry_type = pkg.get("registryType")
            package_identifier = pkg.get("identifier")
            runtime_hint = pkg.get("runtimeHint")
            transport = pkg.get("transport", {}).get("type")
            for ev in pkg.get("environmentVariables", []):
                env_vars[ev["name"]] = ev.get("description", "")

        # Check remotes if no packages
        remotes = data.get("remotes", [])
        if not transport and remotes:
            transport = remotes[0].get("type")

        return RawMcpService(
            name=name,
            source_url=repository.get("url", ""),
            source_type="mcp_registry",
            doc_url=doc_url,
            branch_hash=version,
            transport=transport,
            registry_type=registry_type,
            package_identifier=package_identifier,
            runtime_hint=runtime_hint,
            env_vars=env_vars,
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        if not service.doc_url:
            return None

        # Try subfolder README first
        readme_url = self._resolve_raw_readme_url(service.doc_url)
        if readme_url:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(readme_url, headers=self._github_headers())
                if resp.status_code == 200:
                    return resp.text

        # Fallback: root README of the repo
        if service.source_url:
            root_readme = (
                service.source_url.replace("github.com", "raw.githubusercontent.com")
                + "/main/README.md"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(root_readme, headers=self._github_headers())
                if resp.status_code == 200:
                    return resp.text

        return None

    def _resolve_raw_readme_url(self, doc_url: str) -> str | None:
        if "github.com" not in doc_url:
            return None
        raw_url = doc_url.replace("github.com", "raw.githubusercontent.com").replace(
            "/tree/", "/"
        )
        return f"{raw_url}/README.md"
