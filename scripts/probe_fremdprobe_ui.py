#!/usr/bin/env python3
"""Browserprobe zur Fremdprobe (docs/48-fremdprobe.md): die behobenen Befunde 3, 4, 5, 21, 23, 27, 29 und 30.

Echter Sidecar (`create_app()` unter uvicorn, frisches Datenverzeichnis), echte Oberfläche (`npm run build`), Chromium
über Playwright, und eine IMAP-Attrappe auf 127.0.0.1 (`sidecar/tests/imap_attrappe.py`), die je nach Schritt die
Anmeldung verweigert, schweigt oder nach der Anmeldung nicht mehr antwortet. Ein Anbieter „Probe-Post“ für
`example.org` zeigt auf die Attrappe; sonst gilt der Katalog aus `providers_mail.py`. Nur synthetische Zugänge
(`lena.probe@example.org`). Die Zeitgrenzen sind für die Probe auf wenige Sekunden gekürzt.

Geprüft wird im Browser:

* 27: „Schritt 1 von 6“ über sechs Punkten (ohne Helfer entfällt „Beim Anmelden“, Befund 26); der Knopf, der ein Feld zuklappt, heißt nicht „Fertig“.
* 21: Name tippen, „Später weitermachen“: der Name ist gespeichert.
* 3: falsches Passwort, schweigender Server: ein Satz mit Grund, kein „verbunden“; richtiges Passwort: verbunden.
* 4: „Mails einlesen“ bei einem Postfach, das nach der Anmeldung schweigt: sichtbarer Start, dann der Grund;
  danach mit antwortendem Postfach der Fortschritt.
* 5: Fertig-Seite bei schweigendem Postfach: „Dein Postfach antwortet nicht“ mit Knopf, kein „Dein Briefing ist
  bereit“; der Knopf führt zum Mail-Schritt, der den Grund und „neu verbinden“ zeigt.
* 23: „Zum Briefing“ öffnet das Briefing.
* 29: „Heute: …“ statt „Seit gestern Abend: …“ am Tag der Einrichtung.
* 30: „Verbindungen prüfen“ öffnet Einstellungen → Zugänge (die Postfächer).
* 9: Mit einem lokalen Modell (Ollama-Attrappe als HTTP-Dienst auf 127.0.0.1:11434) sagen Übersicht und „Lokale KI“
  dasselbe: „Bereit: …“, ohne „Anderer Anbieter“, „Keine Modellliste erreichbar“ oder „noch kein installiertes Modell“.
* 17: Die Fertig-Seite bietet Einlesen und Sortieren einmal an, vorausgewählt; nach „Zum Briefing“ laufen beide, und
  die Einstellungen sagen es.
* die Konsole bleibt ohne Fehler, außer den absichtlich ausgelösten Fehlantworten (422, 503), die getrennt stehen.

Aufruf: `python scripts/probe_fremdprobe_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build`).
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
ADRESSE = 'lena.probe@example.org'


MODELL = 'qwen3.5:4b'


def ollama_attrappe(modell: str):
    """Ein lokales Ollama als HTTP-Dienst auf 127.0.0.1:11434: Modellliste und Modellangaben, sonst nichts."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Dienst(BaseHTTPRequestHandler):
        def _json(self, daten: dict) -> None:
            roh = json.dumps(daten).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def do_GET(self) -> None:  # noqa: N802 - Name aus http.server
            if self.path == '/api/tags':
                self._json({'models': [{'name': modell, 'model': modell, 'size': 1, 'digest': '0' * 64,
                                        'details': {'format': 'gguf'}}]})
            elif self.path == '/v1/models':
                self._json({'data': [{'id': modell}]})
            else:
                self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path == '/api/show':
                self._json({'details': {'format': 'gguf'}, 'capabilities': ['completion'],
                            'model_info': {'general.architecture': 'qwen3', 'general.parameter_count': 4_000_000_000}})
            else:
                self.send_error(404)

        def log_message(self, *_: object) -> None:
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 11434), Dienst)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


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

    from tests.imap_attrappe import PASSWORT, ImapAttrappe
    attrappe = ImapAttrappe()
    # Eine Ollama-Attrappe als echter HTTP-Dienst auf dem Standardport, von Anfang an da (wie in der Fremdprobe).
    ollama = ollama_attrappe(MODELL)
    daten = tempfile.mkdtemp(prefix='probe-fremdprobe-')
    # Der Sidecar vertraut dem Zertifikat der Attrappe wie einem echten (ssl.create_default_context liest das).
    os.environ.update(ICARUS_DATA_DIR=daten, SSL_CERT_FILE=str(attrappe.zertifikat))
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'ICARUS_USER_NAME'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import logbuch, mail_anmeldung, mail_intake_routes, providers_mail, server
    from icarus_memory.providers_mail import MailProvider
    from icarus_memory.server import create_app

    providers_mail.PROVIDERS = (*providers_mail.PROVIDERS, MailProvider(
        id='probepost', label='Probe-Post', imap_host='127.0.0.1', smtp_host='127.0.0.1', imap_port=attrappe.port,
        domains=('example.org',), hint='Bei Probe-Post muss „IMAP“ eingeschaltet sein.'))
    mail_anmeldung.ZEITGRENZE = 3.0
    mail_intake_routes.ZEITGRENZE = 3.0
    server.POSTFACH_ZEITGRENZE = 2.0

    app = create_app()
    port = freier_port()
    uv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=uv.run, daemon=True).start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.1)
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        seite = browser.new_context(viewport={'width': 1280, 'height': 1000}).new_page()
        # Die Probe löst absichtlich Fehlantworten aus (abgelehnte Anmeldung 422, schweigendes Postfach 503). Chromium
        # meldet jede davon in der Konsole; sie stehen getrennt, jeder andere Konsolenfehler lässt die Probe scheitern.
        erwartet = re.compile(r'/api/v1/(integrations/mail|mail/intake/[^/]+/preview)$')
        ergebnis['erwartete_fehlantworten'] = []

        def konsole(m) -> None:
            if m.type != 'error':
                return
            ort = (m.location or {}).get('url', '')
            if m.text.startswith('Failed to load resource') and erwartet.search(ort):
                ergebnis['erwartete_fehlantworten'].append(f'{m.text} ({ort.removeprefix(basis)})')
            else:
                ergebnis['konsole'].append(f'{m.type}: {m.text} {ort}'.strip())
        seite.on('console', konsole)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

        def bild(name: str) -> None:
            pfad = args.ausgabe / f'fremdprobe-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def alarm(text: str, timeout: float = 15000):
            ort = seite.locator('[role=alert]', has_text=text).first
            ort.wait_for(timeout=timeout)
            return ort.inner_text()

        try:
            # -- 27 und 21: Zählung, Name mitnehmen -----------------------------------------------------------
            seite.goto(basis + '/willkommen')
            seite.get_by_role('heading', name='Wie heißt du?').wait_for(timeout=15000)
            pruef['27_zaehler_name'] = seite.locator('.erststart-zaehler').inner_text()
            pruef['27_punkte'] = seite.locator('.erststart-punkte li').count()
            pruef['27_zaehlung_stimmt'] = pruef['27_zaehler_name'] == f'Schritt 1 von {pruef["27_punkte"]}' and pruef['27_punkte'] == 6
            seite.locator('#erststart-name').fill('Lena')
            bild('01-name-getippt')
            seite.get_by_role('button', name='Später weitermachen').click()
            seite.wait_for_url(re.compile(r'/today'), timeout=15000)
            pruef['21_name_gespeichert'] = seite.request.get(basis + '/api/v1/einrichtung').json()['name'] == 'Lena'

            # -- 3: Anmeldung wird geprüft --------------------------------------------------------------------
            seite.goto(basis + '/willkommen?schritt=mail')
            seite.get_by_role('heading', name='Deine Mail verbinden').wait_for(timeout=15000)
            pruef['27_zaehler_mail'] = seite.locator('.erststart-zaehler').inner_text() == 'Schritt 2 von 6'
            # Ohne eingerichtete Google-Anmeldung steht der Weg mit Adresse sofort da (Befund 2): kein Knopf zum Wählen.
            pruef['2_nur_der_weg_der_geht'] = seite.get_by_role('button', name='Mit Google anmelden').count() == 0
            seite.locator('#erststart-adresse').fill(ADRESSE)
            seite.get_by_text('Erkannt: Probe-Post').wait_for(timeout=5000)
            seite.locator('#erststart-passwort').fill('erfunden')
            seite.get_by_role('button', name='Postfach verbinden').click()
            pruef['3_falsches_passwort'] = alarm('abgelehnt')
            pruef['3_nicht_verbunden'] = seite.get_by_text('Dein Postfach ist verbunden.').count() == 0 \
                and seite.request.get(basis + '/api/v1/integrations').json()['mail_accounts'] == []
            bild('02-passwort-abgelehnt')
            attrappe.modus = 'stumm'
            start = time.monotonic()
            seite.get_by_role('button', name='Postfach verbinden').click()
            pruef['3_server_schweigt'] = alarm('antwortet gerade nicht')
            pruef['3_zeitgrenze_s'] = round(time.monotonic() - start, 1)
            pruef['3_schnell_genug'] = pruef['3_zeitgrenze_s'] < 8
            bild('03-server-schweigt')
            attrappe.modus = 'annehmen'
            seite.locator('#erststart-passwort').fill(PASSWORT)
            seite.get_by_role('button', name='Postfach verbinden').click()
            seite.get_by_text('Dein Postfach ist verbunden.').wait_for(timeout=15000)
            pruef['3_richtig_verbunden'] = True

            # -- 4: Mails einlesen: sichtbarer Start oder Grund -----------------------------------------------
            attrappe.modus = 'stumm_nach_anmeldung'
            seite.get_by_role('button', name='Mails einlesen').click()
            seite.get_by_text('Kingfisher fragt dein Postfach, welche Mailbereiche es gibt.').wait_for(timeout=3000)
            pruef['4_start_sichtbar'] = True
            bild('04-einlesen-wartet')
            start = time.monotonic()
            pruef['4_grund'] = alarm('antwortet gerade nicht')
            pruef['4_zeitgrenze_s'] = round(time.monotonic() - start, 1)
            pruef['4_schnell_genug'] = pruef['4_zeitgrenze_s'] < 10
            bild('05-einlesen-grund')
            attrappe.modus = 'annehmen'
            seite.get_by_role('button', name='Erneut versuchen').click()
            zeile = seite.locator('.erststart-einlesen [role=status]', has_text='Probe-Post:').first
            zeile.wait_for(timeout=15000)
            pruef['4_fortschritt'] = zeile.inner_text()
            bild('06-einlesen-laeuft')

            # -- 5 und 27: Fertig-Seite bei schweigendem Postfach ---------------------------------------------
            attrappe.modus = 'stumm'
            seite.goto(basis + '/willkommen?schritt=freigaben')
            seite.get_by_role('heading', name='Was darf Kingfisher noch?').wait_for(timeout=15000)
            seite.locator('.erststart-freigaben li').filter(has_text='Wetter').get_by_role('button', name='Einrichten').click()
            seite.get_by_role('button', name='Zuklappen').wait_for(timeout=5000)
            pruef['27_knopfnamen_eindeutig'] = seite.get_by_role('button', name='Fertig', exact=True).count() <= 1
            seite.goto(basis + '/willkommen?schritt=fertig')
            titel = seite.get_by_role('heading', name='Dein Postfach antwortet nicht')
            titel.wait_for(timeout=15000)
            karte = seite.locator('.erststart-stumm')
            pruef['5_text'] = karte.inner_text()
            pruef['5_grund_genannt'] = 'Probe-Post antwortet gerade nicht.' in pruef['5_text']
            pruef['5_nicht_bereit'] = seite.get_by_text('Dein Briefing ist bereit').count() == 0
            pruef['27_zaehler_fertig'] = seite.locator('.erststart-zaehler').inner_text() == 'Schritt 6 von 6'
            bild('07-fertig-postfach-schweigt')
            karte.get_by_role('button', name='Postfach prüfen').click()
            seite.wait_for_url(re.compile(r'schritt=mail'), timeout=5000)
            pruef['5_mailschritt_grund'] = alarm('antwortet gerade nicht')
            pruef['5_neu_verbinden'] = seite.get_by_role('button', name='Probe-Post neu verbinden').count() == 1
            pruef['5_nicht_verbunden_angezeigt'] = seite.get_by_text('Dein Postfach ist verbunden.').count() == 0
            bild('08-mailschritt-postfach-schweigt')

            # -- 23 und 29: Zum Briefing, „Heute“ --------------------------------------------------------------
            logbuch.vermerke('rueckmeldung')
            seite.goto(basis + '/willkommen?schritt=fertig')
            seite.get_by_role('heading', name='Dein Postfach antwortet nicht').wait_for(timeout=15000)
            seite.get_by_role('button', name='Zum Briefing').click()
            seite.wait_for_url(re.compile(r'/today'), timeout=15000)
            seite.locator('section.briefing-drawer.open').wait_for(timeout=20000)
            pruef['23_briefing_offen'] = True
            bild('09-briefing-offen')
            seite.locator('section.briefing-drawer.open .drawer-close').click()

            # Eine fällige Aufgabe, damit Heute seine Karten zeigt (sonst steht dort nur der nächste Schritt).
            antwort = seite.request.post(basis + '/api/v1/tasks', data={'title': 'Angebot an die Probe GmbH schicken',
                                                                        'due': time.strftime('%Y-%m-%d')})
            assert antwort.ok, antwort.text()
            seite.reload()
            seite.locator('.tageslage-verlauf p').first.wait_for(timeout=20000)
            zeile = seite.locator('.tageslage-verlauf p').first.inner_text()
            pruef['29_zeile'] = zeile
            pruef['29_heute'] = zeile.startswith('Heute: ') and 'Seit gestern' not in seite.content()
            bild('10-heute')

            # -- 30: Verbindungen prüfen ------------------------------------------------------------------------
            hinweis = seite.locator('details.today-connection-note')
            hinweis.wait_for(timeout=15000)
            hinweis.locator('summary').click()
            link = hinweis.get_by_role('link', name='Verbindungen prüfen')
            pruef['30_ziel'] = link.get_attribute('href')
            link.click()
            seite.wait_for_url(re.compile(r'/settings#zugaenge'), timeout=15000)
            # Seit docs/47 liegen die Postfächer im Reiter „Zugänge“; der Verweis landet dort, nicht auf der Übersicht.
            mail_knopf = seite.locator('.settings-section-nav button', has_text='Zugänge').first
            mail_knopf.wait_for(timeout=15000)
            pruef['30_mail_offen'] = mail_knopf.get_attribute('aria-pressed') == 'true' \
                and seite.locator('#settings-zugaenge').is_visible()
            bild('11-einstellungen-mail')

            # -- 9 und 17: lokale KI mit einer Aussage; Automatik einmal angeboten ------------------------------
            attrappe.modus = 'annehmen'
            for rolle in ('antwort', 'hintergrund'):
                antwort = seite.request.put(basis + f'/api/v1/models/roles/{rolle}', data={'modell': MODELL})
                assert antwort.ok, antwort.text()
            pruef['9_stand'] = seite.request.get(basis + '/api/v1/models/stand').json()
            # Seit docs/47 stehen der Stand aller Bereiche und die Modelle hinter „Für Techniker“ (#technik-stand, #technik-modelle).
            seite.goto(basis + '/settings#technik-stand')
            karte = seite.locator('.setup-overview-card', has_text='Lokale KI')
            karte.locator('strong', has_text='Bereit').wait_for(timeout=20000)
            pruef['9_karte'] = karte.inner_text()
            seite.goto(basis + '/settings#technik-modelle')
            modelle = seite.locator('#technik-modelle')
            modelle.get_by_text(f'{MODELL} ist installiert').wait_for(timeout=20000)
            modelle.get_by_role('button', name='Modell verwalten').click()
            modelle.get_by_text('installierte Modelle gefunden').wait_for(timeout=20000)
            text = modelle.inner_text() + pruef['9_karte']
            pruef['9_eine_aussage'] = f'Bereit: {MODELL}' in text and not any(widerspruch in text for widerspruch in (
                'Anderer Anbieter', 'bestätigt keine Verbindung', 'Keine Modellliste erreichbar',
                'Ollama meldet noch kein installiertes Modell'))
            bild('12-lokale-ki')

            # Ein zweites Postfach, verbunden, aber noch nicht eingelesen; das Sortieren ist noch pausiert.
            antwort = seite.request.post(basis + '/api/v1/integrations/mail', data={
                'label': 'Probe-Post Zwei', 'imap_host': '127.0.0.1', 'imap_port': attrappe.port,
                'user': 'lena.zwei@example.org', 'sender': 'lena.zwei@example.org', 'password': PASSWORT})
            assert antwort.ok, antwort.text()
            zweites = antwort.json()['mail_accounts'][-1]['id']
            # Seit Fremdprobe 3, Befund 3 merkt schon die erste Fertig-Seite das Sortieren vor, während das Modell lädt.
            # Für das Angebot hier wird es pausiert, wie es jemand unter Verarbeitung & Verlauf täte.
            assert seite.request.put(basis + '/api/v1/memory/automation', data={'enabled': False}).ok
            pruef['17_vorher_pausiert'] = seite.request.get(basis + '/api/v1/memory/automation').json()['state'] == 'paused'
            seite.goto(basis + '/willkommen?schritt=fertig')
            angebot = seite.locator('fieldset.erststart-automatik')
            angebot.wait_for(timeout=20000)
            # Einlesen wird erst angeboten, wenn feststeht, dass das Postfach antwortet.
            angebot.get_by_text('Mails von Probe-Post Zwei').wait_for(timeout=20000)
            pruef['17_angebot'] = angebot.inner_text()
            pruef['17_vorausgewaehlt'] = angebot.locator('input[type=checkbox]').count() == 2 and all(
                angebot.locator('input[type=checkbox]').nth(i).is_checked() for i in range(2))
            bild('13-fertig-automatik')
            seite.get_by_role('button', name='Zum Briefing').click()
            seite.locator('section.briefing-drawer.open').wait_for(timeout=30000)
            automatik = seite.request.get(basis + '/api/v1/memory/automation').json()
            konten = {k['account_id']: k for k in seite.request.get(basis + '/api/v1/mail/intake').json()['accounts']}
            pruef['17_sortieren_an'] = automatik['state'] == 'active' and automatik['requested'] is True
            pruef['17_einlesen_an'] = konten[zweites]['started'] is True
            seite.goto(basis + '/settings#technik-stand')
            karte = seite.locator('.setup-overview-card', has_text='Automatik')
            karte.locator('strong', has_text='Automatisches Sortieren ist an').wait_for(timeout=20000)
            # Seit Befund 12 heißt es „Mails regelmäßig abrufen“ statt „Automatische Quellenaufnahme“.
            pruef['17_einstellungen'] = 'Mails regelmäßig abrufen: an' in karte.inner_text()
            bild('14-einstellungen-automatik')
        except Exception:
            bild('fehler')
            print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
            raise
        finally:
            browser.close()
            uv.should_exit = True
            attrappe.schliessen()
            ollama.shutdown()

    ergebnis['ok'] = all(v is True for k, v in pruef.items() if isinstance(v, bool)) and not ergebnis['konsole']
    (args.ausgabe / 'fremdprobe-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
