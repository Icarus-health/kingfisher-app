#!/usr/bin/env python3
"""Browserprobe für „Mitteilungen auf dem Mac“ (Etappe 5, docs/24-weg-zum-jarvis.md): echte Oberfläche, echter Sidecar,
ein Ollama aus Attrappe, leerer Bestand, kein Netz. Der Sidecar gibt sich als Mac-App aus (Attrappe der Laufumgebung),
denn nur dort lässt sich der Schalter einschalten.

Geprüft wird in Chromium (Playwright), bei 1280 und 390 px:

* Der Schalter steht unter „Was Kingfisher darf“ bei den anderen, ist aus, und sein Satz sagt, dass nichts den Rechner
  verlässt. Ohne Schalter kein Uhrzeitfeld.
* Einschalten: der Sidecar speichert `an`, das Uhrzeitfeld erscheint mit 07:30, der Wochen-Satz steht da.
* Uhrzeit auf 08:15 ändern und speichern: der Sidecar hat 08:15; eine Uhrzeit nach 21:00 Uhr lässt sich nicht speichern.
* Erlaubnis verweigert (Attrappe: die App meldet „abgelehnt“): der Hinweis mit den Systemeinstellungen steht da.
* Ausschalten: `an` ist wieder aus, Uhrzeitfeld weg.
* Ohne Mac (zweiter Lauf als Docker): der Schalter ist gesperrt und sagt ehrlich, dass es Mitteilungen hier nicht gibt.
* Konsole ohne Fehler.

Aufruf: `python scripts/probe_mitteilungen_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
TITEL = 'Mitteilungen auf dem Mac'


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def server_starten(art: str):
    import uvicorn
    from icarus_memory import laufumgebung, providers
    from icarus_memory.server import create_app
    from tests.ollama_fake import FakeOllama

    daten = tempfile.mkdtemp(prefix=f'probe-mitteilungen-{art}-')
    os.environ.update(ICARUS_DATA_DIR=daten, ICARUS_PROVIDER='ollama', ICARUS_MODEL='standard-modell',
                      ICARUS_BASE_URL='http://127.0.0.1:11434/v1')
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_ORS_KEY', 'ICARUS_GOOGLE_ROUTES_KEY', 'OPENAI_API_KEY', 'LLM_API_KEY',
                 'ANTHROPIC_API_KEY', 'KINGFISHER_USER_NAME'):
        os.environ.pop(name, None)
    fake = FakeOllama(installiert=['standard-modell', 'bge-m3'], cloud=[])
    providers.verfuegbare_modelle = lambda *a, **k: [n if ':' in n else n + ':latest' for n in fake.installiert]
    laufumgebung.system_art = lambda **k: art     # Attrappe: Mac-App oder Docker im Browser
    app = create_app()
    app.state.ollama_transport = fake.transport
    app.state.ollama_inventar.vergiss()
    port = freier_port()
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    return server, f'http://127.0.0.1:{port}'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        seite = browser.new_context(viewport={'width': 1280, 'height': 1000}).new_page()
        seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

        def bild(name: str):
            pfad = args.ausgabe / f'mitteilungen-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def karte():
            return seite.get_by_role('region', name=TITEL)

        def schalter(titel: str = TITEL):
            return seite.get_by_role('switch', name=re.compile(titel))

        def oeffne(basis: str, breite: int = 1280, titel: str = TITEL):
            seite.set_viewport_size({'width': breite, 'height': 1000})
            seite.goto(basis + '/settings#darf')
            seite.reload()
            seite.wait_for_selector('#settings-darf:not([hidden])')
            schalter(titel).wait_for(timeout=15000)
            time.sleep(0.4)

        def stand(basis: str) -> dict:
            return seite.request.get(basis + '/api/v1/mitteilungen/einstellung').json()

        # -- Als Mac-App --------------------------------------------------------------------------------------
        server, basis = server_starten('mac')
        oeffne(basis)
        titel = [s.get_attribute('aria-label') for s in seite.locator('#settings-darf .darf-zeile').all()]
        pruef['reihenfolge'] = titel
        assert titel.index(TITEL) == titel.index('Beim Anmelden starten') + 1, titel
        assert not schalter().is_checked(), 'Vorgabe aus'
        text = karte().inner_text()
        assert 'Es verlässt nichts den Rechner.' in text and 'Diese Woche keine Mitteilung.' in text, text
        assert seite.locator('#mitteilungen-morgens').count() == 0, 'ohne Schalter kein Uhrzeitfeld'
        pruef['aus'] = stand(basis)
        assert pruef['aus']['an'] is False and pruef['aus']['morgens'] == '07:30'
        bild('aus-1280')

        schalter().click()
        seite.wait_for_selector('#mitteilungen-morgens', timeout=15000)
        pruef['an'] = stand(basis)
        assert pruef['an']['an'] is True
        assert seite.locator('#mitteilungen-morgens').input_value() == '07:30'
        assert 'fragt beim nächsten Start' in karte().inner_text(), 'Erlaubnis noch unbekannt: der Satz dazu'
        bild('an-1280')

        seite.locator('#mitteilungen-morgens').fill('08:15')
        seite.get_by_role('button', name='Uhrzeit speichern').click()
        seite.wait_for_function("document.querySelector('[aria-label=\"Mitteilungen auf dem Mac\"]').innerText.includes('ab 08:15 Uhr')", timeout=15000)
        pruef['uhrzeit'] = stand(basis)
        assert pruef['uhrzeit']['morgens'] == '08:15'
        seite.locator('#mitteilungen-morgens').fill('21:30')
        assert seite.get_by_role('button', name='Uhrzeit speichern').is_disabled(), 'nach 21:00 Uhr nicht speicherbar'
        assert 'vor 21:00 Uhr' in karte().inner_text()
        pruef['zu_spaet_gesperrt'] = True
        seite.locator('#mitteilungen-morgens').fill('08:15')
        bild('uhrzeit-1280')

        # Die App meldet, dass der Mac die Erlaubnis verweigert hat (Attrappe für den Reporter).
        antwort = seite.request.post(basis + '/api/v1/mitteilungen/erlaubnis', data=json.dumps({'status': 'abgelehnt'}),
                                     headers={'content-type': 'application/json'})
        assert antwort.ok, antwort.status
        oeffne(basis)
        hinweis = 'Der Mac hat Mitteilungen für Kingfisher nicht erlaubt. Systemeinstellungen → Mitteilungen → Kingfisher.'
        assert hinweis in karte().inner_text(), karte().inner_text()
        pruef['erlaubnis_hinweis'] = True
        bild('erlaubnis-1280')

        oeffne(basis, 390)
        assert hinweis in karte().inner_text()
        ueberlauf = seite.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        pruef['ueberlauf_390'] = ueberlauf
        assert ueberlauf <= 0, f'waagerechtes Scrollen bei 390 px: {ueberlauf}'
        bild('erlaubnis-390')

        schalter().click()
        seite.wait_for_function("document.querySelector('#mitteilungen-morgens') === null", timeout=15000)
        pruef['wieder_aus'] = stand(basis)
        assert pruef['wieder_aus']['an'] is False and pruef['wieder_aus']['morgens'] == '08:15', 'aus, die Uhrzeit bleibt'
        assert hinweis not in karte().inner_text(), 'aus: kein Hinweis mehr'
        bild('aus-390')
        server.should_exit = True

        # -- Ohne Mac (Docker im Browser) ----------------------------------------------------------------------
        server, basis = server_starten('docker')
        oeffne(basis, titel='Mitteilungen auf dem Rechner')
        gesperrt = schalter('Mitteilungen auf dem Rechner')
        assert gesperrt.is_disabled(), 'ohne Mac-App gesperrt'
        text = seite.get_by_role('region', name='Mitteilungen auf dem Rechner').inner_text()
        assert 'Mitteilungen gibt es nur in der Kingfisher-App auf dem Mac, nicht im Browser mit Docker.' in text, text
        pruef['ohne_mac'] = True
        bild('docker-1280')
        server.should_exit = True
        browser.close()

    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'mitteilungen-ergebnis.json').write_text(json.dumps(ergebnis, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in ergebnis.items() if k != 'pruefungen'}, indent=2, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
