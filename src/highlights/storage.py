"""Helpers for persisting highlights to Markdown files."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from .markdown import (
    format_front_matter,
    parse_front_matter,
    sanitise_filename,
    _format_location_text,
)
from .models import Highlight


class BookFile:
    """Represents an on-disk Markdown file for a book's highlights."""

    def __init__(self, path: Path, title: str, author: Optional[str]) -> None:
        self.path = path
        self.title = title
        self.author = author

    def read(self) -> tuple[dict, str]:
        if not self.path.exists():
            return {}, ""
        text = self.path.read_text(encoding="utf-8")
        return parse_front_matter(text)

    def write(self, metadata: dict, body: str) -> None:
        content = format_front_matter(metadata) + body
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")


def build_book_filename(
    vault_root: Path,
    subdir: str,
    title: str,
    highlight: Optional[Highlight] = None,
) -> Path:
    safe_title = sanitise_filename(title)
    relative = Path(subdir)

    if highlight is None:
        filename = f"{safe_title}.md"
    else:
        location_fragment = sanitise_filename(highlight.location or "Location unknown") or "Location unknown"
        identifier_fragment = highlight.highlight_id[:12]
        filename = f"{safe_title} - {location_fragment} - {identifier_fragment}.md"

    return vault_root / relative / filename


def append_highlights_to_file(
    book_file: BookFile,
    highlight: Highlight,
    heading_template: str = "Location {location}",
) -> Tuple[int, int]:
    # ``heading_template`` is retained for API compatibility but no longer used for rendering.
    _ = heading_template

    metadata, _ = book_file.read()
    existing_id: Optional[str] = None
    if metadata:
        ids_value = metadata.get("highlight_ids")
        if isinstance(ids_value, list):
            existing_id = ids_value[0] if ids_value else None
        elif ids_value is not None:
            existing_id = str(ids_value)

    if (
        existing_id == highlight.highlight_id
        and metadata.get("highlights") == highlight.text
        and metadata.get("location_text") == _format_location_text(highlight.location)
    ):
        return 0, 1

    new_metadata = {
        "title": book_file.title,
        "author": book_file.author or "Unknown",
        "highlight_ids": highlight.highlight_id,
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "highlights": highlight.text,
        "location_text": _format_location_text(highlight.location),
    }

    book_file.write(new_metadata, "")
    added = 0 if existing_id == highlight.highlight_id else 1
    return added, 1
