"""Connecteur: recherche GitHub par topic.

Source de volume : `topic:mcp-server` compte a lui seul ~44 000 depots, plus
que n'importe quel registre. Surtout, chaque entree arrive avec l'URL de son
depot — ce dont tout le reste du pipeline depend (lecture du README,
verification d'accessibilite, hash de branche), la ou un registre fournit
souvent une fiche sans depot.

Deux contraintes de l'API de recherche dictent la forme du connecteur :

  - une requete ne rend jamais plus de 1000 resultats, quel que soit
    `total_count`. On decoupe donc par fenetre de creation et on bissecte toute
    fenetre qui depasse le plafond.
  - la recherche est limitee a 30 requetes/minute, bien en dessous du quota
    REST que gere le pool de jetons. Ce connecteur impose donc sa propre
    cadence.
"""
import asyncio
import hashlib
import json
import logging
import time
from datetime import date, timedelta

import httpx

from mcp_manager.connectors.base import AbstractConnector, RawMcpService
from mcp_manager.connectors.github_pool import get_github_headers_async
from mcp_manager.connectors.registry import register_connector

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.github.com/search/repositories"
PER_PAGE = 100

# Plafond impose par l'API : au-dela, les pages suivantes sont refusees.
MAX_RESULTS_PER_QUERY = 1000

TOPICS = ("mcp-server", "modelcontextprotocol")

# Le protocole a ete annonce en novembre 2024 : rien a chercher avant.
EPOCH = date(2024, 10, 1)

# 30 requetes/minute autorisees ; on se tient un peu en dessous.
SEARCH_MIN_INTERVAL = 2.2
MAX_ATTEMPTS = 3

_pace_lock = asyncio.Lock()
_last_search_at = 0.0


async def _paced() -> None:
    """Espace les appels a la recherche, dont le quota est propre a l'endpoint."""
    global _last_search_at
    async with _pace_lock:
        wait = SEARCH_MIN_INTERVAL - (time.monotonic() - _last_search_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_search_at = time.monotonic()


@register_connector
class GithubTopicsConnector(AbstractConnector):
    def source_type(self) -> str:
        return "github_topics"

    async def fetch_services(self) -> list[RawMcpService]:
        # Un depot peut porter plusieurs topics recherches : on dedoublonne sur
        # full_name avant de construire les services.
        found: dict[str, dict] = {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            for topic in TOPICS:
                before = len(found)
                await self._collect(client, topic, EPOCH, date.today(), found)
                logger.info(
                    "GitHub topics: %s -> %d depots (%d nouveaux)",
                    topic, len(found), len(found) - before,
                )

        services = [self._parse_repo(item) for item in found.values()]
        services = [s for s in services if s]
        logger.info("GitHub topics: %d services au total", len(services))
        return services

    async def _collect(
        self,
        client: httpx.AsyncClient,
        topic: str,
        start: date,
        end: date,
        found: dict[str, dict],
    ) -> None:
        """Enumere une fenetre de creation, en la bissectant si elle sature."""
        query = f"topic:{topic} created:{start.isoformat()}..{end.isoformat()}"

        page = await self._search(client, query, 1)
        if page is None:
            return

        total, items = page
        if total == 0:
            return

        if total > MAX_RESULTS_PER_QUERY:
            span = (end - start).days
            if span < 1:
                # Une seule journee sature le plafond : l'exces est hors
                # d'atteinte de l'API, on le signale plutot que de le taire.
                logger.warning(
                    "GitHub topics: %s le %s compte %d depots, plafonne a %d",
                    topic, start.isoformat(), total, MAX_RESULTS_PER_QUERY,
                )
            else:
                mid = start + timedelta(days=span // 2)
                await self._collect(client, topic, start, mid, found)
                await self._collect(client, topic, mid + timedelta(days=1), end, found)
                return

        self._absorb(items, found)

        last_page = min(
            (min(total, MAX_RESULTS_PER_QUERY) + PER_PAGE - 1) // PER_PAGE,
            MAX_RESULTS_PER_QUERY // PER_PAGE,
        )
        for p in range(2, last_page + 1):
            page = await self._search(client, query, p)
            if page is None:
                return
            self._absorb(page[1], found)

    @staticmethod
    def _absorb(items: list[dict], found: dict[str, dict]) -> None:
        for item in items:
            # Les forks dupliquent un depot deja indexe sans rien ajouter.
            if item.get("fork"):
                continue
            full_name = item.get("full_name")
            if full_name:
                found[full_name] = item

    async def _search(
        self, client: httpx.AsyncClient, query: str, page: int
    ) -> tuple[int, list[dict]] | None:
        """Un appel de recherche. Renvoie (total_count, items), ou None si perdu."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await _paced()
            headers = await get_github_headers_async()
            try:
                resp = await client.get(
                    SEARCH_URL,
                    params={"q": query, "per_page": str(PER_PAGE), "page": str(page)},
                    headers=headers,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning("GitHub topics: incident reseau (%s), tentative %d", exc, attempt)
                continue

            if resp.status_code == 200:
                data = resp.json()
                return data.get("total_count", 0), data.get("items", [])

            if resp.status_code in (403, 429):
                delay = self._retry_delay(resp)
                logger.warning(
                    "GitHub topics: quota atteint (%d), attente %.0fs", resp.status_code, delay,
                )
                await asyncio.sleep(delay)
                continue

            logger.warning(
                "GitHub topics: la recherche a repondu %d pour %r", resp.status_code, query,
            )
            return None

        logger.warning("GitHub topics: abandon de %r page %d", query, page)
        return None

    @staticmethod
    def _retry_delay(resp: httpx.Response) -> float:
        """Delai dicte par GitHub, borne pour ne pas suspendre un sync entier."""
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 120.0)
            except ValueError:
                pass
        reset = resp.headers.get("x-ratelimit-reset")
        if reset:
            try:
                return max(1.0, min(float(reset) - time.time(), 120.0))
            except ValueError:
                pass
        return 30.0

    @staticmethod
    def _parse_repo(item: dict) -> RawMcpService | None:
        full_name = item.get("full_name")
        html_url = item.get("html_url")
        if not full_name or not html_url:
            return None

        topics = [t for t in (item.get("topics") or []) if isinstance(t, str)]

        # Hacher uniquement des champs stables. Le nombre d'etoiles ou
        # `pushed_at` changent en permanence : les inclure ferait basculer
        # doc_hash a chaque sync, donc needs_reindex, donc une reindexation
        # complete et inutile de dizaines de milliers de services.
        identity = {
            "full_name": full_name,
            "description": item.get("description") or "",
            "topics": sorted(topics),
            "archived": bool(item.get("archived")),
            "default_branch": item.get("default_branch") or "",
        }
        doc_hash = hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode()
        ).hexdigest()

        return RawMcpService(
            name=full_name,
            source_url=html_url,
            source_type="github_topics",
            doc_url=html_url,
            doc_hash=doc_hash,
            tags=topics,
            is_deprecated=bool(item.get("archived")),
        )

    async def fetch_doc_content(self, service: RawMcpService) -> str | None:
        from mcp_manager.connectors.github_readme import fetch_github_readme
        return await fetch_github_readme(service.source_url)
