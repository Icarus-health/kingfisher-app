import hashlib

import httpx
import pytest

from icarus_memory import world_sources


def client(routes):
    return httpx.Client(transport=httpx.MockTransport(routes))


def test_fetches_html_and_returns_digest(monkeypatch):
    monkeypatch.setattr(world_sources, "check_url", lambda url: url)
    body = b"<h1>Hello &amp; world</h1><script>window.bad()</script><p>Text</p>"
    result = world_sources.fetch_public_text(
        "https://example.test/page#fragment",
        client=client(lambda request: httpx.Response(200, content=body, request=request)),
    )
    assert result["url"] == "https://example.test/page"
    assert result["text"] == "Hello & world Text"
    assert result["source_sha256"] == hashlib.sha256(body).hexdigest()
    assert result["truncated"] is False
    assert result["captured_at"].endswith("Z")


def test_redirect_private_is_checked_before_request(monkeypatch):
    checked = []
    monkeypatch.setattr(world_sources, "check_url", lambda url: checked.append(url) or url)
    requests = []

    def route(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"}, request=request)

    with pytest.raises(world_sources.SecurityError):
        world_sources.fetch_public_text("https://example.test", client=client(route))
    assert requests == ["https://example.test"]
    assert "http://127.0.0.1/secret" in checked


def test_redirect_loop_and_limits(monkeypatch):
    monkeypatch.setattr(world_sources, "check_url", lambda url: url)
    with pytest.raises(ValueError, match="Weiterleitungen"):
        world_sources.fetch_public_text(
            "https://example.test/a",
            client=client(lambda request: httpx.Response(302, headers={"location": str(request.url)}, request=request)),
        )
    with pytest.raises(ValueError, match="512 KiB"):
        world_sources.fetch_public_text(
            "https://example.test",
            client=client(lambda request: httpx.Response(200, content=b"x" * (512 * 1024 + 1), request=request)),
        )


def test_malformed_and_empty_sources_fail(monkeypatch):
    monkeypatch.setattr(world_sources, "check_url", lambda url: url)
    with pytest.raises(world_sources.SecurityError):
        world_sources.fetch_public_text("http://example.test")
    with pytest.raises(ValueError):
        world_sources.fetch_public_text(
            "https://example.test", client=client(lambda request: httpx.Response(200, content=b"<html>", request=request))
        )


def test_text_limit_is_explicitly_reported(monkeypatch):
    monkeypatch.setattr(world_sources, "check_url", lambda url: url)
    body = (b"word " * 3000)
    result = world_sources.fetch_public_text(
        "https://example.test", client=client(lambda request: httpx.Response(200, content=body, request=request))
    )
    assert len(result["text"]) == 12_000
    assert result["truncated"] is True


def test_plaintext_keeps_angle_brackets(monkeypatch):
    monkeypatch.setattr(world_sources, "check_url", lambda url: url)
    result = world_sources.fetch_public_text(
        "https://example.test", client=client(lambda request: httpx.Response(
            200, headers={"content-type": "text/plain"}, content=b"literal <tag> text", request=request)))
    assert result["text"] == "literal <tag> text"
