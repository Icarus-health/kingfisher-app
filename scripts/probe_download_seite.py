#!/usr/bin/env python3
"""Browserprobe für die Download-Seite (site/index.html, docs/53-download-und-updates.md).

Baut die Seite wie der Release-Workflow (`scripts/release_seite.py bauen`, synthetisches Datum), liefert den Ordner
über einen lokalen Server aus und öffnet sie in Chromium bei 1280 und 390 px, hell und dunkel:

* Der Knopf „Für Mac laden“ zeigt auf `…/releases/latest/download/Kingfisher.dmg`; Fassung und Datum stehen da.
* Die drei Schritte mit den Links zu Docker Desktop und Ollama, der Weg an Gatekeeper vorbei für macOS 15 und älter.
* Kein Skript, keine Anfrage an eine andere Adresse als die eigene (keine Schrift, kein Bild, kein Zähler von außen).
* Kein waagerechtes Scrollen; die Konsole bleibt leer.

Aufruf: `python scripts/probe_download_seite.py --ausgabe DIR [--chromium PFAD]`.
"""
from __future__ import annotations

import argparse
import functools
import json
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / 'scripts'))
CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
REPO = 'Icarus-health/kingfisher-app'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import release_seite
    from playwright.sync_api import sync_playwright

    fassung = (WURZEL / 'VERSION').read_text(encoding='utf-8').strip()
    ordner = Path(tempfile.mkdtemp(prefix='download-seite-'))
    daten = release_seite.bauen(fassung, REPO, ordner, datum='2026-10-02')

    class Leise(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Leise, directory=str(ordner)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    basis = f'http://127.0.0.1:{server.server_address[1]}'

    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'fremd': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        for breite in (1280, 390):
            for farbe in ('light', 'dark'):
                seite = browser.new_context(viewport={'width': breite, 'height': 900}, color_scheme=farbe).new_page()
                seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
                seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
                seite.on('request', lambda r: ergebnis['fremd'].append(r.url) if not r.url.startswith(basis) else None)
                seite.goto(basis + '/index.html', wait_until='networkidle')
                name = f'{breite}-{farbe}'
                knopf = seite.get_by_role('link', name='Für Mac laden')
                assert knopf.get_attribute('href') == f'https://github.com/{REPO}/releases/latest/download/Kingfisher.dmg'
                text = seite.inner_text('body')
                assert f'Fassung {fassung} vom 2. Oktober 2026' in text, text[:400]
                assert '{{' not in seite.content()
                for satz in ('Docker Desktop installieren und einmal öffnen', 'Kingfisher.dmg öffnen und die App in „Programme“ ziehen',
                             'Ollama installieren', 'Datenschutz & Sicherheit', '„Dennoch öffnen“', 'Neue Fassungen kommen von selbst',
                             daten['hinweise'][0]):
                    assert satz in text, satz
                links = seite.eval_on_selector_all('a', 'as => as.map(a => a.href)')
                assert 'https://www.docker.com/products/docker-desktop/' in links and 'https://ollama.com/download' in links
                assert seite.locator('script').count() == 0, 'keine Skripte'
                masse = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
                pruef[f'breite_{name}'] = masse
                assert masse[0] <= masse[1], f'{name}: waagerechtes Scrollen {masse}'
                pruef[f'knopf_{name}'] = knopf.bounding_box()
                assert knopf.bounding_box()['height'] >= 44
                pfad = args.ausgabe / f'download-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))
                seite.context.close()
        browser.close()
    server.shutdown()
    manifest = json.loads((ordner / 'latest.json').read_text(encoding='utf-8'))
    pruef['manifest'] = manifest
    ergebnis['ok'] = not ergebnis['konsole'] and not ergebnis['fremd']
    (args.ausgabe / 'download-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: ergebnis[k] for k in ('ok', 'konsole', 'fremd', 'bilder')}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
