from pathlib import Path

from highlights.models import Highlight
from highlights.storage import BookFile, append_highlights_to_file, build_book_filename


def make_highlight(**kwargs) -> Highlight:
    base = {
        "book_title": "The Example Book",
        "author": "Jane Doe",
        "location": "120-122",
        "text": "This is a highlight.",
        "note": "Optional note.",
        "source": "test",
    }
    base.update(kwargs)
    return Highlight(**base)


def test_append_highlights_deduplicates(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    book_path = build_book_filename(vault, "Kindle Highlights", "The Example Book")
    book_file = BookFile(book_path, "The Example Book", "Jane Doe")

    first_highlight = make_highlight()
    second_highlight = make_highlight(location="200-201", text="Another highlight")

    added, total = append_highlights_to_file(book_file, [first_highlight])
    assert added == 1
    assert total == 1

    added_again, total_again = append_highlights_to_file(book_file, [first_highlight, second_highlight])
    assert added_again == 1
    assert total_again == 2

    content = book_path.read_text(encoding="utf-8")
    assert content.count("highlight-id") == 2


def test_build_book_filename_preserves_spaces(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = build_book_filename(vault, "Kindle Highlights", "My Book Title")

    assert path == vault / "Kindle Highlights" / "My Book Title.md"
