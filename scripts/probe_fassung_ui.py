#!/usr/bin/env python3
"""Browserprobe für Fassung und Update-Angebot (docs/53-download-und-updates.md): echte Oberfläche, echter Server.

Startet den Sidecar mit einer leeren Instanz als Fassung 1.0.0 und eine Attrappe der Download-Seite auf diesem Rechner,
die ein synthetisches `latest.json` für Fassung 1.2.0 ausliefert. Dann in Chromium (Playwright):

* **Kingfisher und du:** „Fassung 1.0.0“, Schalter „Nach neuen Fassungen sehen“ an, mit dem Satz über GitHub;
  „Jetzt nachsehen“ antwortet „Neue Fassung 1.2.0 ist da.“, und die Attrappe sah genau eine GET-Anfrage ohne Kekse.
  Ausschalten antwortet mit einem Satz und bleibt gespeichert.
* **Heute im Browser (ohne Brücke):** der ruhige Hinweis „Neue Fassung 1.2.0 ist da: …“ und statt des Knopfs
  „Öffne Kingfisher über die App, um zu aktualisieren.“
* **Heute im Fenster der App:** eine Attrappe für `window.webkit.messageHandlers.kingfisher` zeichnet auf. Der Knopf
  „Jetzt aktualisieren“ mit dem Satz vorher; der Klick schickt genau `{aktion, fassung, image}`. Läuft danach 1.2.0,
  sagt die Seite einmal „Kingfisher ist jetzt auf Fassung 1.2.0.“; läuft noch 1.0.0, „Das Update hat nicht geklappt;
  deine Daten sind gesichert.“
* **Neue App nötig:** statt des Knopfs ein Satz mit dem Weg zur Download-Seite.
* **Für Techniker:** „Updates ohne App“ nennt `make aktualisieren`.
* 390 px: kein waagerechtes Scrollen auf Heute und in den Einstellungen; die Konsole bleibt leer.

Aufruf: `python scripts/probe_fassung_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build` in `app/kingfisher`).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
ZONE = 'Europe/Berlin'
STICHTAG = datetime(2026, 10, 2, 8, 0, tzinfo=ZoneInfo(ZONE))
BILD = 'ghcr.io/icarus-health/kingfisher-app:1.2.0'
MANIFEST = {'fassung': '1.2.0', 'datum': '2026-10-02', 'image': BILD,
            'dmg': 'https://github.com/Icarus-health/kingfisher-app/releases/download/v1.2.0/Kingfisher.dmg',
            'hinweise': ['Das Briefing nennt jetzt Geburtstage aus deinem Kreis.', 'Akten lassen sich als Ordner lesen.'],
            'app_mindestens': '1.0.0'}
# Die Brücke der Mac-App als Attrappe: zeichnet jede Nachricht auf, auch über ein Neuladen hinweg.
BRUECKE = """
window.webkit = { messageHandlers: { kingfisher: { postMessage(nachricht) {
  const alt = JSON.parse(sessionStorage.getItem('bruecke') || '[]');
  alt.push(nachricht);
  sessionStorage.setItem('bruecke', JSON.stringify(alt));
} } } };
"""


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class DownloadSeite:
    """Die Download-Seite als Attrappe: liefert `latest.json` und schreibt jede Anfrage mit Kopfzeilen auf."""

    def __init__(self) -> None:
        self.manifest = dict(MANIFEST)
        self.anfragen: list[dict] = []
        seite = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seite.anfragen.append({'methode': 'GET', 'pfad': self.path, 'kopf': {k.lower(): v for k, v in self.headers.items()}})
                rumpf = json.dumps(seite.manifest).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Set-Cookie', 'spur=1')
                self.end_headers()
                self.wfile.write(rumpf)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/latest.json'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from messlatte.instanz import instanz_starten
    from playwright.sync_api import sync_playwright

    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    download = DownloadSeite()
    with instanz_starten(stichtag=STICHTAG, zeitzone=ZONE, provider=None) as instanz:
        app = instanz.app
        app.state.settings.einrichtung = {'name': 'Lea', 'schritte': {}, 'abgeschlossen': True}   # kein Erststart-Assistent
        os.environ['KINGFISHER_UPDATE_URL'] = download.url
        os.environ['KINGFISHER_FASSUNG'] = '1.0.0'
        from icarus_memory import fassung
        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        threading.Thread(target=server.run, daemon=True).start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        pruef = ergebnis['pruefungen']
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])

            def neue_seite(breite=1280, bruecke=False):
                kontext = browser.new_context(viewport={'width': breite, 'height': 900})
                if bruecke:
                    kontext.add_init_script(BRUECKE)
                seite = kontext.new_page()
                seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
                seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
                return seite

            def bild(seite, name):
                pfad = args.ausgabe / f'fassung-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            def kein_ueberlauf(seite, name):
                breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
                pruef[f'breite_{name}'] = breite
                assert breite[0] <= breite[1], f'{name}: waagerechtes Scrollen {breite}'

            # 1. Kingfisher und du: Fassung, Schalter, „Jetzt nachsehen“.
            seite = neue_seite()
            seite.goto(basis + '/settings#ich')
            feld = seite.locator('.fassung-einstellung')
            feld.wait_for(timeout=20000)
            seite.get_by_role('button', name='Jetzt nachsehen').wait_for(timeout=20000)
            pruef['einstellung_vorher'] = feld.inner_text()
            assert 'Fassung 1.0.0' in pruef['einstellung_vorher']
            assert 'Einmal am Tag fragt Kingfisher bei GitHub, ob es eine neue Fassung gibt. Über dich geht dabei nichts hinaus.' in pruef['einstellung_vorher']
            assert 'Noch nie nachgesehen.' in pruef['einstellung_vorher']
            assert seite.get_by_role('switch', name='Nach neuen Fassungen sehen').is_checked()
            assert download.anfragen == [], 'Lesen fragt nie nach außen'
            seite.get_by_role('button', name='Jetzt nachsehen').click()
            seite.wait_for_selector('.fassung-einstellung [role=status]:has-text("Neue Fassung 1.2.0 ist da.")', timeout=10000)
            pruef['einstellung_nachher'] = feld.inner_text()
            assert 'Zuletzt nachgesehen am' in pruef['einstellung_nachher']
            assert 'Öffne Kingfisher über die App, um zu aktualisieren.' in pruef['einstellung_nachher']
            pruef['anfragen'] = download.anfragen
            assert len(download.anfragen) == 1
            kopf = download.anfragen[0]['kopf']
            assert 'cookie' not in kopf and kopf['user-agent'] == 'Kingfisher', kopf
            bild(seite, 'einstellung')
            seite.get_by_role('switch', name='Nach neuen Fassungen sehen').click()
            seite.wait_for_selector('text=Kingfisher sieht nicht mehr von selbst nach.', timeout=10000)
            assert instanz.anfrage('GET', '/api/v1/fassung')['pruefen'] is False
            seite.get_by_role('switch', name='Nach neuen Fassungen sehen').click()
            seite.wait_for_selector('text=Kingfisher sieht einmal am Tag nach neuen Fassungen.', timeout=10000)
            # Für Techniker: der Befehl.
            seite.goto(basis + '/settings#technik-fassung')
            seite.wait_for_selector('text=make aktualisieren', timeout=20000)
            pruef['technik'] = seite.locator('text=make aktualisieren').first.inner_text()
            bild(seite, 'technik')

            # 2. Heute im Browser: Hinweis ohne Knopf.
            seite.goto(basis + '/today')
            hinweis = seite.locator('section.fassung-heute')
            hinweis.wait_for(timeout=20000)
            pruef['heute_browser'] = hinweis.inner_text()
            assert 'Neue Fassung 1.2.0 ist da: Das Briefing nennt jetzt Geburtstage aus deinem Kreis.' in pruef['heute_browser']
            assert 'Öffne Kingfisher über die App, um zu aktualisieren.' in pruef['heute_browser']
            assert hinweis.get_by_role('button').count() == 0
            bild(seite, 'heute-browser')

            # 3. Heute im Fenster der App: Knopf, Nachricht, Rückmeldung nach dem Neuladen.
            app_seite = neue_seite(bruecke=True)
            app_seite.goto(basis + '/today')
            hinweis = app_seite.locator('section.fassung-heute')
            hinweis.wait_for(timeout=20000)
            pruef['heute_app'] = hinweis.inner_text()
            assert 'Kingfisher sichert vorher deine Daten und ist etwa eine Minute weg.' in pruef['heute_app']
            knopf = hinweis.get_by_role('button', name='Jetzt aktualisieren')
            bild(app_seite, 'heute-app')
            knopf.click()
            app_seite.wait_for_selector('section.fassung-heute [role=status]', timeout=10000)
            pruef['nach_klick'] = hinweis.locator('[role=status]').inner_text()
            nachrichten = app_seite.evaluate("() => JSON.parse(sessionStorage.getItem('bruecke') || '[]')")
            pruef['bruecke'] = nachrichten
            assert nachrichten == [{'aktion': 'aktualisieren', 'fassung': '1.2.0', 'image': BILD}], nachrichten
            assert knopf.is_disabled()
            # Die App hat gesichert, das neue Bild gestartet und lädt die Seite neu.
            os.environ['KINGFISHER_FASSUNG'] = '1.2.0'
            app_seite.reload()
            app_seite.wait_for_selector('section.fassung-heute [role=status]', timeout=20000)
            pruef['nach_update'] = app_seite.locator('section.fassung-heute').inner_text()
            assert pruef['nach_update'] == 'Kingfisher ist jetzt auf Fassung 1.2.0.', pruef['nach_update']
            bild(app_seite, 'nach-update')
            app_seite.reload()
            app_seite.wait_for_selector('.today-command', timeout=20000)
            app_seite.wait_for_timeout(800)
            assert app_seite.locator('section.fassung-heute').count() == 0, 'die Rückmeldung kommt nur einmal'
            # Fehlschlag: Die alte Fassung läuft nach dem Neuladen noch.
            os.environ['KINGFISHER_FASSUNG'] = '1.0.0'
            app_seite.reload()
            app_seite.locator('section.fassung-heute').get_by_role('button', name='Jetzt aktualisieren').click()
            app_seite.wait_for_selector('section.fassung-heute [role=status]', timeout=10000)
            app_seite.reload()
            app_seite.wait_for_selector('section.fassung-heute [role=status]', timeout=20000)
            pruef['fehlschlag'] = app_seite.locator('section.fassung-heute [role=status]').inner_text()
            assert pruef['fehlschlag'] == 'Das Update hat nicht geklappt; deine Daten sind gesichert.', pruef['fehlschlag']
            bild(app_seite, 'fehlschlag')

            # 4. Neue App nötig: Weg zur Download-Seite statt Knopf.
            download.manifest = {**MANIFEST, 'app_mindestens': '1.1.0'}
            fassung.download_seite = lambda url=None: 'https://icarus-health.github.io/kingfisher-app/'   # die Attrappe hat kein HTTPS
            instanz.anfrage('POST', '/api/v1/fassung/pruefen')
            app_seite.reload()
            hinweis = app_seite.locator('section.fassung-heute')
            hinweis.wait_for(timeout=20000)
            pruef['neue_app'] = hinweis.inner_text()
            assert 'braucht Kingfisher eine neue App' in pruef['neue_app']
            assert hinweis.get_by_role('button').count() == 0
            link = hinweis.get_by_role('link', name='Zur Download-Seite')
            assert link.get_attribute('href') == 'https://icarus-health.github.io/kingfisher-app/'
            bild(app_seite, 'neue-app')
            download.manifest = dict(MANIFEST)
            instanz.anfrage('POST', '/api/v1/fassung/pruefen')

            # 5. Telefonbreite: kein waagerechtes Scrollen.
            schmal = neue_seite(390, bruecke=True)
            schmal.goto(basis + '/today')
            schmal.locator('section.fassung-heute').wait_for(timeout=20000)
            kein_ueberlauf(schmal, 'heute_390')
            bild(schmal, 'heute-390')
            schmal.goto(basis + '/settings#ich')
            schmal.get_by_role('button', name='Jetzt nachsehen').wait_for(timeout=20000)
            kein_ueberlauf(schmal, 'einstellung_390')
            bild(schmal, 'einstellung-390')
            browser.close()
        server.should_exit = True
    download.server.shutdown()
    ergebnis['fertig'] = True
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'fassung-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'pruefungen': ergebnis['pruefungen']},
                     ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
