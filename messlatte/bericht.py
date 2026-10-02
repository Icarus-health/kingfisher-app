"""Bericht: JSON für Maschinen (vollständig), Markdown für Menschen.

Oben stehen immer dieselben drei Zahlen: **falsche Aussagen**, **richtig**,
**nicht gemessen**. Eine Stufe, die nicht lief, steht dort als „nicht gemessen“,
nie als „bestanden“. Alle Zahlen erscheinen als „x von n“; Prozentwerte gibt es
nicht, weil sie bei kleinen Fallzahlen mehr Sicherheit vortäuschen, als da ist.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

from . import privat as stufe_privat
from . import zeiten as antwortzeit
from .bewertung import x_von_n, zaehle_abruf
from .darstellung import KLASSEN_NAMEN, klassen_tabelle, kuerzen, tabelle, zeiten, zeiten_satz
from .ergebnisse import KENNZEICHNUNGEN
from .lauf import FrageErgebnis, LaufErgebnis


def _plain(wert):
    """Dataclasses, Tupel und Mengen in JSON-Typen umwandeln."""
    if is_dataclass(wert) and not isinstance(wert, type):
        return _plain(asdict(wert))
    if isinstance(wert, dict):
        return {str(k): _plain(v) for k, v in wert.items()}
    if isinstance(wert, (list, tuple, set, frozenset)):
        return [_plain(v) for v in wert]
    if isinstance(wert, datetime):
        return wert.isoformat()
    return wert


def zu_dict(ergebnis: LaufErgebnis) -> dict:
    """Der vollständige Lauf als JSON-fähiges Objekt."""
    aufnahme = _plain(ergebnis.aufnahme)
    aufnahme['episoden'] = len(ergebnis.aufnahme.episoden)  # die Zuordnung selbst gehört nicht in den Bericht
    auswertung = ergebnis.antwort_auswertung
    return {
        'kopf': ergebnis.kopf,
        'aufnahme': aufnahme,
        'abruf': {'gemessen': True, 'gesamt': _plain(ergebnis.abruf_gesamt)},
        'antwort': {'gemessen': ergebnis.antwort_gemessen, 'grund': ergebnis.antwort_grund,
                    'auswertung': _plain(auswertung) if auswertung else None,
                    'zeiten': _zeiten(ergebnis.fragen), 'antwortzeit': _antwortzeit(ergebnis.fragen),
                    'tore': tore(ergebnis.fragen)},
        'hinweise_der_weltpruefung': list(ergebnis.hinweise),
        'privat': stufe_privat.zu_dict(ergebnis.privat) if ergebnis.privat is not None else None,
        'fragen': [{
            'frage': _plain(f.frage), 'abruf': _plain(f.abruf), 'abruf_bewertung': _plain(f.abruf_bewertung),
            'antwort': _plain(f.antwort), 'antwort_bewertung': _plain(f.antwort_bewertung),
        } for f in ergebnis.fragen],
    }


def _antwortzeit(fragen) -> dict:
    """Median und 90-%-Wert je Stufe (Abruf, Antwort, Abschnitte des Produkts) und das Ziel."""
    return antwortzeit.auswerten([f.abruf.dauer_s for f in fragen if f.abruf is not None],
                                 [f.antwort for f in fragen])


def _arten(je_art: dict) -> str:
    """„überholt 4, andere Person 3“: die Zahlen je Art der Kennzeichnung, nur Arten mit Belegen."""
    return ', '.join(f'{KENNZEICHNUNGEN[art]} {n}' for art, n in je_art.items() if art in KENNZEICHNUNGEN and n)


def _arten_belege(je_art: dict) -> str:
    """„überholt: a, b; andere Person: c“: die Belege je Art der Kennzeichnung."""
    return '; '.join(f'{KENNZEICHNUNGEN[art]}: {", ".join(belege)}' for art, belege in je_art.items()
                     if art in KENNZEICHNUNGEN and belege)


def _zeiten(fragen) -> dict:
    """Erste Antwort (kalt) getrennt von den warmen; leer, wenn nichts gemessen wurde."""
    antworten = [f.antwort for f in fragen if f.antwort is not None]
    if not antworten:
        return {}
    return zeiten([a.dauer_s for a in antworten if a.kalt], [a.dauer_s for a in antworten if not a.kalt])


# -- Markdown ----------------------------------------------------------------------


def _erwartung(f: FrageErgebnis) -> str:
    e = f.frage.erwartet
    teile = [e.verhalten]
    if e.aussagen:
        teile.append('Aussagen: ' + ' UND '.join('/'.join(g) for g in e.aussagen))
    if e.bedeutungen:
        teile.append('Bedeutungen: ' + ' | '.join('/'.join(g) for g in e.bedeutungen))
    if e.belege:
        teile.append('Belege: ' + ', '.join(e.belege))
    if f.frage.verboten.aussagen:
        teile.append('verboten: ' + ', '.join(f'„{v}“' for v in f.frage.verboten.aussagen))
    return '; '.join(teile)


def _rueckfall_gruende(ergebnis: LaufErgebnis) -> str:
    """„ (kein Modell: 77)“: warum der Rückfall galt, gezählt."""
    gruende: dict[str, int] = {}
    for f in ergebnis.fragen:
        if f.abruf is not None and f.abruf.verstanden == 'rueckfall':
            gruende[f.abruf.verstanden_grund or 'ohne Angabe'] = gruende.get(f.abruf.verstanden_grund or 'ohne Angabe', 0) + 1
    return ' (' + ', '.join(f'{g}: {n}' for g, n in sorted(gruende.items())) + ')' if gruende else ''


def _suchindex_zeile(stand: dict) -> str:
    jahre = stand['wortteile_jahre']
    wo = 'für alle Quellen' if not jahre else f'nur für die letzten {jahre} Jahre'
    platz = '' if stand.get('bytes') is None else f", Index {stand['bytes'] / (1024 * 1024):.1f} MB"
    return f"Wortteile {wo}; {stand['mit_wortteilen']} Quellen mit Wortteilen, {stand['nur_woerter']} nur als Wörter{platz}"


def tore(fragen) -> dict:
    """Verworfene Sätze je Tor über alle gemessenen Antworten, und der Zustand des zweiten Tors."""
    antworten = [f.antwort for f in fragen if f.antwort is not None]
    zustaende = sorted({a.pruefung for a in antworten if a.pruefung})
    return {'satzpruefung': sum(a.verworfen_satzpruefung for a in antworten),
            'pruefmodell': sum(a.verworfen_pruefmodell for a in antworten),
            'antworten_satzpruefung': sum(1 for a in antworten if a.verworfen_satzpruefung),
            'antworten_pruefmodell': sum(1 for a in antworten if a.verworfen_pruefmodell),
            'zustaende': zustaende}


def _tore_zeile(fragen) -> str:
    t = tore(fragen)
    zustand = ', '.join(t['zustaende']) or 'keine Satzantwort'
    return (f"Sätze verworfen von der Satzprüfung ohne Modell: {t['satzpruefung']} (in {t['antworten_satzpruefung']} Antworten); "
            f"**vom Prüfmodell (zweites Tor): {t['pruefmodell']}** (in {t['antworten_pruefmodell']} Antworten; Tor: {zustand})")


def _tore_tabelle(fragen) -> list[str]:
    zeilen = [[f.frage.id, f.antwort.verworfen_satzpruefung, f.antwort.verworfen_pruefmodell, f.antwort.pruefung or '-']
              for f in fragen if f.antwort is not None and (f.antwort.verworfen_satzpruefung or f.antwort.verworfen_pruefmodell)]
    if not zeilen:
        return [_tore_zeile(fragen), '', 'Keine Antwort mit verworfenen Sätzen.', '']
    return [_tore_zeile(fragen), ''] + tabelle(['Frage', 'Satzprüfung ohne Modell', 'Prüfmodell', 'Tor'], zeilen)


def markdown(ergebnis: LaufErgebnis) -> str:
    k = ergebnis.kopf
    z = ergebnis.abruf_gesamt
    zeilen = ['# Messlatte: Bericht', '']
    welten = '; '.join(f"{w['name']} v{w['version']} ({w['szenarien']} Szenarien, {w['quellen']} Quellen, {w['fragen']} Fragen)"
                       for w in k['welten'])
    zeilen += tabelle(['Kopf', ''], [
        ['Commit', k['commit']], ['Modell', k['modell']],
        *([['Modell (Rolle „frage“)', k['modell_frage']]] if k.get('modell_frage') else []),
        *([['Modell (Rolle „pruefung“, zweites Tor)', k['modell_pruefung']]] if k.get('modell_pruefung') else []),
        ['Welt', welten],
        ['Rauschen', f"{k['rauschen']['anzahl']} Quellen (seed {k['rauschen']['seed']})"],
        *([['Suchindex', _suchindex_zeile(k['suchindex'])]] if k.get('suchindex') else []),
        ['Stichtag der Welt', k['stichtag']], ['Datum der Messung', k['datum']], ['Dauer', f"{k['dauer_s']} s"],
        *([['Nur Kategorie', k['nur_kategorie']]] if k.get('nur_kategorie') else []),
        *([['Lange Quellen', f"Mails auf {k['lange_quellen']['mail']}, Transkripte auf {k['lange_quellen']['transkript']} Zeichen"]]
          if k.get('lange_quellen') else [])])

    auswertung = ergebnis.antwort_auswertung
    fragen_n = len(ergebnis.fragen)
    zeilen += ['## Ergebnis auf einen Blick', '']
    if auswertung is not None:
        g = auswertung.gesamt
        zeilen += [f'- **Falsche Aussagen: {x_von_n(g.falsche_aussagen, g.n)} Antworten** (verbotener Text in der Antwort)',
                   f'- **Richtig: {x_von_n(g.richtig, g.n)} Antworten**',
                   '- **Nicht gemessen: 0 Fragen**']
        if auswertung.kritisch_nicht_richtig:
            kritisch_n = sum(1 for f in ergebnis.fragen if f.frage.schwere == 'kritisch')
            zeilen.append(f'- **Kritische Fragen, die nicht richtig waren: '
                          f'{x_von_n(len(auswertung.kritisch_nicht_richtig), kritisch_n)}** '
                          f'({", ".join(auswertung.kritisch_nicht_richtig)})')
        zeilen.append('- **' + antwortzeit.ziel_zeile(_antwortzeit(ergebnis.fragen)) + '**')
        zeilen.append('- ' + _tore_zeile(ergebnis.fragen))
    else:
        zeilen += ['- **Falsche Aussagen: nicht gemessen** (Stufe „Antwort“ ohne Modell nicht möglich)',
                   '- **Richtig: nicht gemessen**',
                   f'- **Nicht gemessen: {fragen_n} von {fragen_n} Fragen** ({ergebnis.antwort_grund})',
                   '- **' + antwortzeit.ziel_zeile(_antwortzeit(ergebnis.fragen)) + '**']
    zeilen += [
        '', 'Suche ohne Modell (Stufe „Abruf“), gemessen:', '',
        f'- Erwartete Belege gefunden: {x_von_n(z.belege_gefunden, z.belege_erwartet)}',
        f'- Fragen mit allen erwarteten Belegen: {x_von_n(z.fragen_alle_belege, z.fragen_mit_belegen)}',
        f'- Erwartete Belege auf Rang 1: {x_von_n(z.rang_1, z.belege_erwartet)}, bis Rang 5: {x_von_n(z.rang_bis_5, z.belege_erwartet)}, '
        f'bis Rang 12: {x_von_n(z.rang_bis_12, z.belege_erwartet)}',
        f'- Fragen, bei denen verbotene Belege im Kontext waren: {x_von_n(z.fragen_mit_verbotenem_beleg, z.fragen)} '
        f'({z.verbotene_belege} verbotene Belege)',
        f'- davon **ungekennzeichnet** (der Kontext nennt die Quelle weder als überholt noch als andere Person '
        f'noch als außerhalb des Zeitraums): '
        f'{x_von_n(z.fragen_mit_verbotenem_beleg_ungekennzeichnet, z.fragen)} Fragen '
        f'({z.verbotene_belege_ungekennzeichnet} von {z.verbotene_belege} Belegen)',
        f'- die übrigen, **gekennzeichnet nach Art** (Belege; einer mit zwei Arten zählt in beiden): '
        + (_arten(z.verbotene_belege_gekennzeichnet) or 'keine'),
        f'- **Kontext abgeschnitten** (Budget voll; gefunden, aber nicht im Kontext): {x_von_n(z.fragen_abgeschnitten, z.fragen_mit_belegen)} Fragen '
        f'mit mindestens einer erwarteten Quelle ({z.belege_abgeschnitten} von {z.belege_erwartet} Belegen); '
        f'weitere erwartete Belege, die das Arbeitsgedächtnis wegen ihrer Länge nie einordnet: {z.belege_zu_lang} ({z.fragen_zu_lang} Fragen)',
        f'- **Erwartete Belege im Kontext ohne tragende Textstelle** (keine Pflichtaussage der Quelle mehr zu sehen): '
        f'{z.belege_ohne_stelle} Belege in {x_von_n(z.fragen_ohne_stelle, z.fragen_mit_belegen)} Fragen',
        f'- Gekürzte Quellen im Kontext (Zweistufige Auswahl): {z.gekuerzte_quellen} Quellen in allen Fragen, davon gezeigt '
        f'{z.absaetze_gezeigt} von {z.absaetze_gesamt} Absätzen',
        f'- Kontext der Auswahl: im Mittel {z.kontext_zeichen_mittel} Zeichen (Median {z.kontext_zeichen_median}, '
        f'Höchstwert {z.kontext_zeichen_max}), im Mittel {z.kontext_quellen_mittel} Quellen',
        f'- Rückfragen, die das Produkt mit allen Bedeutungen anbietet: {x_von_n(z.rueckfragen_angeboten, z.rueckfragen_erwartet)}'
        + (f' ({z.rueckfragen_ohne_rueckfrage} Mal wurde eine Bedeutung ohne Rückfrage gewählt)' if z.rueckfragen_ohne_rueckfrage else ''),
        f'- Unnötige Rückfragen bei eindeutigen Fragen: {x_von_n(z.unnoetige_rueckfragen, z.unnoetige_rueckfragen_moeglich)}',
        f'- Fragen, die im Gespräch in den freien Chat gingen (statt in den belegten Gedächtnisweg): {x_von_n(z.fragen_im_chat, z.fragen)}',
        f'- Frage verstanden mit Modell: {x_von_n(z.verstanden_modell, z.fragen)}, mit Rückfall: {x_von_n(z.verstanden_rueckfall, z.fragen)}'
        + _rueckfall_gruende(ergebnis),
        '']

    a = ergebnis.aufnahme
    zeilen += ['## Aufnahme', '']
    zeilen += tabelle(['Zähler', ''], [
        ['Quellen der Welt (mit Rauschen)', a.quellen_gesamt], ['Episoden aufgenommen', a.aufgenommen],
        ['dupliziert', a.dupliziert], ['fehlgeschlagen', a.fehlgeschlagen],
        ['Termine in der Live-Anzeige des Kalenders (laufendes Jahr)', a.termine_im_kalender],
        ['Termine außerhalb des Gedächtnisfensters (3 Jahre zurück, 1 Jahr voraus)', a.termine_ausserhalb_fenster],
        ['Einordnung', a.einordnung], ['Dauer', f'{a.dauer_s} s']])
    if a.meldungen:
        zeilen += ['Meldungen des Produkts: ' + '; '.join(a.meldungen), '']
    if a.nicht_angekommen:
        zeilen += ['Nicht angekommen: ' + ', '.join(f'{q} ({g})' for q, g in sorted(a.nicht_angekommen.items())[:20]), '']

    zeilen += ['## Antwort', '']
    if auswertung is None:
        zeilen += [f'Nicht gemessen. {ergebnis.antwort_grund}.', '']
    else:
        zeilen += klassen_tabelle('Gesamt', {'alle': auswertung.gesamt})
        zeilen += ['### Je Kategorie', ''] + klassen_tabelle('Kategorie', auswertung.je_kategorie)
        zeilen += ['### Je Schwere', ''] + klassen_tabelle('Schwere', auswertung.je_schwere)
        if len(auswertung.je_herkunft) > 1 or 'welt' not in auswertung.je_herkunft:
            zeilen += ['### Je Herkunft (Holdout getrennt ausgewiesen)', ''] + klassen_tabelle('Herkunft', auswertung.je_herkunft)
        zeit = _zeiten(ergebnis.fragen)
        if zeit:
            zeilen += [zeiten_satz(zeit), '']
        zeilen += ['### Zwei Tore der Satzprüfung', ''] + _tore_tabelle(ergebnis.fragen)

    zeilen += ['### Antwortzeit', ''] + antwortzeit.markdown(_antwortzeit(ergebnis.fragen))

    zeilen += ['## Abruf je Kategorie', '']
    kategorien = sorted({f.frage.kategorie for f in ergebnis.fragen})
    abruf_zeilen = []
    for kat in kategorien:
        t = zaehle_abruf(f.abruf_bewertung for f in ergebnis.fragen if f.frage.kategorie == kat)
        abruf_zeilen.append([kat, t.fragen, x_von_n(t.belege_gefunden, t.belege_erwartet),
                             x_von_n(t.fragen_alle_belege, t.fragen_mit_belegen),
                             x_von_n(t.fragen_mit_verbotenem_beleg, t.fragen),
                             x_von_n(t.fragen_mit_verbotenem_beleg_ungekennzeichnet, t.fragen)])
    zeilen += tabelle(['Kategorie', 'Fragen', 'Belege gefunden', 'Fragen mit allen Belegen',
                        'verbotene Belege im Kontext', 'davon ungekennzeichnet'], abruf_zeilen)

    if auswertung is not None:
        fehler = [f for f in ergebnis.fragen if f.antwort_bewertung and f.antwort_bewertung.klasse != 'richtig']
        zeilen += [f'## Fehlerliste Antwort ({len(fehler)} von {fragen_n})', '']
        for f in fehler:
            b, an = f.antwort_bewertung, f.antwort
            zeilen += [f'### {f.frage.id}: {KLASSEN_NAMEN[b.klasse]}' + (' · FALSCHE AUSSAGE' if b.falsche_aussage else ''), '',
                       f'- Frage: {f.frage.frage}', f'- Kategorie / Schwere: {f.frage.kategorie} / {f.frage.schwere}',
                       f'- Erwartet: {_erwartung(f)}', f'- Erkannt: {b.erkannt}; Gründe: {"; ".join(b.gruende) or "-"}',
                       f'- Antwort (gekürzt): {kuerzen(an.text) or "(keine)"}',
                       *(['- Angebotene Auswahl: ' + ', '.join(an.auswahl)] if an.auswahl else []), '']
    fehler_abruf = [f for f in ergebnis.fragen if f.abruf_bewertung and (
        f.abruf_bewertung.fehlend or f.abruf_bewertung.verboten_gesehen or f.abruf_bewertung.fehlende_bedeutungen
        or f.abruf_bewertung.ohne_rueckfrage_gewaehlt or f.abruf_bewertung.ohne_stelle)]
    zeilen += [f'## Fehlerliste Abruf ({len(fehler_abruf)} von {fragen_n})', '']
    for f in fehler_abruf:
        b, ab = f.abruf_bewertung, f.abruf
        teile = [f'- **{f.frage.id}** ({f.frage.kategorie}, {f.frage.schwere}): Frage „{kuerzen(f.frage.frage, 120)}“; '
                 f'Weg: {ab.weg}/{ab.route}']
        if b.fehlend:
            teile.append(f'  - erwartete Belege fehlen: {", ".join(b.fehlend)} (gefunden: {", ".join(b.gefunden) or "keine"})')
        if b.abgeschnitten:
            teile.append(f'  - davon vom Zeichenbudget verdrängt (gefunden, nicht im Kontext): {", ".join(b.abgeschnitten)}')
        if b.zu_lang:
            teile.append(f'  - wegen der Länge nie eingeordnet: {", ".join(b.zu_lang)}')
        if b.ohne_stelle:
            teile.append(f'  - im Kontext ohne tragende Textstelle: {", ".join(b.ohne_stelle)}')
        if b.verboten_gesehen:
            teile.append(f'  - verbotene Belege im Kontext: {", ".join(b.verboten_gesehen)}'
                         + (f' (ungekennzeichnet: {", ".join(b.verboten_ungekennzeichnet) or "keiner"}; '
                            f'gekennzeichnet: {_arten_belege(b.verboten_gekennzeichnet)})'
                            if b.verboten_ungekennzeichnet != b.verboten_gesehen else ''))
        if b.fehlende_bedeutungen:
            teile.append('  - Bedeutungen nicht angeboten: ' + ' | '.join('/'.join(g) for g in b.fehlende_bedeutungen))
        if b.ohne_rueckfrage_gewaehlt:
            teile.append('  - eine Bedeutung wurde ohne Rückfrage gewählt')
        zeilen += teile
    zeilen.append('')
    if ergebnis.privat is not None:
        zeilen += stufe_privat.markdown(ergebnis.privat)
    if ergebnis.hinweise:
        zeilen += ['## Hinweise der Weltprüfung', ''] + [f'- {h}' for h in ergebnis.hinweise] + ['']
    zeilen += ['## Was diese Messung nicht sagt', '',
               '- Sie misst eine erfundene Welt; sie ist kein Beleg für die Qualität am echten Postfach (dafür `python -m messlatte lokal`).',
               '- Null beobachtete Fehler beweisen keine Fehlerwahrscheinlichkeit von null; die Fallzahl steht immer daneben.',
               '- Termine liegen als Episoden im Bestand, aber nur im Gedächtnisfenster (3 Jahre zurück, 1 Jahr voraus); ältere oder fernere Termine sind unsichtbar.', '']
    return '\n'.join(zeilen)


def schreibe(ergebnis: LaufErgebnis, ordner: Path) -> tuple[Path, Path]:
    """Legt `bericht-<Zeit>.json` und `.md` an; ein früherer Bericht wird nie überschrieben."""
    ordner.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime('%Y%m%d-%H%M%S')
    json_pfad, md_pfad = ordner / f'bericht-{stempel}.json', ordner / f'bericht-{stempel}.md'
    nummer = 1
    while json_pfad.exists() or md_pfad.exists():
        nummer += 1
        json_pfad, md_pfad = ordner / f'bericht-{stempel}-{nummer}.json', ordner / f'bericht-{stempel}-{nummer}.md'
    json_pfad.write_text(json.dumps(zu_dict(ergebnis), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_pfad.write_text(markdown(ergebnis), encoding='utf-8')
    return json_pfad, md_pfad
