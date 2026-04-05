"""Shared utility to fetch README from GitHub repos, trying multiple branches."""
import logging

import httpx

from mcp_manager.config import settings

logger = logging.getLogger(__name__)

BRANCHES = ["main", "master", "develop"]


async def fetch_github_readme(source_url: str) -> str | None:
    """Fetch README.md from a GitHub repo URL, trying multiple branches."""
    if not source_url or "github.com" not in source_url:
        return None

    # Normalize: remove trailing slash, /tree/xxx suffixes
    base = source_url.rstrip("/")

    headers = {}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"

    # If URL contains /tree/{branch}/{path}, try that exact path first
    if "/tree/" in base:
        raw_url = base.replace("github.com", "raw.githubusercontent.com").replace("/tree/", "/")
        readme_url = f"{raw_url}/README.md"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(readme_url, headers=headers)
            if resp.status_code == 200:
                return resp.text

        # Also try without subfolder (root README)
        parts = base.split("/tree/")
        root = parts[0]
        branch = parts[1].split("/")[0] if len(parts) > 1 else "main"
        root_raw = root.replace("github.com", "raw.githubusercontent.com")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{root_raw}/{branch}/README.md", headers=headers)
            if resp.status_code == 200:
                return resp.text

    # Try each branch
    raw_base = base.replace("github.com", "raw.githubusercontent.com")
    async with httpx.AsyncClient(timeout=15.0) as client:
        for branch in BRANCHES:
            resp = await client.get(f"{raw_base}/{branch}/README.md", headers=headers)
            if resp.status_code == 200:
                return resp.text

    return None
