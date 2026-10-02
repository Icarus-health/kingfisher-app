#!/usr/bin/env python3
"""Browserprobe für den Rückkanal „Stimmt nicht?“: echte Oberfläche, echter Server, ein skriptbares Modell.

Startet den Sidecar mit der synthetischen Welt der Messlatte und dem Skriptmodell der Satzantwort-Probe,
stellt eine Frage über die Konversations-API und öffnet das Gespräch in Chromium (Playwright):

* unter der Antwort steht still „Stimmt nicht?“; der Klick öffnet die Rückfrage mit den fünf Arten,
* Art wählen, „Richtig wäre …“ schreiben, „Melden“ → „Gemerkt.“ (und die Meldung trägt Belege und Modellstand),
* Einstellungen → Rückmeldungen: Anzahl, offene, Frage und Art; „Erledigt“ setzt sie um,
* „Als Prüffragen speichern“ lädt eine Datei, die `messlatte.lokal` lesen kann und in der die
  erledigte Meldung als Fall bleibt,
* die Konsole bleibt leer.

Aufruf: `python scripts/probe_rueckkanal_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
Screenshots und `rueckkanal-probe.json` liegen danach in DIR; sie enthalten nur synthetische Texte.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_satzantwort_ui import CHROMIUM, FRAGEN, Skript, freier_port  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from messlatte import aufnahme, lokal
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=Skript(),
                         eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufnehmen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufnehmen.fehlgeschlagen == 0, aufnehmen
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
            kontext = browser.new_context(viewport={'width': 1100, 'height': 900}, accept_downloads=True)
            seite = kontext.new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            seite.goto(basis + '/today')  # setzt die Sitzung für /api

            def bild(name):
                pfad = args.ausgabe / f'rueckkanal-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            kennung = seite.request.post(basis + '/api/v1/conversations', data={}).json()['conversation']['id']
            antwort = seite.request.post(f'{basis}/api/v1/conversations/{kennung}/messages',
                                         data={'message': FRAGEN['wandel'], 'answer_mode': 'auto'})
            assert antwort.status == 201, antwort.text()

            # 1. still, dann offen
            seite.goto(f'{basis}/conversations/{kennung}')
            seite.wait_for_selector('.satzantwort', timeout=15000)
            link = seite.get_by_role('button', name='Stimmt nicht?')
            assert link.count() == 1, 'genau ein „Stimmt nicht?“ (unter der Antwort, nicht unter der Frage)'
            assert seite.locator('article.message.user button:has-text("Stimmt nicht?")').count() == 0
            bild('1-still')
            link.click()
            gruppe = seite.get_by_role('group', name='Was stimmt an dieser Antwort nicht?')
            gruppe.wait_for(timeout=5000)
            arten = gruppe.get_by_role('button').all_inner_texts()
            pruef['arten'] = arten
            assert arten == ['Falsch', 'Unvollständig', 'Veraltet', 'Zu langsam', 'Etwas anderes'], arten
            assert seite.get_by_role('button', name='Melden').is_disabled(), 'ohne Art kein Melden'
            # 2. Art wählen, freier Text, melden
            gruppe.get_by_role('button', name='Veraltet').click()
            assert gruppe.get_by_role('button', name='Veraltet').get_attribute('aria-pressed') == 'true'
            seite.get_by_label('Richtig wäre', exact=False).fill('12. November 2026')
            bild('2-offen')
            seite.get_by_role('button', name='Melden').click()
            seite.get_by_text('Gemerkt.').wait_for(timeout=5000)
            pruef['gemerkt'] = True
            bild('3-gemerkt')
            meldungen = seite.request.get(basis + '/api/v1/rueckmeldungen').json()
            assert meldungen['zaehlung'] == {'gesamt': 1, 'offen': 1, 'erledigt': 0}, meldungen['zaehlung']
            (meldung,) = meldungen['meldungen']
            pruef['meldung'] = {k: meldung[k] for k in ('art', 'richtig', 'status')}
            pruef['belege'] = len(meldung['belege'])
            pruef['saetze'] = len(meldung['struktur'].get('saetze', []))
            pruef['modellrollen'] = sorted(meldung['modell'])
            assert (meldung['art'], meldung['richtig']) == ('veraltet', '12. November 2026')
            assert meldung['frage'] == FRAGEN['wandel'] and meldung['belege'] and pruef['saetze'] >= 1
            assert {'antwort', 'frage', 'hintergrund'} <= set(meldung['modell'])
            # Nichts geht ins Gedächtnis: keine offenen Vorschläge durch die Meldung.
            assert instanz.app.state.proposals.counts().get('pending', 0) == 0, instanz.app.state.proposals.counts()

            # 3. Liste in den Einstellungen
            seite.goto(basis + '/settings#technik-rueckmeldungen')
            seite.reload()
            abschnitt = seite.get_by_role('region', name='Rückmeldungen').last
            abschnitt.get_by_text('1 Meldung, 1 offen.').wait_for(timeout=5000)
            text = abschnitt.inner_text()
            pruef['liste'] = text
            assert 'Veraltet' in text and 'Richtig wäre: 12. November 2026' in text and FRAGEN['wandel'][:40] in text, text
            bild('4-liste')
            abschnitt.get_by_role('button', name='Erledigt').click()
            abschnitt.get_by_text('1 Meldung, alle erledigt.').wait_for(timeout=5000)
            assert abschnitt.get_by_role('button', name='Erledigt').count() == 0
            bild('5-erledigt')
            # 4. Export: Datei, die die Messlatte liest; die erledigte Meldung bleibt als Fall
            with seite.expect_download(timeout=10000) as download:
                abschnitt.get_by_role('button', name='Als Prüffragen speichern').click()
            ziel = args.ausgabe / 'rueckmeldungen-faelle.json'
            download.value.save_as(str(ziel))
            seite.get_by_text('Gespeichert als rueckmeldungen-faelle.json').wait_for(timeout=5000)
            fragen = lokal.lade_fragen(ziel)
            pruef['export'] = {'faelle': len(fragen), 'name': download.value.suggested_filename,
                               'erwartet': [list(g) for g in fragen[0].erwartet.aussagen], 'schwere': fragen[0].schwere}
            assert len(fragen) == 1 and fragen[0].erwartet.aussagen == (('12. November 2026',),)
            assert fragen[0].verboten.aussagen and 'Regressionstest' in fragen[0].notiz
            bild('6-export')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'rueckkanal-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']}, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
