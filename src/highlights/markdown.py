"""Markdown rendering for highlights."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional, Sequence

from .models import Highlight

SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._\- ]+")


def sanitise_filename(value: str) -> str:
    """Return a filesystem-safe filename derived from ``value``."""

    safe = SAFE_FILENAME_CHARS.sub(" ", value)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe or "untitled"


def format_front_matter(metadata: dict) -> str:
    lines: List[str] = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif value is None:
            lines.append(f"{key}:")
        else:
            if isinstance(value, str):
                safe_value = value.replace("\n", " ").replace('"', '\\"')
                safe_value = f'"{safe_value}"'
            else:
                safe_value = str(value).replace("\n", " ")
            lines.append(f"{key}: {safe_value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end_index = text.find("\n---", 4)
    if end_index == -1:
        return {}, text
    fm_text = text[4:end_index]
    remainder = text[end_index + 4 :]
    if remainder.startswith("\n"):
        remainder = remainder[1:]

    metadata: dict = {}
    current_key: Optional[str] = None
    for raw_line in fm_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_key:
            metadata.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                metadata[key] = []
                current_key = key
            else:
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('\\"', '"')
                metadata[key] = value
                current_key = None
    return metadata, remainder


def render_highlight(highlight: Highlight, heading_template: str = "Location {location}") -> str:
    lines: List[str] = []
    context = {
        "title": highlight.book_title,
        "author": highlight.author or "",
        "location": highlight.location or "unknown",
    }
    try:
        heading_value = heading_template.format(**context)
    except (KeyError, ValueError):
        heading_value = f"Location {context['location']}"
    location_text = heading_value or f"Location {context['location']}"
    lines.append(f"### {location_text}")
    lines.append("")
    if highlight.text:
        quote = highlight.text.strip().replace("\n", "\n>")
        lines.append(f"> {quote}")
    else:
        lines.append("> _No highlight text available._")
    if highlight.note:
        lines.append("")
        lines.append(f"**Note:** {highlight.note.strip()}")
    lines.append("")
    lines.append(f"<!-- highlight-id: {highlight.highlight_id} -->")
    lines.append("")
    return "\n".join(lines)


def render_book_document(
    title: str,
    author: Optional[str],
    highlights: Sequence[Highlight],
    heading_template: str = "Location {location}",
) -> str:
    metadata = {
        "title": title,
        "author": author or "Unknown",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "highlight_ids": [h.highlight_id for h in highlights],
    }
    front_matter = format_front_matter(metadata)
    heading_lines = [f"# {title}"]
    if author:
        heading_lines.append("")
        heading_lines.append(f"_by {author}_")
    heading_lines.append("")

    body_parts = [render_highlight(highlight, heading_template=heading_template) for highlight in highlights]
    body = "\n".join(body_parts)
    return front_matter + "\n".join(heading_lines) + body + ("\n" if not body.endswith("\n") else "")
