#!/usr/bin/env python3
"""Browserprobe für das zweite Tor der Satzprüfung: echte Oberfläche, echter Server, Skriptmodelle der Messlatte.

Startet den Sidecar mit der synthetischen Welt der Messlatte, einem unaufmerksamen Antwortmodell (schreibt zu jeder
Frage der Kategorie `inhalt` den richtigen und einen falschen Satz) und dem Skript-Prüfmodell (Rolle `pruefung`,
verwirft die falschen Sätze der Welt). Geprüft im Chromium:

* Pflanzbeet: Der falsche Satz fehlt, unter der Antwort steht „1 Satz verworfen (Prüfmodell).“, der Fuß nennt das
  Prüfmodell.
* Straßenfest: Die Quelle ist ein Jahr alt; hinter dem Satz steht gedämpft „(nur eine Quelle, von 2025)“.
* Einstellungen, Lokale KI: Schalter „Sätze vom Prüfmodell gegenprüfen“ mit einem Satz Erklärung; ausgeschaltet
  kommt der falsche Satz durch, und der Fuß sagt, dass das Prüfmodell aus ist.
* Die Konsole bleibt leer.

Aufruf: `python scripts/probe_pruefmodell_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
"""
from __future__ import annotations

import argparse
import json
import re
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
    from icarus_memory import agent_verdrahtung
    from messlatte import aufnahme
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.skript import WeltSkript
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    fragen = {f.id: f for f in welt.fragen}
    antwortmodell, pruefmodell = WeltSkript('unaufmerksam', welt.fragen), WeltSkript('pruefung', welt.fragen)
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=antwortmodell,
                         eigene=tuple(welt.nutzer.adressen)) as instanz:
        # Wie im Betrieb: Das Tor liest Einstellung und Modell der Rolle `pruefung` je Antwort (agent_verdrahtung).
        # Die Rolle ist hier mit dem Skript-Prüfmodell besetzt, damit Schalter und Modellkarte echt wirken.
        agent_verdrahtung.anbieter_fuer_pruefung = lambda rollen: pruefmodell
        instanz.agent._pruefung = lambda: agent_verdrahtung.pruef_tor(instanz.app)
        aufgenommen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufgenommen.fehlgeschlagen == 0, aufgenommen
        from icarus_memory.akten_routes import nachfuehren
        nachfuehren(instanz.app, warten=True)
        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(instanz.app, host='127.0.0.1', port=port, log_level='warning'))
        faden = threading.Thread(target=server.run, daemon=True)
        faden.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            seite = browser.new_context(viewport={'width': 1100, 'height': 900}).new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            seite.goto(basis + '/today')  # setzt die Sitzung für /api
            pruef = ergebnis['pruefungen']

            def fragen_stellen(frage_id):
                kennung = seite.request.post(basis + '/api/v1/conversations', data={}).json()['conversation']['id']
                antwort = seite.request.post(f'{basis}/api/v1/conversations/{kennung}/messages',
                                             data={'message': fragen[frage_id].frage, 'answer_mode': 'auto'})
                assert antwort.status == 201, antwort.text()
                return kennung

            def bild(name, element=None):
                pfad = args.ausgabe / f'pruefmodell-{name}.png'
                (element or seite).screenshot(path=str(pfad), **({} if element else {'full_page': True}))
                ergebnis['bilder'].append(str(pfad))

            def antwort_oeffnen(kennung):
                seite.goto(f'{basis}/conversations/{kennung}')
                seite.wait_for_selector('.satzantwort', timeout=15000)
                return seite.locator('.satzantwort').last

            # 1. Verworfen vom Prüfmodell
            richtig, falsch = fragen['inhalt-01'].skript.richtig, fragen['inhalt-01'].skript.falsch
            antwort = antwort_oeffnen(fragen_stellen('inhalt-01'))
            text = antwort.inner_text()
            pruef['verworfen'] = text
            assert richtig in text and falsch not in text, text
            assert '1 Satz verworfen (Prüfmodell).' in text, text
            antwort.locator('.satz-weg > summary').click()
            seite.wait_for_function("document.querySelector('.satz-weg').open === true")
            assert 'dazu von einem Prüfmodell' in antwort.inner_text()
            bild('verworfen')

            # 2. Nebensatz zur Verlässlichkeit (eine Quelle, ein Jahr alt)
            antwort = antwort_oeffnen(fragen_stellen('inhalt-05'))
            satz = antwort.locator('.satz-liste li p').first
            pruef['nebensatz'] = satz.inner_text()
            neben = antwort.locator('.satz-verlaesslichkeit')
            assert neben.count() == 1 and neben.inner_text().strip() == '(nur eine Quelle, von 2025)', pruef['nebensatz']
            farbe = neben.evaluate('e => getComputedStyle(e).color')
            text_farbe = satz.evaluate('e => getComputedStyle(e).color')
            pruef['nebensatz_farbe'] = [farbe, text_farbe]
            assert farbe != text_farbe, 'gedämpft, nicht wie der Satz'
            bild('nebensatz', antwort)

            # 3. Schalter unter Einstellungen, Lokale KI
            seite.goto(basis + '/settings#technik-antwortzeiten')
            seite.reload()
            schalter = seite.get_by_role('switch', name=re.compile('Sätze vom Prüfmodell gegenprüfen'))
            schalter.wait_for(timeout=15000)
            bereich = seite.locator('.antwortzeiten')
            pruef['schalter_text'] = bereich.inner_text()
            assert schalter.is_checked() and 'prüft jeden Satz noch einmal gegen seine Belege' in pruef['schalter_text']
            bild('schalter', bereich)
            schalter.focus()
            seite.keyboard.press('Space')
            seite.wait_for_selector('text=prüft kein Prüfmodell mehr mit', timeout=15000)
            assert not schalter.is_checked()
            pruef['schalter_api'] = seite.request.get(basis + '/api/v1/antwortzeiten').json()['pruefung']
            assert pruef['schalter_api']['zustand'] == 'aus'
            antwort = antwort_oeffnen(fragen_stellen('inhalt-01'))
            text = antwort.inner_text()
            pruef['ohne_tor'] = text
            assert falsch in text and 'verworfen (Prüfmodell)' not in text, text
            antwort.locator('.satz-weg > summary').click()
            assert 'Das Prüfmodell ist ausgeschaltet.' in antwort.inner_text()
            bild('ohne-tor')
            # wieder an
            seite.goto(basis + '/settings#technik-antwortzeiten')
            seite.reload()
            schalter = seite.get_by_role('switch', name=re.compile('Sätze vom Prüfmodell gegenprüfen'))
            schalter.wait_for(timeout=15000)
            assert not schalter.is_checked(), 'der Schalter bleibt nach dem Neuladen aus'
            schalter.focus()
            seite.keyboard.press('Space')
            seite.wait_for_selector('text=prüft ab der nächsten Frage wieder jeden Satz', timeout=15000)
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'pruefmodell-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']}, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
