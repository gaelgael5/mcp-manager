"""Scan skill source repos and extract skills (SKILL.md, instructions, prompts)."""
import logging
import re

import httpx
import yaml

from mcp_manager.config import settings

logger = logging.getLogger(__name__)

# Map source type to the expected skill file per folder
SKILL_FILES = {
    "claude": ["SKILL.md"],
    "copilot": [".github/copilot-instructions.md", "copilot-instructions.md"],
    "cursor": [".cursorrules", "rules.md"],
    "gemini": ["GEMINI.md", "gemini.md"],
}


async def scan_skill_source(url: str, skills_path: str, source_type: str) -> list[dict]:
    """Scan a GitHub repo for skills in the given path.

    Returns list of {name, description, content, licence, source_url, category}.
    """
    # Parse GitHub URL: https://github.com/{owner}/{repo}
    parts = url.rstrip("/").split("/")
    if len(parts) < 5 or "github.com" not in url:
        logger.warning("Not a GitHub URL: %s", url)
        return []

    owner = parts[-2]
    repo = parts[-1]

    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"

    skills = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # List directories in skills_path
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{skills_path}"
        resp = await client.get(api_url, headers=headers)
        if resp.status_code != 200:
            logger.warning("Failed to list %s: %d", api_url, resp.status_code)
            return []

        entries = resp.json()
        if not isinstance(entries, list):
            return []

        for entry in entries:
            if entry.get("type") != "dir":
                continue

            skill_name = entry["name"]
            skill_dir = f"{skills_path}/{skill_name}"
            source_url = f"https://github.com/{owner}/{repo}/tree/main/{skill_dir}"

            # Try to find the skill file
            skill_files = SKILL_FILES.get(source_type, ["SKILL.md"])
            content = None

            for skill_file in skill_files:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{skill_dir}/{skill_file}"
                file_resp = await client.get(raw_url, headers=headers)
                if file_resp.status_code == 200:
                    content = file_resp.text
                    break

            if not content:
                # Try master branch
                for skill_file in skill_files:
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{skill_dir}/{skill_file}"
                    file_resp = await client.get(raw_url, headers=headers)
                    if file_resp.status_code == 200:
                        content = file_resp.text
                        break

            if not content:
                logger.debug("No skill file found in %s", skill_dir)
                continue

            # Parse YAML frontmatter
            name, description, licence = _parse_frontmatter(content, skill_name)

            # Build licence URL
            licence_url = None
            for branch in ["main", "master"]:
                lic_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{skill_dir}/LICENSE.txt"
                lic_raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{skill_dir}/LICENSE.txt"
                lic_resp = await client.get(lic_raw, headers=headers)
                if lic_resp.status_code == 200:
                    licence_url = lic_url
                    break

            skills.append({
                "name": name,
                "description": description,
                "raw_content": content,  # Used for summary generation, not stored
                "licence": licence,
                "licence_url": licence_url,
                "source_url": source_url,
                "category": None,
            })

            logger.debug("Found skill: %s", name)

    logger.info("Scanned %s: found %d skills", url, len(skills))
    return skills


def _parse_frontmatter(content: str, fallback_name: str) -> tuple[str, str | None, str | None]:
    """Extract name, description, licence from YAML frontmatter in markdown."""
    name = fallback_name
    description = None
    licence = None

    # Match --- frontmatter ---
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


async def get_repo_branch_hash(url: str) -> str | None:
    """Get the latest commit SHA of the default branch."""
    parts = url.rstrip("/").split("/")
    if len(parts) < 5:
        return None

    owner = parts[-2]
    repo = parts[-1]

    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1",
            headers=headers,
        )
        if resp.status_code == 200:
            commits = resp.json()
            if commits:
                return commits[0].get("sha", "")[:40]
    return None
