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

    # Normalize path: empty or "." means root
    scan_path = skills_path.strip().strip("/")
    if scan_path in ("", "."):
        scan_path = ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        await _scan_dir(client, owner, repo, scan_path, source_type, headers, skills, depth=0)

    logger.info("Scanned %s: found %d skills", url, len(skills))
    return skills


async def _scan_dir(
    client: httpx.AsyncClient, owner: str, repo: str, dir_path: str,
    source_type: str, headers: dict, skills: list, depth: int,
):
    """Recursively scan a directory for skill files (max depth 3)."""
    if depth > 3:
        return

    api_path = f"contents/{dir_path}" if dir_path else "contents"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/{api_path}"
    resp = await client.get(api_url, headers=headers)
    if resp.status_code != 200:
        return

    entries = resp.json()
    if not isinstance(entries, list):
        return

    for entry in entries:
        if entry.get("type") != "dir":
            continue

        skill_name = entry["name"]
        # Skip hidden dirs and common non-skill dirs
        if skill_name.startswith(".") or skill_name in {"node_modules", "__pycache__", "spec", "template"}:
            continue

        skill_dir = f"{dir_path}/{skill_name}" if dir_path else skill_name
        source_url = f"https://github.com/{owner}/{repo}/tree/main/{skill_dir}"

        # Try to find the skill file in this dir
        skill_files = SKILL_FILES.get(source_type, ["SKILL.md"])
        content = None

        for branch in ["main", "master"]:
            if content:
                break
            for skill_file in skill_files:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{skill_dir}/{skill_file}"
                file_resp = await client.get(raw_url, headers=headers)
                if file_resp.status_code == 200:
                    content = file_resp.text
                    break

        if content:
            name, description, licence = _parse_frontmatter(content, skill_name)

            # Build licence URL
            licence_url = None
            for branch in ["main", "master"]:
                lic_raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{skill_dir}/LICENSE.txt"
                lic_resp = await client.get(lic_raw, headers=headers)
                if lic_resp.status_code == 200:
                    licence_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{skill_dir}/LICENSE.txt"
                    break

            skills.append({
                "name": name,
                "description": description,
                "raw_content": content,
                "licence": licence,
                "licence_url": licence_url,
                "source_url": source_url,
                "category": None,
            })
            logger.debug("Found skill: %s in %s", name, skill_dir)
        else:
            # No skill file here — recurse into subdirectories
            await _scan_dir(client, owner, repo, skill_dir, source_type, headers, skills, depth + 1)


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
