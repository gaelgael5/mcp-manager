"""Passe: verify repo accessibility and fetch GitHub stars.

Principe directeur : ne jamais ecrire de verdict qu'on n'a pas obtenu. Un
incident (quota, jeton refuse, 5xx, timeout) laisse la ligne intacte pour
qu'elle repasse ; seule une reponse definitive de GitHub est enregistree.
L'ancienne version assimilait tout code != 200 a un depot disparu, ce qui a
condamne a tort environ 25 000 services. Cf. docs/repo-check.md.
"""
import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum

import httpx

from mcp_manager.connectors.github_pool import get_github_headers_async
from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import McpService
from sqlalchemy import select

logger = logging.getLogger(__name__)

CONCURRENCY = 10
BATCH_SIZE = 200

# Au-dela de ce nombre d'indetermines d'affilee, la panne n'est plus "ce depot
# la" mais le reseau ou GitHub : continuer n'ajouterait que des lignes a
# reverifier, autant rendre la main.
MAX_CONSECUTIVE_UNDETERMINED = 25

# Codes qui prouvent que le depot n'est plus exploitable : 404 absent ou prive,
# 410 supprime, 451 retire pour raison legale. Reponses definitives, pas des
# incidents.
_CONCLUSIVE_GONE = frozenset({404, 410, 451})


class CheckOutcome(str, Enum):
    OK = "ok"
    GONE = "404"
    # URL hors GitHub : cette passe ne sait pas la verifier. Distinguer ce cas
    # evite de le confondre avec un depot disparu.
    UNSUPPORTED = "unsupported"
    # Rien n'est ecrit en base, la ligne sera reprise au prochain passage.
    UNDETERMINED = "undetermined"


class CheckAborted(Exception):
    """Panne systemique : quota epuise, jeton refuse, ou trop d'echecs d'affilee."""


async def check_repo(
    client: httpx.AsyncClient, url: str
) -> tuple[CheckOutcome, int | None]:
    """Check repo accessibility and return (outcome, stars)."""
    if not url or "github.com" not in url:
        return CheckOutcome.UNSUPPORTED, None

    api_url = url.replace("https://github.com/", "https://api.github.com/repos/")
    headers = await get_github_headers_async()
    try:
        resp = await client.get(api_url, headers=headers)
    except (httpx.TimeoutException, httpx.TransportError):
        return CheckOutcome.UNDETERMINED, None

    if resp.status_code == 200:
        try:
            stars = resp.json().get("stargazers_count")
        except ValueError:
            stars = None
        return CheckOutcome.OK, stars

    if resp.status_code in _CONCLUSIVE_GONE:
        return CheckOutcome.GONE, None

    if resp.status_code == 401:
        raise CheckAborted(
            "GitHub refuse le jeton (401) — verifier le pool de jetons avant de relancer"
        )
    if resp.status_code in (403, 429):
        raise CheckAborted(
            f"quota GitHub atteint ({resp.status_code}) — relancer plus tard"
        )

    # 5xx et tout code inattendu : incident cote GitHub, pas un verdict.
    return CheckOutcome.UNDETERMINED, None


async def _check_batch(
    client: httpx.AsyncClient, rows: list[tuple]
) -> list[tuple[int, CheckOutcome, int | None]]:
    """Check a batch concurrently. Raises CheckAborted if any check aborted."""
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(svc_id: int, url: str):
        async with sem:
            outcome, stars = await check_repo(client, url)
            return svc_id, outcome, stars

    results = await asyncio.gather(
        *(one(svc_id, url) for svc_id, url in rows), return_exceptions=True
    )

    out: list[tuple[int, CheckOutcome, int | None]] = []
    for res in results:
        if isinstance(res, CheckAborted):
            raise res
        if isinstance(res, BaseException):
            # Un imprevu sur un depot ne doit pas perdre le reste du lot.
            logger.warning("Repo check: erreur inattendue, ligne laissee a reprendre", exc_info=res)
            continue
        out.append(res)
    return out


async def run_repo_check(limit: int | None = None) -> dict[str, int]:
    """Verify repos that have no dated check yet.

    Deux phases : d'abord les services sans verdict (jamais tranches ou remis a
    zero), ensuite ceux qui en ont un mais sans date. On obtient ainsi du signal
    neuf avant de depenser du quota a revalider de l'acquis.
    """
    stats = {"checked": 0, "ok": 0, "not_found": 0, "unsupported": 0, "undetermined": 0}
    consecutive_undetermined = 0
    remaining = limit

    phases = (
        ("sans verdict", McpService.repo_status.is_(None)),
        ("verdict a redater", McpService.repo_status.isnot(None)),
    )

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for phase_name, phase_filter in phases:
            cursor = 0
            while True:
                if remaining is not None and remaining <= 0:
                    break

                batch_size = BATCH_SIZE
                if remaining is not None:
                    batch_size = min(batch_size, remaining)

                async with SessionLocal() as db:
                    rows = (await db.execute(
                        select(McpService._id, McpService.source_url)
                        .where(
                            McpService.source_url != "",
                            McpService.repo_checked_at.is_(None),
                            McpService._id > cursor,
                            phase_filter,
                        )
                        .order_by(McpService._id)
                        .limit(batch_size)
                    )).all()

                if not rows:
                    break

                # Le curseur avance sur _id et non sur le verdict : la boucle
                # termine meme quand un lot entier reste indetermine.
                cursor = rows[-1][0]
                if remaining is not None:
                    remaining -= len(rows)

                try:
                    results = await _check_batch(client, [(r[0], r[1]) for r in rows])
                except CheckAborted as exc:
                    logger.warning("Repo check interrompu (%s) : %s", phase_name, exc)
                    logger.info("Repo check: %s", stats)
                    return stats

                now = datetime.now(timezone.utc)
                async with SessionLocal() as db:
                    for svc_id, outcome, stars in results:
                        if outcome is CheckOutcome.UNDETERMINED:
                            stats["undetermined"] += 1
                            consecutive_undetermined += 1
                            continue

                        consecutive_undetermined = 0
                        values: dict = {
                            "repo_status": outcome.value,
                            "repo_checked_at": now,
                        }
                        if stars is not None:
                            values["stars"] = stars
                        await db.execute(
                            McpService.__table__.update()
                            .where(McpService._id == svc_id)
                            .values(**values)
                        )
                        stats["checked"] += 1
                        if outcome is CheckOutcome.OK:
                            stats["ok"] += 1
                        elif outcome is CheckOutcome.GONE:
                            stats["not_found"] += 1
                        else:
                            stats["unsupported"] += 1
                    await db.commit()

                logger.info("Repo check (%s): %s", phase_name, stats)

                if consecutive_undetermined >= MAX_CONSECUTIVE_UNDETERMINED:
                    logger.warning(
                        "Repo check interrompu : %d indetermines d'affilee, panne probablement systemique",
                        consecutive_undetermined,
                    )
                    return stats

    logger.info("Repo check done: %s", stats)
    return stats


async def run_stars_update() -> dict[str, int]:
    """Re-fetch GitHub stars for services with repo_status='ok'."""
    stats = {"services": 0}
    cursor = 0

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        while True:
            async with SessionLocal() as db:
                rows = (await db.execute(
                    select(McpService._id, McpService.source_url)
                    .where(
                        McpService.repo_status == "ok",
                        McpService.source_url.contains("github.com"),
                        McpService.stars.is_(None),
                        McpService._id > cursor,
                    )
                    .order_by(McpService._id)
                    .limit(BATCH_SIZE)
                )).all()

            if not rows:
                break

            cursor = rows[-1][0]

            try:
                results = await _check_batch(client, [(r[0], r[1]) for r in rows])
            except CheckAborted as exc:
                logger.warning("Stars update interrompu : %s", exc)
                return stats

            async with SessionLocal() as db:
                for svc_id, _outcome, stars in results:
                    if stars is None:
                        continue
                    await db.execute(
                        McpService.__table__.update()
                        .where(McpService._id == svc_id)
                        .values(stars=stars)
                    )
                    stats["services"] += 1
                await db.commit()

            logger.info("Stars update: %d updated so far", stats["services"])

    logger.info("Stars update done: %s", stats)
    return stats
