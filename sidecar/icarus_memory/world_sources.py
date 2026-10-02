"""Bounded, read-only retrieval of public web text.

The returned text is untrusted source material.  This module deliberately has
no model, persistence, or credential access; callers decide whether and how to
use the result.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from .security import SecurityError, check_url

MAX_BYTES = 512 * 1024
MAX_TEXT_CHARS = 12_000
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 10.0
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class _TextParser(HTMLParser):
    _BLOCKS = {
        "address", "article", "aside", "blockquote", "br", "div", "dl",
        "dt", "dd", "fieldset", "figcaption", "figure", "footer", "form",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li",
        "main", "nav", "ol", "p", "pre", "section", "table", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in {"script", "style"}:
            self._ignored.append(tag)
        elif not self._ignored and tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._ignored and tag.casefold() in self._BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._ignored:
            if tag == self._ignored[-1]:
                self._ignored.pop()
            return
        if tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            self.parts.append(data)


def _validate_url(raw: str) -> str:
    if not isinstance(raw, str):
        raise ValueError("URL muss eine Zeichenkette sein.")
    value = raw.strip()
    if not value:
        raise ValueError("URL darf nicht leer sein.")
    value, _fragment = urldefrag(value)
    parsed = urlparse(value)
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise SecurityError("URL muss einen öffentlichen Host ohne Zugangsdaten enthalten.")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("URL enthält einen ungültigen Port.") from exc
    # Check the destination before the scheme policy too, so an HTTP redirect
    # to a private address is rejected by the SSRF guard before any request.
    check_url(value)
    if parsed.scheme.casefold() != "https":
        raise SecurityError("Nur HTTPS-URLs sind erlaubt.")
    return value


def _extract_text(source: str, *, html: bool = True) -> tuple[str, bool]:
    if html:
        parser = _TextParser()
        try:
            parser.feed(source)
            parser.close()
        except (RecursionError, ValueError) as exc:
            raise ValueError("Die öffentliche Quelle ist nicht lesbar.") from exc
        source = parser.text
    text = " ".join(source.split())
    if not text:
        raise ValueError("Die öffentliche Quelle enthält keinen Text.")
    truncated = len(text) > MAX_TEXT_CHARS
    return text[:MAX_TEXT_CHARS], truncated


def fetch_public_text(url: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Fetch one public HTTPS URL with strict byte, redirect, and text limits."""
    current = url
    owned_client = client is None
    active = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    body = bytearray()
    try:
        for redirects in range(MAX_REDIRECTS + 1):
            # Re-check here as well as in _validate_url: this guard stays next
            # to the actual network operation, including the first request.
            current = _validate_url(current)
            try:
                with active.stream(
                    "GET", current, follow_redirects=False, timeout=TIMEOUT_SECONDS
                ) as response:
                    if response.status_code in REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Weiterleitung ohne Ziel.")
                        if redirects >= MAX_REDIRECTS:
                            raise ValueError("Zu viele Weiterleitungen.")
                        current = urldefrag(urljoin(current, location))[0]
                        continue
                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    if content_length:
                        try:
                            declared_length = int(content_length)
                        except ValueError:
                            declared_length = 0
                        if declared_length > MAX_BYTES:
                            raise ValueError("Die Quelle überschreitet 512 KiB.")
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise ValueError("Die Quelle überschreitet 512 KiB.")
                    encoding = response.encoding or "utf-8"
                    content_type = response.headers.get("content-type", "").casefold()
            except httpx.HTTPError as exc:
                raise ValueError("Die öffentliche Quelle konnte nicht abgerufen werden.") from exc
            break
        else:  # pragma: no cover - range always enters the loop
            raise ValueError("Zu viele Weiterleitungen.")
    finally:
        if owned_client:
            active.close()

    source_digest = sha256(body).hexdigest()
    decoded = bytes(body).decode(encoding, errors="replace")
    is_html = "text/html" in content_type or "application/xhtml+xml" in content_type
    if not content_type:
        is_html = "<" in decoded and ">" in decoded
    text, truncated = _extract_text(decoded, html=is_html)
    return {
        "url": current,
        "text": text,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_sha256": source_digest,
        "truncated": truncated,
    }


__all__ = ["fetch_public_text"]
