#!/usr/bin/env python3
"""Browserprobe für „Was Kingfisher aufgefallen ist“ (Lint über alle Akten, M2): echte Oberfläche, echter Server.

Startet den Sidecar mit der synthetischen Welt der Messlatte (`messlatte/welt`, Stichtag der Welt, Regel-Einordnung
wie die Stufe Lint), führt aus, was der Nutzer der Welt selbst getan hat (Projekte, Zuordnungen, angenommene
Aussage), stößt den Lint an und öffnet Einstellungen → Gedächtnis in Chromium (Playwright). Geprüft wird:

* Die Liste zeigt je Befund einen Satz, die beteiligten Akten als Links und bei Widersprüchen zwei Knöpfe mit
  dem Wert darauf; ruhende Akten stehen gesammelt unten.
* „29.01.2027 gilt“ speichert den neuen Stand als Wissen (erst jetzt), der Punkt verschwindet, ein Satz sagt,
  was passiert ist. „„Fabrikweg 3“ bleibt“ lässt die angenommene Aussage stehen. „Ignorieren“ nimmt einen
  Hinweis aus der Liste.
* Ein Link öffnet die Akte. Die Konsole bleibt leer.

Aufruf: `python scripts/probe_lint_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel;
vorher `npm run build` in `app/kingfisher`).
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'


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
    from messlatte import aufnahme, handlungen
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufgenommen.fehlgeschlagen == 0, aufgenommen
        handlungen.ausfuehren(instanz, [welt], aufgenommen.episoden)
        # Wie die Stufe Lint: Die eigenen Adressen kennt das Produkt sonst aus den Konten.
        from icarus_memory import akten_routes
        from icarus_memory.akten import Akten
        from icarus_memory.bezuege import Bezuege
        app = instanz.app
        bezuege = Bezuege(instanz.episodes, workspace=app.state.workspace, eigene=lambda: list(instanz.eigene))
        app.state.akten_bausteine = (instanz.episodes, bezuege, Akten(
            instanz.episodes, bezuege, claims=instanz.claims,
            aufgaben=lambda sache, ids: akten_routes.aufgaben_zu(app, bezuege, sache, ids)))
        lauf = instanz.anfrage('POST', '/api/v1/lint')['lauf']
        aussagen_vorher = len(instanz.claims.all_claims(include_inactive=False))
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
        pruef['lauf'] = {k: lauf.get(k) for k in ('befunde', 'neu', 'vorschlaege')}
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            seite = browser.new_context(viewport={'width': 1280, 'height': 1000}).new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

            def bild(name):
                pfad = args.ausgabe / f'lint-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            def zum_gedaechtnis():
                seite.goto(basis + '/settings#technik-befunde')
                seite.reload()
                seite.wait_for_selector('.befunde-liste', timeout=15000)

            zum_gedaechtnis()
            liste = seite.locator('section.befunde')
            pruef['zahl'] = liste.locator('.befunde-zahl').inner_text()
            assert pruef['zahl'] == '5 Punkte, davon 2 zum Entscheiden.', pruef['zahl']
            saetze = liste.locator(':scope > .befunde-liste > .befund .befund-text').all_inner_texts()
            pruef['saetze_oben'] = saetze
            assert len(saetze) == 4 and saetze[0].startswith(('Frist „Belegungsplan“', 'Du hattest angenommen')), saetze
            assert liste.locator('.befunde-ruhend summary').inner_text() == '1 Akte ruht seit über einem Jahr'
            knoepfe = liste.locator('.befund-aktionen button').all_inner_texts()
            pruef['knoepfe'] = knoepfe
            for text in ('29.01.2027 gilt', '15.01.2027 gilt', '„Hafenstraße 8“ übernehmen', '„Fabrikweg 3“ bleibt'):
                assert text in knoepfe, (text, knoepfe)
            assert 'Fortbildungsreihe Hauswirtschaft' in liste.locator('.befund-akten').all_inner_texts()[0] or any(
                'Fortbildungsreihe Hauswirtschaft' in t for t in liste.locator('.befund-akten').all_inner_texts())
            bild('liste')
            # Neu gilt: erst dieser Klick macht aus dem Vorschlag Wissen.
            seite.get_by_role('button', name='29.01.2027 gilt').click()
            seite.wait_for_selector('text=Gespeichert: 29.01.2027 gilt jetzt.', timeout=10000)
            pruef['nach_neu'] = liste.locator('p[role=status]').all_inner_texts()
            assert seite.get_by_role('button', name='29.01.2027 gilt').count() == 0
            aussagen = instanz.claims.all_claims(include_inactive=False)
            pruef['aussagen'] = [a.statement for a in aussagen]
            assert len(aussagen) == aussagen_vorher + 1 and any('29.01.2027' in a.statement for a in aussagen)
            # Alt bleibt: die angenommene Aussage steht weiter.
            seite.get_by_role('button', name='„Fabrikweg 3“ bleibt').click()
            seite.wait_for_selector('text=„Fabrikweg 3“ bleibt, wie du es angenommen hattest.', timeout=10000)
            aussagen = instanz.claims.all_claims(include_inactive=False)
            assert len(aussagen) == aussagen_vorher + 1 and any('Fabrikweg 3' in a.statement for a in aussagen)
            # Ignorieren nimmt einen Hinweis aus der Liste.
            vorher = liste.locator(':scope > .befunde-liste > .befund').count()
            liste.locator(':scope > .befunde-liste > .befund').filter(has_text='Jens Arnold').get_by_role('button', name='Ignorieren').click()
            seite.wait_for_selector('text=Ignoriert.', timeout=10000)
            assert liste.locator(':scope > .befunde-liste > .befund').count() == vorher - 1
            pruef['zahl_danach'] = liste.locator('.befunde-zahl').inner_text()
            assert pruef['zahl_danach'] == '2 Punkte, nur zur Kenntnis.', pruef['zahl_danach']
            bild('nach-entscheidungen')
            # Nach dem Neuladen bleibt es so.
            zum_gedaechtnis()
            assert liste.locator('.befunde-zahl').inner_text() == '2 Punkte, nur zur Kenntnis.'
            # Ein Link öffnet die Akte.
            liste.locator('.befunde-ruhend summary').click()
            liste.locator('.befunde-ruhend').get_by_role('button', name='Akte öffnen: Holger Weidner').click()
            seite.wait_for_url('**/memory/akte/**', timeout=10000)
            pruef['akte_url'] = seite.url
            seite.wait_for_selector('text=Holger Weidner', timeout=15000)
            bild('akte')
            # Schmales Fenster: nichts läuft über den Rand.
            seite.set_viewport_size({'width': 900, 'height': 1000})
            zum_gedaechtnis()
            breite = seite.evaluate("document.querySelector('section.befunde').scrollWidth - document.querySelector('section.befunde').clientWidth")
            pruef['ueberlauf_900px'] = breite
            assert breite <= 1, breite
            bild('schmal')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'lint-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder'],
                      'pruefungen': ergebnis['pruefungen']}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
