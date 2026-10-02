"""Das Morgenbriefing: drei bis fünf Zeilen, was heute wichtig ist. Ein Urteil, keine Liste.

Baut auf dem Vorhandenen auf: `briefing.py` bleibt die Rangfolge der Aufgaben und Vorschläge;
dieses Modul legt die **Tageslage** darüber, aus den Terminen heute (oder morgen, wenn heute nichts
mehr kommt), den Akten und dem Weg. Jede Zeile trägt eine Aktion und, wo es eine gibt, ihre Quelle.
Nichts wird erfunden: Was nicht belegt ist (Packliste, Fahrzeit), fehlt oder sagt ehrlich, dass es
unbekannt ist.

Zeilen, in dieser Reihenfolge, jede nur, wenn es etwas zu sagen gibt:

1. **Termin**: der nächste Termin mit Uhrzeit, Ort und dem Weg („Losfahren um 13:05 Uhr“ oder
   „Fahrzeit unbekannt“).
2. **Leute**: wer kommt und was sie (vermutlich) wollen.
3. **Einpacken**: nur, was in einer Notiz oder Mail steht.
4. **Fristen**: das Dringendste der nächsten sieben Tage oder eine verstrichene, vermutlich noch
   offene Zusage; überholte Fristen nie.
5. **Wetter**: eine Zeile, wenn es Wetterdaten gibt: am Wohnort und, wenn der nächste auswärtige Termin
   einen auflösbaren Ort hat, dort zur Zeit des Termins („Mainz, 14 Uhr: 12 °C, Regen – Schirm einpacken?“).
   Der Wetterhinweis bleibt eine eigene Zeile; die Packliste bleibt belegpflichtig.
6. **Geburtstag**: „Morgen hat Gabriele Geburtstag.“, nur für Personen, die **bestätigt** im inneren Kreis sind und
   deren Geburtstag **angenommen** ist (`wiederkehrendes.im_briefing`); nie für Kollegen oder Kontakte.
7. **Welt**: höchstens eine Meldung, nur wenn sie zu einer Sache aus den Akten passt, mit Begründung und
   Aktionen zum Abbestellen (`welt_meldungen.py`).

Darüber stehen, gedämpft, die drei Zeilen des Logbuchs („Seit gestern Abend: 41 Mails aufgenommen, 2 neue Akten …“,
`logbuch.py`): was sich getan hat, bevor es um den Tag geht.

Die Reihenfolge ist die der Dringlichkeit am Morgen: Wohin, wer, was mit, was drängt, wie draußen, wer feiert, was in
der Welt.
Ohne Modell, deterministisch, nachprüfbar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import wegezeit
from .datumstext import tag_und_monat
from .fristlage import Frist, beschreibung
from .terminvorbereitung import Vorbereitung
from .wetter import satz_am_termin

MAX_ZEILEN = 7


@dataclass
class Aktion:
    art: str
    """`vorbereitung` (Vorbereitung öffnen), `quelle` (Quelle öffnen), `fahrzeiten` (Einwilligung),
    `heimat` (Startort eintragen), `akte` (Akte öffnen, `ref` = Sache), `link` (Meldung lesen, `ref` = https-Adresse),
    `welt_quelle` (Quelle abbestellen, `ref` = Quelle), `welt_sache` (Sache abbestellen, `ref` = Sache)."""
    beschriftung: str
    ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {'art': self.art, 'beschriftung': self.beschriftung, 'ref': self.ref}


@dataclass
class Zeile:
    art: str
    """`termin`, `leute`, `einpacken`, `fristen`, `wetter`, `geburtstag`, `welt`."""
    text: str
    aktionen: list[Aktion] = field(default_factory=list)
    vermutlich: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {'art': self.art, 'text': self.text, 'aktionen': [a.to_dict() for a in self.aktionen],
                'vermutlich': self.vermutlich}


@dataclass
class Tageslage:
    einleitung: str
    zeilen: list[Zeile] = field(default_factory=list)
    tag: str = 'heute'
    """`heute` oder `morgen`: Für welchen Tag die Zeilen gelten."""
    verlauf: list[str] = field(default_factory=list)
    """Die höchstens drei Zeilen des Logbuchs („Seit gestern Abend: …“), ganz oben und gedämpft (`logbuch.py`).
    Sie stehen vor den Zeilen des Tages und zählen nicht zu `MAX_ZEILEN`."""

    def to_dict(self) -> dict[str, Any]:
        return {'einleitung': self.einleitung, 'zeilen': [z.to_dict() for z in self.zeilen], 'tag': self.tag,
                'verlauf': list(self.verlauf)}


def _uhr(zeit: datetime) -> str:
    return f'{zeit.hour}:{zeit.minute:02d} Uhr'


def _datum(zeit: datetime) -> str:
    return tag_und_monat(zeit)


def _kurz(text: str, laenge: int = 90) -> str:
    text = ' '.join(str(text).split())
    return text if len(text) <= laenge else text[:laenge].rsplit(' ', 1)[0].rstrip(',;:.') + ' …'


def _zitat(text: str, laenge: int = 90) -> str:
    return _kurz(text, laenge).rstrip('.')


def _aufzaehlung(namen: list[str]) -> str:
    return namen[0] if len(namen) == 1 else ', '.join(namen[:-1]) + ' und ' + namen[-1]


def naechster(vorbereitungen: list[Vorbereitung], jetzt: datetime) -> tuple[Vorbereitung | None, str]:
    """Der nächste Termin, der noch bevorsteht: heute, sonst morgen. `(None, 'heute')`, wenn keiner ansteht."""
    kommend = sorted((v for v in vorbereitungen if not v.termin.ganztaegig and v.termin.beginn >= jetzt),
                     key=lambda v: v.termin.beginn)
    for v in kommend:
        if v.termin.beginn.date() == jetzt.date():
            return v, 'heute'
    for v in kommend:
        if (v.termin.beginn.date() - jetzt.date()).days == 1:
            return v, 'morgen'
    return None, 'heute'


def _termin_zeile(v: Vorbereitung, tag: str, weitere: int) -> Zeile:
    t = v.termin
    wo = f' bei {_kurz(t.ort, 70)}' if t.ort else ''
    wann = f'{"Morgen" if tag == "morgen" else "Heute"} um {_uhr(t.beginn)}'
    satz = f'{wann}: „{_kurz(t.titel, 70)}“{wo}.'
    aktionen = [Aktion('vorbereitung', 'Vorbereitung öffnen', t.uid)]
    weg = v.wegezeit or {}
    if weg.get('status') == wegezeit.BERECHNET and weg.get('losfahren'):
        los = datetime.fromisoformat(weg['losfahren'])
        satz += (f' Losfahren um {_uhr(los)}: etwa {weg["minuten"]} Minuten {wegezeit.MITTEL_TEXT[weg["verkehrsmittel"]]}'
                 f' ({weg["quelle"]}), {weg["puffer_min"]} Minuten Puffer.')
        if weg.get('knapp'):
            satz += ' ' + weg['knapp']
    elif t.ort and weg.get('status') in (wegezeit.AUS, wegezeit.OHNE_START, wegezeit.OHNE_DIENST, wegezeit.FEHLER):
        satz += ' Fahrzeit unbekannt.'
        hinweis = weg.get('hinweis')
        if hinweis == 'einwilligung':
            aktionen.append(Aktion('fahrzeiten', 'Fahrzeit berechnen'))
        elif hinweis == 'heimat':
            aktionen.append(Aktion('heimat', 'Startort eintragen'))
    if weitere:
        satz += f' Danach {"noch ein Termin" if weitere == 1 else f"noch {weitere} Termine"}.'
    return Zeile('termin', satz, aktionen)


_VERB = {'wunsch': 'schrieb', 'genannt': 'schrieb', 'sie_bittet': 'bat', 'sie_sagte_zu': 'sagte zu',
         'du_sagtest_zu': 'Du hattest zugesagt', 'du_batest': 'Du hattest gebeten', 'offen': 'schrieb'}


def _tag_der_quelle(beleg: Any) -> str:
    try:
        return f' am {_datum(datetime.fromisoformat(beleg.datum))}' if beleg and beleg.datum else ''
    except ValueError:
        return ''


def _leute_zeile(v: Vorbereitung) -> Zeile | None:
    """Wer kommt und was er (nach eigenem Wortlaut, mit Datum) will. Bitten und Zusagen sind Vermutungen."""
    bekannte = [p for p in v.personen if p.bekannt]
    if not bekannte:
        return None
    namen = [p.name for p in bekannte]
    satz = f'Mit {_aufzaehlung(namen[:3])}' + (f' und {len(namen) - 3} weiteren' if len(namen) > 3 else '') + '.'
    aktionen = [Aktion('vorbereitung', 'Vorbereitung öffnen', v.termin.uid)]
    vermutlich = False
    erste_quelle = None
    for p in bekannte[:2]:
        will = (next((z for z in p.will if z.rolle in ('wunsch', 'sie_bittet')), None)
                or (p.will[0] if p.will else None))
        if will is not None:
            verb = _VERB.get(will.rolle, 'schrieb')
            offen = will.rolle in ('sie_bittet', 'sie_sagte_zu', 'du_sagtest_zu', 'du_batest', 'offen')
            wer = verb if verb[0].isupper() else f'{p.name} {verb}'
            satz += f' {wer}{_tag_der_quelle(will.beleg)}: „{_kurz(will.text, 90)}“' + (' (vermutlich noch offen)' if offen else '')
            vermutlich = vermutlich or will.vermutlich
            erste_quelle = erste_quelle or will.beleg
        elif p.letzter_kontakt and p.letzter_kontakt.beleg:
            satz += f' {p.name}: zuletzt{_tag_der_quelle(p.letzter_kontakt.beleg)} geschrieben.'
            erste_quelle = erste_quelle or p.letzter_kontakt.beleg
    if erste_quelle is not None:
        aktionen.append(Aktion('quelle', 'Quelle öffnen', erste_quelle.episode_id))
    if v.unbekannt:
        satz += f' Nicht im Gedächtnis: {_aufzaehlung(v.unbekannt[:3])}.'
    return Zeile('leute', satz, aktionen, vermutlich)


def _einpacken_zeile(v: Vorbereitung) -> Zeile | None:
    if not v.einpacken:
        return None
    erstes = v.einpacken[0]
    herkunft = {'termin': 'aus der Notiz zum Termin', 'notiz': 'aus einer Notiz', 'mail': 'aus einer Mail'}.get(
        erstes.art, 'aus einer Quelle')
    text = f'Einpacken, {herkunft}: „{_zitat(erstes.text, 110)}“'
    if len(v.einpacken) > 1:
        text += f' Dazu noch {"eine weitere Angabe" if len(v.einpacken) == 2 else f"{len(v.einpacken) - 1} weitere Angaben"}.'
    return Zeile('einpacken', text, [Aktion('quelle', 'Quelle öffnen', erstes.episode_id),
                                      Aktion('vorbereitung', 'Vorbereitung öffnen', v.termin.uid)])


def _fristen_zeile(fristen: list[Frist]) -> Zeile | None:
    if not fristen:
        return None
    erste = fristen[0]
    weitere = len(fristen) - 1
    text = f'{beschreibung(erste)} „{_zitat(erste.text, 90)}“'
    if weitere:
        text += f' Dahinter {"wartet noch eine" if weitere == 1 else f"warten noch {weitere}"}.'
    return Zeile('fristen', text, [Aktion('quelle', 'Quelle öffnen', erste.episode_id)], erste.status == 'verstrichen')


def _wetter_zeile(wetter: dict[str, Any] | None, termin_wetter: dict[str, Any] | None = None) -> Zeile | None:
    """Wetter am Wohnort und, getrennt davon, am Ort des nächsten auswärtigen Termins. Nur ein Hinweis."""
    daheim = None
    if wetter and wetter.get('temperature_c') is not None:
        ort = f' in {wetter["location"]}' if wetter.get('location') else ''
        daheim = f'Wetter{ort}: {wetter["temperature_c"]} °C, {str(wetter.get("condition", "")).lower()}.'
    dort = None
    if termin_wetter and termin_wetter.get('wetter') and termin_wetter['wetter'].get('temperature_c') is not None:
        dort = satz_am_termin(termin_wetter['ort'], termin_wetter['wann'], termin_wetter['wetter'])
        if daheim is None:
            dort = f'Wetter: {dort}'
    text = ' '.join(t for t in (daheim, dort) if t)
    return Zeile('wetter', text) if text else None


def _geburtstag_zeile(geburtstage: list[dict[str, Any]] | None) -> Zeile | None:
    """„Morgen hat Gabriele Geburtstag.“ Die Liste kommt schon gefiltert (bestätigter innerer Kreis, angenommen)."""
    nah = [g for g in geburtstage or () if g.get('wann') in ('heute', 'morgen')]
    if not nah:
        return None
    saetze = []
    for wann in ('heute', 'morgen'):
        namen = [g['vorname'] for g in nah if g['wann'] == wann]
        if namen:
            verb = 'hat' if len(namen) == 1 else 'haben'
            saetze.append(f'{"Heute" if wann == "heute" else "Morgen"} {verb} {_aufzaehlung(namen)} Geburtstag.')
    return Zeile('geburtstag', ' '.join(saetze), [Aktion('akte', 'Akte öffnen', nah[0]['sache'])])


def _welt_zeile(welt: dict[str, Any] | None) -> Zeile | None:
    """Die eine Meldung des Tages: was, warum, und zwei Wege, sie abzubestellen. Fremder Text steht nur als Zitat."""
    if not welt or not welt.get('titel') or not welt.get('grund'):
        return None
    text = f'„{_zitat(welt["titel"], 140)}“ ({_kurz(welt.get("quelle") or "Quelle", 40)}). {welt["grund"]}'
    aktionen: list[Aktion] = []
    if welt.get('link'):
        aktionen.append(Aktion('link', 'Meldung lesen', welt['link']))
    if welt.get('sache'):
        aktionen.append(Aktion('akte', 'Akte öffnen', welt['sache']))
    if welt.get('quelle_id'):
        aktionen.append(Aktion('welt_quelle', 'Quelle abbestellen', welt['quelle_id']))
    if welt.get('sache'):
        aktionen.append(Aktion('welt_sache', f'Nicht mehr zu {_kurz(welt.get("sache_name") or "dieser Sache", 30)}', welt['sache']))
    return Zeile('welt', text, aktionen)


def erstellen(vorbereitungen: list[Vorbereitung], fristen: list[Frist], wetter: dict[str, Any] | None,
              *, jetzt: datetime, termin_wetter: dict[str, Any] | None = None,
              welt: dict[str, Any] | None = None, verlauf: list[str] | None = None,
              geburtstage: list[dict[str, Any]] | None = None) -> Tageslage:
    """Die Tageslage aus den vorbereiteten Terminen, den Fristen, dem Wetter und der einen Meldung aus der Welt.

    `verlauf` sind die Zeilen des Logbuchs, unverändert durchgereicht: Sie sagen, was seit dem letzten Blick geschah,
    und stehen über dem, was heute zählt."""
    v, tag = naechster(vorbereitungen, jetzt)
    zeilen: list[Zeile] = []
    if v is not None:
        heute = [x for x in vorbereitungen if not x.termin.ganztaegig and x.termin.beginn >= jetzt
                 and x.termin.beginn.date() == v.termin.beginn.date()]
        for zeile in (_termin_zeile(v, tag, len(heute) - 1), _leute_zeile(v), _einpacken_zeile(v)):
            if zeile is not None:
                zeilen.append(zeile)
    for zeile in (_fristen_zeile(fristen), _wetter_zeile(wetter, termin_wetter), _geburtstag_zeile(geburtstage),
                  _welt_zeile(welt)):
        if zeile is not None:
            zeilen.append(zeile)
    zeilen = zeilen[:MAX_ZEILEN]
    if zeilen:
        einleitung = 'Das zählt morgen.' if tag == 'morgen' else 'Das zählt heute.'
    else:
        einleitung = 'Heute liegt nichts an, das ich vorbereiten müsste.'
    return Tageslage(einleitung=einleitung, zeilen=zeilen, tag=tag, verlauf=list(verlauf or []))


__all__ = ['Aktion', 'MAX_ZEILEN', 'Tageslage', 'Zeile', 'erstellen', 'naechster']
