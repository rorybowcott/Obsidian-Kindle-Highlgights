"""Data models for Kindle highlight synchronization."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from typing import Optional


@dataclass(frozen=True)
class Highlight:
    """Represents a Kindle highlight or note."""

    book_title: str
    author: Optional[str]
    location: Optional[str]
    text: str
    note: Optional[str] = None
    source: str = "unknown"
    highlight_id: str = field(init=False)

    def __post_init__(self) -> None:
        # Normalise values used for hashing so that id generation is stable.
        components = [
            (self.book_title or "").strip(),
            (self.author or "").strip(),
            (self.location or "").strip(),
            (self.text or "").strip(),
            (self.note or "").strip(),
            (self.source or "").strip(),
        ]
        digest_input = "\u241f".join(components).encode("utf-8")
        object.__setattr__(self, "highlight_id", sha1(digest_input).hexdigest())


@dataclass
class BookHighlights:
    """Grouping of highlights for a single book."""

    title: str
    author: Optional[str]
    highlights: list[Highlight]
