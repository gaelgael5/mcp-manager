import asyncio
import hashlib
import logging
import re

import httpx
from bs4 import BeautifulSoup

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.registry import register_connector
from mcp_manager.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://www.pulsemcp.com"
HEADERS = {
    "User-Agent": "MCPManager/1.0 (MCP service catalog)",
    "Accept": "text/html,application/xhtml+xml",
}
# Max concurrent detail page fetches
CONCURRENCY = 5
# Delay between listing page fetches (seconds)
PAGE_DELAY = 1.0


@register_connector
class PulseMcpConnector(AbstractConnector):
    def source_type(self) -> str:
        return "pulsemcp"

    async def fetch_services(self) -> list[RawMcpService]:
        slugs = await self._fetch_all_slugs()
        logger.info("PulseMCP: found %d server slugs", len(slugs))

        services: list[RawMcpService] = []
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
            tasks = [self._fetch_detail(client, semaphore, slug) for slug in slugs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, RawMcpService):
                services.append(result)
            elif isinstance(result, Exception):
                logger.debug("Failed to fetch detail: %s", result)

        logger.info("PulseMCP: fetched %d services with details", len(services))
        return services

    async def _fetch_all_slugs(self) -> list[str]:
        """Scrape all listing pages to collect server slugs."""
        slugs: list[str] = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, follow_redirects=True) as client:
            while True:
                url = f"{BASE_URL}/servers?page={page}&sort=last-updated-desc"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning("PulseMCP listing page %d returned %d", page, resp.status_code)
                        break

                    soup = BeautifulSoup(resp.text, "html.parser")
                    page_slugs = self._extract_slugs_from_listing(soup)

                    if not page_slugs:
                        break

                    slugs.extend(page_slugs)
                    logger.info("PulseMCP: page %d — %d slugs (total: %d)", page, len(page_slugs), len(slugs))
                    page += 1
                    await asyncio.sleep(PAGE_DELAY)

                except Exception:
                    logger.exception("PulseMCP: error on listing page %d", page)
                    break

        return slugs

    def _extract_slugs_from_listing(self, soup: BeautifulSoup) -> list[str]:
        """Extract server slugs from a listing page."""
        slugs: list[str] = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Match /servers/{slug} but not /servers?page= or /servers/{slug}/serverjson
            match = re.match(r"^/servers/([a-zA-Z0-9_.-]+-[a-zA-Z0-9_.-]+)$", href)
            if match:
                slug = match.group(1)
                if slug not in slugs:
                    slugs.append(slug)
        return slugs

    async def _fetch_detail(
        self, client: httpx.AsyncClient, semaphore: asyncio.Semaphore, slug: str
    ) -> RawMcpService | None:
        """Fetch a server detail page and extract metadata."""
        async with semaphore:
            url = f"{BASE_URL}/servers/{slug}"
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            await asyncio.sleep(0.5)  # Rate limit

        soup = BeautifulSoup(resp.text, "html.parser")

        # Name from og:title or h1
        name = None
        og_title = soup.find("meta", property="og:title")
        if og_title:
            name = og_title.get("content", "").strip()
        if not name:
            h1 = soup.find("h1")
            if h1:
                name = h1.get_text(strip=True)
        if not name:
            name = slug

        # Description from meta description
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "").strip()

        # GitHub URL — first link containing github.com that's not a pulsemcp internal link
        github_url = ""
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "github.com" in href and "/servers" not in href and "pulsemcp" not in href:
                github_url = href.split("?")[0].rstrip("/")  # Clean query params
                break

        doc_hash = hashlib.sha256(resp.text.encode()).hexdigest()

        return RawMcpService(
            name=name,
            source_url=github_url,
            source_type="pulsemcp",
            doc_url=f"{BASE_URL}/servers/{slug}",
            doc_hash=doc_hash,
            transport="stdio",  # Default, most are stdio
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        """Fetch README from GitHub if source_url is set."""
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
