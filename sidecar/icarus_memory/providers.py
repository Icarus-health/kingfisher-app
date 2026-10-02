"""Säule 2 auf der Modellseite: austauschbare Anbieter.

Zwei Formen decken praktisch das Feld ab:

* **OpenAI-kompatibel** — OpenAI selbst, Ollama, LM Studio, vLLM, llama.cpp,
  Groq, Together und die meisten lokalen Server. Ein lokales Modell ist damit
  eine Frage der Basis-URL, keine Sonderbehandlung.
* **Anthropic** — eigenes Format für Nachrichten und Werkzeuge.

Nach außen sehen beide gleich aus. Der Rest des Systems kennt nur `Provider`,
`Reply` und `ToolCall` und weiß nicht, wer antwortet — das ist der Punkt.
"""

from __future__ import annotations

import json
from contextlib import nullcontext
import ipaddress
import os
from dataclasses import dataclass, field
from collections.abc import Collection
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""


class ProviderError(Exception):
    pass


class Provider(Protocol):
    name: str
    model: str
    is_local: bool
    """Ist der Endpunkt lokal? Dies allein beweist keine lokalen Modellgewichte."""

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Reply: ...


def _http(timeout: float = 120.0) -> httpx.Client:
    return httpx.Client(timeout=timeout)


def is_local_endpoint(
    base_url: str,
    trusted_hosts: Collection[str] = (),
) -> bool:
    """Läuft dieser Anbieter auf diesem Rechner?

    Entscheidet über den Schutzbedarf, der ihm zugemutet werden darf. Nur
    Loopback zählt als lokal: ein Ollama im Heimnetz ist bereits ein Netzwerk,
    und ein Hostname, der heute auf 127.0.0.1 zeigt, kann morgen umziehen.
    Deshalb wird die Adresse literal geprüft und nicht aufgelöst.

    Container erreichen einen Dienst auf dem Host nicht als Loopback. Dafür
    gibt es eine kleine, ausdrückliche Ausnahme: Ein vom Betreiber wörtlich
    freigegebener Bridge-Hostname darf ebenfalls als lokal gelten. Es gibt
    keine Suffix-, DNS- oder Netzbereichsfreigabe.
    """
    try:
        host = urlparse(base_url).hostname
    except ValueError:
        return False
    if not host:
        return False
    if host == "localhost":
        return True
    if host in {entry.strip().lower() for entry in trusted_hosts if entry.strip()}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class OpenAICompatible:
    """Deckt OpenAI und jeden Server mit /chat/completions ab.

    Ollama nutzt etwa base_url=http://localhost:11434/v1 und einen beliebigen
    Schlüssel. Lokale Automatik prüft zusätzlich die installierten Gewichte:
    Auch ein lokaler Ollama-Endpunkt kann ein Cloud-Modell weiterleiten.
    """

    name = "openai"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        trusted_local_hosts: Collection[str] = (),
    ) -> None:
        self.model = model
        self._key = api_key or "not-needed"
        self._base = base_url.rstrip("/")
        self._trusted_local_hosts = tuple(trusted_local_hosts)
        self.is_local = is_local_endpoint(base_url, trusted_local_hosts)
        try:
            self._uses_ollama_default_port = urlparse(base_url).port == 11434
        except ValueError:
            self._uses_ollama_default_port = False

    @property
    def base_url(self) -> str:
        """Wohin dieser Anbieter zeigt.

        Öffentlich, weil die Einrichtung es anzeigen können muss — wer drei
        Dienste ausprobiert hat, will sehen, welcher gerade eingestellt ist.
        Der Schlüssel bleibt privat; er hat in keiner Anzeige etwas verloren.
        """
        return self._base

    def _ampel(self):
        """Lokale Modelle teilen sich den Speicher dieses Rechners: höchstens ein Aufruf zugleich,
        die Antwort vor dem Hintergrund (`hintergrund.ModellAmpel`). Entfernte Anbieter warten nicht."""
        if not self.is_local:
            return nullcontext()
        from .hintergrund import AMPEL
        return AMPEL.aufruf()

    def _client(self, timeout: float):
        # Local-only automation must not inherit a process-wide HTTP proxy.
        # The verified job wrapper enables this on its own provider copy.
        if getattr(self, '_verified_local_transport', False):
            return httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False)
        return _http(timeout=timeout)

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Reply:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        timeout = 120.0
        if self.is_local:
            # Local reasoning models can spend their entire default generation
            # budget on hidden reasoning. Keep ordinary turns bounded as well.
            payload["max_tokens"] = 1024
            timeout = 60.0
            if self._uses_ollama_default_port:
                # Port 11434 is Ollama's default convention, not an identity
                # check. The local gate prevents this flag reaching remote hosts.
                payload["reasoning_effort"] = "none"
        if tools:
            payload["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]
        try:
            with self._ampel(), self._client(timeout) as client:
                response = client.post(
                    f"{self._base}/chat/completions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Anfrage an {self._base} fehlgeschlagen: {exc}") from exc

        choice = (data.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            raise ProviderError("Das Modell hat die begrenzte Antwort abgeschnitten. Bitte frage kürzer.")
        message = choice.get("message", {})
        calls = []
        for raw in message.get("tool_calls") or []:
            fn = raw.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=raw.get("id", ""), name=fn.get("name", ""), arguments=args))

        content = message.get("content")
        if not calls and (not isinstance(content, str) or not content.strip()):
            raise ProviderError("Das Modell hat keine sichtbare Antwort geliefert. Bitte erneut versuchen oder ein anderes Modell wählen.")
        return Reply(text=content or "", tool_calls=calls, model=self.model)

    def complete_json(self, messages: list[dict[str, Any]], *, max_tokens: int = 256, schema: dict[str, Any] | None = None) -> Reply:
        """Bounded JSON-only completion for local screening tasks."""
        if not self.is_local:
            raise ProviderError("JSON screening requires a local provider")
        if type(max_tokens) is not int or not 64 <= max_tokens <= 1200:
            raise ProviderError("JSON token budget must be between 64 and 1200")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "none",
        }
        if schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "local_result", "strict": True, "schema": schema}}
            payload["temperature"] = 0
        try:
            with self._ampel(), self._client(30.0 if max_tokens <= 256 else 60.0) as client:
                response = client.post(
                    f"{self._base}/chat/completions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Anfrage an {self._base} fehlgeschlagen: {exc}") from exc
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        if message.get("tool_calls"):
            raise ProviderError("JSON screening provider returned tool calls")
        if choice.get('finish_reason') not in (None, 'stop'):
            raise ProviderError("JSON screening stopped before completion")
        return Reply(text=message.get("content") or "", model=self.model)


class Anthropic:
    """Anthropic Messages API."""

    name = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._max_tokens = max_tokens
        self.is_local = is_local_endpoint(base_url)

    @property
    def base_url(self) -> str:
        return self._base

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Reply:
        system = " ".join(m["content"] for m in messages if m.get("role") == "system")
        converted = [
            self._convert(m) for m in messages if m.get("role") != "system"
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "messages": converted,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object"}),
                }
                for t in tools
            ]

        try:
            with _http() as client:
                response = client.post(
                    f"{self._base}/messages",
                    headers={
                        "x-api-key": self._key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Anfrage an {self._base} fehlgeschlagen: {exc}") from exc

        text_parts, calls = [], []
        for block in data.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input") or {},
                    )
                )
        return Reply(text="".join(text_parts), tool_calls=calls, model=self.model)

    @staticmethod
    def _convert(message: dict[str, Any]) -> dict[str, Any]:
        """Übersetzt die neutrale Form in Anthropics Blockformat."""
        role = message.get("role")

        if role == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": message.get("tool_call_id", ""),
                        "content": message.get("content", ""),
                    }
                ],
            }

        if role == "assistant" and message.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if message.get("content"):
                blocks.append({"type": "text", "text": message["content"]})
            for raw in message["tool_calls"]:
                fn = raw.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": raw.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": args,
                    }
                )
            return {"role": "assistant", "content": blocks}

        return {"role": role, "content": message.get("content") or ""}


def verfuegbare_modelle(base_url: str, api_key: str | None = None) -> list[str]:
    """Fragt einen OpenAI-kompatiblen Endpunkt, welche Modelle er kennt.

    Damit wird aus einem Tippfeld eine Liste — der Nutzer muss den genauen
    Namen eines Modells nicht auswendig können, und ein Tippfehler kann nicht
    mehr in einen Fehler beim ersten Gespräch münden.

    Wirft nichts: kann der Endpunkt nicht antworten oder kennt er den Weg
    nicht, kommt eine leere Liste zurück und das Feld bleibt ein Tippfeld.
    """
    ziel = base_url.rstrip("/") + "/models"
    kopf = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        with _http(timeout=8.0) as client:
            antwort = client.get(ziel, headers=kopf)
            antwort.raise_for_status()
            daten = antwort.json()
    except Exception:  # noqa: BLE001 - eine fehlende Liste ist kein Fehler
        return []

    posten = daten.get("data") if isinstance(daten, dict) else None
    if not isinstance(posten, list):
        return []

    namen = []
    for eintrag in posten:
        if isinstance(eintrag, dict):
            name = eintrag.get("id") or eintrag.get("name")
            if isinstance(name, str) and name:
                namen.append(name)
    return sorted(set(namen))


def from_env() -> Provider | None:
    """Baut den Anbieter aus der Umgebung.

    Reihenfolge: ausdrückliche Wahl über ICARUS_PROVIDER, sonst der erste
    Anbieter, für den ein Schlüssel vorliegt, sonst Ollama, falls es lokal
    erreichbar ist. Gibt None zurück, wenn nichts konfiguriert ist — der
    Gedächtniskern funktioniert auch ohne Modell.
    """
    choice = os.environ.get("ICARUS_PROVIDER", "").strip().lower()
    model = os.environ.get("ICARUS_MODEL", "").strip()
    trusted_local_hosts = tuple(
        host.strip().lower()
        for host in os.environ.get("ICARUS_TRUSTED_LOCAL_MODEL_HOSTS", "").split(",")
        if host.strip()
    )

    if choice == "anthropic" or (not choice and os.environ.get("ANTHROPIC_API_KEY")):
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key:
            return Anthropic(model or "claude-sonnet-5", key)

    # Ein Anbieter, der die OpenAI-Schnittstelle spricht, aber woanders steht.
    # Das ist der Schlüssel zu OpenRouter, Groq, Together, DeepSeek, Mistral,
    # LM Studio, llama.cpp und vLLM — eine Zeile statt eines Anbieters je Dienst.
    if choice == "kompatibel":
        adresse = os.environ.get("ICARUS_BASE_URL", "").strip()
        if not adresse:
            return None
        return OpenAICompatible(
            model or "",
            # Manche lokalen Server verlangen gar keinen Schlüssel und stören
            # sich auch nicht an einem beliebigen. Leer ginge oft schief.
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY") or "kein-schluessel",
            base_url=adresse,
            trusted_local_hosts=trusted_local_hosts,
        )

    if choice == "ollama":
        return OpenAICompatible(
            model or "llama3.1",
            api_key="ollama",
            base_url=os.environ.get("ICARUS_BASE_URL", "http://localhost:11434/v1"),
            trusted_local_hosts=trusted_local_hosts,
        )

    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    if choice == "openai" or key:
        if key:
            return OpenAICompatible(
                model or "gpt-4.1-mini",
                api_key=key,
                base_url=os.environ.get("ICARUS_BASE_URL", "https://api.openai.com/v1"),
            )

    return None


__all__ = [
    "Anthropic",
    "OpenAICompatible",
    "Provider",
    "ProviderError",
    "Reply",
    "ToolCall",
    "from_env",
    "verfuegbare_modelle",
]
