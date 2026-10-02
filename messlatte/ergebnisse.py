"""Was die Stufen einander übergeben. Nur Daten, keine Logik.

Alle Verweise auf Quellen sind **Welt-IDs** (`mainz-003`), nie Episoden-IDs des
Produkts: Die Zuordnung leistet allein die Aufnahme. So kennen Abruf, Antwort
und Bewertung das Produkt nicht mehr, sobald sie ihr Ergebnis abgeben.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AufnahmeErgebnis:
    """Zähler und Zuordnung nach dem Einspielen der Welt."""
    aufgenommen: int = 0
    dupliziert: int = 0
    fehlgeschlagen: int = 0
    # je Quellenart: {'mail': {'aufgenommen': n, ...}}
    je_art: dict = field(default_factory=dict)
    # Welt-ID -> Episoden-ID (Termine: Episode der Art `event`, UID = Welt-ID).
    episoden: dict = field(default_factory=dict)
    # Welt-Quellen, die über den Produktpfad nicht ankamen, mit Grund.
    nicht_angekommen: dict = field(default_factory=dict)
    termine_im_kalender: int = 0
    termine_ausserhalb_fenster: int = 0
    einordnung: str = ''
    # Fehlermeldungen des Produkts während der Aufnahme (Mailfortschritt, Ordnerimport)
    meldungen: tuple = ()
    dauer_s: float = 0.0
    quellen_gesamt: int = 0
    rauschen: int = 0


@dataclass(frozen=True)
class Angebot:
    """Eine Bedeutung, die das Produkt bei einer offenen Frage anbietet."""
    art: str
    label: str
    detail: str = ''
    quellen: tuple = ()


#: Arten, in denen der Kontext eine Quelle kennzeichnet, mit ihrer Anzeige: überholt (E2, Akten), andere Person gleichen
#: Namens und außerhalb des gefragten Zeitraums (`icarus_memory/kennzeichnung.py`). Die Schlüssel sind die Feldnamen
#: der Zeile im Kontext des Modells.
KENNZEICHNUNGEN = {'ueberholt': 'überholt', 'andere_person': 'andere Person', 'ausserhalb_zeitraum': 'außerhalb des Zeitraums'}


@dataclass(frozen=True)
class AbrufErgebnis:
    """Was die produktseitige Suche zu einer Frage liefert, ohne Modell."""
    frage_id: str
    # Wie das Produkt die Frage angeht: bedeutungsfrage, gewaehlte_bedeutung, arbeitsstand,
    # kalender, unbekannt, nur_lokal, fehler
    weg: str = 'fehler'
    status: str = ''
    # Wohin das Produkt die Frage im Gespräch lenken würde: memory_evidence oder chat
    route: str = ''
    # Kandidaten in Rangfolge (Welt-IDs). Rauschen zählt mit, damit Ränge ehrlich sind.
    kandidaten: tuple = ()
    davon_rauschen: int = 0
    angebote: tuple = ()
    termine_kalender: tuple = ()
    kontext_zeichen: int = 0
    # Quellen im Kontext der Auswahl (was ein Modell sähe) und die davon, die der Kontext als überholt kennzeichnet (E2).
    kontext_quellen: int = 0
    gekennzeichnet: tuple = ()
    # Dieselben Quellen nach Art der Kennzeichnung (Schlüssel aus KENNZEICHNUNGEN, Werte Welt-IDs). Eine Quelle mit
    # zwei Kennzeichnungen steht in beiden; `gekennzeichnet` ist ihre Vereinigung.
    gekennzeichnet_nach_art: dict = field(default_factory=dict)
    # Gefundene Quellen, die das Zeichenbudget des Kontexts verdrängte (Welt-IDs, Rangfolge): gefunden, aber nicht gesehen.
    abgeschnitten: tuple = ()
    # Erwartete Belege, die das Arbeitsgedächtnis wegen ihrer Länge gar nicht einordnet (Welt-IDs): weder gefunden noch
    # abgeschnitten, eine eigene Lücke (`MAX_SOURCE_CHARS`).
    zu_lang: tuple = ()
    # Erwartete Belege im Kontext, bei denen keine tragende Textstelle (Pflichtaussage der Frage, die der Volltext der Quelle
    # trägt) zu sehen ist: gesehen, aber ohne das, worauf es ankommt (Welt-IDs).
    ohne_stelle: tuple = ()
    # Gekürzte Quellen im Kontext (Zweistufige Auswahl) und die Zahl der Absätze, die gezeigt, und die, die vorhanden waren.
    gekuerzt: int = 0
    absaetze_gezeigt: int = 0
    absaetze_gesamt: int = 0
    # Bevorzugte Quellen aus den Akten der genannten Sachen und Zählung der Akten (E2), sonst leer.
    akten_zaehlung: dict = field(default_factory=dict)
    # Größe der Anfrage an das Modell der Rolle „antwort“ (Sätze, E3), soweit gestellt.
    satz_zeichen: int = 0
    dauer_s: float = 0.0
    fehler: str = ''
    # Wie das Produkt die Frage verstanden hat (frage.py): `modell` (Rolle „frage“) oder `rueckfall`,
    # bei Rückfall mit Grund (kein Modell, Zeitlimit, ungültige Ausgabe), dazu Absicht und erkannte Sachen.
    verstanden: str = ''
    verstanden_grund: str = ''
    absicht: str = ''
    sachen: tuple = ()


@dataclass(frozen=True)
class AntwortErgebnis:
    """Antwort des echten Antwortpfads (Konversations-API)."""
    frage_id: str
    text: str = ''
    status: str = ''
    # Zitierte Belege als Welt-IDs; None, wenn der Weg keine Belege ausweist (freier Chat).
    belege: tuple | None = None
    # Angebotene Auswahl (Beschriftungen der Antwortknöpfe)
    auswahl: tuple = ()
    dauer_s: float = 0.0
    kalt: bool = False
    fehler: str = ''
    # Die Zeiten, die das Produkt der Antwort mitgibt (Abschnitte in Sekunden, siehe `zeiten.py`); leer ohne Messung.
    zeiten: dict = field(default_factory=dict)
    # Verworfene Sätze der Satzantwort, getrennt nach Tor: die Satzprüfung ohne Modell und das Prüfmodell (zweites Tor).
    verworfen_satzpruefung: int = 0
    verworfen_pruefmodell: int = 0
    # Zustand des zweiten Tors laut Produkt (an, aus, kein_modell); leer ohne Satzantwort.
    pruefung: str = ''
