"""Ein Modell über die lokale Ollama-Schnittstelle laden, mit abfragbarem Fortschritt.

Nie ungefragt: Die aufrufende Route verlangt die ausdrückliche Bestätigung des
Nutzers und lädt nur Modelle aus dem Katalog (`model_recommendation.py`), nie
einen frei eingegebenen Namen. Dieses Modul kennt weder Katalog noch Einstellungen.

Jeder Fehler kommt als Paar aus **Grund** und **nächstem Schritt** an, in Worten,
die der Nutzer versteht. Rohe Ausnahmetexte gelangen nicht in die Oberfläche.
"""
from __future__ import annotations

import json
import math
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

import httpx

# Wie schnell eine Leitung mindestens/höchstens lädt (MB/s): 100 bzw. 500 Mbit/s.
_LANGSAM_MB_S = 12.5
_SCHNELL_MB_S = 62.5


def dauer_minuten(groesse_gb: float) -> tuple[int, int]:
    """Grobe Spanne in Minuten, je nach Leitung. Eine Schätzung, keine Zusage."""
    mb = groesse_gb * 1024
    return max(1, math.ceil(mb / _SCHNELL_MB_S / 60)), max(2, math.ceil(mb / _LANGSAM_MB_S / 60))


def bestaetigungssatz(name: str, groesse_gb: float) -> str:
    """Der eine Satz, dem der Nutzer vor dem Laden zustimmt."""
    von, bis = dauer_minuten(groesse_gb)
    groesse = f"{groesse_gb:g}".replace(".", ",")
    return (f"{name} ist etwa {groesse} GB groß; das Laden dauert je nach Internetleitung "
            f"etwa {von} bis {bis} Minuten. Es wird nur dieses Modell geladen.")


@dataclass(frozen=True)
class Fehlergrund:
    grund: str
    naechster_schritt: str
    art: str = ""
    """`pruefung`, wenn das Modell geladen ist, die Prüfung aber nicht bestand (dann hilft ein anderes Modell)."""

    def als_dict(self) -> dict[str, str]:
        daten = {"grund": self.grund, "naechster_schritt": self.naechster_schritt}
        return {**daten, "art": self.art} if self.art else daten


def deute_fehler(meldung: str | None = None, ausnahme: BaseException | None = None) -> Fehlergrund:
    """Übersetzt Ollamas Fehlertext oder eine Ausnahme in Grund und nächsten Schritt."""
    text = (meldung or "").lower()
    if isinstance(ausnahme, (httpx.ConnectError, httpx.ConnectTimeout)):
        return Fehlergrund("Ollama ist nicht erreichbar.",
                           "Ollama auf diesem Rechner starten und dann erneut auf „Einrichten“ klicken.")
    if any(w in text for w in ("no space", "disk full", "not enough space", "insufficient")):
        return Fehlergrund("Auf dem Rechner ist nicht genug Speicherplatz frei.",
                           "Speicherplatz freigeben (Ollama-Modelle, die du nicht brauchst, löschen) und erneut versuchen.")
    if any(w in text for w in ("lookup", "dial tcp", "timeout", "timed out", "connection refused",
                               "no such host", "network", "eof", "reset by peer", "i/o")):
        return Fehlergrund("Die Verbindung zum Modellserver im Internet ist abgebrochen.",
                           "Internetverbindung prüfen und erneut versuchen; bereits Geladenes wird fortgesetzt.")
    if any(w in text for w in ("not found", "file does not exist", "manifest")):
        return Fehlergrund("Ollama kennt dieses Modell unter diesem Namen nicht (mehr).",
                           "Ollama aktualisieren und erneut versuchen; hilft das nicht, ein anderes Modell wählen.")
    if isinstance(ausnahme, (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError)):
        return Fehlergrund("Die Verbindung zu Ollama ist abgebrochen.",
                           "Prüfen, ob Ollama noch läuft, und erneut versuchen; bereits Geladenes wird fortgesetzt.")
    return Fehlergrund("Das Modell konnte nicht geladen werden.",
                       "Ollama prüfen und erneut versuchen. Bleibt es dabei, im Ollama-Fenster nachsehen.")


@dataclass(frozen=True)
class PullStand:
    """Was die Oberfläche über einen Ladevorgang erfährt."""

    id: str
    modell: str
    rolle: str
    phase: str = "wartet"  # wartet | laedt | prueft | fertig | fehler
    fortschritt: float | None = None  # 0..1; None = unbekannt
    text: str = "Wird vorbereitet …"
    fehler: dict[str, str] | None = None
    ergebnis: dict[str, Any] | None = None

    def als_dict(self) -> dict[str, Any]:
        return {"id": self.id, "modell": self.modell, "rolle": self.rolle, "phase": self.phase,
                "fortschritt": self.fortschritt, "text": self.text, "fehler": self.fehler,
                "ergebnis": self.ergebnis}

    @property
    def laeuft(self) -> bool:
        return self.phase in {"wartet", "laedt", "prueft"}


class PullBelegt(RuntimeError):
    """Es läuft schon ein Ladevorgang; es wird immer nur ein Modell zugleich geladen."""


ClientFactory = Callable[[], httpx.Client]
# Nach dem Laden: Qualifikationsprüfung und Übernahme. Liefert das Ergebnis oder wirft `Fehlschlag`.
Nachher = Callable[[str, str], dict[str, Any]]


class Fehlschlag(Exception):
    """Ladevorgang oder Prüfung endete mit einem erklärbaren Fehler."""

    def __init__(self, fehler: Fehlergrund) -> None:
        super().__init__(fehler.grund)
        self.fehler = fehler


def _standard_client() -> httpx.Client:
    # Lokaler Dienst: keinen Umgebungs-Proxy, keine Weiterleitung. Kein Gesamt-
    # Zeitlimit (ein Modell lädt Minuten), aber eine Frist je Datenpaket.
    return httpx.Client(timeout=httpx.Timeout(None, connect=5.0, read=120.0),
                        trust_env=False, follow_redirects=False)


#: Der eine Satz, solange das Laden läuft (Heute, Gespräch, Assistent); `{prozent}` wird eingesetzt.
LAEDT_SATZ = "Kingfisher lädt noch sein Sprachmodell ({prozent} %)."


class PullManager:
    """Führt Ladevorgänge im Hintergrund aus; immer höchstens einen zugleich.

    `starte_reihe` lädt mehrere Modelle nacheinander in einem Hintergrundlauf (Fremdprobe 2, Befunde 6 und 7): Der
    Mensch klickt einmal und geht weiter; der Lauf hängt an keiner Seite im Browser. Ein Fehlschlag hält die übrigen
    nicht auf. `reihe_stand` sagt, wie weit er ist, gewichtet nach Größe, und was am Ende fehlt."""

    def __init__(self, wurzel: Callable[[], str], nachher: Nachher,
                 client: ClientFactory = _standard_client) -> None:
        self._wurzel = wurzel
        self._nachher = nachher
        self._client = client
        self._lock = threading.Lock()
        self._staende: dict[str, PullStand] = {}
        self._thread: threading.Thread | None = None
        self._reihe: dict[str, Any] | None = None

    # -- Abfrage --------------------------------------------------------------------------
    def stand(self, job_id: str) -> PullStand | None:
        with self._lock:
            return self._staende.get(job_id)

    def aktuell(self) -> PullStand | None:
        with self._lock:
            laufend = [s for s in self._staende.values() if s.laeuft]
            return laufend[0] if laufend else None

    def warte(self, timeout: float = 10.0) -> None:
        """Für Tests: wartet, bis der Hintergrundlauf fertig ist."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # -- Start ----------------------------------------------------------------------------
    def starte(self, modell: str, rolle: str) -> PullStand:
        with self._lock:
            if any(s.laeuft for s in self._staende.values()):
                raise PullBelegt("Es wird gerade ein anderes Modell geladen.")
            stand = PullStand(id=uuid.uuid4().hex[:12], modell=modell, rolle=rolle)
            self._staende[stand.id] = stand
            # Alte, beendete Stände nicht ewig behalten.
            for alt in [k for k, s in self._staende.items() if not s.laeuft][:-5]:
                self._staende.pop(alt, None)
            self._thread = threading.Thread(target=self._lauf, args=(stand.id,), daemon=True,
                                            name="kingfisher-modell-laden")
            self._thread.start()
            return stand

    def starte_reihe(self, auftraege: list[tuple[str, str, float]]) -> dict[str, Any]:
        """Lädt `(modell, rolle, groesse_gb)` nacheinander im Hintergrund; `groesse_gb` ist, was noch zu laden ist."""
        with self._lock:
            if any(s.laeuft for s in self._staende.values()):
                raise PullBelegt("Es wird gerade ein anderes Modell geladen.")
            for alt in [k for k, s in self._staende.items() if not s.laeuft]:
                self._staende.pop(alt, None)
            jobs = []
            for modell, rolle, groesse in auftraege:
                stand = PullStand(id=uuid.uuid4().hex[:12], modell=modell, rolle=rolle)
                self._staende[stand.id] = stand
                jobs.append((stand.id, max(0.0, float(groesse))))
            self._reihe = {"id": uuid.uuid4().hex[:12], "jobs": jobs}
            self._thread = threading.Thread(target=self._reihe_lauf, args=([j for j, _ in jobs],), daemon=True,
                                            name="kingfisher-modelle-laden")
            self._thread.start()
        return self.reihe_stand() or {}

    def _reihe_lauf(self, jobs: list[str]) -> None:
        for job_id in jobs:
            self._lauf(job_id)  # fängt jeden Fehler selbst; der nächste Auftrag kommt trotzdem dran

    def reihe_stand(self) -> dict[str, Any] | None:
        """Wie weit das Laden ist: `laeuft`, `prozent` (nach Größe gewichtet), je Auftrag der Stand, und am Ende,
        was eingerichtet ist und was nicht. `None`, wenn es noch keinen Lauf gab."""
        with self._lock:
            reihe = self._reihe
            if reihe is None:
                return None
            staende = [(self._staende.get(j), g) for j, g in reihe["jobs"]]
        staende = [(s, g) for s, g in staende if s is not None]
        if not staende:
            return None

        def anteil(stand: PullStand) -> float:
            if stand.phase in ("fertig", "fehler", "prueft"):
                return 1.0
            return float(stand.fortschritt or 0.0) if stand.phase == "laedt" else 0.0

        gesamt = sum(g for _, g in staende)
        if gesamt > 0:
            wert = sum(g * anteil(s) for s, g in staende) / gesamt
        else:
            wert = sum(anteil(s) for s, _ in staende) / len(staende)
        laeuft = any(s.laeuft for s, _ in staende)
        prozent = min(99, int(wert * 100)) if laeuft else 100
        fertig = [s.rolle for s, _ in staende if s.phase == "fertig"]
        fehler = [s.rolle for s, _ in staende if s.phase == "fehler"]
        return {"id": reihe["id"], "laeuft": laeuft, "prozent": prozent, "gesamt_gb": round(gesamt, 1),
                "satz": LAEDT_SATZ.format(prozent=prozent) if laeuft else "",
                "eingerichtet": fertig, "fehlgeschlagen": fehler,
                "auftraege": [s.als_dict() for s, _ in staende]}

    def _setze(self, job_id: str, **felder: Any) -> None:
        with self._lock:
            self._staende[job_id] = replace(self._staende[job_id], **felder)

    # -- Lauf -----------------------------------------------------------------------------
    def _lauf(self, job_id: str) -> None:
        stand = self.stand(job_id)
        assert stand is not None
        try:
            with self._client() as client:
                if not self._installiert(client, stand.modell):
                    self._setze(job_id, phase="laedt", text="Modell wird geladen …", fortschritt=0.0)
                    self._lade(client, job_id, stand.modell)
                else:
                    self._setze(job_id, fortschritt=1.0, text="Modell ist schon installiert.")
            self._setze(job_id, phase="prueft", fortschritt=1.0, text="Modell wird geprüft …")
            ergebnis = self._nachher(stand.modell, stand.rolle)
            self._setze(job_id, phase="fertig", fortschritt=1.0, text="Eingerichtet.", ergebnis=ergebnis)
        except Fehlschlag as exc:
            self._setze(job_id, phase="fehler", text=exc.fehler.grund, fehler=exc.fehler.als_dict())
        except Exception as exc:  # noqa: BLE001 - jeder Fehler wird erklärt, kein Rohtext nach außen
            self._setze(job_id, phase="fehler", fehler=(f := deute_fehler(ausnahme=exc)).als_dict(), text=f.grund)

    def _installiert(self, client: httpx.Client, modell: str) -> bool:
        antwort = client.get(self._wurzel().rstrip("/") + "/api/tags")
        antwort.raise_for_status()
        ziel = modell if ":" in modell else modell + ":latest"
        return any(isinstance(z, dict) and z.get("name") in {ziel, modell}
                   for z in antwort.json().get("models", []))

    def _lade(self, client: httpx.Client, job_id: str, modell: str) -> None:
        je_teil: dict[str, tuple[int, int]] = {}  # Prüfsumme -> (gesamt, geladen)
        bisher = 0.0  # Der Balken läuft nie zurück, auch wenn ein weiterer Teil dazukommt.
        with client.stream("POST", self._wurzel().rstrip("/") + "/api/pull",
                           json={"model": modell, "stream": True}) as antwort:
            if antwort.status_code >= 400:
                antwort.read()
                raise Fehlschlag(deute_fehler(antwort.text))
            fertig = False
            for zeile in antwort.iter_lines():
                if not zeile.strip():
                    continue
                try:
                    daten = json.loads(zeile)
                except ValueError:
                    continue
                if not isinstance(daten, dict):
                    continue
                if daten.get("error"):
                    raise Fehlschlag(deute_fehler(str(daten["error"])))
                status = str(daten.get("status", ""))
                gesamt, geladen = daten.get("total"), daten.get("completed")
                if isinstance(gesamt, int) and gesamt > 0 and daten.get("digest"):
                    je_teil[str(daten["digest"])] = (gesamt, min(int(geladen or 0), gesamt))
                summe = sum(g for g, _ in je_teil.values())
                anteil = round(sum(c for _, c in je_teil.values()) / summe, 3) if summe else None
                if anteil is not None:
                    # Nie zurück, und nie „fertig“, bevor Ollama „success“ meldet: Ein kleiner
                    # erster Teil ist schnell da, ein weiterer kann folgen.
                    anteil = bisher = min(max(anteil, bisher), 0.99)
                if status == "success":
                    fertig = True
                    anteil = 1.0
                self._setze(job_id, fortschritt=anteil,
                            text=("Modell wird geladen …" if status.startswith("pulling") and summe
                                  else "Wird vorbereitet …" if status.startswith("pulling manifest")
                                  else "Wird überprüft und abgelegt …" if not fertig else "Geladen."))
            if not fertig:
                raise Fehlschlag(deute_fehler("connection reset by peer"))


__all__ = [
    "Fehlergrund", "Fehlschlag", "LAEDT_SATZ", "PullBelegt", "PullManager", "PullStand",
    "bestaetigungssatz", "dauer_minuten", "deute_fehler",
]
