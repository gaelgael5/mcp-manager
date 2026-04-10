"""Scan a GitHub repo referenced by a skills.sh source for SKILL.md files.

Strategy:
1. Check if the repo has a `skills/` directory via GitHub API
2. If yes: list subdirectories, fetch SKILL.md from each one
3. If no: return status "no_skills_dir"
"""
import logging
import re

import httpx
import yaml

from mcp_manager.config import settings
from mcp_manager.connectors.github_pool import get_github_headers

logger = logging.getLogger(__name__)


async def scan_repo_skills(repo_url: str) -> dict:
    """Scan a GitHub repo for skills.

    Returns {"status": "ok"|"no_skills_dir"|"repo_404", "skills": [...]}
    Each skill: {name, description, raw_content, source_url, licence, licence_url}
    """
    if not repo_url or "github.com" not in repo_url:
        return {"status": "repo_404", "skills": []}

    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 5:
        return {"status": "repo_404", "skills": []}

    owner = parts[-2]
    repo = parts[-1]

    headers = get_github_headers()

    skills = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Check if skills/ directory exists
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/skills",
            headers=headers,
        )

        if resp.status_code == 404:
            # Check if repo itself exists
            repo_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
            )
            if repo_resp.status_code == 404:
                return {"status": "repo_404", "skills": []}
            return {"status": "no_skills_dir", "skills": []}

        if resp.status_code != 200:
            logger.warning("GitHub API %d for %s/skills", resp.status_code, repo_url)
            return {"status": "repo_404", "skills": []}

        entries = resp.json()
        if not isinstance(entries, list):
            return {"status": "no_skills_dir", "skills": []}

        # Step 2: Each subdirectory = a skill, look for SKILL.md inside
        for entry in entries:
            if entry.get("type") != "dir":
                continue

            skill_name = entry["name"]
            if skill_name.startswith("."):
                continue

            # Try to fetch SKILL.md from this directory
            for branch in ["main", "master"]:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/skills/{skill_name}/SKILL.md"
                file_resp = await client.get(raw_url)
                if file_resp.status_code == 200:
                    content = file_resp.text.replace("\x00", "")
                    name, description, licence = _parse_frontmatter(content, skill_name)
                    source_url = f"https://github.com/{owner}/{repo}/tree/{branch}/skills/{skill_name}"

                    skills.append({
                        "name": name,
                        "description": description,
                        "raw_content": content,
                        "source_url": source_url,
                        "licence": licence,
                        "licence_url": None,
                        "category": None,
                    })
                    logger.debug("Found skill: %s in %s/skills/%s", name, repo, skill_name)
                    break

    logger.info("Scanned %s: %d skills found", repo_url, len(skills))
    return {"status": "ok" if skills else "no_skills_dir", "skills": skills}


def _parse_frontmatter(content: str, fallback_name: str) -> tuple[str, str | None, str | None]:
    """Extract name, description, licence from YAML frontmatter."""
    name = fallback_name
    description = None
    licence = None

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if match:
        try:
            fm = yaml.safe_load(match.group(1))
            if isinstance(fm, dict):
                name = fm.get("name", fallback_name)
                description = fm.get("description")
                licence = fm.get("license") or fm.get("licence")
        except yaml.YAMLError:
            pass

    return name, description, licence
