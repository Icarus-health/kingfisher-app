#!/usr/bin/env python3
"""Browserprobe für das Logbuch (M2): echte Oberfläche, echter Server, synthetische Daten.

Startet den Sidecar mit einer leeren Instanz (Stichtag 30. September 2026, 7:10 Uhr, Europa/Berlin), legt synthetisch an,
was über Nacht geschah (41 Mails aufgenommen, zwei neue Akten, ein Widerspruch), setzt den letzten Blick auf den Abend
davor und öffnet das Briefing in Chromium (Playwright):

* Die drei Zeilen stehen ganz oben im Tagesbriefing, gedämpft, in Alltagssprache („Seit gestern Abend: …“).
* Neuladen lässt sie stehen (Sitzungsregel), die Konsole bleibt leer.
* Der stille Link „Verlauf“ klappt die Chronik nach Tagen auf; „Verlauf schließen“ klappt sie zu.
* Hell, dunkel und Telefonbreite: kein waagerechtes Scrollen, Text bleibt lesbar.

Aufruf: `python scripts/probe_logbuch_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
ZONE = 'Europe/Berlin'
STICHTAG = datetime(2026, 9, 30, 7, 10, tzinfo=ZoneInfo(ZONE))


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from messlatte.instanz import instanz_starten
    from playwright.sync_api import sync_playwright
    from tests.test_terminvorbereitung import ANNA, BEN, ICH, _mail

    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    with instanz_starten(stichtag=STICHTAG, zeitzone=ZONE, provider=None, eigene=(ICH.split('<')[1][:-1],)) as instanz:
        app = instanz.app
        from icarus_memory.akten_routes import nachfuehren
        buch = app.state.logbuch
        app.state.settings.einrichtung = {'name': 'Lea', 'schritte': {}, 'abgeschlossen': True}   # kein Erststart-Assistent
        abend = (STICHTAG - timedelta(hours=12, minutes=10)).timestamp()   # gestern 19:00
        buch._marke_setzen('angelegt', abend - 86400)
        buch._marke_setzen('blick', abend)
        buch._conn.commit()
        # Gestern war Anna schon da: der erste Abgleich setzt nur den Stand.
        _mail(app, 'Format', [('Das Plakat hätte ich gern im Format A2.', 'fact')], [ANNA, ICH], tage=30)
        nachfuehren(app, warten=True)
        # Über Nacht: Mails, eine neue Person, ein Widerspruch. Die Uhr des Logbuchs steht auf 7:00.
        buch._uhr = lambda: (STICHTAG - timedelta(minutes=10)).timestamp()
        _mail(app, 'Angebot', [('Das Angebot der Druckerei liegt bei 1.200 Euro.', 'status')], [BEN, ICH], tage=0)
        nachfuehren(app, warten=True)
        buch.vermerke('quellen', sorte='mail', anzahl=41)
        buch.vermerke('akte_neu', sache='projekt:mainz', name='Mainz')
        buch.vermerke('lint', befunde={'widerspruch': 1})
        buch.vermerke('vorschlag_erzeugt', sorte='task', id='v-synthetisch')
        vorher = buch.zaehlen()
        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        faden = threading.Thread(target=server.run, daemon=True)
        faden.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        pruef = ergebnis['pruefungen']
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])

            def neue_seite(breite=1440, farbe='light'):
                seite = browser.new_context(viewport={'width': breite, 'height': 900}, color_scheme=farbe).new_page()
                seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
                seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
                return seite

            def bild(seite, name):
                pfad = args.ausgabe / f'logbuch-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            seite = neue_seite()
            seite.goto(basis + '/today')
            try:
                seite.wait_for_selector('.tageslage-verlauf p', timeout=20000)
            except Exception:
                bild(seite, 'fehlschlag')
                print(seite.url, seite.inner_text('body')[:600], ergebnis['konsole'], file=sys.stderr)
                raise
            zeilen = seite.locator('.tageslage-verlauf p').all_inner_texts()
            pruef['zeilen'] = zeilen
            assert zeilen[0].startswith('Seit gestern Abend: 41 Mails aufgenommen, '), zeilen
            assert 'neue Akten (' in zeilen[0] and 'Projekt Mainz' in zeilen[0] and 'Ben Braun' in zeilen[0], zeilen   # Ben kam über das Nachführen, Mainz als Eintrag
            assert any('1 Widerspruch gefunden' in z for z in zeilen), zeilen
            assert any('1 neuer Vorschlag' in z for z in zeilen), zeilen
            assert len(zeilen) <= 3
            for fachwort in ('episode', 'claim', 'lint', 'proposal', 'sqlite', 'task'):
                assert fachwort not in ' '.join(zeilen).lower(), fachwort
            # Ganz oben: Die Zeilen stehen vor der Überschrift des Tages.
            oben = seite.evaluate("""() => {
              const v = document.querySelector('.tageslage-verlauf').getBoundingClientRect().top;
              const h = document.querySelector('#tageslage-titel').getBoundingClientRect().top;
              const farbe = getComputedStyle(document.querySelector('.tageslage-verlauf p')).color;
              const tinte = getComputedStyle(document.querySelector('#tageslage-titel')).color;
              return { verlaufOben: v < h, gedaempft: farbe !== tinte };
            }""")
            pruef['position'] = oben
            assert oben['verlaufOben'] and oben['gedaempft'], oben
            bild(seite, 'briefing')
            # Neuladen: dieselben Zeilen (Sitzungsregel), nichts wird leer.
            seite.reload()
            seite.wait_for_selector('.tageslage-verlauf p', timeout=20000)
            assert seite.locator('.tageslage-verlauf p').all_inner_texts() == zeilen
            pruef['neuladen_gleich'] = True
            # Der Verlauf: ruhig, nach Tagen.
            knopf = seite.get_by_role('button', name='Verlauf', exact=True)
            assert knopf.get_attribute('aria-expanded') == 'false'
            knopf.click()
            seite.wait_for_selector('.logbuch .logbuch-tag', timeout=10000)
            verlauf = seite.locator('.logbuch').inner_text()
            pruef['verlauf'] = verlauf
            assert 'HEUTE' in verlauf.upper() and '41 Mails aufgenommen' in verlauf and 'Mainz' in verlauf, verlauf
            assert seite.get_by_role('button', name='Verlauf schließen').count() == 1
            bild(seite, 'verlauf')
            seite.get_by_role('button', name='Verlauf schließen').click()
            assert seite.locator('.logbuch').count() == 0
            assert buch.zaehlen() == vorher, 'Anzeigen darf nichts ins Logbuch schreiben'
            pruef['anzeigen_schreibt_nichts'] = True
            # Dunkel und Telefonbreite.
            for name, breite, farbe in (('dunkel', 1440, 'dark'), ('telefon', 390, 'light')):
                s2 = neue_seite(breite, farbe)
                s2.goto(basis + '/today')
                s2.wait_for_selector('.tageslage-verlauf p', timeout=20000)
                s2.get_by_role('button', name='Verlauf', exact=True).click()
                s2.wait_for_selector('.logbuch .logbuch-tag', timeout=10000)
                breiter = s2.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
                pruef[f'{name}_waagerecht_scrollen'] = breiter
                if breiter:
                    bild(s2, f'{name}-ueberbreit')
                    print(name, s2.evaluate('''() => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
                      .slice(0, 8).map(e => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))'''), file=sys.stderr)
                assert not breiter, name
                bild(s2, name)
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'logbuch-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']}, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
