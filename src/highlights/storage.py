"""Helpers for persisting highlights to Markdown files."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

from .markdown import format_front_matter, parse_front_matter, render_highlight, sanitise_filename
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
    metadata, existing_body = book_file.read()
    existing_ids_list: List[str] = []
    if metadata:
        ids = metadata.get("highlight_ids")
        if isinstance(ids, list):
            existing_ids_list = [str(value) for value in ids]
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

    if not existing_body:
        header_lines = [f"# {book_file.title}"]
        if book_file.author:
            header_lines.append("")
            header_lines.append(f"_by {book_file.author}_")
        header_lines.append("")
        existing_body = "\n".join(header_lines)

    body_parts = [existing_body.rstrip("\n"), ""]
    for highlight in new_highlights:
        body_parts.append(render_highlight(highlight, heading_template=heading_template))
    body_parts.append("")
    new_body = "\n".join(body_parts)

    book_file.write(metadata, new_body)
    return len(new_highlights), len(updated_ids)
