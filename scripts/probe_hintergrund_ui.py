#!/usr/bin/env python3
"""Browserprobe für „Hintergrund ohne Nacht“: echte Oberfläche, echter Server, synthetische Welt der Messlatte.

Prüft in Chromium (Playwright):

* Startseite: „Kingfisher lernt gerade“ mit der Gesamtzeile „x von y Quellen, fertig etwa …“ und dem Satz
  „Es geht schneller, wenn der Rechner heute anbleibt.“; „Pausieren“ und „Weiter“ wirken und überdauern
  (Zustand in `hintergrund.json`),
* eine Taste in der Oberfläche lässt den Hintergrund zurücktreten (Sperre „nutzer“), Abfragen im Takt nicht,
* Assistent `/willkommen?schritt=autostart`: Frage mit einem Satz, Schalter aus; ohne Helfer entfällt der Schritt
  (Befund 26); mit gemeldetem Helfer schaltbar; die Launch-Agent-Datei entsteht (gegen einen
  temporären Ordner) erst nach dem Klick,
* die Konsole bleibt leer.

Die Messpunkte der Rate und ein Teil der erledigten Einordnung werden synthetisch gesetzt, damit die Schätzung
sichtbar ist; es läuft kein Modell. Aufruf: `python scripts/probe_hintergrund_ui.py --ausgabe DIR [--chromium PFAD]`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_satzantwort_ui import CHROMIUM, Skript, freier_port  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from messlatte import aufnahme
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    spec = importlib.util.spec_from_file_location('mac_autostart', WURZEL / 'scripts/mac_autostart.py')
    helfer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helfer)

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=Skript(),
                         eigene=tuple(welt.nutzer.adressen)) as instanz:
        app = instanz.app
        aufnehmen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufnehmen.fehlgeschlagen == 0, aufnehmen
        # Freigabe wie nach dem Start der Mailaufnahme, lokales Modell.
        app.state.settings.schedule.enabled = True
        app.state.settings.schedule.with_model = True
        ep = app.state.episodes
        with ep._lock:
            ids = [r[0] for r in ep._conn.execute(
                "SELECT id FROM episodes WHERE kind IN ('message','document','event') ORDER BY id")]
            # Die Aufnahme der Messlatte ordnet mit Regeln alles ein; für die Probe sind zwei Drittel wieder offen.
            for kennung in ids[len(ids) // 3:]:
                ep._conn.execute("DELETE FROM working_memory_sources WHERE episode_id=?", (kennung,))
            ep._conn.commit()
        steuerung = app.state.hintergrund
        jetzt = time.time()
        # Gemessen: etwa sechs Quellen je Stunde Laufzeit (eine Stunde am Stück).
        steuerung._zustand['proben'] = [[jetzt - 3600 + i * 60, i / 10] for i in range(61)]
        pruef['schlange'] = steuerung.schlange()

        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        threading.Thread(target=server.run, daemon=True).start()
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

            def bild(name):
                pfad = args.ausgabe / f'hintergrund-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            seite.goto(basis + '/today')
            # Die Einrichtung gilt als durchlaufen; sonst führt die leere Welt ohne Konten in den Assistenten.
            seite.request.put(basis + '/api/v1/einrichtung', data={'abgeschlossen': True})
            pruef['api_stand'] = seite.request.get(basis + '/api/v1/hintergrund').json()['zustand']
            seite.goto(basis + '/today')
            try:
                seite.locator('section.lernt').wait_for(timeout=15000)
            except Exception:
                bild('fehler-startseite')
                raise
            karte = seite.locator('section.lernt')
            karte.wait_for(timeout=15000)
            seite.wait_for_function("document.querySelector('section.lernt')?.textContent.includes('Quellen')", timeout=15000)
            text = karte.inner_text()
            pruef['startseite_text'] = text
            pruef['gesamtzeile'] = ' von ' in text and 'Quellen, fertig etwa' in text
            pruef['satz_anbleiben'] = 'Es geht schneller, wenn der Rechner heute anbleibt.' in text
            # Zehn Sekunden ohne Eingabe, die Seite fragt derweil im Takt nach: Das darf den Hintergrund nicht anhalten.
            steuerung.aktivitaet._letzte = float('-inf')
            seite.wait_for_timeout(10000)
            pruef['abfragen_sind_keine_eingabe'] = steuerung.sperre() is None
            bild('startseite')

            seite.keyboard.press('Shift')
            for _ in range(50):
                if steuerung.sperre() == 'nutzer':
                    break
                time.sleep(0.1)
            pruef['taste_haelt_an'] = steuerung.sperre() == 'nutzer'

            karte.get_by_role('button', name='Pausieren').click()
            seite.wait_for_function("document.querySelector('section.lernt')?.textContent.includes('pausiert')", timeout=10000)
            pruef['pausiert_sichtbar'] = 'Quellen, pausiert' in karte.inner_text()
            pruef['pause_gespeichert'] = json.loads((Path(app.state.hintergrund._datei)).read_text())['pausiert'] is True
            bild('pausiert')
            karte.get_by_role('button', name='Weiter').click()
            seite.wait_for_function("document.querySelector('section.lernt')?.textContent.includes('fertig etwa')", timeout=10000)
            pruef['weiter_wirkt'] = not steuerung.pausiert

            # Assistent ohne Helfer: Der Schritt „Kingfisher beim Anmelden starten?“ entfällt (Fremdprobe, Befund 26);
            # ein Verweis auf ihn führt zum ersten offenen Schritt.
            seite.goto(basis + '/willkommen?schritt=autostart')
            seite.locator('.erststart-karte h1').wait_for(timeout=10000)
            pruef['ohne_helfer_ausgeblendet'] = seite.get_by_role('heading', name='Kingfisher beim Anmelden starten?').count() == 0 \
                and seite.locator('.erststart-punkte', has_text='Beim Anmelden').count() == 0
            bild('autostart-ohne-helfer')

            # Ein Helfer meldet sich (wie scripts/mac_autostart.py) und bekommt ohne Klick keine Antwort.
            agenten = Path(tempfile.mkdtemp()) / 'LaunchAgents'
            aufruf = helfer.programm('/usr/bin/python3', WURZEL / 'scripts', 'kingfisher-probe', Path('/tmp/probe.env'), basis)

            def helfer_takt(eingerichtet):
                antwort = seite.request.post(basis + '/api/v1/autostart/helfer',
                                             data={'plattform': 'macos', 'eingerichtet': eingerichtet},
                                             headers={'X-Icarus-Token': 'probe'}).json()
                return helfer.anwenden(antwort['gewuenscht'], agenten, aufruf, agenten.parent / 'log')

            pruef['ohne_klick_keine_datei'] = helfer_takt(False) is False and not helfer.pfad(agenten).exists()
            seite.goto(basis + '/willkommen?schritt=autostart')
            seite.get_by_role('heading', name='Kingfisher beim Anmelden starten?').wait_for(timeout=10000)
            schalter = seite.get_by_role('switch', name='Beim Anmelden starten')
            seite.wait_for_function("document.querySelector('.autostart-schalter input')?.disabled === false", timeout=15000)
            pruef['vorgabe_aus'] = not schalter.is_checked()
            bild('autostart-frage')
            schalter.click()
            seite.wait_for_function("document.querySelector('.autostart-meldung')?.textContent.includes('Wird eingerichtet')", timeout=10000)
            pruef['nach_klick_datei'] = helfer_takt(False) is True
            helfer_takt(True)
            seite.wait_for_function("document.querySelector('.autostart-meldung')?.textContent.includes('Eingerichtet')", timeout=15000)
            pruef['eingerichtet_sichtbar'] = True
            bild('autostart-eingerichtet')
            browser.close()
        server.should_exit = True
    ergebnis['ok'] = all(v is True for k, v in pruef.items() if isinstance(v, bool)) and not ergebnis['konsole']
    (args.ausgabe / 'hintergrund-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
