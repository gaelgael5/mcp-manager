"""Shared utility to fetch README from GitHub repos, trying multiple branches."""
import logging
import re

import httpx

from mcp_manager.connectors.github_pool import get_github_headers_async

logger = logging.getLogger(__name__)

BRANCHES = ["main", "master", "develop"]

_GITHUB_OWNER_REPO_RE = re.compile(r"github\.com[/:]([^/]+)/([^/#?]+)")


def _parse_owner_repo(source_url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a github URL, stripping .git and /tree/ suffixes."""
    if not source_url or "github.com" not in source_url:
        return None
    m = _GITHUB_OWNER_REPO_RE.search(source_url)
    if not m:
        return None
    owner = m.group(1)
    repo = m.group(2).removesuffix(".git")
    return owner, repo


async def fetch_branch_sha(source_url: str) -> str | None:
    """Return the SHA of the HEAD commit on the default branch.

    Single GitHub API call to /repos/{owner}/{repo}/commits?per_page=1 which
    returns the latest commit on the default branch without needing to know
    the branch name.

    Returns None on any failure (non-github URL, 404, network error).
    """
    parsed = _parse_owner_repo(source_url)
    if parsed is None:
        return None
    owner, repo = parsed

    headers = await get_github_headers_async()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                params={"per_page": 1},
                headers=headers,
            )
            if resp.status_code != 200:
                return None
            commits = resp.json()
            if not isinstance(commits, list) or not commits:
                return None
            return commits[0].get("sha")
    except Exception:
        logger.debug("fetch_branch_sha failed for %s", source_url, exc_info=True)
        return None


async def fetch_github_readme(source_url: str) -> str | None:
    """Fetch README.md from a GitHub repo URL, trying multiple branches."""
    if not source_url or "github.com" not in source_url:
        return None

    # Normalize: remove trailing slash, /tree/xxx suffixes
    base = source_url.rstrip("/")

    headers = await get_github_headers_async()

    # If URL contains /tree/{branch}/{path}, try that exact path first
    if "/tree/" in base:
        raw_url = base.replace("github.com", "raw.githubusercontent.com").replace("/tree/", "/")
        readme_url = f"{raw_url}/README.md"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(readme_url, headers=headers)
            if resp.status_code == 200:
                return resp.text.replace("\x00", "")

        # Also try without subfolder (root README)
        parts = base.split("/tree/")
        root = parts[0]
        branch = parts[1].split("/")[0] if len(parts) > 1 else "main"
        root_raw = root.replace("github.com", "raw.githubusercontent.com")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{root_raw}/{branch}/README.md", headers=headers)
            if resp.status_code == 200:
                return resp.text.replace("\x00", "")

    # Try each branch
    raw_base = base.replace("github.com", "raw.githubusercontent.com")
    async with httpx.AsyncClient(timeout=15.0) as client:
        for branch in BRANCHES:
            resp = await client.get(f"{raw_base}/{branch}/README.md", headers=headers)
            if resp.status_code == 200:
                return resp.text.replace("\x00", "")

    return None
