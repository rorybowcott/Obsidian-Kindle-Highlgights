"""Markdown rendering for highlights."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence

from .models import Highlight

SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._\- ]+")


def sanitise_filename(value: str) -> str:
    """Return a filesystem-safe filename derived from ``value``."""

    safe = SAFE_FILENAME_CHARS.sub(" ", value).strip()
    safe = re.sub(r"\s+", " ", safe)
    safe = safe.replace(" ", "_")
    return safe or "untitled"


def format_front_matter(metadata: dict) -> str:
    def format_scalar(value: Any) -> str:
        return json.dumps(value)

    lines: List[str] = ["---"]

    def emit(key: str, value: Any, indent: int, is_list_item: bool = False) -> None:
        prefix = "  " * indent
        if is_list_item:
            if isinstance(value, dict):
                if not value:
                    lines.append(f"{prefix}- {{}}")
                else:
                    lines.append(f"{prefix}-")
                    for subkey, subvalue in value.items():
                        emit(subkey, subvalue, indent + 1, is_list_item=False)
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{prefix}- []")
                else:
                    lines.append(f"{prefix}-")
                    for item in value:
                        emit("", item, indent + 1, is_list_item=True)
            else:
                lines.append(f"{prefix}- {format_scalar(value)}")
            return

        if isinstance(value, dict):
            if not value:
                lines.append(f"{prefix}{key}: {{}}")
            else:
                lines.append(f"{prefix}{key}:")
                for subkey, subvalue in value.items():
                    emit(subkey, subvalue, indent + 1, is_list_item=False)
        elif isinstance(value, list):
            if not value:
                lines.append(f"{prefix}{key}: []")
            else:
                lines.append(f"{prefix}{key}:")
                for item in value:
                    emit("", item, indent + 1, is_list_item=True)
        else:
            lines.append(f"{prefix}{key}: {format_scalar(value)}")

    for key, value in metadata.items():
        emit(key, value, 0, is_list_item=False)

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

    metadata: dict[str, Any] = {}
    lines = fm_text.splitlines()

    def parse_scalar(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    stack: List[dict[str, Any]] = [
        {"indent": -1, "container": metadata, "parent": None, "key": None},
    ]

    for raw_line in lines:
        if not raw_line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        content = raw_line[indent:]

        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()

        frame = stack[-1]
        container = frame["container"]

        if frame["container"] is None:
            if content.startswith("-"):
                container = []
            else:
                container = {}
            frame["container"] = container
            parent = frame["parent"]
            key = frame["key"]
            if isinstance(parent, list) and isinstance(key, int):
                parent[key] = container
            elif isinstance(parent, dict) and isinstance(key, str):
                parent[key] = container

        container = frame["container"]

        if content.startswith("-"):
            if not isinstance(container, list):
                new_list: list[Any] = []
                frame["container"] = new_list
                parent = frame["parent"]
                key = frame["key"]
                if isinstance(parent, list) and isinstance(key, int):
                    parent[key] = new_list
                elif isinstance(parent, dict) and isinstance(key, str):
                    parent[key] = new_list
                container = new_list

            item_value = content[1:].strip()
            if not item_value:
                index = len(container)
                container.append(None)
                stack.append(
                    {"indent": indent, "container": None, "parent": container, "key": index}
                )
            elif item_value == "{}":
                container.append({})
            elif item_value == "[]":
                container.append([])
            else:
                container.append(parse_scalar(item_value))
            continue

        if not isinstance(container, dict):
            # Unexpected structure; skip gracefully.
            continue

        if ":" not in content:
            continue

        key, value = content.split(":", 1)
        key = key.strip()
        value = value.strip()

        if not value:
            stack.append(
                {"indent": indent, "container": None, "parent": container, "key": key}
            )
        elif value == "{}":
            container[key] = {}
        elif value == "[]":
            container[key] = []
        else:
            container[key] = parse_scalar(value)

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
