"""Modelle nach Rolle: wer bekommt welches Modell, lokal oder in der Cloud.

Erweitert das vorhandene Routing (`model_routing.py`, `routing_runtime.py`)
um eine zweite Achse: neben „welches geprüfte Modell für diese Anfrage“
(dort) steht hier „welche Aufgabe des Stabschefs bekommt welches Modell“.

Rollen (Etappe E4 in `docs/27-schichten-und-fragen.md`):

    frage        Frage in eine strukturierte Anfrage übersetzen (schnell, klein)
    antwort      Antwort aus Akten und Belegen formulieren (Gespräch, Agent)
    pruefung     jeden Satz der Antwort ein zweites Mal gegen seine Belege prüfen (klein, immer lokal)
    hintergrund  Einordnen, Bezüge, Akten, Verdichtung (gründlich, darf langsam sein)
    einbettung   Suche nach Bedeutung (Embedding-Modell, immer lokal)

Grundsätze, an denen nichts weich sein darf:

* **Ohne Rollenkonfiguration verhält sich alles wie bisher.** `provider_fuer`
  gibt dann genau den Standardanbieter zurück.
* **Cloud nur mit Einwilligung je Rolle.** Ein Zeitstempel, den nur die Route
  nach ausdrücklicher Bestätigung setzt. Ohne gültigen Zeitstempel wird die
  Cloudwahl ignoriert, nie umgangen; die Einwilligung einer Rolle gilt nicht
  für eine andere.
* **Hintergrundarbeit, Einbettung und Prüfung bleiben lokal.** Diese Rollen sehen das
  Rohmaterial; die Freigabe für die Cloud ist für sie (noch) nicht vorgesehen
  (`RolleSpec.cloud_moeglich`), auch nicht per Handeintrag in der Datei.
* **Ein Modell „auf dem lokalen Ollama“ ist nicht automatisch lokal.** Modelle mit dem
  Tag `cloud` reicht Ollama an seinen Server weiter. `ollama_inventar.py` weiß je
  installiertem Modell, ob die Gewichte auf der Platte liegen. Ein Cloud-über-Ollama-Modell
  wird wie ein Cloudanbieter behandelt (Anbieter `ollama-cloud`): für Hintergrund und
  Einbettung nie, für Frage und Antwort nur mit gültiger Einwilligung. Ist Ollama stumm,
  gilt ein gewähltes Modell als nicht belegt lokal (fail closed).
"""
from __future__ import annotations

import os
import threading
from collections.abc import Callable, Mapping
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .ollama_inventar import CLOUD, LOKAL, OllamaInventar, inventar_von
from .providers import Anthropic, OpenAICompatible, Provider

STANDARD_EINBETTUNG = "bge-m3:latest"

# Cloud-Modelle, die über das lokale Ollama laufen: kein eigener Schlüssel, das Modell trägt die Wahl.
OLLAMA_CLOUD = "ollama-cloud"
OLLAMA_CLOUD_SATZ = "Die Daten gehen an Ollama (USA), nicht an den Modellhersteller: Ollama reicht die Anfrage an seinen Server weiter."

# Welche Cloudanbieter je Rolle anwählbar sind, samt Schlüsselname in der Umgebung.
CLOUD_ANBIETER = {
    "anthropic": ("ANTHROPIC_API_KEY", "claude-sonnet-5"),
    "openai": ("OPENAI_API_KEY", "gpt-4.1-mini"),
    OLLAMA_CLOUD: ("", ""),
}


@dataclass(frozen=True)
class RolleSpec:
    name: str
    titel: str  # Alltagssprache für die Oberfläche
    beschreibung: str  # ein Satz
    cloud_moeglich: bool
    cloud_satz: str  # der Satz, dem der Nutzer bei der Einwilligung zustimmt


ROLLEN: dict[str, RolleSpec] = {s.name: s for s in (
    RolleSpec("frage", "Fragen verstehen",
              "Übersetzt deine Frage in Stichworte, bevor gesucht wird.",
              True, "Deine Fragen (nicht deine Quellen) werden an den Cloudanbieter gesendet."),
    RolleSpec("antwort", "Antworten formulieren",
              "Formuliert die Antwort aus den gefundenen Belegen.",
              True, "Deine Fragen und die dafür gefundenen Textstellen werden an den Cloudanbieter gesendet."),
    RolleSpec("pruefung", "Sätze gegenprüfen",
              "Prüft jeden Satz einer Antwort ein zweites Mal gegen seine Belege.",
              False, "Diese Aufgabe liest die Textstellen deiner Quellen und bleibt deshalb auf diesem Rechner."),
    RolleSpec("hintergrund", "Im Hintergrund ordnen",
              "Ordnet neue Mails und Dokumente ein und legt Bezüge an.",
              False, "Diese Aufgabe liest alle deine Quellen und bleibt deshalb auf diesem Rechner."),
    RolleSpec("einbettung", "Bedeutungen finden",
              "Findet Sinnverwandtes, auch wenn andere Wörter benutzt wurden.",
              False, "Diese Aufgabe liest alle deine Quellen und bleibt deshalb auf diesem Rechner."),
)}


@dataclass(frozen=True)
class RollenWahl:
    """Die Wahl des Nutzers für eine Rolle. Leer heißt „wie Standard“."""

    modell: str = ""  # Modellname; leer = wie Standard
    cloud: bool = False
    anbieter: str = ""  # Cloudanbieter, nur bei cloud=True
    cloud_einwilligung: str = ""  # ISO-Zeitstempel der ausdrücklichen Einwilligung

    def als_dict(self) -> dict[str, Any]:
        return {"modell": self.modell, "cloud": self.cloud, "anbieter": self.anbieter,
                "cloud_einwilligung": self.cloud_einwilligung}

    @property
    def ist_leer(self) -> bool:
        return not self.modell and not self.cloud


def lese_wahlen(roh: Any) -> dict[str, RollenWahl]:
    """Liest die gespeicherten Wahlen; Unbekanntes und Kaputtes wird überlesen."""
    wahlen: dict[str, RollenWahl] = {}
    if not isinstance(roh, Mapping):
        return wahlen
    for rolle, eintrag in roh.items():
        if rolle not in ROLLEN or not isinstance(eintrag, Mapping):
            continue
        modell = eintrag.get("modell")
        anbieter = eintrag.get("anbieter")
        einwilligung = eintrag.get("cloud_einwilligung")
        wahl = RollenWahl(
            modell=modell.strip() if isinstance(modell, str) else "",
            cloud=eintrag.get("cloud") is True,
            anbieter=anbieter if isinstance(anbieter, str) and anbieter in CLOUD_ANBIETER else "",
            cloud_einwilligung=einwilligung if isinstance(einwilligung, str) else "",
        )
        if not wahl.ist_leer:
            wahlen[rolle] = wahl
    return wahlen


def einwilligung_gueltig(rolle: str, wahl: RollenWahl) -> bool:
    """Darf diese Rolle die Cloud nutzen? Nur mit Zeitstempel, nur wo die Rolle es zulässt."""
    spec = ROLLEN.get(rolle)
    if spec is None or not spec.cloud_moeglich or not wahl.cloud or not wahl.anbieter:
        return False
    try:
        datetime.fromisoformat(wahl.cloud_einwilligung)
    except (TypeError, ValueError):
        return False
    return True


def einbettung_modell(wahlen: Mapping[str, RollenWahl]) -> str:
    wahl = wahlen.get("einbettung")
    return wahl.modell if wahl and wahl.modell else STANDARD_EINBETTUNG


def lokaler_endpunkt(standard: Provider | None, umgebung: Mapping[str, str] | None = None) -> str:
    """Wo das lokale Ollama steht, ohne dass der Nutzer es angeben muss.

    Ist der Standardanbieter lokal, gilt dessen Adresse. Sonst der vom Betreiber
    ausdrücklich freigegebene Wirtsname (im Container: `host.docker.internal`),
    zuletzt die Loopback-Adresse.
    """
    if standard is not None and getattr(standard, "is_local", False) and getattr(standard, "base_url", ""):
        return str(standard.base_url).rstrip("/")
    umgebung = os.environ if umgebung is None else umgebung
    for host in umgebung.get("ICARUS_TRUSTED_LOCAL_MODEL_HOSTS", "").split(","):
        if host.strip():
            return f"http://{host.strip()}:11434/v1"
    return "http://localhost:11434/v1"


def ollama_wurzel(endpunkt: str) -> str:
    """`http://host:11434/v1` -> `http://host:11434`."""
    endpunkt = endpunkt.rstrip("/")
    return endpunkt[:-3] if endpunkt.endswith("/v1") else endpunkt


def _vertraute_hosts(umgebung: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(h.strip().lower() for h in umgebung.get("ICARUS_TRUSTED_LOCAL_MODEL_HOSTS", "").split(",")
                 if h.strip())


def _lokal(standard: Provider | None, modell: str, umgebung: Mapping[str, str]) -> Provider:
    if isinstance(standard, OpenAICompatible) and standard.is_local:
        kopie = copy(standard)  # gleiche Adresse, gleiche freigegebenen Hosts, anderes Modell
        kopie.model = modell
        return kopie
    return OpenAICompatible(modell, api_key="ollama", base_url=lokaler_endpunkt(standard, umgebung),
                            trusted_local_hosts=_vertraute_hosts(umgebung))


def _cloud(wahl: RollenWahl, umgebung: Mapping[str, str]) -> Provider | None:
    schluessel_name, standardmodell = CLOUD_ANBIETER[wahl.anbieter]
    schluessel = umgebung.get(schluessel_name) or (
        umgebung.get("LLM_API_KEY") if wahl.anbieter == "openai" else None)
    if not schluessel:
        return None
    modell = wahl.modell or standardmodell
    return Anthropic(modell, schluessel) if wahl.anbieter == "anthropic" else OpenAICompatible(modell, schluessel)


def _ollama_lokal(anbieter: Provider | None) -> bool:
    """Ein Anbieter, der auf das lokale Ollama zeigt (nur dort kann ein Modell in die Cloud weiterreichen)."""
    return isinstance(anbieter, OpenAICompatible) and bool(anbieter.is_local)


def _art(anbieter: OpenAICompatible, modell: str, inventar: OllamaInventar) -> str:
    return inventar.art(modell, ollama_wurzel(anbieter.base_url))


def _standard_geprueft(rolle: str, standard: Provider | None, inventar: OllamaInventar | None) -> Provider | None:
    """Der Standardanbieter, außer er ist ein Ollama-Modell, das für diese Rolle nicht infrage kommt.

    Cloud über Ollama gilt nie ohne Einwilligung. Rollen, die die Cloud nicht nutzen dürfen, verlangen
    zusätzlich den Beleg „lokal“ (unbekannt reicht nicht). Die Einbettung nutzt den Standard nur als
    Adresse des lokalen Ollama; ihr Modell wird getrennt geprüft.
    """
    if standard is None or inventar is None or rolle == "einbettung" or not _ollama_lokal(standard):
        return standard
    art = _art(standard, standard.model, inventar)
    if art == LOKAL:
        return standard
    if art == CLOUD or not ROLLEN[rolle].cloud_moeglich:
        return None
    return standard


def _ollama_cloud(wahl: RollenWahl, standard: Provider | None, umgebung: Mapping[str, str]) -> Provider | None:
    """Das gewählte Cloud-Modell über Ollama, ausdrücklich als „nicht lokal“ gekennzeichnet."""
    if not wahl.modell:
        return None
    kopie = copy(_lokal(standard, wahl.modell, umgebung))
    kopie.is_local = False
    kopie.ueber_ollama_cloud = True
    return kopie


def provider_fuer(rolle: str, standard: Provider | None, wahlen: Mapping[str, RollenWahl],
                  umgebung: Mapping[str, str] | None = None, inventar: OllamaInventar | None = None) -> Provider | None:
    """Der Anbieter für eine Rolle.

    Reihenfolge: gültige Cloudwahl (mit Einwilligung und Schlüssel), sonst
    gewähltes lokales Modell, sonst der Standardanbieter. Jede Lücke fällt auf
    den Standard zurück, nie auf die Cloud.

    Rollen, die die Cloud nicht nutzen dürfen (`RolleSpec.cloud_moeglich`), bekommen nie
    einen Anbieter, der nicht lokal ist: Ist der Standard ein Cloudanbieter, ist ihr Anbieter
    `None` (die Arbeit läuft dann ohne Modell), statt dass Rohquellen in die Cloud gehen.

    Mit `inventar` (`ollama_inventar.py`) zählt auch ein Modell auf dem lokalen Ollama nur als lokal,
    wenn seine Gewichte belegt auf der Platte liegen. Ohne `inventar` wird nur der Endpunkt geprüft;
    die Anwendung übergibt es immer (`Rollen`).
    """
    anbieter = _anbieter_fuer(rolle, standard, wahlen, umgebung, inventar)
    if anbieter is not None and not ROLLEN[rolle].cloud_moeglich and not getattr(anbieter, "is_local", False):
        return None
    return anbieter


def _anbieter_fuer(rolle: str, standard: Provider | None, wahlen: Mapping[str, RollenWahl],
                   umgebung: Mapping[str, str] | None, inventar: OllamaInventar | None) -> Provider | None:
    if rolle not in ROLLEN:
        raise KeyError(rolle)
    wahl = wahlen.get(rolle)
    if wahl is None or wahl.ist_leer:
        return _standard_geprueft(rolle, standard, inventar)
    umgebung = os.environ if umgebung is None else umgebung
    if wahl.cloud and einwilligung_gueltig(rolle, wahl):
        if wahl.anbieter == OLLAMA_CLOUD:
            return _cloud_ueber_ollama(rolle, wahl, standard, umgebung, inventar)
        cloud = _cloud(wahl, umgebung)
        if cloud is not None:
            return cloud
        return _standard_geprueft(rolle, standard, inventar)  # kein Schlüssel: lieber der Standard als ein Fehler beim ersten Satz
    if wahl.cloud:
        # Cloud angefordert, aber ohne gültige Einwilligung: die Wahl wird
        # ignoriert. Der Standard gilt, nie die Cloud.
        return _standard_geprueft(rolle, standard, inventar)
    if wahl.modell:
        lokal = _lokal(standard, wahl.modell, umgebung)
        if inventar is None or _art(lokal, wahl.modell, inventar) == LOKAL:
            return lokal
        # Cloud über Ollama (oder nicht belegt lokal) ohne Einwilligung: nie stillschweigend.
        # Rollen ohne Cloud bleiben ohne Modell; Frage und Antwort fallen auf den geprüften Standard zurück.
        return _standard_geprueft(rolle, standard, inventar) if ROLLEN[rolle].cloud_moeglich else None
    return _standard_geprueft(rolle, standard, inventar)


def _cloud_ueber_ollama(rolle: str, wahl: RollenWahl, standard: Provider | None, umgebung: Mapping[str, str],
                        inventar: OllamaInventar | None) -> Provider | None:
    """Eine gültige Einwilligung für ein Ollama-Cloud-Modell. Liegt es doch lokal, ist es einfach lokal."""
    if wahl.modell and inventar is not None:
        lokal = _lokal(standard, wahl.modell, umgebung)
        if _art(lokal, wahl.modell, inventar) == LOKAL:
            return lokal
    return _ollama_cloud(wahl, standard, umgebung) or _standard_geprueft(rolle, standard, inventar)


class Rollen:
    """Die Anbieter aller Rollen für den laufenden Agenten, je Rolle einmal gebaut.

    Ein stabiles Objekt je Rolle ist nötig, weil die Hintergrundläufe prüfen, ob
    „ihr“ Anbieter noch der gültige ist (Identitätsvergleich). Ein Neubau
    (`_build_agent`) erzeugt eine neue `Rollen` und macht so alte Läufe ungültig,
    wie es beim Anbieterwechsel schon der Fall war. Ändert sich, ob ein gewähltes Modell
    lokal ist (`ollama_inventar.py`), wird der Anbieter der Rolle ebenfalls neu gebaut.
    """

    def __init__(self, wahlen: Mapping[str, RollenWahl], standard: Callable[[], Provider | None],
                 umgebung: Mapping[str, str] | None = None, inventar: OllamaInventar | None = None) -> None:
        self.wahlen = dict(wahlen)
        self._standard = standard
        self._umgebung = umgebung
        self._inventar = inventar
        self._cache: dict[str, tuple[Provider | None, tuple[str, ...], Provider | None]] = {}
        self._lock = threading.Lock()

    @property
    def leer(self) -> bool:
        return not self.wahlen

    def _modelle_im_blick(self, rolle: str, standard: Provider | None) -> list[tuple[OpenAICompatible, str]]:
        """Die Ollama-Modelle, die für diese Rolle zählen: das gewählte und (außer Einbettung) der Standard."""
        gefunden: list[tuple[OpenAICompatible, str]] = []
        wahl = self.wahlen.get(rolle)
        if wahl is not None and wahl.modell:
            gefunden.append((_lokal(standard, wahl.modell, self._umgebung or os.environ), wahl.modell))
        if rolle != "einbettung" and _ollama_lokal(standard):
            gefunden.append((standard, standard.model))
        return gefunden

    def _arten(self, rolle: str, standard: Provider | None) -> tuple[str, ...]:
        if self._inventar is None:
            return ()
        return tuple(_art(anbieter, modell, self._inventar) for anbieter, modell in self._modelle_im_blick(rolle, standard))

    def provider(self, rolle: str) -> Provider | None:
        if rolle not in ROLLEN:
            raise KeyError(rolle)
        standard = self._standard()
        if self.leer:  # ohne Rollenwahl gilt der Standard, der Anbieter wird je Aufruf frisch beurteilt
            return provider_fuer(rolle, standard, self.wahlen, self._umgebung, self._inventar)
        arten = self._arten(rolle, standard)
        with self._lock:
            gemerkt = self._cache.get(rolle)
            if gemerkt is None or gemerkt[0] is not standard or gemerkt[1] != arten:
                gemerkt = (standard, arten,
                           provider_fuer(rolle, standard, self.wahlen, self._umgebung, self._inventar))
                self._cache[rolle] = gemerkt
            return gemerkt[2]

    def standard(self) -> Provider | None:
        """Der Anbieter „wie Standard“ (vor jeder Rollenwahl)."""
        return self._standard()

    def cloud_modell_im_weg(self, rolle: str) -> str | None:
        """Name des Cloud-über-Ollama-Modells, das diese Rolle lahmlegt (ohne Einwilligung), sonst `None`.

        Für die Anzeige: Der Nutzer soll lesen, warum eine Aufgabe ruht, statt nur zu sehen, dass sie ruht.
        """
        if self._inventar is None or getattr(self.provider(rolle), "ueber_ollama_cloud", False):
            return None
        standard = self._standard()
        for anbieter, modell in self._modelle_im_blick(rolle, standard):
            if _art(anbieter, modell, self._inventar) == CLOUD:
                return modell
        return None

    def einbettung_modell(self) -> str:
        """Das Einbettungsmodell; ein Cloud-über-Ollama-Modell wird nie genommen, dann gilt die Vorgabe."""
        modell = einbettung_modell(self.wahlen)
        wahl = self.wahlen.get("einbettung")
        if self._inventar is not None and wahl is not None and wahl.modell:
            anbieter, _ = self._modelle_im_blick("einbettung", self._standard())[0]
            if _art(anbieter, modell, self._inventar) != LOKAL:
                return STANDARD_EINBETTUNG
        return modell


def anbieter_fuer_frage(rollen: Rollen) -> Provider | None:
    """Der Anbieter der Rolle `frage`, nur wenn ihr ein Modell zugewiesen ist; sonst None (Rückfall).

    Die Rolle ist ausdrücklich einzurichten (Einstellungen, Lokale KI, oder die
    Geräteempfehlung). Ohne Zuweisung versteht der deterministische Rückfall
    (`frage.py`) die Frage: kein Modellaufruf, keine Wartezeit, nichts geht an einen
    Anbieter. Der Standardanbieter der Antworten ist dafür ungeeignet, er kann groß
    und langsam oder in der Cloud sein.

    Auch mit Zuweisung nie ein Cloudanbieter ohne gültige Einwilligung für genau
    diese Rolle (`provider_fuer` fällt ohne sie auf den Standard zurück; ist der
    nicht lokal, gilt hier wieder der Rückfall).
    """
    wahl = rollen.wahlen.get("frage")
    if wahl is None or wahl.ist_leer:
        return None
    anbieter = rollen.provider("frage")
    if anbieter is None:
        return None
    if getattr(anbieter, "is_local", False) or einwilligung_gueltig("frage", wahl):
        return anbieter
    return None


def anbieter_fuer_pruefung(rollen: Rollen) -> Provider | None:
    """Der Anbieter der Rolle `pruefung` (zweites Tor der Satzprüfung), nur mit Zuweisung und nur lokal; sonst None.

    Wie bei `frage` gibt es keinen Rückfall auf den Standardanbieter: Das Antwortmodell prüft sich nicht selbst,
    und ein großes Modell kostete bei jedem Satz Sekunden. Ohne Zuweisung ist das Tor still aus
    (`satzpruefung_modell.py`). Die Rolle darf nie in die Cloud (`cloud_moeglich` ist falsch; `provider_fuer`
    gibt dann `None`), hier zusätzlich geprüft.
    """
    wahl = rollen.wahlen.get("pruefung")
    if wahl is None or not wahl.modell:
        return None
    anbieter = rollen.provider("pruefung")
    return anbieter if anbieter is not None and getattr(anbieter, "is_local", False) else None


_NICHT_GESETZT = object()


def hintergrund_anbieter(app: Any) -> Provider | None:
    """Der Anbieter für jede Hintergrundarbeit (Einordnen, Verdichten, Überblicke): Rolle `hintergrund`.

    Immer lokal oder `None`; nie der Anbieter des Gesprächs (Rolle `antwort`), der eine Cloud sein darf.
    """
    return rollen_von(app).provider("hintergrund")


def rollen_von(app: Any) -> Rollen:
    """Die `Rollen` zum aktuellen Stand der Einstellungen (dünn am Anwendungsobjekt).

    Ohne Rollenkonfiguration ist der Standard der **lebende** `agent.provider`,
    genau wie vor E4. Mit Konfiguration ist es der beim Neubau des Agenten
    gemerkte Standardanbieter (`app.state.standard_provider`), denn
    `agent.provider` ist dann schon der Anbieter der Rolle `antwort`.
    """
    zustand = app.state
    wahlen = lese_wahlen(getattr(getattr(zustand, "settings", None), "model_roles", None))
    rollen = getattr(zustand, "rollen", None)
    if rollen is None or rollen.wahlen != wahlen:
        def standard() -> Provider | None:
            gemerkt = getattr(zustand, "standard_provider", _NICHT_GESETZT)
            if wahlen and gemerkt is not _NICHT_GESETZT:
                return gemerkt
            return getattr(getattr(zustand, "agent", None), "provider", None)
        rollen = Rollen(wahlen, standard, inventar=inventar_von(app))
        zustand.rollen = rollen
    return rollen


__all__ = [
    "anbieter_fuer_frage", "anbieter_fuer_pruefung", "hintergrund_anbieter", "rollen_von",
    "CLOUD_ANBIETER", "OLLAMA_CLOUD", "OLLAMA_CLOUD_SATZ", "ROLLEN", "Rollen", "RollenWahl", "RolleSpec", "STANDARD_EINBETTUNG",
    "einbettung_modell", "einwilligung_gueltig", "lese_wahlen", "lokaler_endpunkt",
    "ollama_wurzel", "provider_fuer",
]
