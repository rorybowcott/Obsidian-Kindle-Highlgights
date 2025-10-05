"""Markdown rendering for highlights."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

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
        if isinstance(value, (list, dict)):
            json_value = json.dumps(value, ensure_ascii=False)
            lines.append(f"{key}: {json_value}")
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
            existing = metadata.get(current_key)
            if not isinstance(existing, list):
                existing = []
            existing.append(line[4:].strip())
            metadata[current_key] = existing
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                metadata[key] = None
                current_key = key
            else:
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('\\"', '"')
                    parsed_value: Any = value
                else:
                    try:
                        parsed_value = json.loads(value)
                    except json.JSONDecodeError:
                        parsed_value = value
                metadata[key] = parsed_value
                current_key = None
    return metadata, remainder


def serialise_highlight(highlight: Highlight) -> Dict[str, Any]:
    return {
        "highlight_id": highlight.highlight_id,
        "location": highlight.location,
        "text": highlight.text,
        "note": highlight.note,
        "source": highlight.source,
    }


def render_book_document(
    title: str,
    author: Optional[str],
    highlights: Sequence[Highlight],
    heading_template: str = "Location {location}",
) -> str:
    _ = heading_template
    metadata = {
        "title": title,
        "author": author or "Unknown",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "highlight_ids": [h.highlight_id for h in highlights],
        "highlights": [serialise_highlight(h) for h in highlights],
    }
    front_matter = format_front_matter(metadata)
    return front_matter
