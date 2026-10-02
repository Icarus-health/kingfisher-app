"""Was im lokalen Ollama wirklich lokal ist und was nur so aussieht.

Ollama bietet Modelle mit dem Tag `cloud` an (`name:cloud`): Das lokale Ollama nimmt die
Anfrage an und reicht sie an den Server von Ollama weiter. Das Modell steht dann in
`/api/tags` wie jedes andere, und der Endpunkt ist Loopback. Wer nur den Endpunkt prüft,
hält es für lokal, auch für Aufgaben, die nie in die Cloud dürfen.

Dieses Modul beantwortet je installiertem Modell eine Frage: **lokal** (Gewichte auf der
Platte: Format `gguf`, Digest, kein `remote_host`/`remote_model`) oder **Cloud über
Ollama**. Quelle ist `/api/tags`; `/api/show` nur, wenn die Zeile dort keine Einzelheiten
enthält. Die Antwort wird kurz zwischengespeichert (`TTL_SEKUNDEN`).

Fail closed: Antwortet Ollama nicht oder ist die Antwort unbrauchbar, ist die Art
`unbekannt`, und unbekannt gilt nicht als lokal.
"""
from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx

from .model_recommendation import normalisiere

LOKAL = "lokal"
CLOUD = "cloud"  # Cloud über Ollama
UNBEKANNT = "unbekannt"

TTL_SEKUNDEN = 30.0
FEHLER_TTL_SEKUNDEN = 5.0  # ein Ausfall soll sich schnell erholen können, nicht 30 s sperren
_DIGEST = re.compile(r"[0-9a-f]{64}")
_CLOUD_TAG = re.compile(r"(?:^|-)cloud$")

HINWEIS_CLOUD = ("läuft in Ollamas Cloud: Ollama reicht die Anfrage an seinen Server in den USA weiter, "
                 "nicht an den Hersteller des Modells.")


def ist_cloud_name(name: str) -> bool:
    """Der Name allein verrät Cloud-Modelle (`x:cloud`, `x:120b-cloud`); das Gegenteil beweist nichts."""
    letzter = name.strip().rsplit("/", 1)[-1].lower()  # Namensraum und Registry-Port sind nicht der Tag
    return ":" in letzter and bool(_CLOUD_TAG.search(letzter.rsplit(":", 1)[1]))


def _art_aus_zeile(zeile: dict[str, Any], show: dict[str, Any] | None) -> str:
    """Die Art einer Zeile aus `/api/tags`, bei Bedarf ergänzt um die Antwort von `/api/show`."""
    quelle = {**zeile, **(show or {})}
    if (zeile.get("remote_host") or zeile.get("remote_model")
            or quelle.get("remote_host") or quelle.get("remote_model")):
        return CLOUD
    if ist_cloud_name(str(zeile.get("name", ""))):
        return CLOUD
    details = quelle.get("details")
    digest = zeile.get("digest")
    if isinstance(details, dict) and details.get("format") == "gguf" and isinstance(digest, str) \
            and _DIGEST.fullmatch(digest):
        return LOKAL
    return CLOUD  # ohne gguf-Gewichte auf der Platte ist es nicht als lokal belegt


class OllamaInventar:
    """Art je installiertem Modell, kurz gemerkt, je Ollama-Adresse getrennt."""

    def __init__(self, wurzel: Callable[[], str], client: Callable[[], httpx.Client],
                 ttl: float = TTL_SEKUNDEN, fehler_ttl: float = FEHLER_TTL_SEKUNDEN,
                 uhr: Callable[[], float] = time.monotonic) -> None:
        self._wurzel = wurzel
        self._client = client
        self._ttl, self._fehler_ttl, self._uhr = ttl, fehler_ttl, uhr
        self._gemerkt: dict[str, tuple[float, dict[str, str] | None]] = {}  # Wurzel -> (gültig bis, Name -> Art)
        self._lock = threading.Lock()

    def vergiss(self) -> None:
        """Nach dem Laden oder Löschen eines Modells: nicht auf den Ablauf warten."""
        with self._lock:
            self._gemerkt.clear()

    def installiert(self, wurzel: str | None = None) -> dict[str, str] | None:
        """Name, wie Ollama ihn nennt -> `lokal` | `cloud`; `None`, wenn Ollama nicht zuverlässig antwortet."""
        wurzel = (wurzel or self._wurzel()).rstrip("/")
        with self._lock:
            jetzt = self._uhr()
            gemerkt = self._gemerkt.get(wurzel)
            if gemerkt is not None and jetzt < gemerkt[0]:
                return gemerkt[1]
            ergebnis = self._lade(wurzel)
            self._gemerkt[wurzel] = (jetzt + (self._ttl if ergebnis is not None else self._fehler_ttl), ergebnis)
            return ergebnis

    def art(self, name: str, wurzel: str | None = None) -> str:
        """`lokal`, `cloud` oder `unbekannt` (Ollama stumm, Modell nicht installiert)."""
        installiert = self.installiert(wurzel)
        if installiert is None:
            return UNBEKANNT
        ziel = normalisiere(name)
        return next((art for roh, art in installiert.items() if normalisiere(roh) == ziel), UNBEKANNT)

    def ist_lokal(self, name: str, wurzel: str | None = None) -> bool:
        return self.art(name, wurzel) == LOKAL

    def _lade(self, wurzel: str) -> dict[str, str] | None:
        try:
            with self._client() as client:
                antwort = client.get(wurzel + "/api/tags")
                antwort.raise_for_status()
                zeilen = antwort.json().get("models")
                if not isinstance(zeilen, list):
                    return None
                arten: dict[str, str] = {}
                for zeile in zeilen:
                    if not isinstance(zeile, dict) or not isinstance(zeile.get("name"), str) or not zeile["name"]:
                        continue
                    show = None
                    if not isinstance(zeile.get("details"), dict) and not ist_cloud_name(zeile["name"]):
                        show = self._show(client, wurzel, zeile["name"])  # nur bei Zeilen ohne Einzelheiten
                    arten[zeile["name"]] = _art_aus_zeile(zeile, show)
                return arten
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return None

    @staticmethod
    def _show(client: httpx.Client, wurzel: str, name: str) -> dict[str, Any] | None:
        try:
            antwort = client.post(wurzel + "/api/show", json={"model": name})
            antwort.raise_for_status()
            daten = antwort.json()
            return daten if isinstance(daten, dict) else None
        except (httpx.HTTPError, ValueError):
            return None  # ohne Einzelheiten bleibt es „nicht als lokal belegt“


def inventar_von(app: Any) -> OllamaInventar:
    """Das Inventar zur laufenden Anwendung, einmal gebaut (am Anwendungszustand gemerkt)."""
    zustand = app.state
    inventar = getattr(zustand, "ollama_inventar", None)
    if inventar is None:
        from .model_roles import lokaler_endpunkt, ollama_wurzel  # spät: model_roles importiert dieses Modul

        def wurzel() -> str:
            rollen = getattr(zustand, "rollen", None)
            standard = rollen.standard() if rollen is not None else getattr(getattr(zustand, "agent", None), "provider", None)
            return ollama_wurzel(lokaler_endpunkt(standard))

        def client() -> httpx.Client:
            # `ollama_transport` ist nur für Tests gesetzt; im Betrieb spricht das direkt mit dem lokalen Ollama.
            return httpx.Client(timeout=3.0, trust_env=False, follow_redirects=False,
                                transport=getattr(zustand, "ollama_transport", None))

        inventar = OllamaInventar(wurzel, client)
        zustand.ollama_inventar = inventar
    return inventar


__all__ = ["CLOUD", "HINWEIS_CLOUD", "LOKAL", "UNBEKANNT", "OllamaInventar", "ist_cloud_name", "inventar_von"]
