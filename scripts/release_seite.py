#!/usr/bin/env python3
"""Fassung prüfen und Download-Seite bauen, für den Release-Workflow (.github/workflows/release.yml, docs/53).

    python3 scripts/release_seite.py pruefen --tag v1.2.0
        Prüft, dass der Tag `v` + Inhalt von `VERSION` ist und dass `docs/fassungen/<fassung>.md` Neuerungen hat.
        Gibt die Fassung aus; sonst ein Satz, was nicht stimmt, und Rückgabewert 1.

    python3 scripts/release_seite.py bauen --fassung 1.2.0 --repo Icarus-health/kingfisher-app --ausgabe _site [--datum …]
        Schreibt die Download-Seite (aus `site/index.html`), `latest.json`, das App-Zeichen und die Schrift nach
        `--ausgabe`. Das Manifest hat genau die Form, die der Sidecar annimmt (`icarus_memory/fassung.py`).

Nur die Standardbibliothek; läuft ohne installierten Sidecar.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
BILD_PRAEFIX = 'ghcr.io/icarus-health/kingfisher-app:'
SEMVER = re.compile(r'(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
#: Die Fassung der App, die mindestens nötig ist, um diese Fassung per Knopf zu laden. Steht in der Notiz der Fassung
#: als Zeile `App mindestens: 1.0.0`; ohne die Zeile genügt jede App.
APP_MINDESTENS = re.compile(r'^App mindestens:\s*(\S+)\s*$', re.M)
MONATE = ('Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November',
          'Dezember')
ZEICHEN = 'design-source/01_Brand/Approved/App_Icon_Exports/kingfisher-app-icon-256.png'
SCHRIFTEN = ('Inter-Regular.ttf', 'Inter-SemiBold.ttf')
SCHRIFT_ORDNER = 'design-source/07_Coding_Package/Fonts'


class Fehler(Exception):
    """Ein Satz für den Menschen, der den Release anstößt."""


def notiz(fassung: str, wurzel: Path = WURZEL) -> Path:
    return wurzel / 'docs' / 'fassungen' / f'{fassung}.md'


def hinweise(text: str) -> list[str]:
    """Eine Zeile je Spiegelstrich (`- …` oder `* …`) auf oberster Ebene; Folgezeilen gehören dazu."""
    ergebnis: list[str] = []
    for zeile in text.splitlines():
        treffer = re.match(r'^[-*]\s+(.+)$', zeile)
        if treffer:
            ergebnis.append(treffer.group(1).strip())
        elif ergebnis and zeile.startswith('  ') and zeile.strip():
            ergebnis[-1] += ' ' + zeile.strip()
        elif not zeile.strip() and ergebnis:
            continue
    return ergebnis


def pruefen(tag: str, wurzel: Path = WURZEL) -> str:
    fassung = (wurzel / 'VERSION').read_text(encoding='utf-8').strip()
    if not SEMVER.fullmatch(fassung):
        raise Fehler(f'VERSION enthält „{fassung}“; erwartet ist eine Fassung wie 1.2.0 (ohne „v“).')
    if tag != f'v{fassung}':
        raise Fehler(f'Der Tag {tag} passt nicht zu VERSION ({fassung}). Erwartet ist der Tag v{fassung}.')
    datei = notiz(fassung, wurzel)
    if not datei.is_file() or not hinweise(datei.read_text(encoding='utf-8')):
        raise Fehler(f'Es fehlen die Neuerungen: docs/fassungen/{fassung}.md mit mindestens einem Spiegelstrich.')
    return fassung


def manifest(fassung: str, repo: str, datum: str, text: str) -> dict:
    if not SEMVER.fullmatch(fassung) or not REPO.fullmatch(repo):
        raise Fehler(f'Fassung „{fassung}“ oder Repository „{repo}“ ist ungültig.')
    app = APP_MINDESTENS.search(text)
    app_mindestens = app.group(1) if app else '1.0.0'
    if not SEMVER.fullmatch(app_mindestens):
        raise Fehler(f'„App mindestens: {app_mindestens}“ ist keine Fassung wie 1.0.0.')
    neu = hinweise(text)
    if not neu or len(neu) > 20 or any(len(h) > 300 for h in neu):
        raise Fehler('Die Neuerungen brauchen ein bis zwanzig Spiegelstriche mit höchstens 300 Zeichen.')
    date.fromisoformat(datum)
    return {
        'fassung': fassung,
        'datum': datum,
        'image': BILD_PRAEFIX + fassung,
        'dmg': f'https://github.com/{repo}/releases/download/v{fassung}/Kingfisher.dmg',
        'hinweise': neu,
        'app_mindestens': app_mindestens,
    }


def datum_text(datum: str) -> str:
    tag = date.fromisoformat(datum)
    return f'{tag.day}. {MONATE[tag.month - 1]} {tag.year}'


def seite(vorlage: str, daten: dict, repo: str) -> str:
    ersetzungen = {
        '{{DMG_LATEST}}': html.escape(f'https://github.com/{repo}/releases/latest/download/Kingfisher.dmg'),
        '{{FASSUNG}}': html.escape(daten['fassung']),
        '{{DATUM}}': html.escape(datum_text(daten['datum'])),
        '{{REPO}}': html.escape(f'https://github.com/{repo}'),
        '{{NEU}}': '\n'.join(f'      <li>{html.escape(h)}</li>' for h in daten['hinweise']),
    }
    for platzhalter, wert in ersetzungen.items():
        vorlage = vorlage.replace(platzhalter, wert)
    if '{{' in vorlage:
        raise Fehler('In site/index.html steht noch ein unbekannter Platzhalter.')
    return vorlage


def bauen(fassung: str, repo: str, ausgabe: Path, datum: str | None = None, wurzel: Path = WURZEL) -> dict:
    datum = datum or date.today().isoformat()
    daten = manifest(fassung, repo, datum, notiz(fassung, wurzel).read_text(encoding='utf-8'))
    ausgabe.mkdir(parents=True, exist_ok=True)
    (ausgabe / 'index.html').write_text(seite((wurzel / 'site' / 'index.html').read_text(encoding='utf-8'), daten, repo),
                                        encoding='utf-8')
    (ausgabe / 'latest.json').write_text(json.dumps(daten, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(wurzel / ZEICHEN, ausgabe / 'kingfisher.png')
    for schrift in SCHRIFTEN:
        shutil.copyfile(wurzel / SCHRIFT_ORDNER / schrift, ausgabe / schrift)
    # GitHub Pages soll die Dateien so ausliefern, wie sie sind.
    (ausgabe / '.nojekyll').write_text('', encoding='utf-8')
    return daten


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    befehle = parser.add_subparsers(dest='befehl', required=True)
    p = befehle.add_parser('pruefen')
    p.add_argument('--tag', required=True)
    b = befehle.add_parser('bauen')
    b.add_argument('--fassung', required=True)
    b.add_argument('--repo', required=True)
    b.add_argument('--ausgabe', type=Path, required=True)
    b.add_argument('--datum')
    args = parser.parse_args(argv)
    try:
        if args.befehl == 'pruefen':
            print(pruefen(args.tag))
        else:
            daten = bauen(args.fassung, args.repo, args.ausgabe, args.datum)
            print(json.dumps(daten, ensure_ascii=False))
    except (Fehler, ValueError, OSError) as fehler:
        print(fehler, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
