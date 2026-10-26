"""Bereiche je Postfach und Kalender und ihre Vererbung (docs/66-automatik.md, Paket K).

Der Nutzer trennt Arbeit und Privat (oder eigene Bereiche wie „Verein“) nicht je Mail, je Termin oder je Aufgabe,
sondern einmal je Konto: Kingfisher schlägt für ein Postfach oder einen Kalender „Privat“ oder „Arbeit“ vor, der
Mensch bestätigt mit einem Klick. Gespeichert wird **nur das Bestätigte**, in der Konfiguration
(`Settings.konten['bereich_je_konto']`), ohne Datenbankspalte. Ein Vorschlag wirkt nie, bevor er bestätigt ist.

Alles Weitere ist abgeleitet und wird bei jeder Antwort neu bestimmt:

* eine Mail hat den Bereich ihres Postfachs (Präfix der Quellreferenz, `mail_ingestion.remember`),
* ein Termin den seines Kalenders (`source_id` bzw. beim Mac `view_source_id`; im Gedächtnis `calendar:<quelle>:…`),
* eine Aufgabe den ihrer Quelle (`episode:<id>`), sonst den ihres Projekts,
* ein Projekt sein Feld `area`, wenn es einen Bereich nennt, sonst den überwiegenden Bereich seiner Quellen
  (mehr als die Hälfte der Quellen mit Bereich; sonst keiner statt Raten).

Ein Bereich ist Ablage, kein Fakt über einen Menschen. Er ändert nichts im Bestand und verlässt den Rechner nicht.

Öffentlich für andere Pakete (Aufgaben und Projekte von selbst): `bereich_einer_referenz`, `bereich_einer_episode`,
`bereich_einer_aufgabe`, `bereich_eines_projekts`, `aufgaben_anreichern`, `projekte_anreichern`, `termine_anreichern`.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import identitaet

ARBEIT = "arbeit"
PRIVAT = "privat"
#: Die zwei Bereiche, die es immer gibt. Eigene kommen dazu (`neuer_bereich`).
VORGEGEBEN: tuple[dict[str, str], ...] = ({"id": ARBEIT, "name": "Arbeit"}, {"id": PRIVAT, "name": "Privat"})
MAX_NAME = 40
MAX_EIGENE = 12

#: Wörter im Namen eines Kalenders, die den Bereich verraten. Nur eindeutige; „Feiertage“ etwa sagt nichts.
_WOERTER_ARBEIT = ("arbeit", "work", "büro", "buero", "office", "firma", "job", "team", "kunden", "projekt",
                   "geschäft", "geschaeft", "business", "kanzlei")
_WOERTER_PRIVAT = ("privat", "private", "personal", "persönlich", "persoenlich", "familie", "family", "zuhause",
                   "kinder", "freunde", "geburtstag", "birthdays")

_MAC_KALENDER = "mac-calendar"


# -- Einstellung ------------------------------------------------------------------------------------------------------


def _roh(settings: Any) -> dict[str, Any]:
    roh = getattr(settings, "konten", None)
    return roh if isinstance(roh, dict) else {}


def eigene_bereiche(settings: Any) -> list[dict[str, str]]:
    """Die selbst angelegten Bereiche, je `{id, name}`."""
    ergebnis = []
    for eintrag in _roh(settings).get("eigene") or []:
        if isinstance(eintrag, dict) and isinstance(eintrag.get("id"), str) and isinstance(eintrag.get("name"), str):
            ergebnis.append({"id": eintrag["id"], "name": eintrag["name"]})
    return ergebnis


def bereiche(settings: Any) -> list[dict[str, Any]]:
    """Alle Bereiche: Arbeit, Privat, dann die eigenen in der Reihenfolge ihrer Anlage."""
    return ([{**b, "eigen": False} for b in VORGEGEBEN]
            + [{**b, "eigen": True} for b in eigene_bereiche(settings)])


def bereich_name(settings: Any, bereich_id: str | None) -> str | None:
    return next((b["name"] for b in bereiche(settings) if b["id"] == bereich_id), None)


def bereich_finden(settings: Any, text: str | None) -> str | None:
    """Die Kennung zu einer Kennung oder einem Namen (Groß- und Kleinschreibung egal), sonst None."""
    gesucht = str(text or "").strip().casefold()
    if not gesucht:
        return None
    return next((b["id"] for b in bereiche(settings)
                 if b["id"].casefold() == gesucht or b["name"].casefold() == gesucht), None)


def _kennung(name: str) -> str:
    umlaute = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
    return re.sub(r"[^a-z0-9]+", "-", name.casefold().translate(umlaute)).strip("-")[:32]


def neuer_bereich(settings: Any, name: str) -> str:
    """Legt einen eigenen Bereich an (oder findet den gleichnamigen) und gibt seine Kennung zurück."""
    name = " ".join(str(name or "").split())
    if not name:
        raise ValueError("Bitte gib dem Bereich einen Namen.")
    if len(name) > MAX_NAME:
        raise ValueError(f"Der Name ist zu lang; höchstens {MAX_NAME} Zeichen.")
    vorhanden = bereich_finden(settings, name)
    if vorhanden is not None:
        return vorhanden
    eigene = eigene_bereiche(settings)
    if len(eigene) >= MAX_EIGENE:
        raise ValueError(f"Mehr als {MAX_EIGENE} eigene Bereiche gibt es nicht.")
    basis = "eigen-" + (_kennung(name) or hashlib.sha256(name.encode()).hexdigest()[:8])
    kennung, n = basis, 2
    belegt = {b["id"] for b in bereiche(settings)}
    while kennung in belegt:
        kennung, n = f"{basis}-{n}", n + 1
    roh = dict(_roh(settings))
    roh["eigene"] = [*eigene, {"id": kennung, "name": name}]
    settings.konten = roh
    return kennung


def bereich_je_konto(settings: Any) -> dict[str, str]:
    """Bestätigte Bereiche je Konto-Kennung (`mail-…`, `calendar-…`, `mac-calendar:<Kalender>`)."""
    gueltig = {b["id"] for b in bereiche(settings)}
    roh = _roh(settings).get("bereich_je_konto") or {}
    return {str(k): str(v) for k, v in roh.items() if isinstance(v, str) and v in gueltig} if isinstance(roh, dict) else {}


def setze_bereich(settings: Any, konto_id: str, bereich_id: str | None) -> str | None:
    """Setzt (oder löscht mit None) den bestätigten Bereich eines Kontos; gibt den vorigen zurück."""
    if bereich_id is not None and bereich_id not in {b["id"] for b in bereiche(settings)}:
        raise ValueError("Diesen Bereich gibt es nicht.")
    roh = dict(_roh(settings))
    zuordnung = dict(roh.get("bereich_je_konto") or {}) if isinstance(roh.get("bereich_je_konto"), dict) else {}
    vorher = zuordnung.get(konto_id) if isinstance(zuordnung.get(konto_id), str) else None
    if bereich_id is None:
        zuordnung.pop(konto_id, None)
    else:
        zuordnung[konto_id] = bereich_id
    roh["bereich_je_konto"] = zuordnung
    settings.konten = roh
    return vorher


def ausgeblendete_kalender(settings: Any) -> list[str]:
    """Kalender, die der Mensch auf der Kalenderseite ausgeblendet hat; bleibt über das Neuladen hinaus."""
    roh = _roh(settings).get("kalender_ausgeblendet") or []
    return [str(k) for k in roh if isinstance(k, str)] if isinstance(roh, list) else []


def setze_ausgeblendet(settings: Any, kennungen: Iterable[str]) -> list[str]:
    roh = dict(_roh(settings))
    roh["kalender_ausgeblendet"] = list(dict.fromkeys(str(k) for k in kennungen if str(k).strip()))[:200]
    settings.konten = roh
    return roh["kalender_ausgeblendet"]


def in_gebrauch(settings: Any, konto_ids: Iterable[str] | None = None) -> list[str]:
    """Die Bereiche, die mindestens ein (noch vorhandenes) Konto trägt, in der Reihenfolge von `bereiche`."""
    zuordnung = bereich_je_konto(settings)
    if konto_ids is not None:
        erlaubt = set(konto_ids)
        zuordnung = {k: v for k, v in zuordnung.items() if k in erlaubt}
    benutzt = set(zuordnung.values())
    return [b["id"] for b in bereiche(settings) if b["id"] in benutzt]


# -- Vorschlag --------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Vorschlag:
    bereich: str
    grund: str

    def to_dict(self) -> dict[str, str]:
        return {"bereich": self.bereich, "grund": self.grund}


def vorschlag_postfach(adresse: str | None) -> Vorschlag | None:
    """Private Anbieter-Adresse → Privat, eigene Domäne einer Firma → Arbeit; ohne Adresse kein Vorschlag."""
    adresse = str(adresse or "").strip()
    domaene = identitaet.domaene(adresse).casefold()
    if not domaene or "." not in domaene:
        return None
    if identitaet.ist_privater_anbieter(adresse):
        return Vorschlag(PRIVAT, f"{domaene} ist ein Anbieter für private Adressen.")
    return Vorschlag(ARBEIT, f"{domaene} ist die Adresse einer Firma oder Organisation.")


def _wort_im_namen(name: str) -> str | None:
    text = str(name or "").casefold()
    woerter = set(re.findall(r"[\wäöüß]+", text))
    def trifft(liste: tuple[str, ...]) -> bool:
        return any(w in woerter or any(t.startswith(w) for t in woerter) for w in liste)
    arbeit, privat = trifft(_WOERTER_ARBEIT), trifft(_WOERTER_PRIVAT)
    if arbeit == privat:
        return None
    return ARBEIT if arbeit else PRIVAT


def vorschlag_kalender(name: str, *, adresse: str = "", konto: tuple[str, str] | None = None) -> Vorschlag | None:
    """Erst der Name („Arbeit“, „Familie“), dann das zugehörige Postfach (`konto` = (Name, Bereich)), dann die Adresse.

    Ohne Hinweis kein Vorschlag: lieber einmal fragen als falsch einsortieren.
    """
    aus_name = _wort_im_namen(name)
    if aus_name is not None:
        return Vorschlag(aus_name, f"Der Name „{name}“ klingt nach {'Arbeit' if aus_name == ARBEIT else 'privat'}.")
    if konto is not None and konto[1]:
        return Vorschlag(konto[1], f"Er gehört zum Postfach {konto[0]}.")
    aus_adresse = vorschlag_postfach(adresse)
    if aus_adresse is not None:
        return Vorschlag(aus_adresse.bereich, f"Er gehört zu {adresse.strip()}: {aus_adresse.grund}")
    return None


# -- Vererbung --------------------------------------------------------------------------------------------------------


def mac_quelle(kalender_id: str) -> str:
    """Die Gedächtnisquelle eines Mac-Kalenders (`calendar_memory.quelle_fuer_mac`)."""
    from .calendar_memory import quelle_fuer_mac
    return quelle_fuer_mac(kalender_id)


def quelle_von_referenz(source_ref: str | None) -> str | None:
    """Die Konto-Kennung hinter einer Quellreferenz: `mail-…:<id>` → `mail-…`, `calendar:<quelle>:<uid>` → `<quelle>`.

    Ältere Referenzen ohne Postfach (`imap:…`, `<message-id>`) haben keine; dann None.
    """
    ref = str(source_ref or "")
    if ref.startswith("calendar:"):
        quelle, trenner, _ = ref[len("calendar:"):].partition(":")
        return (quelle or None) if trenner else None
    vorne, trenner, _ = ref.partition(":")
    if not trenner or not vorne or vorne in {"imap", "episode", "upload", "ui"} or vorne.startswith("<"):
        return None
    return vorne


def _zuordnung_mit_mac(settings: Any) -> dict[str, str]:
    """Bestätigte Bereiche, dazu jeder Mac-Kalender auch unter seiner Gedächtnisquelle (`mac-calendar/<Kurzhash>`)."""
    zuordnung = bereich_je_konto(settings)
    erweitert = dict(zuordnung)
    praefix = _MAC_KALENDER + ":"
    for kennung, bereich in zuordnung.items():
        if kennung.startswith(praefix):
            erweitert[mac_quelle(kennung[len(praefix):])] = bereich
    return erweitert


def bereich_einer_quelle(settings: Any, quelle: str | None) -> str | None:
    return _zuordnung_mit_mac(settings).get(str(quelle or "")) if quelle else None


def bereich_einer_referenz(settings: Any, source_ref: str | None) -> str | None:
    """Der Bereich einer Mail oder eines Termins im Gedächtnis, aus seiner Quellreferenz."""
    return bereich_einer_quelle(settings, quelle_von_referenz(source_ref))


def bereich_eines_termins(settings: Any, termin: Mapping[str, Any], *, _zuordnung: dict[str, str] | None = None) -> str | None:
    """Der Bereich eines angezeigten Termins (`Event.to_dict`), bei Kopien in mehreren Kalendern der erste bekannte."""
    zuordnung = _zuordnung if _zuordnung is not None else bereich_je_konto(settings)
    if termin.get("art") == "geburtstag":
        # Geburtstage stehen nur für den bestätigten inneren Kreis im Kalender (`wiederkehrendes.py`): privat.
        return PRIVAT
    kopien = [termin, *(termin.get("source_copies") or [])]
    for kopie in kopien:
        for kennung in (kopie.get("view_source_id"), kopie.get("source_id")):
            if kennung and kennung in zuordnung:
                return zuordnung[kennung]
    return None


def termine_anreichern(settings: Any, termine: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Setzt `bereich` an jedem Termin (None ohne bestätigten Bereich); gibt dieselbe Liste zurück."""
    zuordnung = bereich_je_konto(settings)
    for termin in termine:
        if isinstance(termin, dict):
            termin["bereich"] = bereich_eines_termins(settings, termin, _zuordnung=zuordnung)
    return termine


def _episoden_referenzen(app: Any, episode_ids: Iterable[str]) -> dict[str, str | None]:
    ids = list(dict.fromkeys(i for i in episode_ids if i))
    if not ids:
        return {}
    store = getattr(app.state, "episodes", None)
    if store is None:
        return {}
    ergebnis: dict[str, str | None] = {}
    with store._lock:
        for start in range(0, len(ids), 500):
            stueck = ids[start:start + 500]
            zeilen = store._conn.execute(
                "SELECT id, json_extract(document, '$.provenance.source_ref') FROM episodes WHERE id IN ("
                + ",".join("?" * len(stueck)) + ")", stueck).fetchall()
            ergebnis.update({str(z[0]): z[1] for z in zeilen})
    return ergebnis


def bereiche_von_episoden(app: Any, episode_ids: Iterable[str]) -> dict[str, str | None]:
    settings = app.state.settings
    return {eid: bereich_einer_referenz(settings, ref) for eid, ref in _episoden_referenzen(app, episode_ids).items()}


def bereich_einer_episode(app: Any, episode_id: str) -> str | None:
    return bereiche_von_episoden(app, [episode_id]).get(episode_id)


_QUELLE_SQL = ("CASE WHEN ref LIKE 'calendar:%' THEN substr(ref, 10, instr(substr(ref, 10), ':') - 1) "
               "WHEN instr(ref, ':') > 0 THEN substr(ref, 1, instr(ref, ':') - 1) ELSE '' END")


def _quellen_je_projekt(app: Any, projekt_ids: list[str]) -> dict[str, Counter]:
    """Je Projekt: wie viele aktuelle Quellen aus welchem Konto stammen (eine Abfrage, gruppiert)."""
    store = getattr(app.state, "episodes", None)
    if store is None or not projekt_ids:
        return {}
    from .episodes import sql_aktuell
    ergebnis: dict[str, Counter] = {}
    with store._lock:
        for start in range(0, len(projekt_ids), 500):
            stueck = projekt_ids[start:start + 500]
            zeilen = store._conn.execute(
                f"SELECT project_id, quelle, COUNT(*) FROM (SELECT e.project_id AS project_id, ({_QUELLE_SQL}) AS quelle "
                f"FROM (SELECT *, COALESCE(json_extract(document, '$.provenance.source_ref'), '') AS ref FROM episodes) e "
                f"WHERE e.project_id IN ({','.join('?' * len(stueck))}) AND {sql_aktuell('e')}) GROUP BY project_id, quelle",
                stueck).fetchall()
            for projekt, quelle, anzahl in zeilen:
                ergebnis.setdefault(str(projekt), Counter())[str(quelle or "")] += int(anzahl)
    return ergebnis


def _ueberwiegend(settings: Any, je_quelle: Counter | None, zuordnung: dict[str, str]) -> str | None:
    if not je_quelle:
        return None
    je_bereich: Counter = Counter()
    for quelle, anzahl in je_quelle.items():
        bereich = zuordnung.get(quelle)
        if bereich:
            je_bereich[bereich] += anzahl
    if not je_bereich:
        return None
    bereich, anzahl = je_bereich.most_common(1)[0]
    return bereich if anzahl * 2 > sum(je_bereich.values()) else None


def projekte_anreichern(app: Any, projekte: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Setzt `bereich` je Projekt: sein `area`, wenn es einen Bereich nennt, sonst der überwiegende seiner Quellen."""
    settings = app.state.settings
    zuordnung = _zuordnung_mit_mac(settings)
    offen = [p["id"] for p in projekte if isinstance(p, dict) and p.get("id") and not bereich_finden(settings, p.get("area"))]
    try:
        quellen = _quellen_je_projekt(app, offen)
    except Exception:  # noqa: BLE001 - ein Fehler kostet den abgeleiteten Bereich, nie die Projekte
        quellen = {}
    for projekt in projekte:
        if isinstance(projekt, dict):
            projekt["bereich"] = (bereich_finden(settings, projekt.get("area"))
                                  or _ueberwiegend(settings, quellen.get(str(projekt.get("id"))), zuordnung))
    return projekte


def bereich_eines_projekts(app: Any, projekt_id: str | None) -> str | None:
    if not projekt_id:
        return None
    try:
        projekt = app.state.workspace.project(projekt_id).to_dict()
    except Exception:  # noqa: BLE001 - unbekanntes Projekt: kein Bereich
        return None
    return projekte_anreichern(app, [projekt])[0]["bereich"]


def _aufgaben_quelle(aufgabe: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """(Episode, direkte Referenz) aus `provenance.source_ref` einer Aufgabe."""
    ref = str(((aufgabe.get("provenance") or {}).get("source_ref")) or "")
    if ref.startswith("episode:"):
        return ref[len("episode:"):] or None, None
    return None, ref or None


def aufgaben_anreichern(app: Any, aufgaben: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Setzt `bereich` je Aufgabe (`Task.to_dict`): der ihrer Quelle, sonst der ihres Projekts, sonst None."""
    settings = app.state.settings
    eintraege = [a for a in aufgaben if isinstance(a, dict)]
    try:
        aus_episoden = bereiche_von_episoden(app, [e for a in eintraege if (e := _aufgaben_quelle(a)[0])])
    except Exception:  # noqa: BLE001 - ein Fehler kostet den abgeleiteten Bereich, nie die Aufgaben
        aus_episoden = {}
    ohne = {str(a["project_id"]) for a in eintraege if a.get("project_id")}
    projekte: dict[str, str | None] = {}
    if ohne:
        try:
            liste = [p.to_dict() for p in app.state.workspace.projects(include_closed=True) if p.id in ohne]
        except Exception:  # noqa: BLE001
            liste = []
        projekte = {p["id"]: p["bereich"] for p in projekte_anreichern(app, liste)}
    for aufgabe in eintraege:
        episode, direkt = _aufgaben_quelle(aufgabe)
        bereich = aus_episoden.get(episode) if episode else bereich_einer_referenz(settings, direkt)
        aufgabe["bereich"] = bereich or projekte.get(str(aufgabe.get("project_id") or ""))
    return aufgaben


def bereich_einer_aufgabe(app: Any, aufgabe: Any) -> str | None:
    daten = aufgabe.to_dict() if hasattr(aufgabe, "to_dict") else dict(aufgabe)
    return aufgaben_anreichern(app, [daten])[0]["bereich"]


def mail_bereich(settings: Any, konto_id: str | None) -> str | None:
    """Der Bereich einer Mail aus der Kennung ihres Postfachs."""
    return bereich_je_konto(settings).get(str(konto_id or "")) if konto_id else None


__all__ = [
    "ARBEIT", "PRIVAT", "VORGEGEBEN", "Vorschlag", "aufgaben_anreichern", "ausgeblendete_kalender",
    "bereich_einer_aufgabe", "bereich_einer_episode", "bereich_einer_quelle", "bereich_einer_referenz",
    "bereich_eines_projekts", "bereich_eines_termins", "bereich_finden", "bereich_je_konto", "bereich_name",
    "bereiche", "bereiche_von_episoden", "eigene_bereiche", "in_gebrauch", "mail_bereich", "neuer_bereich",
    "projekte_anreichern", "quelle_von_referenz", "setze_ausgeblendet", "setze_bereich", "termine_anreichern",
    "vorschlag_kalender", "vorschlag_postfach",
]
