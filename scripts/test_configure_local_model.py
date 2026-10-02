#!/usr/bin/env python3
"""Focused stdlib tests for configure_local_model.py."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import configure_local_model as cli


TOKEN = "test-token-that-must-not-be-printed"
MODEL = "qwen3.5:4b"


class _FakeServer:
    def __init__(self, responses: dict[str, tuple[int, Any] | str]):
        self.responses = responses
        self.requests: list[tuple[str, str, dict[str, str], bytes]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: Any) -> None:
                return

            def _respond(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                headers = {key.lower(): value for key, value in self.headers.items()}
                outer.requests.append((self.command, self.path, headers, body))
                response = outer.responses.get(f"{self.command} {self.path}")
                if response is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                if isinstance(response, str):
                    raw = response.encode("utf-8")
                    status = 200
                else:
                    status, document = response
                    raw = json.dumps(document).encode("utf-8")
                self.send_response(status)
                if status == 302 and isinstance(response, tuple):
                    self.send_header("Location", response[1]["location"])
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = _respond
            do_PUT = _respond
            do_POST = _respond

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self) -> "_FakeServer":
        self.thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _setup(
    provider: str = "",
    model: str = "",
    endpoint: str = "",
    *,
    status_endpoint: str | None = None,
) -> dict[str, Any]:
    return {
        "settings": {"provider": provider, "model": model, "endpoint": endpoint},
        "status": {
            "provider": provider or None,
            "model": model or None,
            **({"endpoint": status_endpoint} if status_endpoint is not None else {}),
        },
    }


@contextlib.contextmanager
def _run_cli(*args: str, env_contents: str = f"ICARUS_SIDECAR_TOKEN={TOKEN}\n"):
    with tempfile.TemporaryDirectory() as directory:
        env_file = Path(directory) / "kingfisher.env"
        env_file.write_text(env_contents, encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.run(("--env-file", str(env_file), *args))
        yield code, stdout.getvalue(), stderr.getvalue(), env_file


class ConfigureLocalModelTests(unittest.TestCase):
    def test_env_file_is_literal_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist"
            env_file = Path(directory) / "kingfisher.env"
            env_file.write_text(
                f"ICARUS_SIDECAR_TOKEN=literal-token\n"
                f"RUN_THIS=$(touch {marker})\n",
                encoding="utf-8",
            )
            self.assertEqual(cli._read_token(env_file), "literal-token")
            self.assertFalse(marker.exists())

    def test_success_saves_then_requires_connection_test(self) -> None:
        with _FakeServer(
            {
                "GET /setup": (200, _setup()),
                "PUT /setup": (200, _setup("ollama", MODEL, cli.DEFAULT_ENDPOINT, status_endpoint=cli.DEFAULT_ENDPOINT)),
                "POST /setup/test/modell": (200, {"ok": True, "detail": TOKEN}),
            }
        ) as server:
            with _run_cli(
                "--base-url", server.base_url, "--endpoint", cli.DEFAULT_ENDPOINT, "--model", MODEL
            ) as result:
                code, stdout, stderr, _ = result
            self.assertEqual(code, 0)
            self.assertIn(MODEL, stdout)
            self.assertNotIn(TOKEN, stdout + stderr)
            self.assertEqual([item[:2] for item in server.requests], [
                ("GET", "/setup"), ("PUT", "/setup"), ("POST", "/setup/test/modell")
            ])
            self.assertTrue(all(item[2].get("x-icarus-token") == TOKEN for item in server.requests))
            self.assertEqual(json.loads(server.requests[1][3])["provider"], "ollama")

    def test_http_200_false_is_failure_without_detail_leak(self) -> None:
        secret_detail = f"provider output {TOKEN}"
        with _FakeServer(
            {
                "GET /setup": (200, _setup()),
                "PUT /setup": (200, _setup("ollama", MODEL, cli.DEFAULT_ENDPOINT, status_endpoint=cli.DEFAULT_ENDPOINT)),
                "POST /setup/test/modell": (200, {"ok": False, "detail": secret_detail}),
            }
        ) as server:
            with _run_cli("--base-url", server.base_url, "--model", MODEL) as result:
                code, stdout, stderr, _ = result
            self.assertNotEqual(code, 0)
            self.assertEqual(stdout, "")
            self.assertNotIn(TOKEN, stdout + stderr)
            self.assertNotIn(secret_detail, stderr)

    def test_startup_override_is_detected_before_connection_test(self) -> None:
        with _FakeServer(
            {
                "GET /setup": (200, _setup()),
                # Settings are saved, but the effective status remains an env override.
                "PUT /setup": (200, {
                    "settings": {"provider": "ollama", "model": MODEL, "endpoint": cli.DEFAULT_ENDPOINT},
                    "status": {"provider": "openai", "model": "gpt-override"},
                }),
                "POST /setup/test/modell": (200, {"ok": True}),
            }
        ) as server:
            with _run_cli("--base-url", server.base_url, "--model", MODEL) as result:
                code, stdout, stderr, _ = result
            self.assertNotEqual(code, 0)
            self.assertEqual(stdout, "")
            self.assertIn("überschreiben", stderr)
            self.assertEqual(len(server.requests), 2)

    def test_endpoint_override_is_detected_even_when_model_matches(self) -> None:
        with _FakeServer(
            {
                "GET /setup": (200, _setup()),
                "PUT /setup": (200, {
                    "settings": {"provider": "ollama", "model": MODEL, "endpoint": cli.DEFAULT_ENDPOINT},
                    "status": {"provider": "ollama", "model": MODEL, "endpoint": "http://other-host:11434/v1"},
                }),
                "POST /setup/test/modell": (200, {"ok": True}),
            }
        ) as server:
            with _run_cli("--base-url", server.base_url, "--model", MODEL) as result:
                code, stdout, stderr, _ = result
            self.assertNotEqual(code, 0)
            self.assertEqual(stdout, "")
            self.assertIn("Modell-Endpunkt", stderr)
            self.assertEqual(len(server.requests), 2)

    def test_missing_effective_endpoint_is_failure(self) -> None:
        with _FakeServer(
            {
                "GET /setup": (200, _setup()),
                "PUT /setup": (200, _setup("ollama", MODEL, cli.DEFAULT_ENDPOINT)),
                "POST /setup/test/modell": (200, {"ok": True}),
            }
        ) as server:
            with _run_cli("--base-url", server.base_url, "--model", MODEL) as result:
                code, stdout, stderr, _ = result
            self.assertNotEqual(code, 0)
            self.assertEqual(stdout, "")
            self.assertIn("Modell-Endpunkt", stderr)
            self.assertEqual(len(server.requests), 2)

    def test_unreachable_server_is_failure_without_exception_dump(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "kingfisher.env"
            env_file.write_text(f"ICARUS_SIDECAR_TOKEN={TOKEN}\n", encoding="utf-8")
            # Port zero is not a listening endpoint after this temporary socket is closed.
            import socket
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.run(("--base-url", f"http://127.0.0.1:{port}", "--env-file", str(env_file), "--model", MODEL))
            self.assertNotEqual(code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn(TOKEN, stdout.getvalue() + stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_malformed_setup_response_is_failure(self) -> None:
        with _FakeServer({"GET /setup": "not-json"}) as server:
            with _run_cli("--base-url", server.base_url, "--model", MODEL) as result:
                code, stdout, stderr, _ = result
            self.assertNotEqual(code, 0)
            self.assertEqual(stdout, "")
            self.assertIn("ungültiges JSON", stderr)
            self.assertNotIn(TOKEN, stderr)

    def test_redirect_is_failure(self) -> None:
        with _FakeServer({"GET /setup": (200, _setup())}) as target:
            with _FakeServer({"GET /setup": (302, {"location": target.base_url + "/setup"})}) as server:
                with _run_cli("--base-url", server.base_url, "--model", MODEL) as result:
                    code, stdout, stderr, _ = result
                self.assertNotEqual(code, 0)
                self.assertEqual(stdout, "")
                self.assertNotIn(TOKEN, stderr)
                self.assertEqual(len(server.requests), 1)
                self.assertEqual(target.requests, [])

    def test_invalid_model_and_literal_env_file_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist"
            env_file = Path(directory) / "kingfisher.env"
            env_file.write_text(
                f"ICARUS_SIDECAR_TOKEN=$(touch {marker})\n"
                f"IGNORED=$(touch {marker})\n",
                encoding="utf-8",
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.run(("--env-file", str(env_file), "--model", "bad;touch"))
            self.assertNotEqual(code, 0)
            self.assertFalse(marker.exists())
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn("touch", stderr.getvalue())

    def test_model_can_come_from_MODELL_environment(self) -> None:
        with _FakeServer(
            {
                "GET /setup": (200, _setup()),
                "PUT /setup": (200, _setup("ollama", MODEL, cli.DEFAULT_ENDPOINT, status_endpoint=cli.DEFAULT_ENDPOINT)),
                "POST /setup/test/modell": (200, {"ok": True}),
            }
        ) as server:
            previous = os.environ.get("MODELL")
            os.environ["MODELL"] = MODEL
            try:
                with _run_cli("--base-url", server.base_url) as result:
                    code, stdout, stderr, _ = result
            finally:
                if previous is None:
                    os.environ.pop("MODELL", None)
                else:
                    os.environ["MODELL"] = previous
            self.assertEqual(code, 0)
            self.assertIn("verbunden", stdout)
            self.assertEqual(stderr, "")


if __name__ == "__main__":
    unittest.main()
