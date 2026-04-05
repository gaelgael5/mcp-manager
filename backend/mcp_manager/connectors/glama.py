import hashlib
import json
import logging

import httpx

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.registry import register_connector
from mcp_manager.config import settings

logger = logging.getLogger(__name__)

API_URL = "https://glama.ai/api/mcp/v1/servers"
PAGE_SIZE = 100

# Map glama attributes to transport types
TRANSPORT_MAP = {
    "hosting:local-only": "stdio",
    "hosting:remote-capable": "sse",
    "hosting:hybrid": "stdio",
}


@register_connector
class GlamaConnector(AbstractConnector):
    def source_type(self) -> str:
        return "glama"

    async def fetch_services(self) -> list[RawMcpService]:
        services: list[RawMcpService] = []
        cursor: str | None = None
        page = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: dict[str, str] = {"limit": str(PAGE_SIZE)}
                if cursor:
                    params["after"] = cursor

                resp = await client.get(API_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("Glama API returned %d", resp.status_code)
                    break

                data = resp.json()
                servers = data.get("servers", [])
                if not servers:
                    break

                for srv in servers:
                    service = self._parse_server(srv)
                    if service:
                        services.append(service)

                page += 1
                page_info = data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")

                if page % 10 == 0:
                    logger.info("Glama: fetched %d services (%d pages)", len(services), page)

        logger.info("Glama: fetched %d services total", len(services))
        return services

    def _parse_server(self, data: dict) -> RawMcpService | None:
        name = data.get("name", "")
        if not name:
            return None

        namespace = data.get("namespace", "")
        slug = data.get("slug", "")
        description = data.get("description", "")
        repo = data.get("repository", {})
        repo_url = repo.get("url", "") if repo else ""
        attributes = data.get("attributes", [])
        license_info = data.get("spdxLicense") or {}
        env_schema = data.get("environmentVariablesJsonSchema", {})

        # Determine transport from attributes
        transport = "stdio"
        for attr in attributes:
            if attr in TRANSPORT_MAP:
                transport = TRANSPORT_MAP[attr]
                break

        # Extract env vars from JSON schema
        env_vars: dict[str, str] = {}
        props = env_schema.get("properties", {})
        for var_name, var_info in props.items():
            env_vars[var_name] = var_info.get("description", "")

        # Build unique name
        full_name = f"{namespace}/{slug}" if namespace else slug

        raw_json = json.dumps(data, sort_keys=True)
        doc_hash = hashlib.sha256(raw_json.encode()).hexdigest()

        return RawMcpService(
            name=full_name,
            source_url=repo_url,
            source_type="glama",
            doc_url=data.get("url", ""),
            doc_hash=doc_hash,
            transport=transport,
            env_vars=env_vars,
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        if not service.source_url or "github.com" not in service.source_url:
            return None

        readme_url = (
            service.source_url.replace("github.com", "raw.githubusercontent.com")
            + "/main/README.md"
        )
        headers = {}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(readme_url, headers=headers)
            if resp.status_code == 200:
                return resp.text

        return None
