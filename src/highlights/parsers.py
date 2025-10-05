"""Parsers that ingest Kindle highlight exports."""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Highlight


class HighlightParser:
    """Base class for highlight parsers."""

    def parse(self, path: Path) -> Iterable[Highlight]:
        raise NotImplementedError


class MyClippingsParser(HighlightParser):
    """Parses the legacy `My Clippings.txt` Kindle export."""

    SEPARATOR = "=========="
    META_PATTERN = re.compile(
        r"^-\s*Your\s+(?P<entry_type>Highlight|Note)\s+on\s+"  # entry type
        r"(?:(?:Location|Page)\s+(?P<location>[\d\-]+))?.*"  # location (optional)
    )

    HEADER_PATTERN = re.compile(
        r"^(?P<title>.+?)(?:\s*\((?P<author>[^)]*)\))?$"
    )

    @staticmethod
    def _location_key(location: Optional[str]) -> Optional[str]:
        if not location:
            return None
        match = re.match(r"(\d+)", location)
        if match:
            return match.group(1)
        return location

    def parse(self, path: Path) -> Iterable[Highlight]:
        text = path.expanduser().resolve().read_text(encoding="utf-8-sig")
        raw_entries = [segment.strip() for segment in text.split(self.SEPARATOR)]

        entries: List[Dict[str, Optional[str]]] = []
        last_highlight_index: Dict[Tuple[str, Optional[str], Optional[str]], int] = {}

        for raw in raw_entries:
            if not raw:
                continue
            lines = [line.rstrip("\ufeff").strip() for line in raw.splitlines() if line.strip()]
            if len(lines) < 2:
                continue
            header_match = self.HEADER_PATTERN.match(lines[0])
            if not header_match:
                continue
            title = header_match.group("title").strip()
            author = header_match.group("author")
            author = author.strip() if author else None

            meta_match = self.META_PATTERN.match(lines[1])
            if not meta_match:
                continue
            entry_type = meta_match.group("entry_type")
            location = meta_match.group("location")

            body = "\n".join(lines[2:]).strip()
            key = (title, author, self._location_key(location))

            if entry_type == "Note":
                if not body:
                    continue
                index = last_highlight_index.get(key)
                if index is not None:
                    entries[index]["note"] = body
                else:
                    entries.append(
                        {
                            "book_title": title,
                            "author": author,
                            "location": location,
                            "text": "",
                            "note": body,
                            "source": "my_clippings",
                        }
                    )
                continue

            entry = {
                "book_title": title,
                "author": author,
                "location": location,
                "text": body,
                "note": None,
                "source": "my_clippings",
            }
            entries.append(entry)
            last_highlight_index[key] = len(entries) - 1

        highlights: List[Highlight] = []
        for entry in entries:
            if not (entry["text"] or entry["note"]):
                continue
            highlights.append(
                Highlight(
                    book_title=entry["book_title"] or "Unknown",
                    author=entry["author"],
                    location=entry["location"],
                    text=entry["text"] or "",
                    note=entry["note"],
                    source=str(entry["source"] or "my_clippings"),
                )
            )

        return highlights


class KindleCsvParser(HighlightParser):
    """Parses Kindle Export CSV files."""

    def parse(self, path: Path) -> Iterable[Highlight]:
        highlights: List[Highlight] = []
        with path.expanduser().resolve().open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                title = (row.get("title") or row.get("Book Title") or row.get("book_title") or "").strip()
                author = (row.get("author") or row.get("Authors") or row.get("authors") or None)
                author = author.strip() if author else None
                location = (row.get("Location") or row.get("location") or row.get("annotation_location") or None)
                location = location.strip() if isinstance(location, str) else location
                text = (row.get("Highlight") or row.get("highlight") or row.get("annotation") or "").strip()
                note = row.get("Note") or row.get("note")
                if isinstance(note, str):
                    note = note.strip() or None

                if not any([text, note]):
                    continue

                highlights.append(
                    Highlight(
                        book_title=title,
                        author=author,
                        location=location,
                        text=text,
                        note=note,
                        source="kindle_csv",
                    )
                )
        return highlights


def group_by_book(highlights: Iterable[Highlight]) -> Iterable[Tuple[str, Optional[str], List[Highlight]]]:
    grouped: Dict[Tuple[str, Optional[str]], List[Highlight]] = defaultdict(list)
    for highlight in highlights:
        grouped[(highlight.book_title, highlight.author)].append(highlight)

    for (title, author), items in sorted(
        grouped.items(), key=lambda item: (item[0][0].lower(), item[0][1] or "")
    ):
        # Sort by numeric component of location if available
        def location_key(value: Highlight) -> Tuple[int, str]:
            if value.location:
                match = re.search(r"\d+", value.location)
                if match:
                    return int(match.group()), value.location
            return (1 << 30, value.location or "")

        items.sort(key=location_key)
        yield title, author, items
