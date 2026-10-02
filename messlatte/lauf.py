"""Ein Lauf: Welt laden, einspielen, Abruf messen, Antwort messen, bewerten.

Verbindet die Stufen und kennt sonst nichts von ihnen: jede Stufe bekommt Daten
und gibt Daten zurück (`ergebnisse.py`). Wer eine Stufe austauscht, ändert nur
das Modul der Stufe.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import abruf, antwort, aufnahme, bewertung, handlungen, lange, privat, rauschen
from .darstellung import git_stand
from .daten import Frage, Welt
from .ergebnisse import AbrufErgebnis, AntwortErgebnis, AufnahmeErgebnis
from .instanz import instanz_starten
from .modell import ModellWahl, baue_anbieter, lese_modell
from .welt import lade_welten

@dataclass(frozen=True)
class Optionen:
    welten: tuple = ()
    modell: str = 'keins'
    modell_hintergrund: str = ''  # Modell der Rolle „hintergrund“ (Einordnung); leer = wie --modell
    modell_frage: str = ''  # Modell der Rolle „frage“ (Frage verstehen); leer = Rückfall, wie im Produkt ohne Zuweisung
    modell_pruefung: str = ''  # Modell der Rolle „pruefung“ (zweites Tor der Satzprüfung); leer = kein Prüfmodell, wie im Produkt
    rauschen: int = 0
    seed: int = 1
    nur: str | None = None
    einordnung: str = 'auto'  # auto | konstant | regel (Regel-Einordnung der Stufe Akten für die Weltquellen, Rauschen konstant)
    ohne_akten: bool = False  # Versuch: Suche ohne die Akten (Stand vor E2), zum Vergleich
    plaetze: int = 0  # Versuch: so viele Abschnitte im Kontext der Auswahl (0 = Vorgabe des Produkts)
    kontext_zeichen: int = 0  # Versuch: Zeichenbudget des Kontexts (0 = Vorgabe)
    wortteile_jahre: int = 0  # Einstellung des Suchindex: Wortteile nur für die letzten N Jahre (0 = alle, Vorgabe)
    lange_quellen: bool = False  # Mails und Transkripte in der Länge des Alltags (`lange.py`), Pflichtaussagen unverändert
    lange_mail: int = lange.MAIL_ZEICHEN
    lange_transkript: int = lange.TRANSKRIPT_ZEICHEN
    ausgabe: Path | None = None


@dataclass(frozen=True)
class FrageErgebnis:
    frage: Frage
    abruf: AbrufErgebnis | None = None
    abruf_bewertung: bewertung.AbrufBewertung | None = None
    antwort: AntwortErgebnis | None = None
    antwort_bewertung: bewertung.AntwortBewertung | None = None


@dataclass(frozen=True)
class LaufErgebnis:
    kopf: dict
    aufnahme: AufnahmeErgebnis
    fragen: tuple
    antwort_gemessen: bool
    antwort_grund: str
    hinweise: tuple = ()
    privat: object = None
    """Stufe Privat (`privat.PrivatMessung`), wenn die Welt Kreise, Akten-Arten oder Fristen erwartet; sonst None."""

    @property
    def antwort_auswertung(self) -> bewertung.Auswertung | None:
        if not self.antwort_gemessen:
            return None
        return bewertung.aggregiere((f.frage, f.antwort_bewertung) for f in self.fragen)

    @property
    def abruf_gesamt(self) -> bewertung.AbrufZaehler:
        return bewertung.zaehle_abruf(f.abruf_bewertung for f in self.fragen)


def kopf(optionen: Optionen, welten: list[Welt], modell: ModellWahl, anzahl_rauschen: int, dauer_s: float,
         suchindex: dict | None = None) -> dict:
    return {
        'suchindex': suchindex or {},
        'commit': git_stand(), 'modell': modell.bezeichnung, 'modell_hintergrund': optionen.modell_hintergrund or modell.bezeichnung,
        'modell_frage': optionen.modell_frage or 'keins (Rückfall)',
        'modell_pruefung': optionen.modell_pruefung or 'keins (zweites Tor aus)',
        'datum': datetime.now().astimezone().isoformat(timespec='seconds'),
        'stichtag': welten[0].stichtag.isoformat(), 'zeitzone': welten[0].zeitzone,
        'welten': [{'name': w.name, 'version': w.version, 'szenarien': len(w.szenarien), 'quellen': len(w.quellen),
                    'fragen': len(w.fragen)} for w in welten],
        'rauschen': {'anzahl': anzahl_rauschen, 'seed': optionen.seed},
        'nur_kategorie': optionen.nur, 'dauer_s': round(dauer_s, 1),
        'lange_quellen': ({'mail': optionen.lange_mail, 'transkript': optionen.lange_transkript}
                          if optionen.lange_quellen else None),
    }


@contextmanager
def _versuch(optionen: Optionen):
    """Die Versuchsgrößen (Plätze, Kontextbudget) gelten nur für die Dauer einer Frage und werden danach zurückgesetzt."""
    from icarus_memory import akten_kontext, working_memory_answers as wma
    vorher = (wma.MAX_REFS, wma.MAX_CONTEXT, akten_kontext.AKTIV)
    akten_kontext.AKTIV = not optionen.ohne_akten
    if optionen.plaetze:
        wma.MAX_REFS = optionen.plaetze
    if optionen.kontext_zeichen:
        wma.MAX_CONTEXT = optionen.kontext_zeichen
    try:
        yield
    finally:
        wma.MAX_REFS, wma.MAX_CONTEXT, akten_kontext.AKTIV = vorher


def quellen_des_laufs(optionen: Optionen, welten: list[Welt]) -> tuple[list, tuple]:
    """Die Quellen der Welten und das Rauschen; mit `lange_quellen` beide in der Länge des Alltags (`lange.py`)."""
    quellen = [q for w in welten for q in w.quellen]
    lauter = rauschen.erzeuge(optionen.rauschen, welten, optionen.seed)
    if optionen.lange_quellen:
        # Weltquellen und Rauschen gleich: jede Mail auf `lange_mail`, jedes Transkript auf `lange_transkript` Zeichen.
        quellen = list(lange.aufblasen(quellen, welten, optionen.seed, mail=optionen.lange_mail,
                                       transkript=optionen.lange_transkript))
        lauter = lange.aufblasen(lauter, welten, optionen.seed, mail=optionen.lange_mail,
                                 transkript=optionen.lange_transkript)
    return quellen, lauter


def durchfuehren(optionen: Optionen, *, melden: Callable[[str], None] = lambda text: None,
                 anbieter_bauen: Callable[..., object] = baue_anbieter) -> LaufErgebnis:
    """Der ganze Lauf. `melden` bekommt Fortschrittszeilen (die CLI gibt sie aus).

    `anbieter_bauen` setzt die Modellerzeugung aus `--modell` ab (Tests reichen ein Skriptmodell hinein).
    """
    start = time.perf_counter()
    welten = lade_welten(list(optionen.welten))
    alle_fragen = [f for w in welten for f in w.fragen]

    def bauen(spec_oder_wahl):
        # Das Skriptmodell braucht die Fragen der Welt (ihre Skripte); jedes andere Modell nicht.
        wahl_ = spec_oder_wahl if isinstance(spec_oder_wahl, ModellWahl) else lese_modell(spec_oder_wahl)
        return anbieter_bauen(wahl_, alle_fragen) if wahl_.art == 'skript' else anbieter_bauen(wahl_)

    wahl = lese_modell(optionen.modell)
    anbieter = bauen(wahl)
    fragen = [f for f in alle_fragen if optionen.nur in (None, f.kategorie)]
    if optionen.nur and not fragen and optionen.nur != 'privat':
        raise ValueError(f'Keine Frage der Kategorie „{optionen.nur}“.')
    quellen, lauter = quellen_des_laufs(optionen, welten)
    melden(f'{len(quellen)} Quellen, {len(lauter)} Rauschen, {len(fragen)} Fragen; Modell: {wahl.bezeichnung}')
    # Ein lokales Modell ordnet die Quellen der Welt selbst ein (wie im Betrieb); sonst die konstante Einordnung.
    hintergrund = bauen(optionen.modell_hintergrund) if optionen.modell_hintergrund else anbieter
    einordnung_mit_modell = (hintergrund if hintergrund is not None and getattr(hintergrund, 'is_local', False)
                             and optionen.einordnung == 'auto' else None)
    if optionen.einordnung == 'regel':
        # Ohne Modell haben die Akten keine Arten (Änderung, Zusage …) und damit nichts Überholtes zu berichten.
        from .akten import RegelEinordnung
        einordnung_mit_modell = RegelEinordnung()
    # Rolle „frage“: nur mit ausdrücklicher Wahl. Wie im Produkt versteht sonst der deterministische Rückfall
    # die Frage, auch wenn ein Modell für die Antworten läuft.
    frage_anbieter = bauen(optionen.modell_frage) if optionen.modell_frage else None
    # Rolle „pruefung“ (zweites Tor): nur mit ausdrücklicher Wahl, wie im Produkt ohne Zuweisung.
    pruef_anbieter = bauen(optionen.modell_pruefung) if optionen.modell_pruefung else None
    with instanz_starten(stichtag=welten[0].stichtag, zeitzone=welten[0].zeitzone, provider=anbieter,
                         eigene=tuple(welten[0].nutzer.adressen), frage_provider=frage_anbieter,
                         pruef_provider=pruef_anbieter, wortteile_jahre=optionen.wortteile_jahre) as instanz:
        aufgenommen = aufnahme.aufnehmen(instanz, [*quellen, *lauter], welten[0].stichtag, modell=einordnung_mit_modell)
        # Was der Nutzer der Welt selbst getan hat (Projekte, Zuordnungen, angenommene Aussagen), über die Routen der Oberfläche.
        handlungen.ausfuehren(instanz, welten, aufgenommen.episoden)
        # Die Akten sind Teil der Suche (E2): Bezüge vollständig, damit der Lauf nicht vom Hintergrundfaden abhängt.
        from icarus_memory.akten_routes import nachfuehren
        nachfuehren(instanz.app, warten=True)
        melden(f'aufgenommen: {aufgenommen.aufgenommen} Episoden, {aufgenommen.termine_im_kalender} Termine im Kalender, '
               f'{aufgenommen.fehlgeschlagen} fehlgeschlagen ({aufgenommen.dauer_s} s)')
        rueck = {episode: welt for welt, episode in aufgenommen.episoden.items()}
        # Volltexte der erwarteten Belege: für „zu lang“ und „ohne tragende Stelle“ (nur Weltquellen, kein Rauschen).
        gebraucht = {b for f in fragen for b in f.erwartet.belege}
        texte = {q.id: abruf.quellentext(q) for q in quellen if q.id in gebraucht}
        ergebnisse: list[FrageErgebnis] = []
        antwort_gemessen = anbieter is not None
        for nummer, frage in enumerate(fragen, 1):
            with _versuch(optionen):
                gesucht = abruf.abrufen(instanz, frage, rueck, texte)
            with _versuch(optionen):
                gegeben = antwort.antworten(instanz, frage, rueck, kalt=nummer == 1) if antwort_gemessen else None
            ergebnisse.append(FrageErgebnis(
                frage, gesucht, bewertung.bewerte_abruf(frage, gesucht), gegeben,
                bewertung.bewerte_antwort(frage, gegeben) if gegeben else None))
            melden(f'{nummer}/{len(fragen)} {frage.id}')
        # Stufe Privat (M4) nach den Fragen: Ihr Anstoß legt Aufgabenvorschläge an, die keine Frage sehen soll.
        privat_messung = None
        if optionen.nur in (None, 'privat') and any(
                w.kreis_erwartungen or w.art_erwartungen or w.frist_erwartungen or w.geburtstag_erwartungen
                or w.wiederkehr_erwartungen for w in welten):
            privat_messung = privat.messen(instanz, welten, aufgenommen)
            melden(f'privat: Kreise {privat_messung.kreise_richtig} von {len(privat_messung.kreise)}, '
                   f'falsche innere {len(privat_messung.falsche_innere)}, Fristen {privat_messung.fristen_gefunden} '
                   f'von {len(privat_messung.fristen)}, Geburtstage {privat_messung.geburtstage_gefunden} von '
                   f'{len(privat_messung.geburtstage)}, Wiederkehrendes {privat_messung.wiederkehrend_gefunden} von '
                   f'{len(privat_messung.wiederkehrend)}')
        suchindex = instanz.episodes.suchindex_stand()
    grund = ('' if antwort_gemessen else
             'kein Modell angegeben (--modell); die Stufe „Antwort“ wurde übersprungen')
    hinweise = tuple(h for w in welten for h in w.hinweise)
    return LaufErgebnis(kopf(optionen, welten, wahl, len(lauter), time.perf_counter() - start, suchindex), aufgenommen,
                        tuple(ergebnisse), antwort_gemessen, grund, hinweise, privat_messung)
