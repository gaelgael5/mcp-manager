"""Scan a GitHub repo referenced by a skills.sh source for SKILL.md files.

Two supported layouts:

1. "skills" format (historical skills.sh layout):
     <repo>/skills/<skill-name>/SKILL.md

2. "plugin" format (Claude Code plugin marketplace layout, e.g. wshobson/agents):
     <repo>/plugins/<plugin-name>/skills/<skill-name>/SKILL.md

The scanner auto-detects the format: try "skills" first, fall back to "plugin"
on 404. The detected format is returned so the caller can persist it on the
skill_sources row.
"""
import logging
import re

import httpx
import yaml

from mcp_manager.config import settings
from mcp_manager.connectors.github_pool import get_github_headers

logger = logging.getLogger(__name__)


async def scan_repo_skills(repo_url: str, repo_format: str | None = None) -> dict:
    """Scan a GitHub repo for skills in either "skills" or "plugin" layout.

    If ``repo_format`` is provided ("skills" or "plugin"), the scanner uses
    that layout directly. Otherwise it auto-detects by trying the "skills"
    layout first and falling back to "plugin" on 404.

    Returns ``{"status", "skills", "repo_format"}``:
      - ``status``: "ok" | "no_skills_dir" | "repo_404"
      - ``skills``: list of {name, description, raw_content, source_url, licence, licence_url, category}
      - ``repo_format``: "skills" | "plugin" | None (unknown)
    """
    if not repo_url or "github.com" not in repo_url:
        return {"status": "repo_404", "skills": [], "repo_format": None}

    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 5:
        return {"status": "repo_404", "skills": [], "repo_format": None}

    owner = parts[-2]
    repo = parts[-1]

    headers = get_github_headers()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Use repo_format as a priority hint, but always fall back to the
        # other layout if the first one returns no_skills_dir. This handles
        # legacy rows that have repo_format='skills' as default but whose
        # repo actually uses the plugin layout.
        if repo_format == "plugin":
            primary = _scan_plugin_layout
            fallback = _scan_skills_layout
        else:
            primary = _scan_skills_layout
            fallback = _scan_plugin_layout

        result = await primary(client, owner, repo, headers)
        if result["status"] == "ok":
            return result
        if result["status"] == "repo_404":
            return result
        # no_skills_dir on the primary layout — try the other one.
        fallback_result = await fallback(client, owner, repo, headers)
        if fallback_result["status"] == "ok":
            return fallback_result
        # Neither layout matched — return the primary's no_skills_dir.
        return result


async def _scan_skills_layout(
    client: httpx.AsyncClient, owner: str, repo: str, headers: dict
) -> dict:
    """Scan for the flat `skills/<skill>/SKILL.md` layout."""
    skills: list[dict] = []

    resp = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/skills",
        headers=headers,
    )

    if resp.status_code == 404:
        repo_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
        )
        if repo_resp.status_code == 404:
            return {"status": "repo_404", "skills": [], "repo_format": None}
        return {"status": "no_skills_dir", "skills": [], "repo_format": None}

    if resp.status_code != 200:
        logger.warning("GitHub API %d for %s/%s/skills", resp.status_code, owner, repo)
        return {"status": "repo_404", "skills": [], "repo_format": None}

    entries = resp.json()
    if not isinstance(entries, list):
        return {"status": "no_skills_dir", "skills": [], "repo_format": None}

    for entry in entries:
        if entry.get("type") != "dir":
            continue

        skill_name = entry["name"]
        if skill_name.startswith("."):
            continue

        for branch in ("main", "master"):
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

    logger.info("Scanned %s/%s (skills layout): %d skills found", owner, repo, len(skills))
    return {
        "status": "ok" if skills else "no_skills_dir",
        "skills": skills,
        "repo_format": "skills" if skills else None,
    }


async def _scan_plugin_layout(
    client: httpx.AsyncClient, owner: str, repo: str, headers: dict
) -> dict:
    """Scan for the `plugins/<plugin>/skills/<skill>/SKILL.md` layout.

    Uses the Git Trees API with recursive=1 to fetch the entire file tree
    in a single call, then filters paths matching the plugin/skill pattern.
    """
    skills: list[dict] = []

    # Determine the default branch to avoid a second API call.
    repo_resp = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}", headers=headers
    )
    if repo_resp.status_code == 404:
        return {"status": "repo_404", "skills": [], "repo_format": None}
    if repo_resp.status_code != 200:
        logger.warning("GitHub API %d for %s/%s", repo_resp.status_code, owner, repo)
        return {"status": "repo_404", "skills": [], "repo_format": None}
    default_branch = repo_resp.json().get("default_branch", "main")

    # Fetch the full recursive tree in one call.
    tree_resp = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1",
        headers=headers,
    )
    if tree_resp.status_code != 200:
        logger.warning("GitHub trees API %d for %s/%s", tree_resp.status_code, owner, repo)
        return {"status": "no_skills_dir", "skills": [], "repo_format": None}

    tree_data = tree_resp.json()
    if tree_data.get("truncated"):
        logger.warning("Git tree truncated for %s/%s — some skills may be missed", owner, repo)

    # Path pattern: plugins/<plugin>/skills/<skill>/SKILL.md
    plugin_skill_re = re.compile(r"^plugins/([^/]+)/skills/([^/]+)/SKILL\.md$")

    matched_paths: list[tuple[str, str, str]] = []
    for item in tree_data.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        m = plugin_skill_re.match(path)
        if m:
            plugin_name = m.group(1)
            skill_dir = m.group(2)
            matched_paths.append((path, plugin_name, skill_dir))

    if not matched_paths:
        return {"status": "no_skills_dir", "skills": [], "repo_format": None}

    # Fetch each SKILL.md via the raw.githubusercontent endpoint.
    for path, plugin_name, skill_dir in matched_paths:
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{path}"
        file_resp = await client.get(raw_url)
        if file_resp.status_code != 200:
            continue
        content = file_resp.text.replace("\x00", "")
        name, description, licence = _parse_frontmatter(content, skill_dir)
        source_url = f"https://github.com/{owner}/{repo}/tree/{default_branch}/plugins/{plugin_name}/skills/{skill_dir}"

        skills.append({
            "name": name,
            "description": description,
            "raw_content": content,
            "source_url": source_url,
            "licence": licence,
            "licence_url": None,
            "category": plugin_name,  # store the parent plugin name in category for UI grouping
        })
        logger.debug("Found skill: %s in %s/plugins/%s/skills/%s", name, repo, plugin_name, skill_dir)

    logger.info("Scanned %s/%s (plugin layout): %d skills found across plugins", owner, repo, len(skills))
    return {
        "status": "ok" if skills else "no_skills_dir",
        "skills": skills,
        "repo_format": "plugin" if skills else None,
    }


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
