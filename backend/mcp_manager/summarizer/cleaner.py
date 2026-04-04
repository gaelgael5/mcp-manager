import re

SKIP_SECTIONS = {"contributing", "contributors", "license", "changelog", "acknowledgements"}


def clean_markdown(content: str | None) -> str:
    if not content:
        return ""

    lines = content.split("\n")
    result: list[str] = []
    in_skip_section = False
    skip_level = 0
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue

        if in_code_block:
            result.append(line)
            continue

        header_match = re.match(r"^(#{1,6})\s+(.+)", line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip().lower()
            if title in SKIP_SECTIONS:
                in_skip_section = True
                skip_level = level
                continue
            if in_skip_section and level <= skip_level:
                in_skip_section = False

        if in_skip_section:
            continue

        if re.search(r"\[!\[.*?\]\(https?://img\.shields\.io", line):
            continue

        if re.match(r"^\s*!\[.*?\]\(.*?\)\s*$", line):
            continue

        result.append(line)

    return "\n".join(result).strip()
