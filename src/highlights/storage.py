"""Helpers for persisting highlights to Markdown files."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

from .markdown import format_front_matter, parse_front_matter, sanitise_filename
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


def build_book_filename(vault_root: Path, subdir: str, title: str) -> Path:
    safe_title = sanitise_filename(title)
    relative = Path(subdir) / f"{safe_title}.md"
    return vault_root / relative


def merge_highlights(existing_ids: Set[str], highlights: Sequence[Highlight]) -> List[Highlight]:
    return [h for h in highlights if h.highlight_id not in existing_ids]


def append_highlights_to_file(
    book_file: BookFile, highlights: Sequence[Highlight], heading_template: str = "Location {location}"
) -> Tuple[int, int]:
    _ = heading_template  # Maintained for backwards compatibility; body content is no longer written.
    metadata, _existing_body = book_file.read()

    existing_highlight_entries: List[dict] = []
    if metadata:
        stored_highlights = metadata.get("highlights")
        if isinstance(stored_highlights, list):
            for item in stored_highlights:
                if isinstance(item, dict):
                    existing_highlight_entries.append(item)

    existing_ids_list = [str(entry.get("id")) for entry in existing_highlight_entries if entry.get("id")]
    existing_ids: Set[str] = set(existing_ids_list)

    new_highlights = merge_highlights(existing_ids, highlights)
    if not new_highlights:
        return 0, len(existing_ids)

    def highlight_to_metadata(highlight: Highlight) -> dict:
        return {
            "id": highlight.highlight_id,
            "location": highlight.location,
            "text": highlight.text,
            "note": highlight.note,
        }

    new_entries = [highlight_to_metadata(h) for h in new_highlights]
    updated_highlights = existing_highlight_entries + new_entries

    metadata = dict(metadata)
    metadata.update(
        {
            "title": metadata.get("title") or book_file.title,
            "author": metadata.get("author") or (book_file.author or "Unknown"),
            "highlight_ids": [entry["id"] for entry in updated_highlights],
            "highlights": updated_highlights,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )

    book_file.write(metadata, "")
    return len(new_highlights), len(updated_highlights)
