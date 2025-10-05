import csv
from pathlib import Path

from highlights.parsers import KindleCsvParser, MyClippingsParser


MY_CLIPPINGS_SAMPLE = """The Example Book (Jane Doe)
- Your Highlight on Location 120-122 | Added on Friday, 1 January 2021 10:00:00
This is a highlight from the book.
========== 
The Example Book (Jane Doe)
- Your Note on Location 120 | Added on Friday, 1 January 2021 10:00:00
This is an attached note.
========== 
"""


def test_my_clippings_parser_combines_notes(tmp_path: Path) -> None:
    sample_path = tmp_path / "My Clippings.txt"
    sample_path.write_text(MY_CLIPPINGS_SAMPLE, encoding="utf-8")

    parser = MyClippingsParser()
    highlights = list(parser.parse(sample_path))

    assert len(highlights) == 1
    highlight = highlights[0]
    assert highlight.text.startswith("This is a highlight")
    assert highlight.note == "This is an attached note."
    assert highlight.location == "120-122"
    assert highlight.highlight_id  # hash generated


def test_my_clippings_parser_handles_highlight_without_your(tmp_path: Path) -> None:
    sample = """Another Book (Author Name)
- Highlight on Page 5 | Added on Friday, 1 January 2021 11:00:00
Highlight text without your token.
==========
"""

    sample_path = tmp_path / "My Clippings.txt"
    sample_path.write_text(sample, encoding="utf-8")

    parser = MyClippingsParser()
    highlights = list(parser.parse(sample_path))

    assert len(highlights) == 1
    highlight = highlights[0]
    assert highlight.text == "Highlight text without your token."
    assert highlight.location == "5"


def test_kindle_csv_parser(tmp_path: Path) -> None:
    sample_path = tmp_path / "kindle.csv"
    with sample_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["title", "author", "Highlight", "Note", "Location"])
        writer.writeheader()
        writer.writerow(
            {
                "title": "The Example Book",
                "author": "Jane Doe",
                "Highlight": "CSV highlight text",
                "Note": "CSV note",
                "Location": "200-201",
            }
        )

    parser = KindleCsvParser()
    highlights = list(parser.parse(sample_path))

    assert len(highlights) == 1
    highlight = highlights[0]
    assert highlight.text == "CSV highlight text"
    assert highlight.note == "CSV note"
    assert highlight.location == "200-201"
