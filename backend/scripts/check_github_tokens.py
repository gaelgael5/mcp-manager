"""Teste chaque jeton du pool et dit lequel est refuse.

Un jeton invalide dans le pool fait echouer une requete sur N en round-robin.
L'ancien verificateur traduisait ces 401 en repo_status='404' ; le nouveau
interrompt la passe, ce qui rend le probleme visible mais pas son origine.
D'ou cet outil.

Interroge /rate_limit, qui ne consomme pas de quota. N'affiche jamais un jeton
en clair.

    docker compose exec mcp-backend python scripts/check_github_tokens.py
"""
import asyncio
import sys

import httpx
from sqlalchemy import select

from mcp_manager.db.session import SessionLocal
from mcp_manager.db.models import ApiToken

RATE_LIMIT_URL = "https://api.github.com/rate_limit"


def _mask(token: str) -> str:
    return f"{token[:7]}…{token[-4:]}" if len(token) > 12 else "…"


async def main() -> int:
    async with SessionLocal() as db:
        tokens = (await db.execute(
            select(ApiToken).where(ApiToken.domain == "github.com").order_by(ApiToken.created_at)
        )).scalars().all()

    if not tokens:
        print("Aucun jeton github.com dans api_tokens.")
        print("Sans jeton, l'API GitHub est limitee a 60 requetes/heure.")
        return 1

    print(f"{len(tokens)} jeton(s) github.com dans le pool\n")
    bad = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for t in tokens:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {t.token}",
            }
            try:
                resp = await client.get(RATE_LIMIT_URL, headers=headers)
            except Exception as exc:
                print(f"  {_mask(t.token)}  id={t.id}  INJOIGNABLE ({exc})")
                bad += 1
                continue

            if resp.status_code == 200:
                core = resp.json().get("resources", {}).get("core", {})
                search = resp.json().get("resources", {}).get("search", {})
                scopes = resp.headers.get("x-oauth-scopes", "(aucun)")
                print(
                    f"  {_mask(t.token)}  id={t.id}  VALIDE  "
                    f"core={core.get('remaining')}/{core.get('limit')}  "
                    f"search={search.get('remaining')}/{search.get('limit')}  "
                    f"scopes={scopes}"
                )
            else:
                print(
                    f"  {_mask(t.token)}  id={t.id}  REFUSE ({resp.status_code})  "
                    f"cree le {t.created_at:%Y-%m-%d}  rate_limit_per_min={t.rate_limit_per_min}"
                )
                bad += 1

    if bad:
        print(f"\n{bad} jeton(s) a remplacer. Retirer un jeton refuse :")
        print("  DELETE FROM api_tokens WHERE id = '<id>';")
        print("\nTant qu'il reste dans le pool, une requete sur "
              f"{len(tokens)} echoue en 401 et interrompt les passes.")
        return 1

    print("\nTous les jetons sont valides.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
