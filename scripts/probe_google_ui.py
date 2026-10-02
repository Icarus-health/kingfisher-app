#!/usr/bin/env python3
"""Browserprobe zu Befund 2 der Fremdprobe (docs/48-fremdprobe.md): Google ohne eigenes Cloud-Projekt.

Echter Sidecar (`create_app()` unter uvicorn, frisches Datenverzeichnis, eigenes Benutzerverzeichnis), echte Oberfläche
(`npm run build`), Chromium über Playwright. Als echte Dienste auf 127.0.0.1: eine IMAP-Attrappe an Stelle von Gmail
(`sidecar/tests/imap_attrappe.py`, lehnt zuerst ab wie Google ein normales Passwort), eine iCal-Attrappe an Stelle von
Google Kalender (`sidecar/tests/ical_attrappe.py`, HTTPS) und ein Namensdienst, der `praxis-probe.example` bei Google
führt (`sidecar/tests/dns_attrappe.py`). Kein Netz nach außen, nur synthetische Zugänge (`lena.probe@gmail.com`).

Geprüft wird im Browser:

* Ohne Einrichtung steht nirgends „Mit Google anmelden“ und kein „Noch nicht freigeschaltet“ (Mail-Schritt,
  Kalender-Schritt, Zugänge); vorne steht nur der Weg, der geht.
* Mail: Gmail-Adresse wird erkannt, das Feld heißt „App-Passwort“, die Karte erklärt in zwei Sätzen mit Verweis auf
  `https://myaccount.google.com/apppasswords`; das normale Passwort lehnt „Google“ ab, und die Karte sagt
  „App-Passwort nötig“; mit App-Passwort ist das Postfach verbunden. Eine Workspace-Adresse mit eigener Domain wird am
  Mailserver erkannt.
* Kalender: „Google-Kalender“ zeigt das Feld für die geheime Adresse mit zwei Sätzen; eine Einbettungsadresse und die
  öffentliche Adresse bekommen je einen Satz; die geheime Adresse verbindet den Kalender (nur lesen), und die Attrappe
  sah genau diese Abrufe, sonst nichts. Unter Zugänge führt die Gmail-Adresse zum selben Feld.
* Hat ein Techniker die Google-Anmeldung eingerichtet, steht „Mit Google anmelden“ wieder vorne.
* Die Konsole bleibt leer außer den absichtlich ausgelösten Fehlantworten (422), die getrennt stehen.

Aufruf: `python scripts/probe_google_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build`).
"""
from __future__ import annotations

import argparse
import dataclasses
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
GMAIL = 'lena.probe@gmail.com'
WORKSPACE = 'lena.probe@praxis-probe.example'
CLIENT = {'installed': {'client_id': '123-probe.apps.googleusercontent.com', 'client_secret': 'synthetisch'}}


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main() -> int:  # noqa: PLR0915 - eine Probe ist eine lange Folge von Schritten
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from tests.dns_attrappe import Namensdienst
    from tests.ical_attrappe import GEHEIM, GOOGLE_GEHEIM, GOOGLE_OEFFENTLICH, OEFFENTLICH, IcalAttrappe
    from tests.imap_attrappe import PASSWORT, ImapAttrappe
    imap, ical, dns = ImapAttrappe(modus='google_ablehnen'), IcalAttrappe(), Namensdienst()
    arbeit = Path(tempfile.mkdtemp(prefix='probe-google-'))
    zuhause, daten = arbeit / 'home', arbeit / 'daten'
    zuhause.mkdir()
    buendel = arbeit / 'zertifikate.pem'
    buendel.write_text(imap.zertifikat.read_text() + ical.zertifikat.read_text())
    os.environ.update(ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(buendel), HOME=str(zuhause),
                      KINGFISHER_DNS=f'127.0.0.1:{dns.port}', ICARUS_SECRETS_PASSPHRASE='probe-google-schluessel')
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'KINGFISHER_USER_NAME'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import mail_anmeldung, providers_mail
    from icarus_memory.server import create_app

    # Gmail zeigt auf die IMAP-Attrappe; erkannt wird die Ablehnung dann an Googles Wortlaut, nicht am Servernamen.
    gmail = dataclasses.replace(providers_mail.BY_ID['gmail'], imap_host='127.0.0.1', imap_port=imap.port)
    providers_mail.PROVIDERS = tuple(gmail if p.id == 'gmail' else p for p in providers_mail.PROVIDERS)
    providers_mail.BY_ID['gmail'] = gmail
    mail_anmeldung.ZEITGRENZE = 3.0

    from icarus_memory import server_finden
    from tests.autoconfig_attrappe import kein_netz
    server_finden.TRANSPORT = kein_netz()  # die Suche nach dem Server einer Domain geht in der Probe nie ins Netz

    app = create_app()
    app.state.ical_transport = ical.google_transport()
    port = freier_port()
    uv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=uv.run, daemon=True).start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.1)
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': [], 'erwartete_fehlantworten': []}
    pruef = ergebnis['pruefungen']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        kontext = browser.new_context(viewport={'width': 1280, 'height': 1000})
        seite = kontext.new_page()
        erwartet = re.compile(r'/api/v1/integrations/(mail|calendar/abo)$')

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
            pfad = args.ausgabe / f'google-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def schritt(name: str, titel: str) -> None:
            seite.goto(f'{basis}/willkommen?schritt={name}')
            seite.get_by_role('heading', name=titel).wait_for(timeout=15000)

        def kein_gesperrter_google_knopf() -> bool:
            seite.wait_for_timeout(600)  # die Abfrage der Google-Einrichtung ist sicher zurück
            return (seite.get_by_role('button', name='Mit Google anmelden').count() == 0
                    and seite.get_by_text('Noch nicht freigeschaltet').count() == 0)

        try:
            # -- Mail: Gmail mit App-Passwort ---------------------------------------------------------------------
            schritt('mail', 'Deine Mail verbinden')
            pruef['mail_ohne_google_knopf'] = kein_gesperrter_google_knopf()
            pruef['mail_formular_sofort'] = seite.locator('#erststart-adresse').count() == 1
            seite.locator('#erststart-adresse').fill(GMAIL)
            seite.get_by_text('Erkannt: Gmail / Google Workspace').wait_for(timeout=5000)
            pruef['mail_app_passwort_feld'] = seite.get_by_label('App-Passwort').count() == 1
            hinweis = seite.locator('.erststart-formular .source-hint', has_text='App-Passwort').first
            pruef['mail_hinweis'] = hinweis.inner_text()
            verweis = hinweis.get_by_role('link')
            pruef['mail_verweis'] = [verweis.inner_text(), verweis.get_attribute('href')]
            pruef['mail_zwei_saetze'] = 'zwei Schritten' in pruef['mail_hinweis'] \
                and pruef['mail_verweis'] == ['Zur Google-Seite „App-Passwörter“', 'https://myaccount.google.com/apppasswords']
            bild('01-gmail-erkannt')
            seite.get_by_label('App-Passwort').fill('mein-normales-passwort')
            seite.get_by_role('button', name='Postfach verbinden').click()
            pruef['mail_abgelehnt'] = seite.locator('.erststart-formular [role=alert]').inner_text(timeout=15000)
            pruef['mail_app_passwort_noetig'] = pruef['mail_abgelehnt'].startswith('App-Passwort nötig:') \
                and seite.request.get(basis + '/api/v1/integrations').json()['mail_accounts'] == []
            bild('02-app-passwort-noetig')
            imap.modus = 'annehmen'
            seite.get_by_label('App-Passwort').fill(PASSWORT)
            seite.get_by_role('button', name='Postfach verbinden').click()
            seite.get_by_text('Dein Postfach ist verbunden.').wait_for(timeout=20000)
            pruef['mail_verbunden'] = [k['user'] for k in seite.request.get(basis + '/api/v1/integrations').json()['mail_accounts']] == [GMAIL]
            bild('03-gmail-verbunden')
            # Workspace mit eigener Domain: erkannt am Mailserver.
            seite.get_by_role('button', name='Noch ein Postfach verbinden').click()
            seite.locator('#erststart-adresse').fill(WORKSPACE)
            seite.get_by_text('Erkannt: Gmail / Google Workspace').wait_for(timeout=8000)
            pruef['workspace_erkannt'] = seite.get_by_label('Welcher Anbieter?').count() == 0
            pruef['workspace_nur_domain_gefragt'] = dns.anfragen and all('@' not in a for a in dns.anfragen)
            bild('04-workspace-erkannt')

            # -- Kalender: geheime iCal-Adresse -------------------------------------------------------------------
            schritt('kalender', 'Deinen Kalender verbinden')
            seite.get_by_role('button', name='Google-Kalender').click()
            formular = seite.locator('form.google-kalender-adresse')
            formular.wait_for(timeout=5000)
            pruef['kalender_ohne_google_knopf'] = kein_gesperrter_google_knopf()
            text = formular.locator('.source-hint').first.inner_text()
            pruef['kalender_zwei_saetze'] = 'Geheime Adresse im iCal-Format' in text \
                and 'hinaus geht nichts außer dem Abruf dieser Adresse' in text
            bild('05-kalender-feld')
            feld = formular.get_by_label('Geheime Adresse im iCal-Format')
            feld.fill('https://calendar.google.com/calendar/embed?src=lena.probe%40example.org')
            formular.get_by_role('button', name='Kalender verbinden').click()
            pruef['kalender_einbettung'] = formular.locator('[role=alert]').inner_text(timeout=10000)
            feld.fill(GOOGLE_OEFFENTLICH)
            formular.get_by_role('button', name='Kalender verbinden').click()
            formular.get_by_text('öffentliche Adresse').wait_for(timeout=10000)
            pruef['kalender_oeffentlich'] = formular.locator('[role=alert]').inner_text()
            bild('06-kalender-oeffentlich')
            feld.fill(GOOGLE_GEHEIM)
            formular.get_by_role('button', name='Kalender verbinden').click()
            # Nach dem Erfolg treten die Wege zurück (Fremdprobe 3, Befund 7); der Satz bleibt im Schritt stehen.
            seite.get_by_text('Verbunden: Google: Lena Probe (2 Termine, nur lesen).').wait_for(timeout=15000)
            quellen = seite.request.get(basis + '/api/v1/integrations').json()['calendar_sources']
            pruef['kalender_verbunden'] = [(q['label'], q['kind']) for q in quellen] == [('Google: Lena Probe', 'ical')]
            seite.get_by_role('button', name='Weiteren Kalender verbinden').wait_for(timeout=15000)
            pruef['kalender_nur_diese_abrufe'] = ical.anfragen[:2] == [('GET', OEFFENTLICH), ('GET', GEHEIM)]
            pruef['kalender_abrufe'] = ical.anfragen
            bild('07-kalender-verbunden')

            # -- Zugänge: kein gesperrter Knopf, die Gmail-Adresse führt zum selben Feld ------------------------------
            seite.goto(f'{basis}/settings#zugaenge')
            seite.locator('#settings-zugaenge:not([hidden])').wait_for(timeout=15000)
            pruef['zugaenge_ohne_google_knopf'] = kein_gesperrter_google_knopf()
            seite.get_by_role('button', name='Kalender hinzufügen').click()
            seite.locator('#kalender-adresse').fill(GMAIL)
            seite.get_by_text('Dein Kalender geht ohne Passwort über seine Adresse.').wait_for(timeout=5000)
            pruef['zugaenge_gmail_zum_feld'] = seite.locator('form.google-kalender-adresse').count() == 1 \
                and seite.locator('#kalender-passwort').count() == 0
            bild('08-zugaenge-gmail')

            # -- Mit Einrichtung: „Mit Google anmelden“ wieder vorne ---------------------------------------------------
            antwort = seite.request.put(basis + '/api/v1/google/config', data=CLIENT)
            pruef['techniker_einrichtung'] = antwort.status
            schritt('mail', 'Deine Mail verbinden')
            seite.get_by_role('button', name='Noch ein Postfach verbinden').click()
            seite.get_by_role('button', name='Mit Google anmelden').wait_for(timeout=10000)
            pruef['eingerichtet_google_knopf_vorne'] = seite.get_by_role('button', name='Mit Google anmelden').is_enabled()
            bild('09-eingerichtet')
            ergebnis['ok'] = all(v for k, v in pruef.items() if not k.startswith(('mail_hinweis', 'mail_verweis',
                                 'mail_abgelehnt', 'kalender_einbettung', 'kalender_oeffentlich', 'kalender_abrufe',
                                 'techniker_einrichtung'))) and pruef['techniker_einrichtung'] == 200 \
                and not ergebnis['konsole']
        except Exception as fehler:  # noqa: BLE001 - die Probe hält fest, wo sie stand
            ergebnis['fehler'] = repr(fehler)
            bild('fehler')
        finally:
            browser.close()
    uv.should_exit = True
    imap.schliessen()
    ical.schliessen()
    dns.schliessen()
    (args.ausgabe / 'google-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'pruefungen': pruef, 'konsole': ergebnis['konsole'],
                      'fehler': ergebnis.get('fehler')}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
