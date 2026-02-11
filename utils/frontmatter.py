"""Shared YAML-frontmatter helpers."""

import re


def parse_frontmatter(content: str) -> dict:
    """Parse YAML-style frontmatter from a markdown string.

    Returns a dict of key-value pairs (all values are strings).
    """
    fm: dict[str, str] = {}
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return fm
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def create_frontmatter(data: dict) -> str:
    """Serialize a dict into a YAML frontmatter block.

    >>> create_frontmatter({"type": "task", "priority": "high"})
    '---\\ntype: task\\npriority: high\\n---'
    """
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)
