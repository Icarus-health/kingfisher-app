"""Ein Ollama-Attrappe für Tests: nur `httpx.MockTransport`, kein Netz, kein Prozess."""
from __future__ import annotations

import json
import threading

import httpx


class FakeOllama:
    """Kennt /api/tags, /api/pull (mit Fortschritt oder Fehler) und /api/embed."""

    def __init__(self, installiert=(), modus="ok", warte: threading.Event | None = None, cloud=()):
        self.installiert = list(installiert)
        self.cloud = list(cloud)  # Modelle, die Ollama an seinen Server weiterreicht (remote_host)
        self.modus = modus  # ok | fehler_platz | fehler_netz | abbruch | http500 | unbekannt
        self.warte = warte  # hält /api/pull an, bis das Ereignis gesetzt ist
        self.anfragen: list[tuple[str, str, dict | None]] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.anfragen.append((request.method, request.url.path, body))
        pfad = request.url.path
        if pfad == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": n if ":" in n else n + ":latest", "size": 1, "digest": "0" * 64,
                 "details": {"format": "gguf"}} for n in self.installiert] + [
                {"name": n, "size": 0, "digest": "", "remote_model": n.split(":")[0],
                 "remote_host": "https://ollama.com:443", "details": {"format": ""}} for n in self.cloud]})
        if pfad == "/api/embed":
            return httpx.Response(200, json={"model": body["model"], "embeddings": [[0.1, 0.2, 0.3]]})
        if pfad == "/api/pull":
            if self.warte is not None:
                self.warte.wait(5)
            if self.modus == "http500":
                return httpx.Response(500, json={"error": "server error"})
            if self.modus == "unbekannt":
                return httpx.Response(404, json={"error": "pull model manifest: file does not exist"})
            zeilen = [{"status": "pulling manifest"},
                      {"status": "pulling abc", "digest": "sha256:abc", "total": 1000, "completed": 250},
                      {"status": "pulling abc", "digest": "sha256:abc", "total": 1000, "completed": 1000},
                      {"status": "pulling def", "digest": "sha256:def", "total": 1000, "completed": 500}]
            if self.modus == "fehler_platz":
                zeilen.append({"error": "write /root/.ollama/blobs: no space left on device"})
            elif self.modus == "fehler_netz":
                zeilen.append({"error": "pull model manifest: Get \"https://registry\": dial tcp: lookup registry: no such host"})
            elif self.modus == "ok":
                zeilen += [{"status": "pulling def", "digest": "sha256:def", "total": 1000, "completed": 1000},
                           {"status": "verifying sha256 digest"}, {"status": "success"}]
                name = body["model"]
                self.installiert.append(name)
            return httpx.Response(200, content="\n".join(json.dumps(z) for z in zeilen).encode())
        return httpx.Response(404)


class Verbindungsfehler:
    """Transport, der wie ein nicht laufendes Ollama scheitert."""

    def __init__(self):
        self.transport = httpx.MockTransport(self._handle)

    @staticmethod
    def _handle(request: httpx.Request):
        raise httpx.ConnectError("Verbindung abgelehnt", request=request)
