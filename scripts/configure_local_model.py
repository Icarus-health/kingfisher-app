#!/usr/bin/env python3
"""Ein lokales Ollama-Modell im laufenden Kingfisher einrichten und testen.

Die lokale Schlüsseldatei wird ausschließlich als Daten gelesen. Ihr Inhalt
wird niemals als Shell-Code ausgeführt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_BASE_URL = "http://127.0.0.1:8890"
DEFAULT_ENV_FILE = ".kingfisher.env"
DEFAULT_ENDPOINT = "http://host.docker.internal:11434/v1"
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]+$")
TOKEN_NAME = "ICARUS_SIDECAR_TOKEN"
REQUEST_TIMEOUT_SECONDS = 20
MODEL_TEST_TIMEOUT_SECONDS = 120


class ConfigurationError(Exception):
    """Ein erwarteter Einrichtungsfehler mit verständlicher Meldung."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Authentifizierte Anfragen niemals an einen anderen Host weiterleiten."""

    def redirect_request(self, *_args: Any, **_kwargs: Any):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect())


def _read_token(path: Path) -> str:
    """Nur die wörtliche Zuweisung von ICARUS_SIDECAR_TOKEN lesen.

    Die Datei enthält einfache NAME=Wert-Zeilen. Unbekannte Zeilen bleiben
    unberücksichtigt; keine Shell-Erweiterungen oder Befehle interpretieren.
    """

    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError("Die Env-Datei konnte nicht gelesen werden.") from exc

    values: list[str] = []
    for line in contents.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if separator and key.strip() == TOKEN_NAME:
            values.append(value.strip())

    if len(values) != 1 or not values[0]:
        raise ConfigurationError("Die Env-Datei enthält keinen brauchbaren Sidecar-Schlüssel.")
    if any(ord(character) < 0x21 or ord(character) > 0x7E for character in values[0]):
        raise ConfigurationError("Der Sidecar-Schlüssel enthält ungültige Zeichen.")
    return values[0]


def _validate_model(model: str | None) -> str:
    if not model or not MODEL_RE.fullmatch(model):
        raise ConfigurationError("Der Modellname enthält nicht unterstützte Zeichen.")
    return model


def _validate_base_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ConfigurationError("Die Kingfisher-Adresse ist ungültig.") from exc
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.query or parsed.fragment:
        raise ConfigurationError("Die Kingfisher-Adresse ist ungültig.")
    # Zugangsdaten gehören nicht in die lokale Kingfisher-Adresse.
    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError("Die Kingfisher-Adresse ist ungültig.")
    return value.rstrip("/")


def _validate_endpoint(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ConfigurationError("Der Modell-Endpunkt ist ungültig.") from exc
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.query or parsed.fragment:
        raise ConfigurationError("Der Modell-Endpunkt ist ungültig.")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError("Der Modell-Endpunkt ist ungültig.")
    return value.rstrip("/")


def _json_request(
    base_url: str,
    path: str,
    token: str,
    *,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json", "x-icarus-token": token}
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url}{path}", data=body, headers=headers, method=method
    )
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            response_body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        # Antwortdetails können Pfade, Modelltexte oder Zugangsdaten enthalten.
        # Deshalb ausschließlich den HTTP-Status ausgeben.
        raise ConfigurationError(f"Kingfisher meldet HTTP {exc.code} für {method} {path}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ConfigurationError(f"Kingfisher ist für {method} {path} nicht erreichbar.")
    if status < 200 or status >= 300:
        raise ConfigurationError(f"Kingfisher meldet HTTP {status} für {method} {path}.")
    try:
        decoded = json.loads(response_body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ConfigurationError(f"Kingfisher lieferte ungültiges JSON für {method} {path}.")
    if not isinstance(decoded, dict):
        raise ConfigurationError(f"Kingfisher lieferte ungültiges JSON für {method} {path}.")
    return decoded


def _setup_values(payload: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Aktiven Anbieter, Modellnamen und Endpunkt aus /setup lesen."""

    status = payload.get("status")
    settings = payload.get("settings")
    if not isinstance(status, Mapping) or not isinstance(settings, Mapping):
        raise ConfigurationError("Kingfisher meldet einen unvollständigen Einrichtungsstatus.")

    provider = status.get("provider")
    model = status.get("model")
    endpoint = status.get("endpoint")
    if provider is not None and not isinstance(provider, str):
        raise ConfigurationError("Kingfisher meldet einen unvollständigen Einrichtungsstatus.")
    if model is not None and not isinstance(model, str):
        raise ConfigurationError("Kingfisher meldet einen unvollständigen Einrichtungsstatus.")
    if endpoint is not None and not isinstance(endpoint, str):
        raise ConfigurationError("Kingfisher meldet einen unvollständigen Einrichtungsstatus.")
    return provider, model, endpoint


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE, type=Path)
    parser.add_argument("--model", default=None)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    return parser.parse_args(argv)


def run(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    # Eingaben vor dem Lesen des Schlüssels und vor jeder Anfrage prüfen.
    # Ungültige Werte dürfen die Einrichtung nicht verändern.
    try:
        model = _validate_model(args.model if args.model is not None else os.environ.get("MODELL"))
        base_url = _validate_base_url(args.base_url)
        endpoint = _validate_endpoint(args.endpoint)
        token = _read_token(args.env_file)
    except ConfigurationError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    try:
        before = _json_request(base_url, "/setup", token)
        _setup_values(before)
        after = _json_request(
            base_url,
            "/setup",
            token,
            method="PUT",
            payload={
                "provider": "ollama",
                "model": model,
                "endpoint": endpoint,
                "onboarded": True,
            },
        )
        actual_provider, actual_model, actual_endpoint = _setup_values(after)
    except ConfigurationError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    if actual_provider != "ollama" or actual_model != model:
        print(
            "FEHLER: Die Einrichtung wurde gespeichert, aber Startvariablen überschreiben Anbieter oder Modell.",
            file=sys.stderr,
        )
        return 1
    # Der Status nennt das aktive Ziel. Eine ICARUS_BASE_URL-Startvorgabe
    # darf nicht unbemerkt einen anderen Endpunkt testen lassen.
    if actual_endpoint is None or actual_endpoint.rstrip("/") != endpoint:
        print(
            "FEHLER: Die Einrichtung wurde gespeichert, aber Startvariablen überschreiben den Modell-Endpunkt.",
            file=sys.stderr,
        )
        return 1

    try:
        tested = _json_request(
            base_url,
            "/setup/test/modell",
            token,
            method="POST",
            timeout=MODEL_TEST_TIMEOUT_SECONDS,
        )
    except ConfigurationError:
        print(
            "FEHLER: Die Einrichtung wurde gespeichert, aber der Modell-Verbindungstest ist fehlgeschlagen. Details: make logs.",
            file=sys.stderr,
        )
        return 1
    if tested.get("ok") is not True:
        print(
            "FEHLER: Die Einrichtung wurde gespeichert, aber der Modell-Verbindungstest ist fehlgeschlagen. Details: make logs.",
            file=sys.stderr,
        )
        return 1

    print(f"Ollama-Modell {model} ist mit Kingfisher verbunden.")
    return 0


def main() -> int:
    try:
        return run()
    except ConfigurationError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
