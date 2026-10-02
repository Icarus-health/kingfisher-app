#!/usr/bin/env python3
"""Browserprobe für die Antwortzeit: echte Oberfläche, echter Server, ein skriptbares Modell mit Wartezeiten.

Startet den Sidecar mit der synthetischen Welt der Messlatte und einem Modell, das nach Skript antwortet und beim
Formulieren der Sätze wartet (kein Netz, kein Ollama). Geprüft wird in Chromium (Playwright):

* Zeile unter der Antwort („3,2 s · Suche 0,3 · Sätze 2,1“), nur wo Zeiten vorliegen (eine ältere Antwort ohne Zeiten
  zeigt nichts);
* eine langsame Antwort (mehr als 8 s durch den zweiten Modellaufruf) nennt die Ursache in einem Satz;
* Einstellungen, Lokale KI: die Tabelle (Median und 90-Prozent-Wert) und der Schalter für die Sätze; nach dem
  Ausschalten kommt die nächste Antwort im Zitatmodus und ohne Zeit für die Sätze; die Konsole bleibt leer.

Aufruf: `python scripts/probe_antwortzeit_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
Die Probe dauert etwa eine halbe Minute, weil eine Antwort absichtlich langsam ist.
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
FRAGEN = {
    'schnell': 'Wurde die Frist bei der Stiftung Zukunft Gesundheit geändert und wann ist sie jetzt?',
    'langsam': 'Wer ist bei der Kreisklinik Rheingau jetzt für die Küche zuständig?',
}
# Wartezeit des Modells beim Formulieren der Sätze, je Frage in Sekunden.
WARTEN = {'Stiftung Zukunft Gesundheit geändert': 0.6, 'Kreisklinik Rheingau': 8.6}


class Skript:
    """Ein lokales Modell mit festen Antworten; die Sätze brauchen Zeit (`WARTEN`)."""

    is_local = True
    name = 'skript'
    model = 'skript-probe'
    supports_json = True

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory import satzantwort
        from icarus_memory.providers import Reply
        nutzer = json.loads(messages[-1]['content'])
        if satzantwort.ist_satzanfrage(messages):
            for stichwort, sekunden in WARTEN.items():
                if stichwort in nutzer['anliegen']:
                    time.sleep(sekunden)
            return Reply(text=json.dumps(self.saetze(nutzer)), model=self.model)
        ids = [q['id'] for q in nutzer['sources'] if q['id'].startswith('S')]
        if 'Stiftung Zukunft Gesundheit geändert' in nutzer['question']:
            ids = [q['id'] for q in nutzer['sources'] if q['id'] in ids and any(
                w in q['title'] for w in ('Förderlinie', 'Einreichfrist', 'Verlängerung'))]
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': ids}), model=self.model)

    @staticmethod
    def saetze(nutzer):
        def nr(stichwort):
            return next(b['nr'] for b in nutzer['belege'] if stichwort in b['quelle'])

        if 'Stiftung Zukunft Gesundheit geändert' in nutzer['anliegen']:
            return {'status': 'antwort', 'saetze': [
                {'text': 'Die Einreichfrist wurde von 15. Oktober 2026 auf 12. November 2026 verlängert.',
                 'belege': [nr('Ausschreibung Förderlinie'), nr('Verlängerung der Einreichfrist')]}]}
        return {'status': 'unklar', 'saetze': []}

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='Das weiß ich nicht.', model=self.model)


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
    from messlatte import aufnahme
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright
    from icarus_memory import server

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    modell = Skript()
    # Der Schalter baut den Agenten neu (wie im Betrieb); dabei soll das Skriptmodell der Standardanbieter bleiben.
    server.provider_from_env = lambda: modell
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=modell,
                         eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufnehmen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufnehmen.fehlgeschlagen == 0, aufnehmen
        from icarus_memory.akten_routes import nachfuehren
        nachfuehren(instanz.app, warten=True)
        port = freier_port()
        laufender = uvicorn.Server(uvicorn.Config(instanz.app, host='127.0.0.1', port=port, log_level='warning'))
        faden = threading.Thread(target=laufender.run, daemon=True)
        faden.start()
        for _ in range(100):
            if laufender.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            seite = browser.new_context(viewport={'width': 1100, 'height': 900}).new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            seite.goto(basis + '/today')  # setzt die Sitzung für /api

            def fragen(frage: str) -> str:
                kennung = seite.request.post(basis + '/api/v1/conversations', data={}).json()['conversation']['id']
                antwort = seite.request.post(f'{basis}/api/v1/conversations/{kennung}/messages',
                                             data={'message': frage, 'answer_mode': 'auto'}, timeout=60000)
                assert antwort.status == 201, antwort.text()
                return kennung

            def bild(name: str, **optionen):
                pfad = args.ausgabe / f'antwortzeit-{name}.png'
                seite.screenshot(path=str(pfad), **optionen)
                ergebnis['bilder'].append(str(pfad))

            gespraeche = {name: fragen(frage) for name, frage in FRAGEN.items()}
            # Eine ältere Antwort ohne Zeiten, wie sie vor dieser Änderung gespeichert wurde.
            alt = instanz.app.state.conversations.create('Älter')
            instanz.app.state.conversations.add_message(alt.id, 'user', 'Eine ältere Frage')
            instanz.app.state.conversations.add_message(alt.id, 'assistant', 'Eine ältere Antwort ohne Zeiten.')

            # 1. Schnelle Antwort: Zeile mit Teilen, kein Ursachensatz
            seite.goto(f'{basis}/conversations/{gespraeche["schnell"]}')
            seite.wait_for_selector('.satzantwort', timeout=15000)
            zeile = seite.locator('p.antwortzeit').last.inner_text()
            pruef['zeile_schnell'] = zeile
            assert re.match(r'^\d,\d s · .*Sätze \d,\d', zeile), zeile
            assert seite.locator('.antwortzeit-ursache').count() == 0, 'schnelle Antwort ohne Ursachensatz'
            bild('zeile-schnell', full_page=True)

            # 2. Langsame Antwort: Ursache in einem Satz
            seite.goto(f'{basis}/conversations/{gespraeche["langsam"]}')
            seite.wait_for_selector('p.antwortzeit', timeout=15000)
            text = seite.locator('p.antwortzeit').last.inner_text()
            pruef['zeile_langsam'] = text
            assert 'Der zweite Modellaufruf für die Sätze brauchte' in text, text
            assert re.match(r'^\d+(,\d)? s · ', text), text
            bild('zeile-langsam', full_page=True)

            # 3. Ältere Antwort ohne Zeiten: keine Zeile
            seite.goto(f'{basis}/conversations/{alt.id}')
            seite.wait_for_selector('article.message.assistant', timeout=15000)
            pruef['zeile_alt'] = seite.locator('p.antwortzeit').count()
            assert pruef['zeile_alt'] == 0

            # 4. Einstellungen, Lokale KI: Tabelle und Schalter
            seite.goto(basis + '/settings#technik-antwortzeiten')
            seite.reload()
            seite.wait_for_selector('.antwortzeiten-tabelle', timeout=15000)
            tabelle = seite.locator('.antwortzeiten').inner_text()
            pruef['tabelle'] = tabelle
            for erwartet in ('Antwort insgesamt', 'Sätze formulieren', 'Median', 'Typisch sind', 'Gezählt sind die letzten 2 Antworten',
                             'Antworten formuliert: skript-probe'):
                assert erwartet in tabelle, (erwartet, tabelle)
            schalter = seite.get_by_role('switch', name=re.compile('Antworten in Sätzen formulieren'))
            assert schalter.is_checked()
            seite.locator('.antwortzeiten').screenshot(path=str(args.ausgabe / 'antwortzeit-einstellungen.png'))
            ergebnis['bilder'].append(str(args.ausgabe / 'antwortzeit-einstellungen.png'))

            # 5. Schalter aus: Zitatmodus, keine Zeit für die Sätze
            schalter.focus()
            seite.keyboard.press('Space')
            seite.wait_for_selector('text=Belege wörtlich', timeout=15000)
            pruef['schalter_aus_api'] = seite.request.get(basis + '/api/v1/models/roles').json()['saetze']
            assert pruef['schalter_aus_api'] == 'aus'
            neu = fragen(FRAGEN['schnell'])
            seite.goto(f'{basis}/conversations/{neu}')
            seite.wait_for_selector('article.message.assistant p.antwortzeit', timeout=15000)
            zeile = seite.locator('p.antwortzeit').last.inner_text()
            pruef['zeile_ohne_saetze'] = zeile
            assert 'Sätze' not in zeile and seite.locator('.satzantwort').count() == 0, zeile
            assert 'Quelle berichtet' in seite.locator('article.message.assistant').last.inner_text()
            bild('zeile-ohne-saetze', full_page=True)

            # 6. Der Schalter bleibt nach dem Neuladen aus; wieder einschalten
            seite.goto(basis + '/settings#technik-antwortzeiten')
            seite.reload()
            seite.wait_for_selector('.antwortzeiten-tabelle', timeout=15000)
            schalter = seite.get_by_role('switch', name=re.compile('Antworten in Sätzen formulieren'))
            assert not schalter.is_checked()
            assert 'Gezählt sind die letzten 3 Antworten' in seite.locator('.antwortzeiten').inner_text()
            schalter.focus()
            seite.keyboard.press('Space')
            seite.wait_for_selector('text=wieder in Sätzen', timeout=15000)
            assert seite.request.get(basis + '/api/v1/models/roles').json()['saetze'] == 'an'

            # 7. Schmale Anzeige: die Tabelle bleibt in ihrer Karte
            seite.set_viewport_size({'width': 390, 'height': 900})
            seite.goto(basis + '/settings#technik-antwortzeiten')
            seite.reload()
            seite.wait_for_selector('.antwortzeiten-tabelle', timeout=15000)
            # Die Einstellungsseite ist schon ohne diese Karte 1280 px breit (Bestand); geprüft wird nur die Karte selbst.
            pruef['karte_passt_in_ihr_umfeld'] = seite.evaluate(
                "(() => { const k = document.querySelector('.antwortzeiten'); "
                "return k.querySelector('table').getBoundingClientRect().right <= k.getBoundingClientRect().right + 1; })()")
            assert pruef['karte_passt_in_ihr_umfeld'], 'Tabelle ragt aus der Karte'
            seite.locator('.antwortzeiten').scroll_into_view_if_needed()
            bild('einstellungen-schmal')
            browser.close()
        laufender.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'antwortzeit-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder'],
                      'pruefungen': pruef}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
