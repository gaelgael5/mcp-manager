"""Heuristic quality scoring for summaries (0-100, no LLM needed)."""
import re


def _length_score(text: str) -> int:
    n = len(text)
    if n < 50:
        return 0
    if n < 200:
        return 5
    if n < 400:
        return 10
    if n <= 1500:
        return 20
    if n <= 2000:
        return 15
    return 12  # too verbose


def _structure_score(text: str) -> int:
    score = 0
    if re.search(r"^#{1,3}\s", text, re.MULTILINE):
        score += 5
    if re.search(r"^[-*]\s", text, re.MULTILINE):
        score += 5
    if "**" in text:
        score += 5
    if "`" in text:
        score += 5
    return min(score, 20)


_MCP_KEYWORDS = ["tool", "capability", "server", "resource", "api", "protocol"]
_SKILL_KEYWORDS = ["skill", "workflow", "automation", "command", "api", "tool"]
_USECASE_KEYWORDS = ["use case", "typical", "example", "when to", "scenario"]


def _keyword_score(text: str, keywords: list[str]) -> int:
    lower = text.lower()
    score = sum(3 for kw in keywords if kw in lower)
    return min(score, 15)


def _usecase_score(text: str) -> int:
    lower = text.lower()
    score = sum(5 for kw in _USECASE_KEYWORDS if kw in lower)
    return min(score, 15)


_POLLUTION_PATTERNS = [
    r"npm\s+install",
    r"pip\s+install",
    r"npx\s+",
    r"docker\s+run",
    r"```(json|yaml|yml)",
    r"!\[",  # badge images
    r"https?://badge",
]


def _pollution_score(text: str) -> int:
    score = 15
    for pat in _POLLUTION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            score -= 5
    return max(score, 0)


def _corruption_score(text: str) -> int:
    if "Agent indexer" in text or "démarré" in text:
        return 0
    return 15


def score_mcp_summary(summary: str) -> int:
    """Score 0-100 for an MCP service summary."""
    if not summary or not summary.strip():
        return 0
    return (
        _length_score(summary)
        + _structure_score(summary)
        + _keyword_score(summary, _MCP_KEYWORDS)
        + _usecase_score(summary)
        + _pollution_score(summary)
        + _corruption_score(summary)
    )


def score_skill_summary(summary: str) -> int:
    """Score 0-100 for a skill/skill_source summary."""
    if not summary or not summary.strip():
        return 0
    return (
        _length_score(summary)
        + _structure_score(summary)
        + _keyword_score(summary, _SKILL_KEYWORDS)
        + _usecase_score(summary)
        + _pollution_score(summary)
        + _corruption_score(summary)
    )
