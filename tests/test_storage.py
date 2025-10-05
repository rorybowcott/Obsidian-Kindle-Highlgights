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


def test_writes_single_highlight_per_file(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    first_highlight = make_highlight()
    second_highlight = make_highlight(location="200-201", text="Another highlight")

    first_path = build_book_filename(
        vault, "Kindle Highlights", first_highlight.book_title, first_highlight
    )
    second_path = build_book_filename(
        vault, "Kindle Highlights", second_highlight.book_title, second_highlight
    )

    assert first_path != second_path

    first_file = BookFile(first_path, first_highlight.book_title, first_highlight.author)
    second_file = BookFile(second_path, second_highlight.book_title, second_highlight.author)

    added_first, total_first = append_highlights_to_file(first_file, first_highlight)
    added_second, total_second = append_highlights_to_file(second_file, second_highlight)

    assert (added_first, total_first) == (1, 1)
    assert (added_second, total_second) == (1, 1)

    first_metadata, first_body = first_file.read()
    second_metadata, second_body = second_file.read()

    assert first_metadata["title"] == first_highlight.book_title
    assert first_metadata["author"] == first_highlight.author
    assert first_metadata["highlight_ids"] == first_highlight.highlight_id
    assert first_metadata["highlights"] == first_highlight.text
    assert first_metadata["location_text"] == "Location 120-122"
    assert first_body.strip() == ""

    assert second_metadata["title"] == second_highlight.book_title
    assert second_metadata["author"] == second_highlight.author
    assert second_metadata["highlight_ids"] == second_highlight.highlight_id
    assert second_metadata["highlights"] == second_highlight.text
    assert second_metadata["location_text"] == "Location 200-201"
    assert second_body.strip() == ""


def test_append_highlights_handles_missing_location(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    highlight = make_highlight(location=None, text="No location highlight")
    book_path = build_book_filename(
        vault, "Kindle Highlights", highlight.book_title, highlight
    )
    book_file = BookFile(book_path, highlight.book_title, highlight.author)

    added, total = append_highlights_to_file(book_file, highlight)
    assert added == 1
    assert total == 1

    metadata, _ = book_file.read()
    assert metadata["highlights"] == "No location highlight"
    assert metadata["location_text"] == "Location unknown"


def test_build_book_filename_preserves_spaces(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    path = build_book_filename(vault, "Kindle Highlights", "My Book Title")

    assert path == vault / "Kindle Highlights" / "My Book Title.md"
