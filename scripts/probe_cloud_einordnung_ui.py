#!/usr/bin/env python3
"""Browserprobe für „Neue Mails in der Cloud einordnen“ (Einstellungen → Was Kingfisher darf): echte Oberfläche, echter
Sidecar, Ollama als Attrappe, Schlüsselspeicher als Datei, Claude-Zugang als Attrappe (nur gespeichert, nie gerufen),
kein Netz.

Geprüft wird in Chromium (Playwright):

* Der Schalter ist aus; bei ihm steht, was den Rechner verlässt; vorne kein Fachwort (Liste aus `gliederung.ts`).
* Einschalten ohne vorbereiteten Zugang: ein Satz mit dem Verweis auf KI & Modelle, nichts gespeichert.
* Mit vorbereitetem Zugang (Attrappe über `PUT /api/v1/models/cloud-access/anthropic`): der Satz des Sidecars muss
  angehakt sein, erst dann geht der Knopf; danach die Statuszeile mit Modell und Aufrufen, die Rolle trägt die
  Einwilligung, der Anbieter der Rolle bleibt lokal.
* Ausschalten mit einem Klick: „Einordnen läuft wieder nur auf diesem Rechner.“, Einwilligung erloschen.
* Bilder bei 1280 und 390 px; die Konsole bleibt ohne Fehler.

Aufruf: `python scripts/probe_cloud_einordnung_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
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
TITEL = 'Neue Mails in der Cloud einordnen'


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def fachwoerter_aus_gliederung() -> list[str]:
    quelltext = (WURZEL / 'app' / 'kingfisher' / 'src' / 'Einstellungen' / 'gliederung.ts').read_text(encoding='utf-8')
    block = quelltext.split('export const FACHWOERTER', 1)[1].split('];', 1)[0]
    return re.findall(r'"([^"]+)"', block)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    daten = tempfile.mkdtemp(prefix='probe-cloud-einordnung-')
    os.environ.update(ICARUS_DATA_DIR=daten, ICARUS_PROVIDER='ollama', ICARUS_MODEL='standard-modell',
                      ICARUS_BASE_URL='http://127.0.0.1:11434/v1', ICARUS_SECRETS_PASSPHRASE='probe-passphrase-synthetisch')
    for name in ('ICARUS_SIDECAR_TOKEN', 'OPENAI_API_KEY', 'LLM_API_KEY', 'ANTHROPIC_API_KEY',
                 'ICARUS_PREPARED_ANTHROPIC_API_KEY', 'KINGFISHER_USER_NAME'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import providers
    from icarus_memory.secrets import Keychain
    from icarus_memory.cloud_import_provider import AnthropicImportProvider
    from tests.ollama_fake import FakeOllama

    Keychain._detect = lambda self: 'file'  # der Schlüsselspeicher der Probe ist eine Datei im Probeverzeichnis
    AnthropicImportProvider._client = lambda self: (_ for _ in ()).throw(AssertionError('kein Netz in der Probe'))
    fake = FakeOllama(installiert=['standard-modell', 'bge-m3'], cloud=[])
    providers.verfuegbare_modelle = lambda *a, **k: [n if ':' in n else n + ':latest' for n in fake.installiert]
    from icarus_memory.server import create_app
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
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    fach = fachwoerter_aus_gliederung()

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        seite = browser.new_context(viewport={'width': 1280, 'height': 1000}).new_page()
        seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

        def oeffne(breite: int = 1280):
            seite.set_viewport_size({'width': breite, 'height': 1000})
            seite.goto(basis + '/settings#darf')
            seite.reload()
            seite.wait_for_selector('#settings-darf:not([hidden])')
            schalter().wait_for(timeout=15000)
            time.sleep(0.5)

        def bild(name: str):
            pfad = args.ausgabe / f'cloud-einordnung-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def schalter():
            return seite.get_by_role('switch', name=re.compile(re.escape(TITEL)))

        def rolle():
            zeilen = seite.request.get(basis + '/api/v1/models/roles').json()['rollen']
            return next(z for z in zeilen if z['rolle'] == 'hintergrund')

        def darf_text():
            return seite.locator('#settings-darf').inner_text()

        # 1. Aus, mit Satz, ohne Fachwort
        oeffne()
        assert not schalter().is_checked(), 'der Schalter muss aus sein'
        assert 'Jede neue Mail verlässt den Rechner vollständig, an Anthropic (Claude)' in darf_text()
        funde = [w for w in fach if re.search(rf'(?<![\wäöüÄÖÜß]){re.escape(w)}(?![\wäöüÄÖÜß])', darf_text(), re.I)]
        pruef['fachwoerter_vorne'] = funde
        assert not funde, f'Fachwort vorne: {funde}'
        pruef['aus_ist_vorgabe'] = rolle()['cloud_einordnung'] == {'aktiv': False, 'modell': '', 'seit': None, 'heute': 0,
                                                                   'tagesbudget': 300, 'erschoepft': False, 'zugang_da': False}
        assert pruef['aus_ist_vorgabe'], rolle()['cloud_einordnung']
        bild('aus-1280')

        # 2. Einschalten ohne Zugang: ein Satz, ein Verweis, nichts gespeichert
        schalter().click()
        seite.wait_for_selector('#settings-darf >> text=Dafür braucht es den vorbereiteten Claude-Zugang')
        gruppe = seite.get_by_role('group', name='Cloud-Einordnung einschalten')
        assert gruppe.get_by_role('link', name=re.compile('KI & Modelle')).get_attribute('href') == '#ki'
        assert seite.get_by_role('button', name='Cloud-Einordnung einschalten').count() == 0
        bild('ohne-zugang-1280')
        seite.get_by_role('button', name='Verstanden').click()
        assert not rolle()['wahl']['cloud'] and rolle()['cloud_einordnung']['aktiv'] is False
        pruef['ohne_zugang_satz'] = True

        # 3. Zugang als Attrappe vorbereiten (nur gespeichert, nie gerufen), dann mit Zustimmung einschalten
        antwort = seite.request.put(basis + '/api/v1/models/cloud-access/anthropic',
                                    data={'api_key': 'sk-ant-synthetisch-fuer-die-probe', 'model': 'claude-synthetic'})
        assert antwort.ok, antwort.text()
        oeffne()
        assert rolle()['cloud_einordnung']['zugang_da'] is True and not schalter().is_checked()
        schalter().click()
        knopf = seite.get_by_role('button', name='Cloud-Einordnung einschalten')
        knopf.wait_for(timeout=15000)
        assert knopf.is_disabled(), 'ohne Zustimmung geht nichts'
        satz = seite.get_by_label(re.compile('Ich willige ein'))
        text = satz.locator('xpath=..').inner_text()
        assert 'an Anthropic (Claude API)' in text and '300 Aufrufe am Tag' in text and text.strip().endswith('Ich willige ein.')
        pruef['zustimmungssatz'] = text.strip()
        satz.check()
        assert not knopf.is_disabled()
        bild('frage-1280')
        knopf.click()
        seite.wait_for_selector('#settings-darf >> text=Neue Mails werden über Anthropic (claude-synthetic) eingeordnet. Heute 0 von 300 Aufrufen.')
        assert schalter().is_checked()
        zeile = rolle()
        assert zeile['wahl']['cloud'] and zeile['wahl']['anbieter'] == 'anthropic' and zeile['wahl']['einwilligung_gueltig']
        assert zeile['cloud_einordnung']['aktiv'] is True and zeile['cloud_einordnung']['modell'] == 'claude-synthetic'
        assert zeile['wirksam']['lokal'] is True, 'der Anbieter der Rolle bleibt lokal'
        pruef['an'] = zeile['cloud_einordnung']
        bild('an-1280')
        oeffne()
        assert schalter().is_checked() and 'Heute 0 von 300 Aufrufen' in darf_text()
        pruef['an_bleibt_nach_neuladen'] = True

        # 4. Ausschalten mit einem Klick
        schalter().click()
        seite.wait_for_selector('#settings-darf >> text=Einordnen läuft wieder nur auf diesem Rechner.')
        assert not schalter().is_checked()
        zeile = rolle()
        assert not zeile['wahl']['cloud'] and zeile['cloud_einordnung']['aktiv'] is False and zeile['cloud_einordnung']['zugang_da'] is True
        pruef['aus_mit_einem_klick'] = True
        bild('wieder-aus-1280')

        # 5. 390 px: Schalter, Frage und Status ohne Überlauf
        oeffne(390)
        schalter().click()
        seite.get_by_role('button', name='Cloud-Einordnung einschalten').wait_for(timeout=15000)
        seite.get_by_label(re.compile('Ich willige ein')).check()
        bild('frage-390')
        seite.get_by_role('button', name='Cloud-Einordnung einschalten').click()
        seite.wait_for_selector('#settings-darf >> text=Heute 0 von 300 Aufrufen')
        breite = seite.evaluate('() => document.documentElement.scrollWidth - document.documentElement.clientWidth')
        pruef['ueberlauf_390'] = breite
        assert breite <= 0, f'Seite {breite} px breiter als das Fenster'
        bild('an-390')
        schalter().click()
        seite.wait_for_selector('#settings-darf >> text=Einordnen läuft wieder nur auf diesem Rechner.')
        browser.close()

    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'cloud-einordnung-ergebnis.json').write_text(json.dumps(ergebnis, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(ergebnis, indent=2, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
