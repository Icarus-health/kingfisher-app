#!/usr/bin/env python3
"""Browserprobe für die Satzantwort (E3): echte Oberfläche, echter Server, ein skriptbares Modell.

Startet den Sidecar mit der synthetischen Welt der Messlatte (`messlatte/welt`, Stichtag der Welt) und einem
Modell, das nach Skript antwortet (kein Netz, kein Ollama), stellt drei Fragen über die Konversations-API und
öffnet die Gespräche in Chromium (Playwright):

* Frist verschoben: Sätze mit Belegnummern, „Weg nach unten“ mit der Akte, der überholten Quelle und dem Zitat.
* Nichts liegt vor: die ehrliche Antwort ohne Sätze.
* Modell unklar: Rückfall auf die Zitate, nichts Unbelegtes.
* Namensvetter und Zeitraum: Der „Weg nach unten“ nennt am Beleg, dass er zu einer anderen Person gleichen Namens
  gehört (mit Adresse) oder außerhalb des gefragten Zeitraums liegt (mit Datum), ruhig und gedämpft.

Geprüft werden Inhalt, Bedienung (Belegnummer öffnet den Weg nach unten) und dass die Konsole leer bleibt.
Aufruf: `python scripts/probe_satzantwort_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
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
FRAGEN = {
    'wandel': 'Wurde die Frist bei der Stiftung Zukunft Gesundheit geändert und wann ist sie jetzt?',
    'nichts': 'Was hat das Angebot für die Klinik Vogelsberg für 2026 gekostet?',
    'unklar': 'Wer ist bei der Kreisklinik Rheingau jetzt für die Küche zuständig?',
    'vetter': 'Was kostet das Catering von Alex Winter pro Person?',
    'zeitraum': 'Was lief letzte Woche mit dem Angebot für das Klinikum Rheingau-Süd?',
}


class Skript:
    """Ein lokales Modell mit festen Antworten je Frage (Auswahl: alle Quellen; Sätze: siehe `saetze`)."""

    is_local = True
    name = 'skript'
    model = 'skript-probe'
    supports_json = True

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory import satzantwort
        from icarus_memory.providers import Reply
        nutzer = json.loads(messages[-1]['content'])
        if satzantwort.ist_satzanfrage(messages):
            return Reply(text=json.dumps(self.saetze(nutzer)), model=self.model)
        ids = [q['id'] for q in nutzer['sources'] if q['id'].startswith('S')]
        if 'Stiftung Zukunft Gesundheit geändert' in nutzer['question']:
            # Wie ein Modell: nur die Quellen, die zur Frage gehören.
            ids = [q['id'] for q in nutzer['sources'] if q['id'] in ids and any(
                w in q['title'] for w in ('Förderlinie', 'Einreichfrist', 'Verlängerung'))]
        if 'Catering von Alex Winter' in nutzer['question']:
            # Ein Modell, das auch die Mail des Namensvetters wählt: sie trägt die Kennzeichnung, und die Prüfung lässt sie zu.
            ids = [q['id'] for q in nutzer['sources'] if q['id'] in ids and any(
                w in q['title'] for w in ('Preisanpassung', 'Einladung Gastvortrag'))]
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': ids}), model=self.model)

    @staticmethod
    def saetze(nutzer):
        frage = nutzer['anliegen']

        def nr(stichwort):
            return next(b['nr'] for b in nutzer['belege'] if stichwort in b['quelle'])

        if 'Stiftung Zukunft Gesundheit geändert' in frage:
            return {'status': 'antwort', 'saetze': [
                {'text': 'Die Einreichfrist wurde von 15. Oktober 2026 auf 12. November 2026 verlängert.',
                 'belege': [nr('Ausschreibung Förderlinie'), nr('Verlängerung der Einreichfrist')]},
                {'text': 'Die neue Einreichfrist endet am 12. November 2026 um 12 Uhr.',
                 'belege': [nr('Verlängerung der Einreichfrist')]},
                {'text': 'Die Frist ist der 15. November 2026.', 'belege': [nr('Verlängerung der Einreichfrist')]}]}
        if 'Catering von Alex Winter' in frage:
            return {'status': 'antwort', 'saetze': [
                {'text': 'Das Catering kostet 38 Euro pro Person.',
                 'belege': [nr('Preisanpassung'), nr('Einladung Gastvortrag')]}]}
        if 'letzte Woche mit dem Angebot' in frage:
            return {'status': 'antwort', 'saetze': [
                {'text': 'Das Gremium tagt am 21. Oktober.', 'belege': [nr('Gremium am 21. Oktober'), nr('Bindefrist des Angebots')]}]}
        if 'Vogelsberg' in frage:
            return {'status': 'nichts_vorliegend', 'saetze': []}
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
    from messlatte.instanz import TOKEN, instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
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
            seite = browser.new_context(viewport={'width': 1100, 'height': 900}).new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            seite.goto(basis + '/today')  # setzt die Sitzung für /api
            gespraeche = {}
            for schluessel, frage in FRAGEN.items():
                antwort = seite.request.post(basis + '/api/v1/conversations', data={})
                kennung = antwort.json()['conversation']['id']
                nachricht = seite.request.post(f'{basis}/api/v1/conversations/{kennung}/messages',
                                               data={'message': frage, 'answer_mode': 'auto'})
                assert nachricht.status == 201, nachricht.text()
                gespraeche[schluessel] = kennung
            pruef = ergebnis['pruefungen']

            def bild(name):
                pfad = args.ausgabe / f'satzantwort-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            for schluessel, kennung in gespraeche.items():
                nachrichten = seite.request.get(f'{basis}/api/v1/conversations/{kennung}').json()['messages']
                # Unter der eingefrorenen Uhr haben Frage und Antwort denselben Zeitstempel: die Assistentennachricht suchen.
                letzte = next(m for m in reversed(nachrichten) if m['role'] == 'assistant')
                kontext = (letzte.get('metadata') or {}).get('context') or {}
                pruef.setdefault('antworten', {})[schluessel] = {
                    'status': (kontext.get('answer_contract') or {}).get('status'), 'satzantwort': 'satzantwort' in kontext,
                    'anfang': letzte['content'][:160],
                    'satz': {k: v for k, v in ((kontext.get('working_answer') or {}).get('satzantwort') or {}).items()
                             if k in ('status', 'grund', 'gruende', 'verworfen', 'belege_ausgelassen')}}
            print(json.dumps(pruef['antworten'], ensure_ascii=False, indent=1), file=sys.stderr)
            # 1. Sätze mit Belegnummern und Weg nach unten
            seite.goto(f'{basis}/conversations/{gespraeche["wandel"]}')
            seite.wait_for_selector('.satzantwort', timeout=15000)
            saetze = seite.locator('.satz-liste li p').all_inner_texts()
            pruef['saetze'] = saetze
            assert any('von 15. Oktober 2026 auf 12. November 2026 verlängert' in s for s in saetze), saetze
            assert all('15. November' not in s for s in saetze), 'Der erfundene Satz muss fehlen'
            assert seite.locator('.satz-nr').count() >= 2
            offen_vorher = seite.locator('.satz-weg').get_attribute('open')
            seite.locator('button.satz-nr').first.click()
            seite.wait_for_function("document.querySelector('.satz-weg').open === true")
            pruef['belegnummer_oeffnet_weg'] = offen_vorher is None
            weg = seite.locator('.satz-weg').inner_text()
            pruef['weg_nach_unten'] = weg
            assert 'überholt durch [1]: 15. Oktober 2026 → 12. November 2026' in weg, weg
            assert 'Einreichfrist' in weg and 'verworfen' in seite.locator('.satzantwort').inner_text()
            bild('wandel')
            # 2. nichts liegt vor
            seite.goto(f'{basis}/conversations/{gespraeche["nichts"]}')
            seite.wait_for_selector('article.message.assistant', timeout=15000)
            text = seite.locator('article.message.assistant').last.inner_text()
            pruef['nichts'] = text
            assert 'keine Information vor' in text and seite.locator('.satzantwort').count() == 0, text
            bild('nichts')
            # 3. Rückfall auf Zitate
            seite.goto(f'{basis}/conversations/{gespraeche["unklar"]}')
            seite.wait_for_selector('article.message.assistant', timeout=15000)
            text = seite.locator('article.message.assistant').last.inner_text()
            pruef['zitate'] = text[:300]
            assert 'Quelle berichtet' in text and seite.locator('.satzantwort').count() == 0, text
            bild('zitate')
            # 4. Kennzeichnung: andere Person gleichen Namens, außerhalb des Zeitraums (ruhig, im Weg nach unten)
            for schluessel, erwartet in (('vetter', ('Andere Person gleichen Namens (Alex Winter, alex.winter@ifeh-hessen.example)',)),
                                         ('zeitraum', ('Außerhalb des gefragten Zeitraums (der letzten Woche): Quelle vom',))):
                seite.goto(f'{basis}/conversations/{gespraeche[schluessel]}')
                seite.wait_for_selector('.satzantwort', timeout=15000)
                seite.locator('.satz-weg > summary').click()
                seite.wait_for_function("document.querySelector('.satz-weg').open === true")
                weg = seite.locator('.satz-weg').inner_text()
                pruef[f'kennzeichnung_{schluessel}'] = weg
                for text in erwartet:
                    assert text in weg, (schluessel, weg)
                assert seite.locator('.satz-weg article.satz-ueberholt').count() == 1, (schluessel, weg)
                assert 'überholt durch' not in weg, weg
                bild(f'kennzeichnung-{schluessel}')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'satzantwort-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']}, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
