"""Welt laden und streng gegen FORMAT.md prüfen.

Die Prüfung sammelt **alle** Fehler, statt beim ersten aufzuhören, und nennt je
Fehler Datei und ID. Eine Welt, die ein Autor schreibt, hat selten nur einen
Fehler; wer sie beim fünften Lauf erst vollständig kennt, hat Zeit verloren.

Was hier geprüft wird: eindeutige IDs mit Szenario-Präfix, Beleg-IDs, die es
gibt, Zeiten vor dem Stichtag (außer Terminbeginn), ausschließlich
`.example`-Domains, erlaubte Kategorien und Verhalten, Sent-Mails vom Nutzer,
unbekannte Felder. Was nur auffällt, aber nichts kaputt macht, landet in
`Welt.hinweise`.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .daten import (
    AKTEN_ARTEN, ARTEN, BEREICHE, FRIST_ARTEN, KATEGORIEN, KREISE, LINT_ARTEN, ORDNER, SCHWEREN, VERHALTEN, Adresse,
    Anhang, Angenommen, ArbeitsProjekt, ArtErwartung, Erwartet, Frage, FristErwartung, GeburtstagErwartung, KreisErwartung, LintErwartung, Mail, Nutzer,
    Notiz, Person, Projekt, Quelle, Skript, Szenario, Termin, Transkript, Verboten, Welt, WiederkehrErwartung,
)

_ADRESSE = re.compile(r'[\w.+-]+@((?:[\w-]+\.)+[A-Za-z]{2,})')
_LINK = re.compile(r'https?://([^/\s:?#]+)', re.I)


class WeltFehler(Exception):
    """Alle gefundenen Fehler einer Welt, je Zeile mit Datei und ID."""

    def __init__(self, meldungen: list[str]):
        self.meldungen = list(meldungen)
        super().__init__('Die Welt ist ungültig:\n' + '\n'.join('  - ' + m for m in self.meldungen))


class _Sammler:
    """Sammelt Fehler und Hinweise mit ihrem Ort."""

    def __init__(self) -> None:
        self.fehler: list[str] = []
        self.hinweise: list[str] = []

    def f(self, datei: str, kennung: str, text: str) -> None:
        self.fehler.append(f'{datei}' + (f' [{kennung}]' if kennung else '') + f': {text}')

    def h(self, datei: str, kennung: str, text: str) -> None:
        self.hinweise.append(f'{datei}' + (f' [{kennung}]' if kennung else '') + f': {text}')


def _zeit(wert: Any) -> datetime | None:
    """ISO 8601 mit Zeitzone, sonst None."""
    if not isinstance(wert, str):
        return None
    try:
        moment = datetime.fromisoformat(wert.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None and moment.utcoffset() is not None else None


def _text(wert: Any) -> bool:
    return isinstance(wert, str) and bool(wert.strip())


def _felder(s: _Sammler, datei: str, kennung: str, objekt: Any, pflicht: set[str],
            optional: set[str] = frozenset()) -> bool:
    """Prüft Objektform, Pflichtfelder und unbekannte Felder. True bei Erfolg."""
    if not isinstance(objekt, dict):
        s.f(datei, kennung, 'Erwartet ein Objekt (geschweifte Klammern).')
        return False
    ok = True
    for name in sorted(pflicht - objekt.keys()):
        s.f(datei, kennung, f'Pflichtfeld „{name}“ fehlt.')
        ok = False
    for name in sorted(objekt.keys() - pflicht - optional):
        s.f(datei, kennung, f'Unbekanntes Feld „{name}“ (erlaubt: {", ".join(sorted(pflicht | optional))}).')
        ok = False
    return ok


def _text_liste(s: _Sammler, datei: str, kennung: str, wert: Any, feld: str, *, leer_ok: bool = True) -> tuple[str, ...]:
    if not isinstance(wert, list) or not all(_text(x) for x in wert):
        s.f(datei, kennung, f'„{feld}“ muss eine Liste nichtleerer Texte sein.')
        return ()
    if not wert and not leer_ok:
        s.f(datei, kennung, f'„{feld}“ darf nicht leer sein.')
    return tuple(wert)


def _gruppen(s: _Sammler, datei: str, kennung: str, wert: Any, feld: str) -> tuple[tuple[str, ...], ...]:
    """Liste von Alternativgruppen: [["12. Oktober", "12.10."], ["Becker"]]."""
    if not isinstance(wert, list):
        s.f(datei, kennung, f'„{feld}“ muss eine Liste von Gruppen sein, etwa [["a", "b"], ["c"]].')
        return ()
    ergebnis = []
    for gruppe in wert:
        if not isinstance(gruppe, list) or not gruppe or not all(_text(x) for x in gruppe):
            s.f(datei, kennung, f'„{feld}“: Jede Gruppe muss eine nichtleere Liste nichtleerer Texte sein.')
            continue
        ergebnis.append(tuple(gruppe))
    return tuple(ergebnis)


def _domains_pruefen(s: _Sammler, datei: str, kennung: str, text: str, wo: str) -> None:
    for treffer in _ADRESSE.finditer(text):
        if not treffer.group(1).lower().endswith('.example'):
            s.f(datei, kennung, f'{wo}: Adresse „{treffer.group(0)}“ liegt nicht auf einer .example-Domain.')
    for treffer in _LINK.finditer(text):
        if not treffer.group(1).lower().endswith('.example'):
            s.f(datei, kennung, f'{wo}: Verweis auf „{treffer.group(1)}“ liegt nicht auf einer .example-Domain.')


def _adresse(s: _Sammler, datei: str, kennung: str, wert: Any, wo: str) -> Adresse | None:
    if not _felder(s, datei, kennung, wert, {'name', 'adresse'}):
        return None
    if not _text(wert['name']) or not _text(wert['adresse']) or '@' not in wert['adresse']:
        s.f(datei, kennung, f'{wo}: „name“ und „adresse“ müssen Texte sein, die Adresse mit @.')
        return None
    _domains_pruefen(s, datei, kennung, wert['adresse'], wo)
    return Adresse(wert['name'].strip(), wert['adresse'].strip())


def _adressen(s: _Sammler, datei: str, kennung: str, wert: Any, wo: str) -> tuple[Adresse, ...]:
    if not isinstance(wert, list):
        s.f(datei, kennung, f'„{wo}“ muss eine Liste von {{name, adresse}} sein.')
        return ()
    return tuple(a for a in (_adresse(s, datei, kennung, x, wo) for x in wert) if a is not None)


def _lese_json(s: _Sammler, pfad: Path) -> Any:
    try:
        return json.loads(pfad.read_text(encoding='utf-8'))
    except FileNotFoundError:
        s.f(str(pfad), '', 'Datei fehlt.')
    except UnicodeDecodeError:
        s.f(str(pfad), '', 'Datei ist kein gültiges UTF-8.')
    except json.JSONDecodeError as exc:
        s.f(str(pfad), '', f'Kein gültiges JSON: {exc.msg} (Zeile {exc.lineno}, Spalte {exc.colno}).')
    return None


# -- Quellen -----------------------------------------------------------------


def _quelle(s: _Sammler, datei: str, szenario: str, roh: Any, stichtag: datetime | None,
            nutzer: Nutzer | None) -> Quelle | None:
    kennung = roh.get('id', '?') if isinstance(roh, dict) and isinstance(roh.get('id'), str) else '?'
    if not isinstance(roh, dict):
        s.f(datei, '', 'Eine Quelle muss ein Objekt sein.')
        return None
    art = roh.get('art')
    if art not in ARTEN:
        s.f(datei, kennung, f'„art“ muss eine von {", ".join(ARTEN)} sein (ist: {art!r}).')
        return None
    pflicht = {'id', 'art', 'zeit'}
    optional: set[str] = {'projekt'}
    if art == 'mail':
        pflicht |= {'von', 'an', 'betreff', 'text'}
        optional |= {'cc', 'ordner', 'antwort_auf', 'anhaenge'}
    elif art == 'termin':
        pflicht |= {'beginn', 'ende', 'titel'}
        optional |= {'ort', 'teilnehmer', 'notiz'}
    elif art == 'transkript':
        pflicht |= {'titel', 'text'}
        optional |= {'teilnehmer'}
    else:
        pflicht |= {'titel', 'text'}
    if not _felder(s, datei, kennung, roh, pflicht, optional):
        return None
    if not _text(roh['id']):
        s.f(datei, '?', '„id“ muss ein nichtleerer Text sein.')
        return None
    if not roh['id'].startswith(szenario + '-'):
        s.f(datei, kennung, f'Die ID muss mit dem Szenario-Präfix „{szenario}-“ beginnen.')
    zeit = _zeit(roh['zeit'])
    if zeit is None:
        s.f(datei, kennung, '„zeit“ muss ISO 8601 mit Zeitzone sein, etwa 2026-03-02T09:15:00+01:00.')
        return None
    if stichtag is not None and zeit >= stichtag:
        s.f(datei, kennung, f'„zeit“ ({roh["zeit"]}) liegt nicht vor dem Stichtag ({stichtag.isoformat()}).')
    projekt = roh.get('projekt')
    if projekt is not None and not _text(projekt):
        s.f(datei, kennung, '„projekt“ muss die ID eines Projekts aus „projekte“ sein.')
        projekt = None
    grund = dict(id=roh['id'], zeit=zeit, szenario=szenario, projekt=projekt)
    texte = [(f'{feld}', roh[feld]) for feld in ('betreff', 'text', 'titel', 'ort', 'notiz') if feld in roh]
    for feld, wert in texte:
        if not isinstance(wert, str):
            s.f(datei, kennung, f'„{feld}“ muss Text sein.')
            return None
        _domains_pruefen(s, datei, kennung, wert, f'„{feld}“')
    if art == 'mail':
        von = _adresse(s, datei, kennung, roh['von'], '„von“')
        an = _adressen(s, datei, kennung, roh['an'], 'an')
        cc = _adressen(s, datei, kennung, roh.get('cc', []), 'cc')
        ordner = roh.get('ordner', 'INBOX')
        if ordner not in ORDNER:
            s.f(datei, kennung, f'„ordner“ muss INBOX oder Sent sein (ist: {ordner!r}).')
            ordner = 'INBOX'
        if not _text(roh['betreff']) or not _text(roh['text']) or not an:
            s.f(datei, kennung, 'Eine Mail braucht Betreff, Text und mindestens einen Empfänger.')
        antwort_auf = roh.get('antwort_auf')
        if antwort_auf is not None and not _text(antwort_auf):
            s.f(datei, kennung, '„antwort_auf“ muss eine Quellen-ID sein.')
            antwort_auf = None
        if von is None:
            return None
        if nutzer is not None:
            eigen = von.adresse.lower() in {a.lower() for a in nutzer.adressen}
            if ordner == 'Sent' and not eigen:
                s.f(datei, kennung, 'Eine Mail im Ordner Sent muss vom Nutzer stammen '
                                    f'(„von“ ist {von.adresse}, Nutzer: {", ".join(nutzer.adressen)}).')
            if eigen and ordner != 'Sent':
                s.f(datei, kennung, 'Eine Mail vom Nutzer gehört in den Ordner Sent (setze "ordner": "Sent").')
        return Mail(**grund, von=von, an=an, betreff=roh['betreff'], text=roh['text'], cc=cc,
                    ordner=ordner, antwort_auf=antwort_auf, anhaenge=_anhaenge(s, datei, kennung, roh.get('anhaenge', [])))
    if art == 'termin':
        beginn, ende = _zeit(roh['beginn']), _zeit(roh['ende'])
        if beginn is None or ende is None:
            s.f(datei, kennung, '„beginn“ und „ende“ müssen ISO 8601 mit Zeitzone sein.')
            return None
        if ende <= beginn:
            s.f(datei, kennung, '„ende“ muss nach „beginn“ liegen.')
        if not _text(roh['titel']):
            s.f(datei, kennung, '„titel“ darf nicht leer sein.')
        teilnehmer = _adressen(s, datei, kennung, roh.get('teilnehmer', []), 'teilnehmer')
        return Termin(**grund, beginn=beginn, ende=ende, titel=roh['titel'], ort=roh.get('ort', ''),
                      teilnehmer=teilnehmer, notiz=roh.get('notiz', ''))
    if not _text(roh['titel']) or not _text(roh['text']):
        s.f(datei, kennung, '„titel“ und „text“ dürfen nicht leer sein.')
        return None
    if art == 'transkript':
        teilnehmer = _text_liste(s, datei, kennung, roh.get('teilnehmer', []), 'teilnehmer')
        zeilen = [z for z in roh['text'].splitlines() if z.strip()]
        if not any(re.match(r'^[^:\n]{1,60}:\s*\S', z) for z in zeilen):
            s.f(datei, kennung, 'Ein Transkript braucht Zeilen der Form „Name: Gesagtes“.')
        return Transkript(**grund, titel=roh['titel'], text=roh['text'], teilnehmer=teilnehmer)
    return Notiz(**grund, titel=roh['titel'], text=roh['text'])


# -- Fragen ------------------------------------------------------------------


def _frage(s: _Sammler, datei: str, szenario: str | None, roh: Any, *, lokal: bool = False) -> Frage | None:
    kennung = roh.get('id', '?') if isinstance(roh, dict) and isinstance(roh.get('id'), str) else '?'
    pflicht = {'id', 'frage', 'erwartet'} | (set() if lokal else {'kategorie', 'schwere'})
    if not _felder(s, datei, kennung, roh, pflicht, {'kategorie', 'schwere', 'verboten', 'notiz', 'skript'}):
        return None
    if not _text(roh['id']) or not _text(roh['frage']):
        s.f(datei, kennung, '„id“ und „frage“ müssen nichtleere Texte sein.')
        return None
    if szenario is not None and not roh['id'].startswith(szenario + '-'):
        s.f(datei, kennung, f'Die ID muss mit dem Szenario-Präfix „{szenario}-“ beginnen.')
    kategorie = roh.get('kategorie', 'eigene')
    if kategorie not in KATEGORIEN and not (lokal and kategorie == 'eigene'):
        s.f(datei, kennung, f'„kategorie“ muss eine von {", ".join(KATEGORIEN)} sein (ist: {kategorie!r}).')
        kategorie = None
    schwere = roh.get('schwere', 'normal')
    if schwere not in SCHWEREN:
        s.f(datei, kennung, f'„schwere“ muss kritisch oder normal sein (ist: {schwere!r}).')
        schwere = None
    erwartet_roh = roh['erwartet']
    if not _felder(s, datei, kennung, erwartet_roh, {'verhalten'}, {'aussagen', 'bedeutungen', 'belege'}):
        return None
    verhalten = erwartet_roh['verhalten']
    if verhalten not in VERHALTEN:
        s.f(datei, kennung, f'„erwartet.verhalten“ muss eine von {", ".join(VERHALTEN)} sein (ist: {verhalten!r}).')
        return None
    aussagen = _gruppen(s, datei, kennung, erwartet_roh.get('aussagen', []), 'erwartet.aussagen')
    bedeutungen = _gruppen(s, datei, kennung, erwartet_roh.get('bedeutungen', []), 'erwartet.bedeutungen')
    belege = _text_liste(s, datei, kennung, erwartet_roh.get('belege', []), 'erwartet.belege')
    if verhalten == 'rueckfrage' and len(bedeutungen) < 2:
        s.f(datei, kennung, 'Bei „rueckfrage“ müssen mindestens zwei Bedeutungsgruppen unter „bedeutungen“ stehen.')
    if verhalten != 'rueckfrage' and bedeutungen:
        s.f(datei, kennung, '„bedeutungen“ gehört nur zu „rueckfrage“.')
    if verhalten == 'nicht_bekannt' and (aussagen or belege):
        s.f(datei, kennung, 'Bei „nicht_bekannt“ dürfen weder Pflichtaussagen noch Belege erwartet werden.')
    verboten_roh = roh.get('verboten', {})
    if not _felder(s, datei, kennung, verboten_roh, set(), {'aussagen', 'belege'}):
        return None
    verboten = Verboten(
        aussagen=_text_liste(s, datei, kennung, verboten_roh.get('aussagen', []), 'verboten.aussagen'),
        belege=_text_liste(s, datei, kennung, verboten_roh.get('belege', []), 'verboten.belege'))
    # Im Modus „lokal“ genügt eine verbotene Aussage: „sag das nicht wieder“ ist messbar (Fälle aus dem Rückkanal).
    if verhalten == 'antworten' and not (aussagen or (verboten.aussagen if lokal else belege)):
        s.f(datei, kennung, 'Eine „antworten“-Frage braucht Pflichtaussagen'
                            + (' oder verbotene Aussagen' if lokal else ' oder Belege') + ', sonst ist sie nicht messbar.')
    if set(belege) & set(verboten.belege):
        s.f(datei, kennung, 'Ein Beleg steht zugleich unter „erwartet.belege“ und „verboten.belege“.')
    notiz = roh.get('notiz', '')
    if not isinstance(notiz, str):
        s.f(datei, kennung, '„notiz“ muss Text sein.')
        notiz = ''
    skript = _skript(s, datei, kennung, roh['skript'], verboten) if 'skript' in roh else None
    if schwere is None or kategorie is None:
        return None
    return Frage(id=roh['id'], frage=roh['frage'].strip(), kategorie=kategorie, schwere=schwere,
                 erwartet=Erwartet(verhalten, aussagen, bedeutungen, belege), verboten=verboten,
                 notiz=notiz, szenario=szenario or '', skript=skript)


def _skript(s: _Sammler, datei: str, kennung: str, roh: Any, verboten: Verboten) -> Skript | None:
    """Die Sätze für die Skriptmodelle: `falsch` muss eine verbotene Aussage enthalten, `richtig` keine.

    Sonst wäre ein durchgelassener falscher Satz für die Bewertung unsichtbar, oder ein richtiger würde als falsch
    gezählt.
    """
    if not _felder(s, datei, kennung, roh, {'auswahl', 'richtig', 'falsch'}, set()):
        return None
    auswahl = _text_liste(s, datei, kennung, roh['auswahl'], 'skript.auswahl')
    if not auswahl or not _text(roh['richtig']) or not _text(roh['falsch']):
        s.f(datei, kennung, '„skript“ braucht Wörter unter „auswahl“ und die Sätze „richtig“ und „falsch“.')
        return None
    from .bewertung import gefundene_verbotene
    if not gefundene_verbotene(roh['falsch'], verboten.aussagen):
        s.f(datei, kennung, '„skript.falsch“ muss eine verbotene Aussage der Frage enthalten.')
    if gefundene_verbotene(roh['richtig'], verboten.aussagen):
        s.f(datei, kennung, '„skript.richtig“ enthält eine verbotene Aussage.')
    return Skript(auswahl, roh['richtig'].strip(), roh['falsch'].strip())


def pruefe_fragen_lokal(daten: Any, datei: str = 'fragen') -> tuple[Frage, ...]:
    """Fragen für den Modus „lokal“: gleiches Format, aber ohne Welt und Belege.

    `belege` dürfen leer sein, `kategorie` und `schwere` fehlen dürfen. Ohne Welt
    lässt sich nur der Antworttext prüfen, deshalb braucht jede „antworten“-Frage
    Pflichtaussagen.
    """
    s = _Sammler()
    liste = daten.get('fragen') if isinstance(daten, dict) else daten
    if not isinstance(liste, list):
        raise WeltFehler([f'{datei}: Erwartet eine Liste von Fragen oder {{"fragen": [...]}}.'])
    fragen, ids = [], set()
    for roh in liste:
        frage = _frage(s, datei, None, roh, lokal=True)
        if frage is None:
            continue
        if frage.id in ids:
            s.f(datei, frage.id, 'Doppelte Frage-ID.')
        ids.add(frage.id)
        fragen.append(Frage(**{**frage.__dict__, 'herkunft': 'lokal'}))
    if s.fehler:
        raise WeltFehler(s.fehler)
    if not fragen:
        raise WeltFehler([f'{datei}: Keine Fragen enthalten.'])
    return tuple(fragen)


# -- Welt --------------------------------------------------------------------


def _wahrheit(s: _Sammler, datei: str, roh: Any) -> tuple[tuple[Person, ...], tuple[Projekt, ...]]:
    if not _felder(s, datei, 'wahrheit', roh, set(), {'personen', 'projekte'}):
        return (), ()
    personen, projekte, ids = [], [], set()
    for eintrag in roh.get('personen', []):
        kennung = eintrag.get('id', '?') if isinstance(eintrag, dict) else '?'
        if not _felder(s, datei, kennung, eintrag, {'id', 'namen'}, {'adressen', 'beschreibung'}):
            continue
        if not _text(eintrag['id']) or eintrag['id'] in ids:
            s.f(datei, kennung, 'Person-ID fehlt oder ist doppelt.')
            continue
        ids.add(eintrag['id'])
        namen = _text_liste(s, datei, kennung, eintrag['namen'], 'namen', leer_ok=False)
        adressen = _text_liste(s, datei, kennung, eintrag.get('adressen', []), 'adressen')
        for adresse in adressen:
            _domains_pruefen(s, datei, kennung, adresse, 'adressen')
        personen.append(Person(eintrag['id'], namen, adressen, str(eintrag.get('beschreibung', ''))))
    for eintrag in roh.get('projekte', []):
        kennung = eintrag.get('id', '?') if isinstance(eintrag, dict) else '?'
        if not _felder(s, datei, kennung, eintrag, {'id', 'namen'}, {'beschreibung'}):
            continue
        if not _text(eintrag['id']) or eintrag['id'] in ids:
            s.f(datei, kennung, 'Projekt-ID fehlt oder ist doppelt (auch gegenüber Personen).')
            continue
        ids.add(eintrag['id'])
        projekte.append(Projekt(eintrag['id'], _text_liste(s, datei, kennung, eintrag['namen'], 'namen', leer_ok=False),
                                str(eintrag.get('beschreibung', ''))))
    return tuple(personen), tuple(projekte)


def _wortlich(quellen: dict[str, Quelle], beleg: str) -> str:
    """Alles, was eine Quelle sagt, als ein Text für die Plausibilitätsprüfung."""
    q = quellen[beleg]
    teile = [getattr(q, feld, '') or '' for feld in ('betreff', 'text', 'titel', 'ort', 'notiz')]
    if isinstance(q, Termin):
        teile.append(q.beginn.strftime('%d.%m.%Y %H:%M'))
    return '\n'.join(teile).casefold()


def lade_welt(pfad: str | Path, name: str | None = None) -> Welt:
    """Lädt und prüft ein Weltverzeichnis. Wirft `WeltFehler` mit allen Fehlern."""
    wurzel = Path(pfad)
    name = name or wurzel.name
    s = _Sammler()
    welt_datei = wurzel / 'welt.json'
    roh = _lese_json(s, welt_datei)
    if roh is None:
        raise WeltFehler(s.fehler)
    datei = 'welt.json'
    if not _felder(s, datei, '', roh, {'version', 'stichtag', 'zeitzone', 'nutzer', 'wahrheit'}):
        raise WeltFehler(s.fehler)
    if roh['version'] != 1 or isinstance(roh['version'], bool):
        s.f(datei, '', f'Nur Format-Version 1 wird unterstützt (ist: {roh["version"]!r}).')
    stichtag = _zeit(roh['stichtag'])
    if stichtag is None:
        s.f(datei, '', '„stichtag“ muss ISO 8601 mit Zeitzone sein.')
    zeitzone = roh['zeitzone']
    try:
        ZoneInfo(zeitzone)
    except (ZoneInfoNotFoundError, ValueError, TypeError, OSError):
        s.f(datei, '', f'„zeitzone“ ist keine bekannte Zeitzone (ist: {zeitzone!r}).')
    nutzer = None
    if _felder(s, datei, 'nutzer', roh['nutzer'], {'name', 'adressen'}, {'wohnort'}):
        eintrag = roh['nutzer']
        adressen = _text_liste(s, datei, 'nutzer', eintrag['adressen'], 'adressen', leer_ok=False)
        for adresse in adressen:
            _domains_pruefen(s, datei, 'nutzer', adresse, 'adressen')
        if _text(eintrag['name']):
            nutzer = Nutzer(eintrag['name'], adressen, str(eintrag.get('wohnort', '')))
        else:
            s.f(datei, 'nutzer', '„name“ darf nicht leer sein.')
    personen, projekte = _wahrheit(s, datei, roh['wahrheit'])

    szenarien: list[Szenario] = []
    quellen_ids: dict[str, str] = {}
    fragen_ids: dict[str, str] = {}
    alle_quellen: dict[str, Quelle] = {}
    ordner = wurzel / 'szenarien'
    dateien = sorted(ordner.glob('*.json')) if ordner.is_dir() else []
    if not dateien:
        s.f('szenarien/', '', 'Keine Szenario-Dateien gefunden (erwartet: szenarien/<id>.json).')
    for datei_pfad in dateien:
        datei = f'szenarien/{datei_pfad.name}'
        inhalt = _lese_json(s, datei_pfad)
        if inhalt is None:
            continue
        if not _felder(s, datei, '', inhalt, {'id', 'titel', 'beschreibung', 'quellen', 'fragen'},
                       {'projekte', 'angenommen', 'lint', 'bereich', 'kreise', 'akten_arten', 'fristen', 'keine_fristen',
                        'geburtstage', 'keine_geburtstage', 'wiederkehrend', 'keine_wiederkehrend',
                        'briefing_geburtstag'}):
            continue
        sid = inhalt['id']
        if not _text(sid) or sid != datei_pfad.stem:
            s.f(datei, str(sid), f'Die Szenario-ID muss dem Dateinamen entsprechen ({datei_pfad.stem!r}).')
            continue
        for feld in ('titel', 'beschreibung'):
            if not _text(inhalt[feld]):
                s.f(datei, sid, f'„{feld}“ darf nicht leer sein.')
        if not isinstance(inhalt['quellen'], list) or not isinstance(inhalt['fragen'], list):
            s.f(datei, sid, '„quellen“ und „fragen“ müssen Listen sein.')
            continue
        quellen: list[Quelle] = []
        for eintrag in inhalt['quellen']:
            quelle = _quelle(s, datei, sid, eintrag, stichtag, nutzer)
            if quelle is None:
                continue
            if quelle.id in quellen_ids:
                s.f(datei, quelle.id, f'Doppelte Quellen-ID (schon in {quellen_ids[quelle.id]}).')
                continue
            quellen_ids[quelle.id] = datei
            alle_quellen[quelle.id] = quelle
            quellen.append(quelle)
        fragen: list[Frage] = []
        for eintrag in inhalt['fragen']:
            frage = _frage(s, datei, sid, eintrag)
            if frage is None:
                continue
            if frage.id in fragen_ids:
                s.f(datei, frage.id, f'Doppelte Frage-ID (schon in {fragen_ids[frage.id]}).')
                continue
            fragen_ids[frage.id] = datei
            fragen.append(Frage(**{**frage.__dict__, 'herkunft': name}))
        szenarien.append(Szenario(sid, str(inhalt['titel']), str(inhalt['beschreibung']),
                                  tuple(quellen), tuple(fragen), *_handlungen(s, datei, sid, inhalt),
                                  *_privat(s, datei, sid, inhalt), *_wiederkehrend(s, datei, sid, inhalt)))

    # Verweise zwischen Quellen und Fragen erst prüfen, wenn alles geladen ist.
    projekt_ids = {p.id for sz in szenarien for p in sz.projekte}
    for szenario in szenarien:
        datei = f'szenarien/{szenario.id}.json'
        _handlungen_pruefen(s, datei, szenario, alle_quellen, projekt_ids)
        for quelle in szenario.quellen:
            if isinstance(quelle, Mail) and quelle.antwort_auf is not None:
                ziel = alle_quellen.get(quelle.antwort_auf)
                if not isinstance(ziel, Mail):
                    s.f(datei, quelle.id, f'„antwort_auf“ verweist auf „{quelle.antwort_auf}“, das keine Mail dieser Welt ist.')
                elif ziel.zeit > quelle.zeit:
                    s.f(datei, quelle.id, f'Die Mail antwortet auf „{ziel.id}“, die erst später gesendet wurde.')
        for frage in szenario.fragen:
            verweise = [('erwartet.belege', frage.erwartet.belege), ('verboten.belege', frage.verboten.belege)]
            for feld, ids in verweise:
                for beleg in ids:
                    if beleg not in alle_quellen:
                        s.f(datei, frage.id, f'{feld}: Quelle „{beleg}“ gibt es nicht.')
            vorhanden = [b for b in frage.erwartet.belege if b in alle_quellen]
            if vorhanden:
                text = '\n'.join(_wortlich(alle_quellen, b) for b in vorhanden)
                for gruppe in frage.erwartet.aussagen:
                    if not any(' '.join(a.split()).casefold() in ' '.join(text.split()) for a in gruppe):
                        s.h(datei, frage.id, f'Pflichtaussage {list(gruppe)} kommt in keinem Beleg wörtlich vor '
                                             '(ein Modell müsste sie umformulieren).')
            if frage.erwartet.verhalten == 'rueckfrage':
                for gruppe in frage.erwartet.bedeutungen:
                    if not any(' '.join(a.split()).casefold() in _alles(alle_quellen) for a in gruppe):
                        s.h(datei, frage.id, f'Bedeutungsgruppe {list(gruppe)} kommt in keiner Quelle vor.')

    if s.fehler:
        raise WeltFehler(s.fehler)
    assert stichtag is not None and nutzer is not None
    return Welt(name=name, pfad=str(wurzel), version=roh['version'], stichtag=stichtag, zeitzone=zeitzone,
                nutzer=nutzer, personen=personen, projekte=projekte, szenarien=tuple(szenarien),
                hinweise=tuple(s.hinweise))


def _handlungen(s: _Sammler, datei: str, sid: str, inhalt: dict) -> tuple[tuple, tuple, tuple]:
    """Was der Nutzer selbst getan hat (Projekte, angenommene Aussagen) und die erwarteten Befunde des Lint."""
    projekte, angenommen, lint = [], [], []
    for roh in _liste(s, datei, sid, inhalt.get('projekte', []), 'projekte'):
        kennung = roh.get('id', '?') if isinstance(roh, dict) else '?'
        if not _felder(s, datei, kennung, roh, {'id', 'name'}) or not (_text(roh['id']) and _text(roh['name'])):
            continue
        if not roh['id'].startswith(sid + '-'):
            s.f(datei, kennung, f'Die Projekt-ID muss mit dem Szenario-Präfix „{sid}-“ beginnen.')
        projekte.append(ArbeitsProjekt(roh['id'], roh['name'].strip()))
    for roh in _liste(s, datei, sid, inhalt.get('angenommen', []), 'angenommen'):
        kennung = roh.get('id', '?') if isinstance(roh, dict) else '?'
        felder = {'id', 'beleg', 'zitat', 'subjekt', 'praedikat', 'wert', 'aussage'}
        if not _felder(s, datei, kennung, roh, felder):
            continue
        if not all(_text(roh[f]) for f in felder):
            s.f(datei, kennung, 'Eine angenommene Aussage braucht nichtleere Texte in allen Feldern.')
            continue
        if not roh['id'].startswith(sid + '-'):
            s.f(datei, kennung, f'Die ID muss mit dem Szenario-Präfix „{sid}-“ beginnen.')
        angenommen.append(Angenommen(**{f: roh[f].strip() for f in felder}))
    for nummer, roh in enumerate(_liste(s, datei, sid, inhalt.get('lint', []), 'lint'), 1):
        kennung = f'lint[{nummer}]'
        if not _felder(s, datei, kennung, roh, {'art', 'quellen'}, {'unterart', 'notiz'}):
            continue
        if roh['art'] not in LINT_ARTEN:
            s.f(datei, kennung, f'„art“ muss eine von {", ".join(LINT_ARTEN)} sein (ist: {roh["art"]!r}).')
            continue
        quellen = _text_liste(s, datei, kennung, roh['quellen'], 'quellen', leer_ok=False)
        lint.append(LintErwartung(roh['art'], quellen, str(roh.get('unterart', '')), str(roh.get('notiz', ''))))
    return tuple(projekte), tuple(angenommen), tuple(lint)


def _liste(s: _Sammler, datei: str, kennung: str, wert: Any, feld: str) -> list:
    if not isinstance(wert, list):
        s.f(datei, kennung, f'„{feld}“ muss eine Liste sein.')
        return []
    return wert


def _handlungen_pruefen(s: _Sammler, datei: str, szenario: Szenario, alle_quellen: dict[str, Quelle],
                        projekt_ids: set[str]) -> None:
    for quelle in szenario.quellen:
        if quelle.projekt is not None and quelle.projekt not in projekt_ids:
            s.f(datei, quelle.id, f'„projekt“ verweist auf „{quelle.projekt}“, das in keinem Szenario unter „projekte“ steht.')
    for aussage in szenario.angenommen:
        if aussage.beleg not in alle_quellen:
            s.f(datei, aussage.id, f'„beleg“: Quelle „{aussage.beleg}“ gibt es nicht.')
        elif ' '.join(aussage.zitat.split()).casefold() not in ' '.join(_wortlich(alle_quellen, aussage.beleg).split()):
            s.f(datei, aussage.id, '„zitat“ steht nicht wörtlich in der Belegquelle.')
        art, _, kennung = aussage.subjekt.partition(':')
        if art not in ('person', 'organisation', 'projekt', 'ort', 'thema') or not kennung:
            s.f(datei, aussage.id, '„subjekt“ muss eine Sache sein, etwa „organisation:druckereiweller“ oder „projekt:<Projekt-ID>“.')
        elif art == 'projekt' and kennung not in projekt_ids:
            s.f(datei, aussage.id, f'„subjekt“ nennt das Projekt „{kennung}“, das unter „projekte“ fehlt.')
    for erwartung in szenario.lint:
        for quelle in erwartung.quellen:
            if quelle not in alle_quellen:
                s.f(datei, 'lint', f'Erwarteter Befund ({erwartung.art}): Quelle „{quelle}“ gibt es nicht.')
    adressen = {a.adresse.casefold() for q in alle_quellen.values() for a in _beteiligte(q)}
    for erwartung in (*szenario.kreise, *szenario.akten_arten):
        if erwartung.adresse.casefold() not in adressen:
            s.f(datei, erwartung.adresse, 'Die Adresse kommt in keiner Quelle der Welt vor.')
    for frist in szenario.fristen:
        quelle = alle_quellen.get(frist.quelle)
        text = quelle.text if isinstance(quelle, Mail) else anhang_text(alle_quellen, frist.quelle)
        if text is None:
            s.f(datei, frist.quelle, 'Eine erwartete Frist braucht eine Mail dieser Welt (oder ihren Anhang) als Quelle.')
        elif frist.betrag and frist.betrag not in text:
            s.f(datei, frist.quelle, f'Der erwartete Betrag „{frist.betrag}“ steht nicht wörtlich in der Quelle.')
    for kennung in szenario.keine_fristen:
        if kennung not in alle_quellen and anhang_text(alle_quellen, kennung) is None:
            s.f(datei, kennung, '„keine_fristen“: Quelle gibt es nicht.')
    for adresse in (*(g.adresse for g in szenario.geburtstage), *szenario.keine_geburtstage):
        if adresse.casefold() not in adressen:
            s.f(datei, adresse, 'Die Adresse kommt in keiner Quelle der Welt vor.')
    for erwartung in szenario.wiederkehrend:
        if erwartung.quelle not in alle_quellen and anhang_text(alle_quellen, erwartung.quelle) is None:
            s.f(datei, erwartung.quelle, '„wiederkehrend“: Quelle gibt es nicht.')
    for kennung in szenario.keine_wiederkehrend:
        if kennung not in alle_quellen and anhang_text(alle_quellen, kennung) is None:
            s.f(datei, kennung, '„keine_wiederkehrend“: Quelle gibt es nicht.')


def _beteiligte(quelle: Quelle) -> tuple[Adresse, ...]:
    if isinstance(quelle, Mail):
        return (quelle.von, *quelle.an, *quelle.cc)
    if isinstance(quelle, Termin):
        return quelle.teilnehmer
    return ()


def _privat(s: _Sammler, datei: str, sid: str, inhalt: dict) -> tuple[str, tuple, tuple, tuple, tuple]:
    """Bereich und die Erwartungen der Stufe Privat (M4): Kreise, private Akten-Arten, Fristen."""
    bereich = inhalt.get('bereich', 'beruf')
    if bereich not in BEREICHE:
        s.f(datei, sid, f'„bereich“ muss einer von {", ".join(BEREICHE)} sein (ist: {bereich!r}).')
        bereich = 'beruf'
    kreise, arten, fristen = [], [], []
    for nummer, roh in enumerate(_liste(s, datei, sid, inhalt.get('kreise', []), 'kreise'), 1):
        kennung = f'kreise[{nummer}]'
        if not _felder(s, datei, kennung, roh, {'adresse', 'kreis'}, {'merkmale', 'notiz'}):
            continue
        if roh['kreis'] not in KREISE:
            s.f(datei, kennung, f'„kreis“ muss einer von {", ".join(KREISE)} sein (ist: {roh["kreis"]!r}).')
            continue
        _domains_pruefen(s, datei, kennung, str(roh['adresse']), 'adresse')
        kreise.append(KreisErwartung(str(roh['adresse']).casefold(), roh['kreis'],
                                     _text_liste(s, datei, kennung, roh.get('merkmale', []), 'merkmale')))
    for nummer, roh in enumerate(_liste(s, datei, sid, inhalt.get('akten_arten', []), 'akten_arten'), 1):
        kennung = f'akten_arten[{nummer}]'
        if not _felder(s, datei, kennung, roh, {'adresse', 'art'}, {'notiz'}):
            continue
        if roh['art'] not in AKTEN_ARTEN:
            s.f(datei, kennung, f'„art“ muss eine von {", ".join(AKTEN_ARTEN)} sein (ist: {roh["art"]!r}).')
            continue
        _domains_pruefen(s, datei, kennung, str(roh['adresse']), 'adresse')
        arten.append(ArtErwartung(str(roh['adresse']).casefold(), roh['art']))
    for nummer, roh in enumerate(_liste(s, datei, sid, inhalt.get('fristen', []), 'fristen'), 1):
        kennung = f'fristen[{nummer}]'
        if not _felder(s, datei, kennung, roh, {'quelle', 'art', 'datum'}, {'betrag', 'notiz'}):
            continue
        if roh['art'] not in FRIST_ARTEN:
            s.f(datei, kennung, f'„art“ muss eine von {", ".join(FRIST_ARTEN)} sein (ist: {roh["art"]!r}).')
            continue
        if not isinstance(roh['datum'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', roh['datum']):
            s.f(datei, kennung, '„datum“ muss ein Kalendertag sein (JJJJ-MM-TT).')
            continue
        fristen.append(FristErwartung(str(roh['quelle']), roh['art'], roh['datum'], str(roh.get('betrag', ''))))
    keine = _text_liste(s, datei, sid, inhalt.get('keine_fristen', []), 'keine_fristen')
    return bereich, tuple(kreise), tuple(arten), tuple(fristen), keine

def _anhaenge(s: _Sammler, datei: str, kennung: str, roh: Any) -> tuple[Anhang, ...]:
    """PDF-Anhänge einer Mail: `{"datei": "Rechnung.pdf", "seiten": [["Zeile", …], …]}` oder `{"datei": …, "gescannt": 1}`."""
    ergebnis = []
    for nummer, eintrag in enumerate(_liste(s, datei, kennung, roh, 'anhaenge'), 1):
        stelle = f'{kennung}#anhang-{nummer}'
        if not _felder(s, datei, stelle, eintrag, {'datei'}, {'seiten', 'gescannt', 'notiz'}):
            continue
        if not _text(eintrag['datei']) or not str(eintrag['datei']).lower().endswith('.pdf'):
            s.f(datei, stelle, '„datei“ muss ein PDF-Dateiname sein.')
            continue
        seiten = eintrag.get('seiten', [])
        if not isinstance(seiten, list) or not all(isinstance(z, list) and all(isinstance(t, str) for t in z) for z in seiten):
            s.f(datei, stelle, '„seiten“ muss eine Liste von Seiten sein, jede eine Liste von Zeilen.')
            continue
        gescannt = eintrag.get('gescannt', 0)
        if not isinstance(gescannt, int) or gescannt < 0 or (not seiten and not gescannt):
            s.f(datei, stelle, 'Ein Anhang braucht Seiten mit Text oder „gescannt“ (Anzahl Seiten).')
            continue
        for zeile in (z for seite in seiten for z in seite):
            _domains_pruefen(s, datei, stelle, zeile, '„seiten“')
        ergebnis.append(Anhang(str(eintrag['datei']), tuple(tuple(z) for z in seiten), gescannt))
    return tuple(ergebnis)


def anhang_text(quellen: dict, welt_id: str) -> str | None:
    """Der Text eines Anhangs (`<Mail-ID>#anhang-<n>`), sonst None."""
    mail_id, _, nummer = welt_id.partition('#anhang-')
    mail = quellen.get(mail_id)
    if not isinstance(mail, Mail) or not nummer.isdigit() or not 1 <= int(nummer) <= len(mail.anhaenge):
        return None
    return '\n'.join(z for seite in mail.anhaenge[int(nummer) - 1].seiten for z in seite)


def _wiederkehrend(s: _Sammler, datei: str, sid: str, inhalt: dict) -> tuple[tuple, tuple, tuple, tuple, str]:
    """Erwartungen an Geburtstage und Wiederkehrendes (M4): was vorgeschlagen werden soll und was nie."""
    geburtstage, wiederkehrend = [], []
    for nummer, roh in enumerate(_liste(s, datei, sid, inhalt.get('geburtstage', []), 'geburtstage'), 1):
        kennung = f'geburtstage[{nummer}]'
        if not _felder(s, datei, kennung, roh, {'adresse', 'datum'}, {'notiz'}):
            continue
        if not isinstance(roh['datum'], str) or not re.fullmatch(r'\d{2}-\d{2}', roh['datum']):
            s.f(datei, kennung, '„datum“ muss Monat und Tag sein (MM-TT).')
            continue
        _domains_pruefen(s, datei, kennung, str(roh['adresse']), 'adresse')
        geburtstage.append(GeburtstagErwartung(str(roh['adresse']).casefold(), roh['datum']))
    keine_geburtstage = tuple(a.casefold() for a in _text_liste(s, datei, sid, inhalt.get('keine_geburtstage', []),
                                                                'keine_geburtstage'))
    for nummer, roh in enumerate(_liste(s, datei, sid, inhalt.get('wiederkehrend', []), 'wiederkehrend'), 1):
        kennung = f'wiederkehrend[{nummer}]'
        if not _felder(s, datei, kennung, roh, {'quelle', 'enthaelt'}, {'notiz'}):
            continue
        wiederkehrend.append(WiederkehrErwartung(str(roh['quelle']),
                                                 _text_liste(s, datei, kennung, roh['enthaelt'], 'enthaelt', leer_ok=False)))
    keine = _text_liste(s, datei, sid, inhalt.get('keine_wiederkehrend', []), 'keine_wiederkehrend')
    briefing = inhalt.get('briefing_geburtstag', '')
    if not isinstance(briefing, str):
        s.f(datei, sid, '„briefing_geburtstag“ muss Text sein.')
        briefing = ''
    return tuple(geburtstage), keine_geburtstage, tuple(wiederkehrend), keine, briefing


def _alles(quellen: dict[str, Quelle]) -> str:
    return ' '.join(' '.join(_wortlich(quellen, k).split()) for k in quellen)


def lade_welten(angaben: list[str]) -> list[Welt]:
    """Mehrere `--welt`-Angaben: `PFAD` oder `NAME=PFAD`. Die erste heißt „welt“.

    Alle Welten gehen in **denselben** Bestand. Dafür müssen Stichtag und
    Zeitzone übereinstimmen und die IDs weltweit eindeutig sein; sonst wäre ein
    Holdout keine Fortsetzung, sondern ein anderes Leben.
    """
    if not angaben:
        raise WeltFehler(['Keine Welt angegeben (--welt PFAD).'])
    welten: list[Welt] = []
    meldungen: list[str] = []
    for nummer, angabe in enumerate(angaben):
        name, _, pfad = angabe.partition('=') if '=' in angabe else ('', '', angabe)
        name = name or ('welt' if nummer == 0 else Path(pfad).name or f'welt{nummer + 1}')
        try:
            welten.append(lade_welt(pfad, name))
        except WeltFehler as fehler:
            meldungen += [f'[{name}] {m}' for m in fehler.meldungen]
    if meldungen:
        raise WeltFehler(meldungen)
    namen = [w.name for w in welten]
    for doppelt in sorted({n for n in namen if namen.count(n) > 1}):
        meldungen.append(f'Der Weltname „{doppelt}“ ist doppelt; vergib mit NAME=PFAD eindeutige Namen.')
    erste = welten[0]
    for w in welten[1:]:
        if w.stichtag != erste.stichtag or w.zeitzone != erste.zeitzone:
            meldungen.append(f'[{w.name}] Stichtag und Zeitzone müssen mit „{erste.name}“ übereinstimmen '
                             f'({w.stichtag.isoformat()} {w.zeitzone} statt {erste.stichtag.isoformat()} {erste.zeitzone}).')
    gesehen_q: dict[str, str] = {}
    gesehen_f: dict[str, str] = {}
    for w in welten:
        for q in w.quellen:
            if q.id in gesehen_q:
                meldungen.append(f'[{w.name}] Quellen-ID „{q.id}“ gibt es schon in „{gesehen_q[q.id]}“.')
            gesehen_q[q.id] = w.name
        for f in w.fragen:
            if f.id in gesehen_f:
                meldungen.append(f'[{w.name}] Frage-ID „{f.id}“ gibt es schon in „{gesehen_f[f.id]}“.')
            gesehen_f[f.id] = w.name
    if meldungen:
        raise WeltFehler(meldungen)
    return welten
