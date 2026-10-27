#!/usr/bin/env python3
"""Browserprobe für Paket T (Tempo): echte Oberfläche, echter Server, ein Skriptmodell mit künstlicher Verzögerung.

Startet den Sidecar mit der synthetischen Welt der Messlatte. Das lokale Modell ist eine Attrappe, die bei der
Quellenauswahl und bei den Sätzen absichtlich wartet (zusammen über 8 s); die Cloud ist eine zweite Attrappe. Kein
Netz, kein Ollama, kein bezahlter Aufruf. Geprüft wird in Chromium (Playwright):

1. Eine Frage auf Heute öffnet sofort das Gespräch, die eigene Frage steht sofort da, darunter der echte Schritt
   aus dem Server („Wählt Quellen …“, dann „Formuliert …“), keine Zeitangabe.
2. Unter der langsamen lokalen Antwort steht „Lokal dauert das. …“ samt dem, was dann an wen hinausginge, mit „Cloud einschalten“; der Knopf führt zum
   Schalter (er steht danach sichtbar im Fenster). „Nicht mehr zeigen“ nimmt den Satz weg, auch nach dem Neuladen.
3. Mit eingeschalteter Cloud (gültige Einwilligung) beantwortet die Cloud-Attrappe die Gedächtnisfrage: schnell,
   „Über Anthropic beantwortet.“, kein Satz zur Cloud. Ohne Einwilligung sieht die Cloud-Attrappe nichts.
4. Breiten 1280 und 390 px ohne seitliches Überlaufen, ein Bild dunkel; die Konsole bleibt leer.

Aufruf: `python scripts/probe_tempo_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npx vite build` in app/kingfisher).
"""
from __future__ import annotations

import argparse
import copy
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
FRAGE = 'Wer ist bei der Kreisklinik Rheingau jetzt für die Küche zuständig?'
AUSWAHL_S = 3.5
SAETZE_S = 5.0
EINWILLIGUNG = '2026-10-26T09:00:00+00:00'


class Lokal:
    """Lokales Skriptmodell: wählt alle S-Quellen, wartet bei Auswahl und Sätzen."""

    is_local = True
    name = 'skript'
    model = 'skript-lokal'
    supports_json = True

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory import satzantwort
        from icarus_memory.providers import Reply
        nutzer = json.loads(messages[-1]['content'])
        if satzantwort.ist_satzanfrage(messages):
            time.sleep(SAETZE_S)
            return Reply(text=json.dumps({'status': 'unklar', 'saetze': []}), model=self.model)
        time.sleep(AUSWAHL_S)
        ids = [q['id'] for q in nutzer['sources'] if q['id'].startswith('S')]
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': ids}), model=self.model)

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='Das weiß ich nicht.', model=self.model)


class Cloud:
    """Cloud-Attrappe: nur `complete`, nicht lokal; schnell; hält fest, was sie gesehen hätte."""

    is_local = False
    name = 'anthropic'
    model = 'cloud-attrappe'

    def __init__(self):
        from icarus_memory import gedaechtnis_cloud
        self.cloud_einwilligung = gedaechtnis_cloud.markierung('antwort', 'anthropic', EINWILLIGUNG)
        self.gesehen = []

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        self.gesehen.append(copy.deepcopy(messages))
        nutzer = json.loads(messages[-1]['content'])
        if 'sources' in nutzer:
            ids = [q['id'] for q in nutzer['sources'] if q['id'].startswith('S')]
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': ids}), model=self.model)
        return Reply(text=json.dumps({'status': 'unklar', 'saetze': []}), model=self.model)


UEBERLAUF_JS = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"


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
    lokal = Lokal()
    server.provider_from_env = lambda: lokal
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=lokal,
                         eigene=tuple(welt.nutzer.adressen)) as instanz:
        app = instanz.app
        aufnehmen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufnehmen.fehlgeschlagen == 0, aufnehmen
        from icarus_memory.akten_routes import nachfuehren
        nachfuehren(app, warten=True)
        port = freier_port()
        laufender = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        faden = threading.Thread(target=laufender.run, daemon=True)
        faden.start()
        for _ in range(100):
            if laufender.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])

            def neue_seite(breite, schema='light'):
                seite = browser.new_context(viewport={'width': breite, 'height': 900}, color_scheme=schema).new_page()
                seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}')
                         if m.type in ('error', 'warning') else None)
                seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
                seite.goto(basis + '/today')
                if not getattr(neue_seite, 'eingerichtet', False):
                    # Die Ersteinrichtung ist hier nicht Gegenstand: abschließen wie in probe_seiten_ui.py.
                    antwort = seite.request.put(basis + '/api/v1/einrichtung', data={'name': 'Lea', 'abgeschlossen': True})
                    assert antwort.ok, antwort.text()
                    neue_seite.eingerichtet = True
                    seite.goto(basis + '/today')
                return seite

            def bild(seite, name, **optionen):
                pfad = args.ausgabe / f'tempo-{name}.jpg'
                seite.screenshot(path=str(pfad), type='jpeg', quality=82, **optionen)
                ergebnis['bilder'].append(str(pfad))

            def fragen_auf_heute(seite, breite, name, schema=''):
                feld = seite.locator('.today-command :is(textarea, input)').first
                feld.wait_for(timeout=20000)
                feld.fill(FRAGE)
                start = time.monotonic()
                seite.get_by_role('button', name='Nachricht senden').click()
                seite.wait_for_url('**/conversations/*', timeout=5000)
                seite.locator('article.message.user', has_text=FRAGE).wait_for(timeout=3000)
                pruef[f'{name}_frage_sichtbar_nach_s'] = round(time.monotonic() - start, 2)
                assert pruef[f'{name}_frage_sichtbar_nach_s'] < 3, 'Die Frage muss sofort dastehen'
                seite.locator('.warte-zeile', has_text='Wählt Quellen').wait_for(timeout=6000)
                pruef[f'{name}_schritt_1'] = seite.locator('.warte-zeile').inner_text()
                assert 's' not in pruef[f'{name}_schritt_1'].replace('Wählt Quellen', '').strip(' …'), 'keine Zeitangabe'
                pruef[f'{name}_ueberlauf_warten'] = seite.evaluate(UEBERLAUF_JS)
                # Während der Antwort steht über der eigenen Frage kein Ladeplatzhalter (das Gespräch ist gesperrt).
                assert seite.locator('.skeleton-message, .conversation-empty').count() == 0
                bild(seite, f'warten-{breite}{schema}')
                seite.locator('.warte-zeile', has_text='Formuliert').wait_for(timeout=8000)
                pruef[f'{name}_schritt_2'] = seite.locator('.warte-zeile').inner_text()
                seite.locator('p.lokal-langsam').wait_for(timeout=20000)
                pruef[f'{name}_gesamt_s'] = round(time.monotonic() - start, 1)
                pruef[f'{name}_langsam_satz'] = seite.locator('p.lokal-langsam').inner_text()
                assert 'Lokal dauert das. Mit der Cloud ginge es in wenigen Sekunden.' in pruef[f'{name}_langsam_satz']
                assert 'Dann gingen deine Fragen und Inhalte deiner Mails an' in pruef[f'{name}_langsam_satz']
                assert seite.locator('article.message.user', has_text=FRAGE).count() == 1, 'die Frage steht einmal da'
                pruef[f'{name}_ueberlauf_antwort'] = seite.evaluate(UEBERLAUF_JS)
                seite.locator('p.lokal-langsam').scroll_into_view_if_needed()
                bild(seite, f'langsam-{breite}{schema}')

            # 1 + 2: Heute → Gespräch, Zwischenstand, Satz zur Cloud (1280 px, hell)
            seite = neue_seite(1280)
            fragen_auf_heute(seite, 1280, 'breit')
            gespraech = seite.url
            seite.get_by_role('button', name='Cloud einschalten').click()
            seite.wait_for_url('**/settings#darf', timeout=5000)
            seite.locator('#darf-cloud').wait_for(timeout=10000)
            time.sleep(0.6)
            pruef['schalter_im_fenster'] = seite.evaluate(
                "(() => { const r = document.getElementById('darf-cloud').getBoundingClientRect();"
                " return r.top >= 0 && r.bottom <= innerHeight; })()")
            assert pruef['schalter_im_fenster'], 'Der Knopf führt sichtbar zum Schalter'
            bild(seite, 'schalter-1280')
            seite.goto(gespraech)
            seite.locator('p.lokal-langsam').wait_for(timeout=10000)
            seite.get_by_role('button', name='Nicht mehr zeigen').click()
            assert seite.locator('p.lokal-langsam').count() == 0
            seite.reload()
            seite.locator('article.message.assistant').last.wait_for(timeout=10000)
            time.sleep(0.5)
            pruef['nach_wegklicken_weg'] = seite.locator('p.lokal-langsam').count() == 0
            assert pruef['nach_wegklicken_weg']
            seite.context.close()

            # 390 px hell und 1280 px dunkel: Warten und Satz zur Cloud
            schmal = neue_seite(390)
            fragen_auf_heute(schmal, 390, 'schmal')
            schmal.context.close()
            dunkel = neue_seite(1280, 'dark')
            fragen_auf_heute(dunkel, 1280, 'dunkel', '-dunkel')
            dunkel.context.close()

            # 3: Cloud mit gültiger Einwilligung beantwortet die Gedächtnisfrage
            cloud = Cloud()
            app.state.settings.model_roles = {'antwort': {'modell': '', 'cloud': True, 'anbieter': 'anthropic',
                                                          'cloud_einwilligung': EINWILLIGUNG}}
            app.state.agent._provider = cloud
            seite = neue_seite(1280)
            feld = seite.locator('.today-command :is(textarea, input)').first
            feld.wait_for(timeout=20000)
            feld.fill(FRAGE)
            start = time.monotonic()
            seite.get_by_role('button', name='Nachricht senden').click()
            seite.wait_for_url('**/conversations/*', timeout=5000)
            seite.locator('p.cloud-vermerk').wait_for(timeout=15000)
            pruef['cloud_gesamt_s'] = round(time.monotonic() - start, 1)
            pruef['cloud_vermerk'] = seite.locator('p.cloud-vermerk').inner_text()
            assert pruef['cloud_vermerk'] == 'Über Anthropic beantwortet.'
            assert seite.locator('p.lokal-langsam').count() == 0
            pruef['cloud_sah_frage'] = any(FRAGE in json.dumps(m, ensure_ascii=False) for m in cloud.gesehen)
            assert pruef['cloud_sah_frage']
            seite.locator('p.cloud-vermerk').scroll_into_view_if_needed()
            bild(seite, 'cloud-1280')
            seite.context.close()

            # Schalter aus: die Cloud sieht nichts mehr
            vorher = len(cloud.gesehen)
            app.state.settings.model_roles = {'antwort': {'modell': '', 'cloud': False, 'anbieter': '',
                                                          'cloud_einwilligung': ''}}
            kennung = app.state.conversations.create('Ohne Cloud').id
            seite = neue_seite(1280)
            r = seite.request.post(f'{basis}/api/v1/conversations/{kennung}/messages',
                                   data={'message': FRAGE, 'answer_mode': 'auto'}, timeout=60000)
            assert r.status == 201, r.text()
            pruef['ohne_einwilligung_cloud_aufrufe'] = len(cloud.gesehen) - vorher
            assert pruef['ohne_einwilligung_cloud_aufrufe'] == 0
            pruef['ohne_einwilligung_status'] = r.json()['messages'][-1]['metadata']['context'].get(
                'answer_contract', {}).get('status')
            seite.context.close()
            browser.close()
        laufender.should_exit = True
        faden.join(timeout=5)
    for name in ('breit', 'schmal', 'dunkel'):
        for art in ('warten', 'antwort'):
            assert pruef[f'{name}_ueberlauf_{art}'] <= 0, (name, art, pruef[f'{name}_ueberlauf_{art}'])
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'tempo-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder'],
                      'pruefungen': pruef}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
