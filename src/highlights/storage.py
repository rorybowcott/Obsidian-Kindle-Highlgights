"""Helpers for persisting highlights to Markdown files."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

from .markdown import (
    format_front_matter,
    parse_front_matter,
    sanitise_filename,
    serialise_highlight,
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


def build_book_filename(vault_root: Path, subdir: str, title: str) -> Path:
    safe_title = sanitise_filename(title)
    relative = Path(subdir) / f"{safe_title}.md"
    return vault_root / relative


def merge_highlights(existing_ids: Set[str], highlights: Sequence[Highlight]) -> List[Highlight]:
    return [h for h in highlights if h.highlight_id not in existing_ids]


def append_highlights_to_file(
    book_file: BookFile, highlights: Sequence[Highlight], heading_template: str = "Location {location}"
) -> Tuple[int, int]:
    # ``heading_template`` is retained for API compatibility but no longer used for rendering.
    _ = heading_template
    metadata, existing_body = book_file.read()
    existing_ids_list: List[str] = []
    existing_highlight_entries: List[dict] = []
    if metadata:
        ids = metadata.get("highlight_ids")
        if isinstance(ids, list):
            existing_ids_list = [str(value) for value in ids]
        highlights_meta = metadata.get("highlights")
        if isinstance(highlights_meta, list):
            existing_highlight_entries = list(highlights_meta)
            if not existing_ids_list:
                for entry in existing_highlight_entries:
                    highlight_id = entry.get("highlight_id")
                    if highlight_id is not None:
                        existing_ids_list.append(str(highlight_id))
    existing_ids: Set[str] = set(existing_ids_list)

    new_highlights = merge_highlights(existing_ids, highlights)
    if not new_highlights:
        return 0, len(existing_ids)

    updated_ids = existing_ids_list + [h.highlight_id for h in new_highlights]
    updated_ids = list(dict.fromkeys(updated_ids))

    metadata = dict(metadata)
    metadata.update(
        {
            "title": metadata.get("title") or book_file.title,
            "author": metadata.get("author") or (book_file.author or "Unknown"),
            "highlight_ids": updated_ids,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )

    serialized_highlights = [serialise_highlight(h) for h in new_highlights]
    metadata["highlights"] = existing_highlight_entries + serialized_highlights

    book_file.write(metadata, existing_body)
    return len(new_highlights), len(updated_ids)
