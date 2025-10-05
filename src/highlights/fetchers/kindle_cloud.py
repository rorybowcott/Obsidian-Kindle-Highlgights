"""Fetch highlights from the Kindle Cloud reader API."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

try:  # pragma: no cover - handled in tests via dependency injection
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

from highlights.models import Highlight


class KindleCloudFetchError(RuntimeError):
    """Raised when highlights cannot be fetched from the Kindle Cloud."""


@dataclass(slots=True)
class _ApiRequest:
    """Internal structure describing a paginated API request."""

    page_token: Optional[str] = None
    page_size: int = 100

    def to_payload(self) -> Dict[str, object]:
        payload: Dict[str, object] = {"maxResults": self.page_size}
        if self.page_token:
            payload["pageToken"] = self.page_token
        return payload


class KindleCloudFetcher:
    """Retrieve highlights from the Kindle Cloud notebook service.

    The fetcher performs the two-step flow required by the Kindle Cloud reader:

    * a GET request to the notebook web application in order to obtain a CSRF
      token and authenticated cookies
    * a sequence of POST requests to the ``/notebook/api/annotations`` endpoint
      to iterate through all pages of highlights.

    Parameters
    ----------
    email:
        Optional email address to be included in log messages. Supplying the
        email is not required for authenticated requests but helps identify the
        account when multiple configurations are used.
    region:
        AWS region suffix for the Kindle domain. Supported values include
        ``"us"`` (default), ``"uk"``, ``"de"``, ``"fr"``, ``"jp"`` and
        ``"ca"``. Unknown values are treated as raw domain suffixes.
    cookie_path:
        Path to a file containing Kindle authentication cookies. The file can be
        a JSON object mapping cookie names to values or a plain ``Cookie``
        header string (``name=value; other=value``).
    session:
        Optional ``requests.Session`` instance. Primarily intended for tests so
        that HTTP requests can be mocked.
    """

    _REGION_SUFFIXES = {
        "us": "com",
        "uk": "co.uk",
        "de": "de",
        "fr": "fr",
        "jp": "co.jp",
        "ca": "ca",
        "au": "com.au",
        "in": "in",
    }

    def __init__(
        self,
        *,
        email: Optional[str] = None,
        region: str = "us",
        cookie_path: Optional[Path] = None,
        session: Optional["requests.Session"] = None,
    ) -> None:
        if session is None:
            if requests is None:  # pragma: no cover - handled by dependency tests
                raise KindleCloudFetchError(
                    "The optional 'requests' dependency is required for Kindle Cloud fetches."
                )
            session = requests.Session()
        self._session = session
        self.email = email
        self.region = region
        self.cookie_path = cookie_path
        self._csrf_token: Optional[str] = None
        self._base_url = self._build_base_url(region)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def iter_highlights(self, page_size: int = 100) -> Iterator[Highlight]:
        """Yield every highlight available in the configured Kindle account."""

        self._prepare_session()
        request = _ApiRequest(page_size=page_size)

        while True:
            data = self._fetch_page(request)
            annotations = data.get("items") or data.get("annotations") or []
            for payload in annotations:
                highlight = self._parse_annotation(payload)
                if highlight:
                    yield highlight
            next_token = data.get("nextPageToken") or data.get("nextToken")
            if not next_token:
                break
            request.page_token = str(next_token)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_base_url(self, region: str) -> str:
        suffix = self._REGION_SUFFIXES.get(region.lower(), region.lower())
        return f"https://read.amazon.{suffix}"

    def _prepare_session(self) -> None:
        if self.cookie_path:
            self._load_cookies(self.cookie_path)
        response = self._session.get(self._notebook_url, headers=self._default_headers)
        self._ensure_success(response)
        self._csrf_token = (
            response.cookies.get("csrf-token")
            or response.headers.get("x-amzn-csrf-token")
            or getattr(self._session, "cookies", {}).get("csrf-token")
        )
        if not self._csrf_token:
            raise KindleCloudFetchError(
                "Unable to locate CSRF token required for Kindle Cloud requests."
            )

    def _fetch_page(self, request: _ApiRequest) -> Dict[str, object]:
        headers = dict(self._default_headers)
        headers["x-amzn-csrf-token"] = str(self._csrf_token)
        response = self._session.post(
            self._api_url,
            json=request.to_payload(),
            headers=headers,
        )
        self._ensure_success(response)
        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - defensive programming
            raise KindleCloudFetchError("Received invalid JSON from Kindle Cloud API") from exc
        if not isinstance(payload, dict):
            raise KindleCloudFetchError("Unexpected response format from Kindle Cloud API")
        return payload

    @property
    def _default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": "Obsidian-Kindle-Highlights/1.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self._notebook_url,
            "Origin": self._base_url,
        }

    @property
    def _notebook_url(self) -> str:
        return f"{self._base_url}/notebook"

    @property
    def _api_url(self) -> str:
        return f"{self._base_url}/notebook/api/annotations"

    def _ensure_success(self, response: object) -> None:
        status = getattr(response, "status_code", None)
        if status is None or status >= 400:
            email_info = f" for {self.email}" if self.email else ""
            raise KindleCloudFetchError(
                f"Kindle Cloud request{email_info} failed with status code {status}."
            )

    def _parse_annotation(self, payload: Dict[str, object]) -> Optional[Highlight]:
        highlight_text = self._extract_text(payload)
        if not highlight_text:
            return None

        title = self._extract_first(payload, ["title", "bookTitle", "book_title"])
        author = self._extract_author(payload)
        location = self._extract_first(
            payload,
            [
                "location",
                "highlightLocation",
                "annotationLocation",
                "locationText",
            ],
        )
        note = self._extract_first(payload, ["note", "noteText", "annotationNote"])

        if isinstance(location, dict):
            location = location.get("value") or location.get("location")
        if isinstance(note, dict):
            note = note.get("text") or note.get("note")

        return Highlight(
            book_title=str(title or "Untitled"),
            author=str(author) if author else None,
            location=str(location) if location else None,
            text=str(highlight_text),
            note=str(note) if note else None,
            source="kindle_cloud",
        )

    def _extract_text(self, payload: Dict[str, object]) -> Optional[str]:
        candidates: Iterable[str] = (
            "highlight", "highlightText", "text", "annotationText", "highlight_text"
        )
        value: Optional[str] = None
        for key in candidates:
            maybe = payload.get(key)
            if isinstance(maybe, dict):
                if "text" in maybe and isinstance(maybe["text"], str):
                    return maybe["text"].strip() or None
            elif isinstance(maybe, str):
                stripped = maybe.strip()
                if stripped:
                    value = stripped
                    break
        return value

    def _extract_author(self, payload: Dict[str, object]) -> Optional[str]:
        authors = payload.get("authors") or payload.get("author")
        if isinstance(authors, list) and authors:
            first = authors[0]
            return str(first)
        if isinstance(authors, str) and authors.strip():
            return authors.strip()
        metadata = payload.get("bookMetadata") or payload.get("book")
        if isinstance(metadata, dict):
            return self._extract_author(metadata)
        return None

    def _extract_first(self, payload: Dict[str, object], keys: List[str]) -> Optional[object]:
        for key in keys:
            value = payload.get(key)
            if value:
                return value
            nested = self._seek_nested(payload, key)
            if nested:
                return nested
        return None

    def _seek_nested(self, payload: Dict[str, object], key: str) -> Optional[object]:
        for value in payload.values():
            if isinstance(value, dict) and key in value:
                return value[key]
        return None

    def _load_cookies(self, cookie_path: Path) -> None:
        try:
            raw = cookie_path.expanduser().read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem failure
            raise KindleCloudFetchError(f"Failed to read cookie file: {exc}") from exc

        jar = getattr(self._session, "cookies", None)
        if jar is None:
            return

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            cookies = parsed.get("cookies") if "cookies" in parsed else parsed
            if isinstance(cookies, dict):
                for name, value in cookies.items():
                    jar.set(name, str(value))
                return

        for chunk in raw.split(";"):
            if not chunk.strip():
                continue
            if "=" not in chunk:
                continue
            name, value = chunk.split("=", 1)
            jar.set(name.strip(), value.strip())

