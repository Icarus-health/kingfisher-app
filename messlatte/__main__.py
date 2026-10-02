"""Kommandozeile der Messlatte.

    python -m messlatte lauf --welt messlatte/welt [--welt holdout=PFAD] [--modell keins|ollama:NAME|
                             kompatibel:URL:NAME|anthropic:NAME|skript:ART] [--modell-hintergrund SPEC] [--modell-frage SPEC]
                             [--modell-pruefung SPEC]
                             [--rauschen N] [--nur KATEGORIE]
                             [--seed N] [--einordnung auto|konstant|regel] [--ohne-akten] [--plaetze N] [--kontext-zeichen N]
                             [--wortteile-jahre N] [--lange-quellen [--lange-mail-zeichen N] [--lange-transkript-zeichen N]] [--ausgabe DIR]
    python -m messlatte lokal --fragen DATEI.json [--adresse http://127.0.0.1:8890] [--zeigen] [--ausgabe DIR]
    python -m messlatte faelle --aus rueckmeldungen.sqlite3|meldungen.json [--ausgabe fragen.json]
    python -m messlatte akten --welt messlatte/welt [--rauschen N] [--seed N] [--modell-hintergrund SPEC] [--ausgabe DIR]
    python -m messlatte lint --welt messlatte/welt [--rauschen N] [--seed N] [--ausgabe DIR]
    python -m messlatte pruefen --welt PFAD [--welt ...]

Rückgabewert 0 bei einer vollständigen Messung, 2 bei einer ungültigen Welt, Fragen-Datei oder Modellwahl,
1 bei einem Fehler, der die Messung verhindert (etwa keine erreichbare Instanz).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import lange
from .welt import WeltFehler, lade_welten


def _parser() -> argparse.ArgumentParser:
    haupt = argparse.ArgumentParser(prog='messlatte', description='Messinstrument für das Gedächtnis von Kingfisher.')
    befehle = haupt.add_subparsers(dest='befehl', required=True)

    lauf = befehle.add_parser('lauf', help='Synthetische Welt einspielen, Abruf und Antwort messen')
    lauf.add_argument('--welt', action='append', required=True, metavar='PFAD|NAME=PFAD',
                      help='Weltverzeichnis; mehrfach möglich (zusätzliche Welten, etwa der Holdout, als NAME=PFAD)')
    lauf.add_argument('--modell', default='keins', help='keins | ollama:NAME | kompatibel:URL:NAME | anthropic:NAME')
    lauf.add_argument('--modell-hintergrund', default='', metavar='SPEC',
                      help='Modell nur für die Einordnung der Quellen (Rolle „hintergrund“); Vorgabe: wie --modell')
    lauf.add_argument('--modell-frage', default='', metavar='SPEC',
                      help='Modell nur für das Verstehen der Frage (Rolle „frage“); Vorgabe: keins, es gilt der deterministische Rückfall')
    lauf.add_argument('--modell-pruefung', default='', metavar='SPEC',
                      help='Modell nur für das zweite Tor der Satzprüfung (Rolle „pruefung“); Vorgabe: keins, das Tor ist aus')
    lauf.add_argument('--rauschen', type=int, default=0, metavar='N', help='Anzahl unauffälliger Alltagsquellen')
    lauf.add_argument('--seed', type=int, default=1, help='Startwert des Rauschens (gleicher Wert, gleiche Quellen)')
    lauf.add_argument('--nur', metavar='KATEGORIE', help='nur Fragen dieser Kategorie stellen')
    lauf.add_argument('--einordnung', choices=('auto', 'konstant', 'regel'), default='auto',
                      help='auto: ein lokales Modell ordnet die Weltquellen selbst ein; konstant: nie; '
                           'regel: feste Schlüsselwortregeln der Stufe Akten (Arten wie Änderung, Zusage), Rauschen konstant')
    lauf.add_argument('--ohne-akten', action='store_true',
                      help='Versuch: die Suche ohne die Akten (Stand vor E2), zum Vergleich')
    lauf.add_argument('--plaetze', type=int, default=0, metavar='N',
                      help='Versuch: N Abschnitte im Kontext der Auswahl statt der Vorgabe des Produkts (16 Kandidaten)')
    lauf.add_argument('--kontext-zeichen', type=int, default=0, metavar='N',
                      help='Versuch: Zeichenbudget des Kontexts statt der Vorgabe des Produkts (32000)')
    lauf.add_argument('--wortteile-jahre', type=int, default=0, metavar='N',
                      help='Einstellung des Suchindex: Wortteile nur für Quellen der letzten N Jahre vor dem Stichtag '
                           '(0 = alle, Vorgabe); ältere stehen nur im kleineren Wortindex')
    lauf.add_argument('--lange-quellen', action='store_true',
                      help='Mails auf 3.000 und Transkripte auf 30.000 Zeichen auffüllen (Signatur, Zitat, Small Talk; '
                           'Pflichtaussagen unverändert, seed-fest), Weltquellen und Rauschen gleich')
    lauf.add_argument('--lange-mail-zeichen', type=int, default=lange.MAIL_ZEICHEN, metavar='N',
                      help=f'mit --lange-quellen: Länge einer Mail (Vorgabe {lange.MAIL_ZEICHEN})')
    lauf.add_argument('--lange-transkript-zeichen', type=int, default=lange.TRANSKRIPT_ZEICHEN, metavar='N',
                      help=f'mit --lange-quellen: Länge eines Transkripts (Vorgabe {lange.TRANSKRIPT_ZEICHEN}; '
                           'lange Quellen ordnet das Arbeitsgedächtnis in Abschnitten ein, über 200.000 Zeichen gar nicht)')
    lauf.add_argument('--ausgabe', type=Path, metavar='DIR', help='Ordner für bericht-<Zeit>.json und .md')

    lokal = befehle.add_parser('lokal', help='Eigene Fragen an die laufende Instanz (Bericht ohne Inhalte)')
    lokal.add_argument('--fragen', type=Path, required=True, metavar='DATEI.json')
    lokal.add_argument('--adresse', default=None, help='Adresse der Instanz (Standard http://127.0.0.1:8890)')
    lokal.add_argument('--zeigen', action='store_true', help='Antworten nur im Terminal zeigen, nie in Dateien')
    lokal.add_argument('--ausgabe', type=Path, metavar='DIR', help='Ordner für den Bericht ohne Inhalte')

    faelle = befehle.add_parser('faelle', help='Meldungen „Stimmt nicht?“ als Fälle für „lokal“ (lokale Datei mit Texten)')
    faelle.add_argument('--aus', type=Path, required=True, metavar='DATEI',
                        help='rueckmeldungen.sqlite3 aus dem Datenordner oder JSON von GET /api/v1/rueckmeldungen')
    faelle.add_argument('--ausgabe', type=Path, default=None, metavar='DATEI.json',
                        help='Zieldatei (Vorgabe: rueckmeldungen-faelle.json). Enthält Frage- und Antworttexte: nur lokal verwenden')

    akten = befehle.add_parser('akten', help='Stufe Akten: Quellen und neuer Stand in den Akten (ohne Modell)')
    akten.add_argument('--welt', action='append', required=True, metavar='PFAD|NAME=PFAD')
    akten.add_argument('--rauschen', type=int, default=0, metavar='N', help='Anzahl unauffälliger Alltagsquellen')
    akten.add_argument('--seed', type=int, default=1)
    akten.add_argument('--modell-hintergrund', default='', metavar='SPEC',
                       help='lokales Modell der Rolle „hintergrund“: erzeugt zusätzlich die Lage (Ebene 3) und prüft sie; '
                            'ohne Angabe steht die Lage als „nicht gemessen“ im Bericht')
    akten.add_argument('--ausgabe', type=Path, metavar='DIR', help='Ordner für akten-<Zeit>.md')

    lint = befehle.add_parser('lint', help='Stufe Lint: erwartete Befunde gefunden, Fehlalarme (ohne Modell)')
    lint.add_argument('--welt', action='append', required=True, metavar='PFAD|NAME=PFAD')
    lint.add_argument('--rauschen', type=int, default=0, metavar='N', help='Anzahl unauffälliger Alltagsquellen')
    lint.add_argument('--seed', type=int, default=1)
    lint.add_argument('--ausgabe', type=Path, metavar='DIR', help='Ordner für lint-<Zeit>.md')

    pruefen = befehle.add_parser('pruefen', help='Nur die Welt gegen FORMAT.md prüfen')
    pruefen.add_argument('--welt', action='append', required=True, metavar='PFAD|NAME=PFAD')
    return haupt


def _pruefen(args) -> int:
    welten = lade_welten(args.welt)
    for welt in welten:
        print(f'{welt.name}: {len(welt.szenarien)} Szenarien, {len(welt.quellen)} Quellen, {len(welt.fragen)} Fragen, gültig.')
        for hinweis in welt.hinweise:
            print(f'  Hinweis: {hinweis}')
    return 0


def _lauf(args) -> int:
    from . import bericht
    from .lauf import Optionen, durchfuehren
    from .modell import ModellFehler

    optionen = Optionen(welten=tuple(args.welt), modell=args.modell, modell_hintergrund=args.modell_hintergrund, modell_frage=args.modell_frage, modell_pruefung=args.modell_pruefung, rauschen=args.rauschen, seed=args.seed,
                        nur=args.nur, einordnung=args.einordnung, plaetze=args.plaetze, ohne_akten=args.ohne_akten,
                        kontext_zeichen=args.kontext_zeichen, wortteile_jahre=args.wortteile_jahre,
                        lange_quellen=args.lange_quellen,
                        lange_mail=args.lange_mail_zeichen, lange_transkript=args.lange_transkript_zeichen,
                        ausgabe=args.ausgabe)
    try:
        ergebnis = durchfuehren(optionen, melden=lambda zeile: print(zeile, file=sys.stderr, flush=True))
    except ModellFehler as fehler:
        print(f'Modell: {fehler}', file=sys.stderr)
        return 2
    text = bericht.markdown(ergebnis)
    if args.ausgabe:
        json_pfad, md_pfad = bericht.schreibe(ergebnis, args.ausgabe)
        print(text)
        print(f'Bericht geschrieben: {md_pfad} und {json_pfad}', file=sys.stderr)
    else:
        print(text)
    return 0


def _faelle(args) -> int:
    from . import faelle, lokal

    meldungen = faelle.lese_meldungen(args.aus)
    daten = faelle.erzeuge(meldungen)
    ziel = faelle.schreibe(daten, args.ausgabe or faelle.STANDARD_AUSGABE)
    erledigt = sum(1 for m in meldungen if m.get('status') == 'erledigt')
    print(f'{len(meldungen)} Meldungen ({erledigt} erledigt, bleiben als Fälle): {len(daten["fragen"])} Fälle, '
          f'{len(daten["nicht_messbar"])} ohne messbare Aussage. Geschrieben: {ziel}', file=sys.stderr)
    print('Hinweis: Die Datei enthält Frage- und Antworttexte aus deinem Kingfisher. Nur auf diesem Rechner '
          'verwenden, nicht weitergeben, nicht ins Repository legen.', file=sys.stderr)
    if not daten['fragen']:
        print('Noch kein messbarer Fall: Es fehlt „Richtig wäre …“ oder eine als falsch/veraltet gemeldete Antwort.',
              file=sys.stderr)
        return 0
    lokal.lade_fragen(ziel)   # dieselbe Prüfung wie bei „lokal“; ein Fehler erscheint hier, nicht erst bei der Messung
    print(f'Messen: python -m messlatte lokal --fragen {ziel}', file=sys.stderr)
    return 0


def _akten(args) -> int:
    from . import akten, aufnahme, handlungen, rauschen
    from .instanz import instanz_starten
    from .modell import ModellFehler, baue_anbieter, lese_modell

    welten = lade_welten(args.welt)
    try:
        hintergrund = baue_anbieter(lese_modell(args.modell_hintergrund)) if args.modell_hintergrund else None
    except ModellFehler as fehler:
        print(f'Modell: {fehler}', file=sys.stderr)
        return 2
    quellen = [q for w in welten for q in w.quellen]
    lauter = rauschen.erzeuge(args.rauschen, welten, args.seed)
    with instanz_starten(stichtag=welten[0].stichtag, zeitzone=welten[0].zeitzone,
                         eigene=tuple(welten[0].nutzer.adressen)) as instanz:
        aufgenommen = aufnahme.aufnehmen(instanz, [*quellen, *lauter], welten[0].stichtag, modell=akten.RegelEinordnung())
        handlungen.ausfuehren(instanz, welten, aufgenommen.episoden)
        print(f'aufgenommen: {aufgenommen.aufgenommen} Quellen ({aufgenommen.dauer_s} s)', file=sys.stderr, flush=True)
        text = akten.markdown(akten.messen(instanz, aufgenommen, lage_modell=hintergrund))
    print(text)
    if args.ausgabe:
        from datetime import datetime
        args.ausgabe.mkdir(parents=True, exist_ok=True)
        pfad = args.ausgabe / f"akten-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        pfad.write_text(text, encoding='utf-8')
        print(f'Bericht geschrieben: {pfad}', file=sys.stderr)
    return 0


def _lint(args) -> int:
    from . import akten, aufnahme, handlungen, lint, rauschen
    from .instanz import instanz_starten

    welten = lade_welten(args.welt)
    quellen = [q for w in welten for q in w.quellen]
    lauter = rauschen.erzeuge(args.rauschen, welten, args.seed)
    with instanz_starten(stichtag=welten[0].stichtag, zeitzone=welten[0].zeitzone,
                         eigene=tuple(welten[0].nutzer.adressen)) as instanz:
        aufgenommen = aufnahme.aufnehmen(instanz, [*quellen, *lauter], welten[0].stichtag, modell=akten.RegelEinordnung())
        handlungen.ausfuehren(instanz, welten, aufgenommen.episoden)
        print(f'aufgenommen: {aufgenommen.aufgenommen} Quellen ({aufgenommen.dauer_s} s)', file=sys.stderr, flush=True)
        text = lint.markdown(lint.messen(instanz, welten, aufgenommen), rauschen=len(lauter))
    print(text)
    if args.ausgabe:
        from datetime import datetime
        args.ausgabe.mkdir(parents=True, exist_ok=True)
        pfad = args.ausgabe / f"lint-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        pfad.write_text(text, encoding='utf-8')
        print(f'Bericht geschrieben: {pfad}', file=sys.stderr)
    return 0


def _lokal(args) -> int:
    from . import lokal

    fragen = lokal.lade_fragen(args.fragen)
    adresse = args.adresse or lokal.STANDARD_ADRESSE
    token = lokal.lese_token()
    print('Hinweis: Jede Frage legt in der laufenden Instanz ein Gespräch „Messlatte“ an; die Fragen werden dort '
          'wie im Betrieb als Gesprächsquellen festgehalten.', file=sys.stderr)
    if token is None:
        print('Hinweis: Kein Token gefunden (.kingfisher.env oder ICARUS_SIDECAR_TOKEN); die Instanz lehnt das '
              'wahrscheinlich ab.', file=sys.stderr)
    transport = lokal.oeffne(adresse, token)

    def zeigen(frage, antwort):
        print(f'\n[{frage.id}] {frage.frage}\n{antwort.text or "(keine Antwort) " + antwort.fehler}\n'
              f'-> Status {antwort.status or "-"}, {antwort.dauer_s} s', flush=True)

    try:
        ergebnis = lokal.messen(transport, fragen, zeigen=zeigen if args.zeigen else None)
    except lokal.KeineInstanz as fehler:
        print(str(fehler), file=sys.stderr)
        return 1
    finally:
        transport.close()
    text = lokal.markdown(ergebnis)
    print(text)
    if args.ausgabe:
        from datetime import datetime
        args.ausgabe.mkdir(parents=True, exist_ok=True)
        stempel = datetime.now().strftime('%Y%m%d-%H%M%S')
        (args.ausgabe / f'lokal-{stempel}.md').write_text(text, encoding='utf-8')
        (args.ausgabe / f'lokal-{stempel}.json').write_text(
            json.dumps(lokal.zu_dict(ergebnis), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Bericht ohne Inhalte geschrieben nach {args.ausgabe}', file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return {'lauf': _lauf, 'lokal': _lokal, 'pruefen': _pruefen, 'akten': _akten, 'faelle': _faelle,
                'lint': _lint}[args.befehl](args)
    except WeltFehler as fehler:
        print(fehler, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
