"""Command line entry point for syncing Kindle highlights into an Obsidian vault."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

from highlights.config import SyncConfig, load_config
from highlights.models import Highlight
from highlights.parsers import KindleCsvParser, MyClippingsParser
from highlights.storage import BookFile, append_highlights_to_file, build_book_filename


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Path to JSON configuration file", default=None)
    parser.add_argument("--clippings", type=Path, help="Path to 'My Clippings.txt'", default=None)
    parser.add_argument("--csv", type=Path, help="Path to Kindle Export CSV file", default=None)
    parser.add_argument("--vault", type=Path, help="Path to the root of the Obsidian vault", default=None)
    parser.add_argument("--subdir", help="Subdirectory inside the vault for highlight files", default=None)
    parser.add_argument(
        "--heading-template",
        help="Template for highlight headings (available keys: title, author, location)",
        default=None,
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without writing files")
    parser.add_argument(
        "--list", action="store_true", dest="list_only", help="List parsed highlights without writing"
    )
    return parser.parse_args(argv)


def _combine_config(args: argparse.Namespace) -> SyncConfig:
    try:
        file_config = load_config(args.config)
    except FileNotFoundError as exc:  # pragma: no cover - user error
        raise SystemExit(f"Configuration file not found: {args.config}") from exc
    except OSError as exc:  # pragma: no cover - user error
        raise SystemExit(f"Failed to read configuration file: {exc}") from exc
    config = SyncConfig.from_mapping(file_config)

    if args.clippings is not None:
        config.clippings_path = args.clippings
    if args.csv is not None:
        config.kindle_export_csv = args.csv
    if args.vault is not None:
        config.vault_root = args.vault
    if args.subdir is not None:
        config.vault_subdir = args.subdir
    if args.heading_template is not None:
        config.highlight_heading_template = args.heading_template
    if args.dry_run:
        config.dry_run = True
    return config


def _collect_highlights(config: SyncConfig) -> List[Highlight]:
    highlights: List[Highlight] = []
    if config.clippings_path:
        path = config.clippings_path.expanduser()
        if path.exists():
            parser = MyClippingsParser()
            highlights.extend(parser.parse(path))
        else:
            print(f"Warning: {path} not found; skipping My Clippings source.")
    if config.kindle_export_csv:
        path = config.kindle_export_csv.expanduser()
        if path.exists():
            parser = KindleCsvParser()
            highlights.extend(parser.parse(path))
        else:
            print(f"Warning: {path} not found; skipping Kindle CSV source.")
    return highlights


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    config = _combine_config(args)

    highlights = _collect_highlights(config)
    if not highlights:
        print("No highlights found in the provided sources.")
        return 1

    total_new = 0

    if args.list_only or config.dry_run:
        print(f"Found {len(highlights)} highlight(s).")

    for highlight in highlights:
        book_path = build_book_filename(
            config.vault_root, config.vault_subdir, highlight.book_title, highlight
        )
        book_file = BookFile(book_path, highlight.book_title, highlight.author)

        if args.list_only or config.dry_run:
            metadata, _ = book_file.read()
            existing_id = None
            if metadata:
                ids_value = metadata.get("highlight_ids")
                if isinstance(ids_value, list):
                    existing_id = ids_value[0] if ids_value else None
                elif ids_value is not None:
                    existing_id = str(ids_value)
            is_new = existing_id != highlight.highlight_id
            action = "create" if is_new or not book_file.path.exists() else "update"
            print(f"[DRY-RUN] Would {action} {book_path}")
            continue

        added, _ = append_highlights_to_file(
            book_file, highlight, heading_template=config.highlight_heading_template
        )
        total_new += added
        status = "Created" if added else "Updated"
        print(f"{status} {book_path}.")

    if not (args.list_only or config.dry_run):
        print(f"Sync complete: {total_new} new highlights added.")
    else:
        print("Dry-run complete; no files were written.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
