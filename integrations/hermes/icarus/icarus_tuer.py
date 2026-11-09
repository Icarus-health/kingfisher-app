"""Der Weg von Hermes zur MCP-Tür von Kingfisher — ohne Hermes, nur Standardbibliothek.

Hier steht alles, was das Plugin über Kingfisher wissen muss: wo der Sidecar läuft, welches
Token er verlangt und wie seine Antworten aussehen. `__init__.py` bindet das an die
Schnittstelle von Hermes. Getrennt, damit sich dieser Teil gegen den echten Sidecar prüfen lässt,
ohne Hermes zu installieren (`sidecar/tests/test_hermes_plugin.py`).

Keine eigene Datenbank, kein zweiter Bestand: Jede Anfrage geht an den laufenden Sidecar und
dort durch dieselbe Policy und dasselbe Audit-Log wie die MCP-Tür (`docs/07-mcp-tuer.md`).
Gelesen wird nur, was die Tür einem Assistenten von außen zeigt — Schutzbedarf `normal`.
Geschrieben wird nichts: Fakt wird nur, was ein Mensch in Kingfisher annimmt.

Bewusst ohne httpx oder requests. Hermes bringt seine eigene Umgebung mit, und ein Plugin ohne
Abhängigkeiten muss dort nichts installieren.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

#: Adresse der Mac-App: compose.yaml veröffentlicht den Sidecar nur an 127.0.0.1:8890.
KINGFISHER_ADRESSE = "http://127.0.0.1:8890"
TOKEN_NAME = "ICARUS_SIDECAR_TOKEN"
TUER_SCHALTER = "KINGFISHER_MCP_TUER"
#: Eigene Einstellungen des Plugins, je Hermes-Profil: `$HERMES_HOME/icarus.json`.
EINSTELLUNGSDATEI = "icarus.json"


def kingfisher_env(zuhause: Path) -> Path:
    """Die Schlüsseldatei der Mac-App (`macos/App/Paths.swift`)."""
    return zuhause / "Library" / "Application Support" / "Kingfisher" / "kingfisher.env"


def icarus_daten(zuhause: Path) -> Path:
    """Datenordner eines direkt gestarteten Sidecars; dort schreibt er `verbindung.json`."""
    return zuhause / "Library" / "Application Support" / "Icarus"


class TuerFehler(Exception):
    """Der Sidecar war nicht zu erreichen oder hat abgelehnt. Die Meldung ist für Menschen."""


@dataclass(frozen=True)
class Verbindung:
    adresse: str
    token: str | None
    #: Woher Adresse und Token stammen; steht in jeder Meldung, damit klar ist, was zu ändern wäre.
    herkunft: str
    #: Wo sich die Tür einschalten lässt, falls sie zu ist. Leer, wenn das Plugin es nicht weiß.
    schalter_datei: Path | None = None


def env_wert(text: str, name: str) -> str | None:
    """Liest einen Wert aus einer Env-Datei wie `EnvFile.value` der Mac-App.

    `export` davor und Anführungszeichen drumherum sind erlaubt. Nur dieser eine Name wird
    gelesen; alles andere in der Datei (die Passphrase) bleibt unberührt.
    """
    for zeile in text.splitlines():
        rest = zeile.strip()
        if rest.startswith("export "):
            rest = rest[len("export "):].lstrip()
        if not rest.startswith(name + "="):
            continue
        wert = rest[len(name) + 1:].strip()
        for zeichen in ('"', "'"):
            if len(wert) >= 2 and wert.startswith(zeichen) and wert.endswith(zeichen):
                wert = wert[1:-1]
        return wert or None
    return None


def einstellungen(hermes_home: Path | None) -> dict[str, Any]:
    """`$HERMES_HOME/icarus.json`, falls vorhanden. Fehlt sie, gelten die Vorgaben."""
    if hermes_home is None:
        return {}
    try:
        daten = json.loads((hermes_home / EINSTELLUNGSDATEI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return daten if isinstance(daten, dict) else {}


def finde_verbindung(
    werte: dict[str, Any], token: str | None, zuhause: Path
) -> Verbindung | None:
    """Wo läuft Kingfisher? Ohne Netz, nur aus Dateien — `is_available()` darf nichts senden.

    Reihenfolge:
    1. `adresse` aus `icarus.json`, Token aus dem Geheimnis `ICARUS_SIDECAR_TOKEN` von Hermes.
    2. Die Mac-App: Token aus `~/Library/Application Support/Kingfisher/kingfisher.env`, Adresse
       fest 127.0.0.1:8890. Das ist der Normalfall; er braucht keine Einstellung.
    3. Ein direkt gestarteter Sidecar: `verbindung.json` in `daten_ordner` aus `icarus.json`,
       sonst in `~/Library/Application Support/Icarus`.

    Wird bei jeder Anfrage neu bestimmt: Ein direkt gestarteter Sidecar vergibt das Token bei
    jedem Start neu, und ein Plugin, das es einmal liest, bliebe nach einem Neustart ausgesperrt.
    """
    adresse = str(werte.get("adresse") or "").strip()
    if adresse:
        return Verbindung(adresse.rstrip("/"), token, f"{EINSTELLUNGSDATEI}: adresse")

    env = kingfisher_env(zuhause)
    try:
        app_token = env_wert(env.read_text(encoding="utf-8"), TOKEN_NAME)
    except OSError:
        app_token = None
    if app_token:
        return Verbindung(KINGFISHER_ADRESSE, app_token, str(env), schalter_datei=env)

    ordner = werte.get("daten_ordner")
    datei = (Path(str(ordner)).expanduser() if ordner else icarus_daten(zuhause)) / "verbindung.json"
    try:
        daten = json.loads(datei.read_text(encoding="utf-8"))
        return Verbindung(str(daten["url"]).rstrip("/"), daten.get("token"), str(datei))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def nicht_gefunden(zuhause: Path) -> str:
    """Der Satz für `unavailable_reason()`: was fehlt und was man tun kann."""
    return (
        f"Kingfisher nicht gefunden: weder {kingfisher_env(zuhause)} noch "
        f"{icarus_daten(zuhause) / 'verbindung.json'}. Läuft Kingfisher auf diesem Rechner? "
        f"Sonst die Adresse unter „adresse“ in $HERMES_HOME/{EINSTELLUNGSDATEI} eintragen "
        f"und das Token als {TOKEN_NAME} in $HERMES_HOME/.env."
    )


#: Eine Anfrage: (Methode, Pfad, Nutzlast, Verbindung) -> (Status, Antwort als JSON).
Transport = Callable[[str, str, Any, Verbindung], tuple[int, Any]]


def urllib_transport(zeitlimit: float) -> Transport:
    """HTTP über Loopback mit der Standardbibliothek."""

    def senden(methode: str, pfad: str, nutzlast: Any, verbindung: Verbindung) -> tuple[int, Any]:
        kopf = {"Accept": "application/json"}
        if verbindung.token:
            kopf["x-icarus-token"] = verbindung.token
        rumpf = None
        if nutzlast is not None:
            rumpf = json.dumps(nutzlast).encode("utf-8")
            kopf["Content-Type"] = "application/json"
        anfrage = urllib.request.Request(verbindung.adresse + pfad, data=rumpf, headers=kopf, method=methode)
        try:
            with urllib.request.urlopen(anfrage, timeout=zeitlimit) as antwort:
                return antwort.status, _json(antwort.read())
        except urllib.error.HTTPError as fehler:
            return fehler.code, _json(fehler.read())
        except (urllib.error.URLError, OSError) as fehler:
            raise TuerFehler(
                f"Kingfisher ist unter {verbindung.adresse} nicht erreichbar ({_grund(fehler)}). "
                "Läuft die App?"
            ) from fehler

    return senden


def _json(rumpf: bytes) -> Any:
    try:
        return json.loads(rumpf.decode("utf-8") or "null")
    except (UnicodeDecodeError, ValueError):
        return None


def _grund(fehler: Exception) -> str:
    return str(getattr(fehler, "reason", None) or fehler)


class Tuer:
    """Liest über die MCP-Tür. Mehr nicht: Schreibende Werkzeuge gibt es hier nicht."""

    def __init__(self, finden: Callable[[], Verbindung | None], transport: Transport,
                 nicht_gefunden_text: str = "Kingfisher nicht gefunden.") -> None:
        self._finden = finden
        self._transport = transport
        self._nicht_gefunden = nicht_gefunden_text

    def suchen(self, frage: str, anzahl: int = 5) -> str:
        """Belegte Aussagen zur Frage, gerendert vom Sidecar — samt Quelle und Auswahlgrund."""
        antwort = self._anfrage("POST", "/tools/gedaechtnis_suchen", {"query": frage, "limit": anzahl})
        if not isinstance(antwort, dict) or not antwort.get("ok"):
            text = antwort.get("text") if isinstance(antwort, dict) else None
            raise TuerFehler(str(text or "Kingfisher hat die Suche abgelehnt."))
        return str(antwort.get("text") or "")

    def kontext(self) -> str:
        """Was Kingfisher einem Assistenten von außen insgesamt zeigt."""
        antwort = self._anfrage("GET", "/context", None)
        if not isinstance(antwort, dict) or "context" not in antwort:
            raise TuerFehler("Kingfisher hat keinen Kontext geliefert.")
        return str(antwort["context"])

    def pruefen(self) -> str:
        """Ein Satz, ob es geht — für `hermes icarus pruefen`."""
        verbindung = self._verbindung()
        self._anfrage("GET", "/mcp/tuer", None, verbindung)
        return f"Verbunden mit Kingfisher unter {verbindung.adresse} (aus {verbindung.herkunft}); die Tür ist offen."

    def _verbindung(self) -> Verbindung:
        verbindung = self._finden()
        if verbindung is None:
            raise TuerFehler(self._nicht_gefunden)
        return verbindung

    def _anfrage(self, methode: str, pfad: str, nutzlast: Any,
                 verbindung: Verbindung | None = None) -> Any:
        verbindung = verbindung or self._verbindung()
        status, antwort = self._transport(methode, pfad, nutzlast, verbindung)
        if status == 401:
            raise TuerFehler(
                f"Kingfisher hat das Token abgelehnt (aus {verbindung.herkunft}). "
                "Wurde die App neu eingerichtet?"
            )
        if status == 403:
            raise TuerFehler(_tuer_zu(antwort, verbindung))
        if status >= 400:
            detail = antwort.get("detail") if isinstance(antwort, dict) else None
            raise TuerFehler(f"Kingfisher antwortet mit {status}: {detail or 'ohne Begründung'}")
        return antwort


def _tuer_zu(antwort: Any, verbindung: Verbindung) -> str:
    """Der Satz des Sidecars, für die Mac-App um den Ort ergänzt, an dem man es ändert."""
    satz = str(antwort.get("detail") if isinstance(antwort, dict) else "") or (
        "Die MCP-Anbindung von Kingfisher ist ausgeschaltet.")
    if verbindung.schalter_datei is not None:
        satz += (f" In der Mac-App: die Zeile {TUER_SCHALTER}=1 in {verbindung.schalter_datei} "
                 "ergänzen und Kingfisher neu starten.")
    return satz


def treffer(text: str) -> int:
    """Wie viele Aussagen der Sidecar geliefert hat: jede steht in einer Zeile mit `- `."""
    return sum(1 for zeile in text.splitlines() if zeile.startswith("- "))
