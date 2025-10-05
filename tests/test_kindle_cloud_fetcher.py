"""Tests for the Kindle Cloud fetcher using mocked HTTP sessions."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

import pytest

from highlights.fetchers import KindleCloudFetchError, KindleCloudFetcher
from highlights.models import Highlight


class FakeCookies(dict):
    def set(self, name: str, value: str) -> None:  # pragma: no cover - behaviour covered indirectly
        self[name] = value


class FakeJar:
    def __init__(self) -> None:
        self.data: Dict[str, str] = {}

    def set(self, name: str, value: str) -> None:
        self.data[name] = value

    def get(self, name: str, default: str | None = None) -> str | None:
        return self.data.get(name, default)


class FakeResponse:
    def __init__(self, payload: Dict[str, object] | None = None, *, status_code: int = 200, cookies=None, headers=None) -> None:
        self._payload = payload
        self.status_code = status_code
        self.cookies = cookies or FakeCookies()
        self.headers = headers or {}

    def json(self) -> Dict[str, object]:
        if self._payload is None:
            raise ValueError("No JSON payload provided")
        return self._payload


class FakeSession:
    def __init__(self, get_responses: Iterable[FakeResponse], post_responses: Iterable[FakeResponse]) -> None:
        self.get_calls: List[tuple[str, Dict[str, str] | None]] = []
        self.post_calls: List[tuple[str, Dict[str, object] | None, Dict[str, str] | None]] = []
        self.cookies = FakeJar()
        self._get_responses = list(get_responses)
        self._post_responses = list(post_responses)

    def get(self, url: str, headers: Dict[str, str] | None = None) -> FakeResponse:
        self.get_calls.append((url, headers))
        return self._get_responses.pop(0)

    def post(
        self,
        url: str,
        *,
        json: Dict[str, object] | None = None,
        headers: Dict[str, str] | None = None,
    ) -> FakeResponse:
        self.post_calls.append((url, json, headers))
        return self._post_responses.pop(0)


def test_iter_highlights_paginates_and_parses(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("session-id=abc123; other=value", encoding="utf-8")

    get_response = FakeResponse(status_code=200, cookies=FakeCookies({"csrf-token": "csrf"}))
    page_one = FakeResponse(
        {
            "items": [
                {
                    "title": "Book One",
                    "authors": ["Author One"],
                    "highlight": {"text": "First highlight", "location": {"value": "123"}},
                    "note": {"text": "My note"},
                },
                {
                    "bookMetadata": {"title": "Book Two", "authors": ["Author Two"]},
                    "highlightText": "Second highlight",
                    "annotationLocation": "456",
                },
            ],
            "nextPageToken": "NEXT",
        }
    )
    page_two = FakeResponse(
        {
            "items": [
                {
                    "bookTitle": "Book Three",
                    "author": "Solo Author",
                    "text": "Final highlight",
                }
            ]
        }
    )
    session = FakeSession([get_response], [page_one, page_two])

    fetcher = KindleCloudFetcher(
        email="user@example.com",
        region="us",
        cookie_path=cookie_file,
        session=session,  # type: ignore[arg-type]
    )

    highlights = list(fetcher.iter_highlights(page_size=2))

    assert [h.book_title for h in highlights] == ["Book One", "Book Two", "Book Three"]
    assert [h.author for h in highlights] == ["Author One", "Author Two", "Solo Author"]
    assert [h.location for h in highlights] == ["123", "456", None]
    assert [h.note for h in highlights] == ["My note", None, None]
    assert all(h.source == "kindle_cloud" for h in highlights)
    assert isinstance(highlights[0], Highlight)

    # The cookie file should have been loaded into the session jar
    assert session.cookies.data["session-id"] == "abc123"

    # Ensure CSRF header was attached to POST requests
    _, _, headers = session.post_calls[0]
    assert headers is not None
    assert headers.get("x-amzn-csrf-token") == "csrf"
    assert session.post_calls[0][1] == {"maxResults": 2}
    assert session.post_calls[1][1] == {"maxResults": 2, "pageToken": "NEXT"}


def test_iter_highlights_raises_on_http_error(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("{}", encoding="utf-8")

    get_response = FakeResponse(status_code=500)
    session = FakeSession([get_response], [])

    fetcher = KindleCloudFetcher(cookie_path=cookie_file, session=session)  # type: ignore[arg-type]

    with pytest.raises(KindleCloudFetchError):
        list(fetcher.iter_highlights())
