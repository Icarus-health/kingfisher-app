"""Datenklassen der Welt und der Fragen (Format: FORMAT.md).

Unveränderlich und ohne Logik: Laden und Prüfen steht in `welt.py`, alles
Weitere in den Stufen. So kann jede Stufe ausgetauscht werden, ohne dass die
anderen etwas davon merken.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

KATEGORIEN = (
    'rueckblick', 'mehrdeutigkeit', 'frist', 'vorbereitung', 'profil', 'identitaet',
    'aktualitaet', 'falle', 'paraphrase', 'zeitraum', 'wartet_auf', 'fremde_anweisung', 'inhalt',
)
SCHWEREN = ('kritisch', 'normal')
VERHALTEN = ('antworten', 'rueckfrage', 'nicht_bekannt')
ARTEN = ('mail', 'termin', 'transkript', 'notiz')
ORDNER = ('INBOX', 'Sent')
#: Arten der Befunde des Lint (wie `icarus_memory.lint.ARTEN`; ein Test hält beide gleich).
LINT_ARTEN = ('widerspruch', 'aussage_gegen_quelle', 'veralteter_satz', 'waise', 'querverweis')
#: Bereich eines Szenarios: `privat` hält die Wörter des Szenarios aus dem Rauschen heraus (M4, docs/49).
BEREICHE = ('beruf', 'privat')
#: Kreise und private Akten-Arten (wie `icarus_memory.kreis.KREISE`, `icarus_memory.akten_arten.ARTEN`; ein Test hält
#: beide gleich).
KREISE = ('innerer_kreis', 'kollegen', 'kontakte')
AKTEN_ARTEN = ('haushalt', 'familie', 'gesundheit', 'vertraege')
FRIST_ARTEN = ('kuendigung', 'zahlung')


@dataclass(frozen=True)
class Adresse:
    name: str
    adresse: str


@dataclass(frozen=True)
class Quelle:
    """Gemeinsame Felder jeder Quelle. `zeit` liegt immer vor dem Stichtag."""
    id: str
    zeit: datetime
    szenario: str
    art: str = field(init=False, default='')
    # Projekt des Arbeitsbereichs, dem der Nutzer die Quelle zugeordnet hat (ID aus `projekte` eines Szenarios).
    projekt: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class Anhang:
    """Ein PDF-Anhang einer Mail: Text je Seite, oder `gescannt` (Seiten ohne Textebene). Die Datei entsteht beim
    Einspielen (`pdf.py`); ihre Welt-ID ist `<Mail-ID>#anhang-<n>` (n ab 1, in der Reihenfolge der Mail)."""
    datei: str
    seiten: tuple[tuple[str, ...], ...] = ()
    gescannt: int = 0
    """Anzahl gescannter Seiten (nur ein Bild, kein Text)."""


@dataclass(frozen=True)
class Mail(Quelle):
    von: Adresse = Adresse('', '')
    an: tuple[Adresse, ...] = ()
    betreff: str = ''
    text: str = ''
    cc: tuple[Adresse, ...] = ()
    ordner: str = 'INBOX'
    antwort_auf: str | None = None
    anhaenge: tuple[Anhang, ...] = ()
    art: str = field(init=False, default='mail')


@dataclass(frozen=True)
class Termin(Quelle):
    """`zeit` ist der Zeitpunkt der Anlage; der Termin selbst beginnt bei `beginn`."""
    beginn: datetime = None  # type: ignore[assignment]
    ende: datetime = None  # type: ignore[assignment]
    titel: str = ''
    ort: str = ''
    teilnehmer: tuple[Adresse, ...] = ()
    notiz: str = ''
    art: str = field(init=False, default='termin')


@dataclass(frozen=True)
class Transkript(Quelle):
    titel: str = ''
    text: str = ''
    teilnehmer: tuple[str, ...] = ()
    art: str = field(init=False, default='transkript')


@dataclass(frozen=True)
class Notiz(Quelle):
    titel: str = ''
    text: str = ''
    art: str = field(init=False, default='notiz')


@dataclass(frozen=True)
class Erwartet:
    verhalten: str
    # Jede Gruppe muss vorkommen, je Gruppe genügt eine Schreibweise.
    aussagen: tuple[tuple[str, ...], ...] = ()
    # Bei `rueckfrage`: jede Gruppe ist eine Bedeutung, die angeboten werden soll.
    bedeutungen: tuple[tuple[str, ...], ...] = ()
    belege: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verboten:
    aussagen: tuple[str, ...] = ()
    belege: tuple[str, ...] = ()


@dataclass(frozen=True)
class Skript:
    """Sätze für die Skriptmodelle der Messlatte (`skript.py`): Mechanik messen, ohne echtes Modell.

    `auswahl` sind Wörter, an denen das Skript die Quellen wählt und die Belege seiner Sätze erkennt; `richtig` ist ein
    Satz, den die Quellen tragen, `falsch` einer, der dieselben Wörter benutzt und das Falsche sagt (er enthält eine
    verbotene Aussage der Frage).
    """
    auswahl: tuple[str, ...]
    richtig: str
    falsch: str


@dataclass(frozen=True)
class Frage:
    id: str
    frage: str
    kategorie: str
    schwere: str
    erwartet: Erwartet
    verboten: Verboten = Verboten()
    notiz: str = ''
    szenario: str = ''
    # Aus welcher Welt die Frage stammt („welt“, „holdout“, „lokal“ …): So bleibt
    # eine gesperrte Sammlung im Bericht getrennt ausgewiesen.
    herkunft: str = 'welt'
    skript: Skript | None = None


@dataclass(frozen=True)
class ArbeitsProjekt:
    """Ein Projekt, das der Nutzer im Arbeitsbereich angelegt hat (anders als `wahrheit.projekte` wird es eingespielt)."""
    id: str
    name: str


@dataclass(frozen=True)
class Angenommen:
    """Eine Aussage, die der Nutzer angenommen hat: ein Wissenskandidat mit Beleg, den ein Mensch bestätigt hat."""
    id: str
    beleg: str
    zitat: str
    subjekt: str
    praedikat: str
    wert: str
    aussage: str


@dataclass(frozen=True)
class LintErwartung:
    """Ein Befund, den der Lint in dieser Welt finden soll. Jeder andere Befund ist ein Fehlalarm."""
    art: str
    quellen: tuple[str, ...]
    unterart: str = ''
    notiz: str = ''


@dataclass(frozen=True)
class KreisErwartung:
    """Welchen Kreis Kingfisher für die Person mit dieser Adresse vorschlagen soll, und was die Begründung nennt."""
    adresse: str
    kreis: str
    merkmale: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtErwartung:
    """Welche private Art Kingfisher für die Akte der Organisation hinter dieser Adresse vorschlagen soll."""
    adresse: str
    art: str


@dataclass(frozen=True)
class FristErwartung:
    """Eine Kündigungs- oder Zahlungsfrist, die Kingfisher aus dieser Quelle vorschlagen soll (Datum ISO)."""
    quelle: str
    art: str
    datum: str
    betrag: str = ''


@dataclass(frozen=True)
class GeburtstagErwartung:
    """Welchen Geburtstag (`MM-TT`) Kingfisher für die Person mit dieser Adresse vorschlagen soll."""
    adresse: str
    datum: str


@dataclass(frozen=True)
class WiederkehrErwartung:
    """Etwas Wiederkehrendes, das aus dieser Quelle vorgeschlagen werden soll; `enthaelt` steht in der Aussage."""
    quelle: str
    enthaelt: tuple[str, ...]


@dataclass(frozen=True)
class Szenario:
    id: str
    titel: str
    beschreibung: str
    quellen: tuple[Quelle, ...]
    fragen: tuple[Frage, ...]
    projekte: tuple[ArbeitsProjekt, ...] = ()
    angenommen: tuple[Angenommen, ...] = ()
    lint: tuple[LintErwartung, ...] = ()
    bereich: str = 'beruf'
    kreise: tuple[KreisErwartung, ...] = ()
    akten_arten: tuple[ArtErwartung, ...] = ()
    fristen: tuple[FristErwartung, ...] = ()
    keine_fristen: tuple[str, ...] = ()
    """Quellen, aus denen keine Frist vorgeschlagen werden darf (Erledigtes, Abbuchung, Guthaben)."""
    geburtstage: tuple[GeburtstagErwartung, ...] = ()
    keine_geburtstage: tuple[str, ...] = ()
    """Adressen, für die nie ein Geburtstag vorgeschlagen werden darf (Kollegen, Kontakte)."""
    wiederkehrend: tuple[WiederkehrErwartung, ...] = ()
    keine_wiederkehrend: tuple[str, ...] = ()
    """Quellen, aus denen nichts Wiederkehrendes kommen darf."""
    briefing_geburtstag: str = ''
    """Die Zeile, die das Briefing am Stichtag zeigen soll, wenn die erwarteten Geburtstage des inneren Kreises
    angenommen und die Kreise bestätigt sind (Probe nach der Messung)."""


@dataclass(frozen=True)
class Nutzer:
    name: str
    adressen: tuple[str, ...]
    wohnort: str = ''


@dataclass(frozen=True)
class Person:
    id: str
    namen: tuple[str, ...]
    adressen: tuple[str, ...] = ()
    beschreibung: str = ''


@dataclass(frozen=True)
class Projekt:
    id: str
    namen: tuple[str, ...]
    beschreibung: str = ''


@dataclass(frozen=True)
class Welt:
    """Eine geladene Weltverzeichnis-Einheit (Standardwelt oder Holdout)."""
    name: str
    pfad: str
    version: int
    stichtag: datetime
    zeitzone: str
    nutzer: Nutzer
    personen: tuple[Person, ...]
    projekte: tuple[Projekt, ...]
    szenarien: tuple[Szenario, ...]
    # Nicht fatale Auffälligkeiten der Prüfung (siehe welt.py).
    hinweise: tuple[str, ...] = ()

    @property
    def quellen(self) -> tuple[Quelle, ...]:
        return tuple(q for s in self.szenarien for q in s.quellen)

    @property
    def fragen(self) -> tuple[Frage, ...]:
        return tuple(f for s in self.szenarien for f in s.fragen)

    @property
    def arbeitsprojekte(self) -> tuple[ArbeitsProjekt, ...]:
        return tuple(p for s in self.szenarien for p in s.projekte)

    @property
    def angenommen(self) -> tuple[Angenommen, ...]:
        return tuple(a for s in self.szenarien for a in s.angenommen)

    @property
    def lint_erwartungen(self) -> tuple[LintErwartung, ...]:
        return tuple(e for s in self.szenarien for e in s.lint)

    @property
    def kreis_erwartungen(self) -> tuple[KreisErwartung, ...]:
        return tuple(e for s in self.szenarien for e in s.kreise)

    @property
    def art_erwartungen(self) -> tuple[ArtErwartung, ...]:
        return tuple(e for s in self.szenarien for e in s.akten_arten)

    @property
    def frist_erwartungen(self) -> tuple[FristErwartung, ...]:
        return tuple(e for s in self.szenarien for e in s.fristen)

    @property
    def keine_fristen(self) -> tuple[str, ...]:
        return tuple(q for s in self.szenarien for q in s.keine_fristen)

    @property
    def geburtstag_erwartungen(self) -> tuple[GeburtstagErwartung, ...]:
        return tuple(e for s in self.szenarien for e in s.geburtstage)

    @property
    def keine_geburtstage(self) -> tuple[str, ...]:
        return tuple(a for s in self.szenarien for a in s.keine_geburtstage)

    @property
    def wiederkehr_erwartungen(self) -> tuple[WiederkehrErwartung, ...]:
        return tuple(e for s in self.szenarien for e in s.wiederkehrend)

    @property
    def keine_wiederkehrend(self) -> tuple[str, ...]:
        return tuple(q for s in self.szenarien for q in s.keine_wiederkehrend)

    @property
    def briefing_geburtstag(self) -> tuple[str, ...]:
        return tuple(s.briefing_geburtstag for s in self.szenarien if s.briefing_geburtstag)

    @property
    def private_szenarien(self) -> frozenset[str]:
        return frozenset(s.id for s in self.szenarien if s.bereich == 'privat')
