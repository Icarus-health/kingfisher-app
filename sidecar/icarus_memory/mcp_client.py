"""Die MCP-Tür in die andere Richtung: Icarus dockt an fremde Server an.

`mcp.py` macht Icarus zum **Server** — fremde Assistenten lesen und schreiben
im Gedächtnis. Dieses Modul macht Icarus zum **Client**: es startet einen
fremden MCP-Server und benutzt dessen Werkzeuge.

## Warum das der Weg ist

Die naheliegende Antwort auf „wir brauchen noch Dienst X“ ist ein weiterer
Konnektor. Nach dem fünften ist das ein Zweitberuf, und jeder einzelne altert
mit der API, an der er hängt.

Über MCP dockt stattdessen jeder Dienst an, für den irgendwer einen Server
geschrieben hat — ohne dass hier eine Zeile dafür entsteht.

## Was dabei nicht verhandelbar ist

**Jedes angedockte Werkzeug liefert fremden Inhalt.** Seine Ausgabe ist
`returns_untrusted`: Sie verseucht den Zug, hebt die Freigabestufe, und keine
Dauerregel senkt sie wieder. Ein angedockter Dienst erweitert, was Icarus
**kann** — nicht, wem es **glaubt**.

**Die Handlungsklasse ist die vorsichtige.** Ein fremdes Werkzeug sagt nicht,
ob es liest oder handelt; `tools/list` kennt kein Feld dafür. Ein Name wie
`send_message` sieht nach Versand aus, aber danach zu raten hieße, eine
Sicherheitszusage an eine Zeichenkette zu hängen, die der fremde Server frei
wählt. Deshalb: **alles ist `OUTWARD`**, bis ein Mensch für diesen einen
Server etwas anderes sagt. Lieber einmal zu oft gefragt als einmal zu wenig.

## Protokoll

JSON-RPC 2.0 über stdin/stdout, zeilenweise — wie in `mcp.py`, und aus
demselben Grund von Hand statt über ein SDK: Es sind vier Methoden, und eine
Abhängigkeit, die sich im Halbjahrestakt ändert, ist für eine App, die zehn
Jahre laufen soll, der schlechtere Tausch.

## Zeitlimits

Überall. Ein fremder Server, der nicht antwortet, darf Icarus nicht anhalten —
er läuft als eigener Prozess auf demselben Rechner, und ein hängender
Kindprozess wäre sonst ein hängendes Programm.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any

#: Was der Client spricht. Neuere Server verhandeln herunter.
PROTOKOLL = "2025-06-18"

#: Wie lange auf eine einzelne Antwort gewartet wird.
ANTWORT_SEKUNDEN = 20.0

#: Wie lange ein Server zum Starten und Beenden bekommt.
START_SEKUNDEN = 15.0
ENDE_SEKUNDEN = 5.0

#: Mehr als das schluckt kein Zug sinnvoll — und ein Server, der Tausende
#: Werkzeuge meldet, hat entweder ein Problem oder will eines machen.
MAX_WERKZEUGE = 60


#: Was ein fremder Kindprozess von der Umgebung des Sidecars sehen darf. Der
#: Rest — API-Schlüssel, `ICARUS_SIDECAR_TOKEN`, Mailpasswörter — bleibt
#: draußen: Ein Fremdprogramm bekommt nur, was es zum Laufen braucht.
ERLAUBTE_UMGEBUNG = frozenset({
    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LANGUAGE", "TZ",
    "TMPDIR", "TEMP", "TMP", "TERM",
    # Windows kommt ohne diese nicht aus dem Start.
    "SYSTEMROOT", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
})

#: Das Token des Sidecars darf auch nicht über die eingetragene `umgebung`
#: hineinrutschen — sonst hielte ein Fremdprogramm den Schlüssel zu allem.
GESPERRTE_UMGEBUNG = frozenset({"ICARUS_SIDECAR_TOKEN"})


def kind_umgebung(
    konfiguriert: dict[str, str], basis: dict[str, str] | None = None
) -> dict[str, str]:
    """Die minimale Umgebung eines fremden Servers.

    Erlaubtes aus der Umgebung des Sidecars (`ERLAUBTE_UMGEBUNG` und `LC_*`)
    plus genau das, was bei der Serverangabe ausdrücklich eingetragen wurde.
    """
    basis = os.environ if basis is None else basis
    erlaubt = {
        k: v for k, v in basis.items()
        if k in ERLAUBTE_UMGEBUNG or k.startswith("LC_")
    }
    eigene = {k: v for k, v in konfiguriert.items() if k not in GESPERRTE_UMGEBUNG}
    return {**erlaubt, **eigene}


class MCPFehler(Exception):
    """Etwas ging schief. Der Text ist für Menschen, nie ein Stapelabzug."""


@dataclass
class Serverangabe:
    """Was ein Mensch eingetragen hat, damit ein Server startet."""

    name: str
    """Wie der Dienst hier heißt. Geht in die Werkzeugnamen ein."""

    befehl: list[str]
    """Programm und Argumente. Wird **nicht** durch eine Shell gejagt."""

    umgebung: dict[str, str] = field(default_factory=dict)
    aktiv: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "befehl": list(self.befehl),
            # Die Werte nicht: Dort stehen Zugangsdaten, und diese Antwort
            # geht an die Oberfläche.
            "umgebung": sorted(self.umgebung),
            "aktiv": self.aktiv,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Serverangabe:
        befehl = d.get("befehl") or []
        if isinstance(befehl, str):
            befehl = befehl.split()
        return cls(
            name=str(d.get("name", "")).strip(),
            befehl=[str(t) for t in befehl],
            umgebung={str(k): str(v) for k, v in (d.get("umgebung") or {}).items()},
            aktiv=bool(d.get("aktiv", True)),
        )


@dataclass
class FremdesWerkzeug:
    """Ein Werkzeug, das ein angedockter Server anbietet."""

    server: str
    name: str
    beschreibung: str
    schema: dict[str, Any]

    @property
    def voller_name(self) -> str:
        """`dienst__werkzeug` — der Server steht vorn.

        Zwei Server können dasselbe Werkzeug anbieten, und wichtiger noch: Wer
        einen Werkzeugnamen im Protokoll liest, soll sehen, von wem er kam.
        Der Trenner ist ein doppelter Unterstrich, weil die Cloud-Schnittstellen
        Namen nur aus `[A-Za-z0-9_-]` (höchstens 64 Zeichen) annehmen — ein
        Punkt würde dort die ganze Anfrage abweisen. Die Namensteile enthalten
        nie zwei Unterstriche hintereinander, deshalb ist die Trennstelle
        eindeutig. Rückabgebildet wird über die Registry: Sie führt vom vollen
        Namen zum Werkzeug, das den echten Namen des Fremdservers trägt.
        """
        return _kuerze(_sauber(self.server), _sauber(self.name))


#: Trenner zwischen Dienst und Werkzeug im vollen Namen.
NAMENSTRENNER = "__"

#: Längenlimit der Cloud-Schnittstellen für Werkzeugnamen.
MAX_NAMENSLAENGE = 64


def _sauber(text: str) -> str:
    """Nur `[A-Za-z0-9_-]`, und nie zwei Unterstriche in Folge.

    Sonderzeichen und Umlaute werden zu `_`; Folgen von Unterstrichen werden
    zu einem — das hält den Trenner `__` im vollen Namen eindeutig.
    """
    behalten = [z if (z.isascii() and (z.isalnum() or z in "_-")) else "_"
                for z in text.strip()]
    einzeln = re.sub(r"_+", "_", "".join(behalten))
    return einzeln.strip("_") or "unbenannt"


def _kuerze(server: str, werkzeug: str) -> str:
    """Setzt den vollen Namen zusammen und hält ihn im Längenlimit.

    Ist er zu lang, wird der Werkzeugteil gekürzt, der Dienst bleibt lesbar
    stehen; bleibt kein Platz, kürzt der Dienstteil. Gekürzt wird nie
    stillschweigend zu einem Namen, der mit einem anderen zusammenfällt: Ein
    Kurz-Hash der ungekürzten Namen hängt hinten dran.
    """
    voll = f"{server}{NAMENSTRENNER}{werkzeug}"
    if len(voll) <= MAX_NAMENSLAENGE:
        return voll
    marke = hashlib.sha1(voll.encode("utf-8")).hexdigest()[:6]
    platz = MAX_NAMENSLAENGE - len(NAMENSTRENNER) - len(marke) - 1
    server_teil = server[: max(8, platz // 3)]
    werkzeug_teil = werkzeug[: platz - len(server_teil)]
    return f"{server_teil}{NAMENSTRENNER}{werkzeug_teil}_{marke}"


class MCPVerbindung:
    """Ein laufender fremder Server, an dem Icarus hängt.

    Bewusst kein Kontextmanager als einziger Weg: Die Verbindung überlebt
    einzelne Aufrufe, weil das Starten eines Prozesses je Werkzeugaufruf teurer
    wäre als der Aufruf selbst.
    """

    def __init__(self, angabe: Serverangabe) -> None:
        self._angabe = angabe
        self._prozess: subprocess.Popen[str] | None = None
        self._zaehler = 0
        self._schloss = threading.Lock()

    # -- Leben -------------------------------------------------------------

    def start(self) -> None:
        if self._prozess is not None:
            return
        if not self._angabe.befehl:
            raise MCPFehler(f"Für „{self._angabe.name}“ ist kein Befehl eingetragen.")

        umgebung = kind_umgebung(self._angabe.umgebung)
        try:
            self._prozess = subprocess.Popen(
                self._angabe.befehl,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=umgebung,
                text=True,
                encoding="utf-8",
                bufsize=1,
                # Ausdrücklich **keine** Shell: Der Befehl kommt aus einer
                # Einstellungsdatei, und eine Shell würde daraus eine
                # Befehlszeile machen, die mehr kann als starten.
                shell=False,
            )
        except FileNotFoundError as exc:
            raise MCPFehler(
                f"„{self._angabe.befehl[0]}“ gibt es auf diesem Rechner nicht."
            ) from exc
        except OSError as exc:
            raise MCPFehler(f"„{self._angabe.name}“ ließ sich nicht starten: {exc}") from exc

        try:
            self._ruf("initialize", {
                "protocolVersion": PROTOKOLL,
                "capabilities": {},
                "clientInfo": {"name": "icarus", "version": "0.1.0"},
            }, frist=START_SEKUNDEN)
            self._melde("notifications/initialized", {})
        except MCPFehler:
            self.stop()
            raise

    def stop(self) -> None:
        prozess, self._prozess = self._prozess, None
        if prozess is None:
            return
        try:
            if prozess.stdin:
                prozess.stdin.close()
            prozess.wait(timeout=ENDE_SEKUNDEN)
        except Exception:  # noqa: BLE001
            prozess.kill()
            try:
                prozess.wait(timeout=ENDE_SEKUNDEN)
            except Exception:  # noqa: BLE001
                pass

    def __enter__(self) -> MCPVerbindung:
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()

    # -- Benutzen ----------------------------------------------------------

    def werkzeuge(self) -> list[FremdesWerkzeug]:
        antwort = self._ruf("tools/list", {})
        gefunden = []
        for eintrag in (antwort.get("tools") or [])[:MAX_WERKZEUGE]:
            name = str(eintrag.get("name") or "").strip()
            if not name:
                continue
            gefunden.append(FremdesWerkzeug(
                server=self._angabe.name,
                name=name,
                beschreibung=str(eintrag.get("description") or "").strip(),
                schema=eintrag.get("inputSchema") or {"type": "object", "properties": {}},
            ))
        return gefunden

    def rufe(self, name: str, argumente: dict[str, Any]) -> str:
        """Ruft ein Werkzeug und gibt seine Ausgabe als Text zurück.

        Der Text ist **fremder Inhalt**. Wer ihn weiterreicht, muss die Runde
        als kontaminiert behandeln — siehe `tools.py` und `policy.py`.
        """
        antwort = self._ruf("tools/call", {"name": name, "arguments": argumente})
        stuecke = []
        for teil in antwort.get("content") or []:
            if isinstance(teil, dict) and teil.get("type") == "text":
                stuecke.append(str(teil.get("text") or ""))
        text = "\n".join(s for s in stuecke if s).strip()
        if antwort.get("isError"):
            raise MCPFehler(text or f"„{name}“ meldete einen Fehler ohne Begründung.")
        return text or "(keine Ausgabe)"

    # -- Protokoll ---------------------------------------------------------

    def _melde(self, methode: str, params: dict[str, Any]) -> None:
        """Eine Mitteilung ohne Kennung — darauf kommt keine Antwort."""
        self._schreibe({"jsonrpc": "2.0", "method": methode, "params": params})

    def _ruf(self, methode: str, params: dict[str, Any],
             frist: float = ANTWORT_SEKUNDEN) -> dict[str, Any]:
        with self._schloss:
            self._zaehler += 1
            kennung = self._zaehler
            self._schreibe({
                "jsonrpc": "2.0", "id": kennung,
                "method": methode, "params": params,
            })
            antwort = self._lies(kennung, frist)

        if "error" in antwort:
            fehler = antwort["error"] or {}
            raise MCPFehler(
                str(fehler.get("message") or "Der Server meldete einen Fehler.")
            )
        return antwort.get("result") or {}

    def _schreibe(self, nachricht: dict[str, Any]) -> None:
        prozess = self._prozess
        if prozess is None or prozess.stdin is None:
            raise MCPFehler(f"„{self._angabe.name}“ läuft nicht.")
        try:
            prozess.stdin.write(json.dumps(nachricht, ensure_ascii=False) + "\n")
            prozess.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise MCPFehler(f"„{self._angabe.name}“ hat sich beendet.") from exc

    def _lies(self, kennung: int, frist: float) -> dict[str, Any]:
        """Wartet auf genau diese Antwort.

        Der Zeitzähler läuft über einen Thread, nicht über ein Signal:
        Signale gehen nur im Hauptthread, und der Sidecar bedient aus einem
        Threadpool. Ein Zeitlimit, das dort nicht greift, wäre keines.
        """
        prozess = self._prozess
        if prozess is None or prozess.stdout is None:
            raise MCPFehler(f"„{self._angabe.name}“ läuft nicht.")

        ergebnis: dict[str, Any] = {}
        fehler: list[str] = []

        def lesen() -> None:
            while True:
                zeile = prozess.stdout.readline()
                if not zeile:
                    fehler.append(f"„{self._angabe.name}“ hat sich beendet.")
                    return
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    nachricht = json.loads(zeile)
                except json.JSONDecodeError:
                    # Manche Server schreiben Protokollzeilen nach stdout. Das
                    # ist ihr Fehler, aber kein Grund, hier aufzugeben.
                    continue
                if not isinstance(nachricht, dict):
                    continue
                # Mitteilungen des Servers tragen keine Kennung — überspringen.
                if nachricht.get("id") != kennung:
                    continue
                ergebnis.update(nachricht)
                return

        leser = threading.Thread(target=lesen, daemon=True)
        leser.start()
        leser.join(timeout=frist)

        if leser.is_alive():
            self.stop()
            raise MCPFehler(
                f"„{self._angabe.name}“ hat nicht innerhalb von "
                f"{int(frist)} Sekunden geantwortet."
            )
        if fehler:
            raise MCPFehler(fehler[0])
        return ergebnis


def nachsehen(angabe: Serverangabe) -> list[FremdesWerkzeug]:
    """Einmal verbinden, Werkzeuge holen, wieder beenden.

    Das ist der Weg für den Knopf „Verbinden und nachsehen“: Er soll sagen,
    was dabei herauskam, und nichts offen lassen.
    """
    with MCPVerbindung(angabe) as verbindung:
        return verbindung.werkzeuge()


__all__ = [
    "ANTWORT_SEKUNDEN",
    "MAX_WERKZEUGE",
    "PROTOKOLL",
    "FremdesWerkzeug",
    "MCPFehler",
    "MCPVerbindung",
    "Serverangabe",
    "nachsehen",
]
