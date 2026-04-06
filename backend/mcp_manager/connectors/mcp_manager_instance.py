"""Connector to sync from another MCP Manager instance via its /search API."""
import logging

import httpx

from mcp_manager.connectors.base import AbstractConnector, RawMcpService

logger = logging.getLogger(__name__)

# Not auto-registered — instantiated per instance in the sync process


class McpManagerInstanceConnector(AbstractConnector):
    def __init__(self, instance_url: str, api_key: str | None = None, last_sync: str | None = None):
        self.instance_url = instance_url.rstrip("/")
        self.api_key = api_key
        self.last_sync = last_sync  # ISO timestamp for delta sync

    def source_type(self) -> str:
        return "mcp_instance"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def fetch_services(self) -> list[RawMcpService]:
        services: list[RawMcpService] = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: dict[str, str] = {
                    "page": str(page),
                    "per_page": "50",
                }
                if self.last_sync:
                    params["updated_since"] = self.last_sync

                resp = await client.get(
                    f"{self.instance_url}/api/v1/search",
                    params=params,
                    headers=self._headers(),
                )
                if resp.status_code != 200:
                    logger.warning("Instance %s returned %d", self.instance_url, resp.status_code)
                    break

                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    service = self._parse_item(item)
                    if service:
                        services.append(service)

                total = data.get("total", 0)
                if page * 50 >= total:
                    break
                page += 1

        logger.info("Instance %s: fetched %d services", self.instance_url, len(services))
        return services

    def _parse_item(self, item: dict) -> RawMcpService | None:
        name = item.get("name", "")
        if not name:
            return None

        return RawMcpService(
            name=name,
            source_url=item.get("source_url", ""),
            source_type="mcp_instance",
            doc_url=item.get("doc_url"),
            transport=item.get("transport"),
            category=item.get("category"),
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        from mcp_manager.connectors.github_readme import fetch_github_readme
        return await fetch_github_readme(service.source_url)
