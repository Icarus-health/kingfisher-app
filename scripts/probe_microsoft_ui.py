#!/usr/bin/env python3
"""Browserprobe Microsoft 365 (docs/50-microsoft-365.md): erkennen, anmelden mit Code, Mitschriften, ehrliche Sätze.

Echter Sidecar (`create_app()` unter uvicorn, frisches Datenverzeichnis), echte Oberfläche (`npm run build`), Chromium
über Playwright. Microsoft spielt die Graph-Attrappe (`sidecar/tests/graph_attrappe.py`) auf 127.0.0.1, den Namensdienst
des Rechners die DNS-Attrappe (`sidecar/tests/dns_attrappe.py`, `KINGFISHER_DNS`), die `hochschule.example` bei Microsoft
365 führt; erkannt wird über dieselbe eine Anbieter-Erkennung wie bei Google Workspace. Kein Netz, nur synthetische Zugänge (`lena.probe@hochschule.example`).

Geprüft wird im Browser:

* Ohne Kennung der App: Die Karte unter Zugänge sagt, was fehlt, der Knopf ist gesperrt; im Mail-Schritt erscheint
  dazu der Weg mit Adresse und Passwort.
* Für Techniker: Die Kennung lässt sich eintragen; danach ist die Anmeldung bereit.
* Mail-Schritt: Die Adresse genügt, „Erkannt: Microsoft 365 …“ steht da, ohne dass Microsoft gefragt wurde; „Mit
  Microsoft anmelden“ zeigt den Code, „Code kopieren“ legt ihn in die Zwischenablage, der Link führt zu
  microsoft.com/devicelogin, der Stand zählt die Zeit; nach der Anmeldung steht „Verbunden: Post und Kalender …“, und
  „Mails einlesen“ ist da.
* Zugänge: das Konto mit „Post, Kalender · nur lesen“; „Teams-Mitschriften dazunehmen“ mit zweitem Code; „Jetzt
  nachsehen“ zeigt die Besprechung mit „Mitschrift aufgenommen.“
* Fehlerweg: Verweigert die IT die Zustimmung, steht der Satz über die IT da, nichts wird angelegt.
* Bei 390 px läuft nichts seitlich über; die Konsole bleibt ohne Fehler. Kein Token im Seiteninhalt.

Aufruf: `python scripts/probe_microsoft_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build`).
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
GEHEIM = re.compile(r'geraet-geheim|erneuern-\d+|zugriff-\d+')


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

    from tests.dns_attrappe import Namensdienst
    from tests.graph_attrappe import ADRESSE, CLIENT_ID, USER_CODE, GraphAttrappe
    graph, dns = GraphAttrappe(), Namensdienst()
    arbeit = Path(tempfile.mkdtemp(prefix='probe-microsoft-'))
    zuhause, daten = arbeit / 'home', arbeit / 'daten'
    zuhause.mkdir()
    os.environ.update(ICARUS_DATA_DIR=str(daten), HOME=str(zuhause), ICARUS_SECRETS_PASSPHRASE='probe-passphrase',
                      KINGFISHER_MS_LOGIN_URL=graph.login, KINGFISHER_MS_GRAPH_URL=graph.graph,
                      KINGFISHER_HINTERGRUND_RUHE_S='0', KINGFISHER_DNS=f'127.0.0.1:{dns.port}')
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'KINGFISHER_MS_CLIENT_ID',
                 'KINGFISHER_MS_TENANT', 'HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import microsoft_anmeldung, secrets
    from icarus_memory.server import create_app

    microsoft_anmeldung.INTERVALL = 0
    secrets.Keychain._detect = lambda self: 'file'  # verschlüsselte Datei im Datenordner, nie der Schlüsselbund des Rechners
    from icarus_memory import server_finden
    from tests.autoconfig_attrappe import kein_netz
    server_finden.TRANSPORT = kein_netz()  # die Suche nach dem Server einer Domain geht in der Probe nie ins Netz

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
        kontext = browser.new_context(viewport={'width': 1280, 'height': 1000})
        kontext.grant_permissions(['clipboard-read', 'clipboard-write'], origin=basis)
        seite = kontext.new_page()
        seite.on('console', lambda m: m.type == 'error' and ergebnis['konsole'].append(f'{m.type}: {m.text}'))
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

        def bild(name: str) -> None:
            pfad = args.ausgabe / f'microsoft-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def zugaenge():
            seite.goto(basis + '/settings#zugaenge')
            seite.locator('#settings-zugaenge:not([hidden])').wait_for(timeout=15000)
            karte = seite.locator('section[aria-label="Microsoft 365"]')
            karte.wait_for(timeout=15000)
            return karte

        def ueberlauf() -> int:
            return seite.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')

        try:
            # -- Ohne Kennung der App ----------------------------------------------------------------------------
            karte = zugaenge()
            karte.get_by_role('button', name='Mit Microsoft anmelden').click()
            karte.get_by_text('fehlt noch die Kennung der App').wait_for(timeout=15000)
            pruef['ohne_app_satz'] = 'Techniker' in karte.inner_text()
            pruef['ohne_app_knopf_gesperrt'] = karte.locator('.ms-anmeldung button.primary-action').is_disabled()
            bild('01-ohne-app')
            seite.goto(basis + '/willkommen?schritt=mail')
            seite.get_by_role('heading', name='Deine Mail verbinden').wait_for(timeout=15000)
            seite.locator('#erststart-adresse').fill(ADRESSE)
            seite.get_by_text('Erkannt: Microsoft 365').wait_for(timeout=15000)
            seite.get_by_text('fehlt noch die Kennung der App').wait_for(timeout=15000)
            pruef['ohne_app_passwortweg'] = seite.locator('#erststart-passwort').count() == 1
            bild('02-mailschritt-ohne-app')

            # -- Für Techniker: Kennung eintragen -----------------------------------------------------------------
            seite.goto(basis + '/settings#technik-microsoft')
            seite.locator('#settings-technik:not([hidden])').wait_for(timeout=15000)
            abschnitt = seite.locator('#technik-microsoft')
            if abschnitt.get_attribute('open') is None:
                abschnitt.locator('summary').click()
            abschnitt.get_by_label('App-Kennung (Client-ID)').fill(CLIENT_ID)
            abschnitt.get_by_role('button', name='Kennung speichern').click()
            abschnitt.get_by_text('Kennung gespeichert').wait_for(timeout=15000)
            pruef['technik_bereit'] = 'Bereit: App-Kennung' in abschnitt.inner_text()
            bild('03-techniker')

            # -- Mail-Schritt: Adresse genügt, Code, kopieren, Link, verbunden ------------------------------------
            graph.ablauf[:] = ['pending', 'pending', 'ok']
            vorher = len(graph.anfragen)
            seite.goto(basis + '/willkommen?schritt=mail')
            seite.get_by_role('heading', name='Deine Mail verbinden').wait_for(timeout=15000)
            seite.locator('#erststart-adresse').fill(ADRESSE)
            seite.get_by_text('Erkannt: Microsoft 365').wait_for(timeout=15000)
            pruef['erkannt_ohne_microsoft'] = len(graph.anfragen) == vorher and ('hochschule.example', 'MX') in dns.fragen
            pruef['dns_nur_domain'] = bool(dns.anfragen) and all('@' not in a and 'lena' not in a for a in dns.anfragen)
            pruef['kein_passwortfeld_vorne'] = seite.locator('#erststart-passwort').count() == 0
            seite.get_by_role('button', name='Mit Microsoft anmelden').click()
            code = seite.locator('.ms-code-wert')
            code.wait_for(timeout=15000)
            pruef['code_sichtbar'] = code.inner_text() == USER_CODE
            seite.get_by_role('button', name='Code kopieren').click()
            seite.get_by_role('button', name='Kopiert').wait_for(timeout=5000)
            pruef['code_kopiert'] = seite.evaluate('navigator.clipboard.readText()') == USER_CODE
            link = seite.get_by_role('link', name='Seite von Microsoft öffnen')
            pruef['link_devicelogin'] = link.get_attribute('href') == 'https://microsoft.com/devicelogin' \
                and link.get_attribute('target') == '_blank'
            pruef['stand_mit_zeit'] = bool(re.search(r'noch 1[45] Minuten', seite.locator('.ms-stand').inner_text()))
            bild('04-code')
            seite.set_viewport_size({'width': 390, 'height': 900})
            pruef['390_kein_ueberlauf'] = ueberlauf() <= 0
            bild('05-code-390')
            seite.set_viewport_size({'width': 1280, 'height': 1000})
            seite.get_by_text('Verbunden: Post und Kalender von').wait_for(timeout=20000)
            seite.get_by_text('Dein Postfach ist verbunden.').wait_for(timeout=20000)
            pruef['mails_einlesen_da'] = seite.get_by_role('button', name='Mails einlesen').count() == 1
            # Eine Anmeldung bringt auch den Kalender: Der Kalender-Schritt gilt als erledigt.
            pruef['kalender_mit_verbunden'] = seite.request.get(basis + '/api/v1/einrichtung').json()['vorhanden']['kalender'] is True
            pruef['kein_token_in_seite'] = not GEHEIM.search(seite.content())
            bild('06-verbunden')

            # -- Zugänge: Konto, Mitschriften dazunehmen, nachsehen -----------------------------------------------
            karte = zugaenge()
            karte.get_by_text(ADRESSE).wait_for(timeout=15000)
            pruef['zugang_post_kalender'] = 'Post, Kalender · nur lesen' in karte.inner_text()
            kalender = seite.locator('.source-section[aria-label="Kalender"]')
            kalender.get_by_text('Microsoft · nur lesen').wait_for(timeout=15000)  # die Liste lädt eigenständig
            pruef['kalender_microsoft'] = 'Microsoft · nur lesen' in kalender.inner_text()
            karte.get_by_role('button', name='Teams-Mitschriften dazunehmen').click()
            karte.get_by_text('Microsoft gibt sie erst frei').wait_for(timeout=15000)
            graph.ablauf[:] = ['pending', 'ok']
            karte.get_by_role('button', name='Bei Microsoft zustimmen').click()
            karte.locator('.ms-code-wert').wait_for(timeout=15000)
            karte.get_by_text('Teams-Mitschriften', exact=False).first.wait_for(timeout=15000)
            seite.wait_for_function("document.querySelector('section[aria-label=\"Microsoft 365\"]').innerText.includes('Teams-Mitschriften · nur lesen')", timeout=20000)
            karte.get_by_role('button', name='Jetzt nachsehen').click()
            karte.get_by_text('Mitschrift aufgenommen.').wait_for(timeout=20000)
            pruef['mitschrift_aufgenommen'] = 'Haushalt Fakultät' in karte.inner_text()
            pruef['kein_token_in_zugaengen'] = not GEHEIM.search(seite.content())
            bild('07-mitschriften')

            # -- Fehlerweg: IT verweigert ------------------------------------------------------------------------
            graph.ablauf[:] = ['admin']
            konten_vorher = len(seite.request.get(basis + '/api/v1/integrations').json()['mail_accounts'])
            karte.get_by_role('button', name='Weiteres Microsoft-Konto anmelden').click()
            karte.get_by_role('button', name='Mit Microsoft anmelden').click()
            karte.get_by_text('Zustimmung ihrer IT').wait_for(timeout=20000)
            pruef['admin_satz'] = karte.locator('[role=alert]').count() >= 1
            pruef['admin_nichts_angelegt'] = len(seite.request.get(basis + '/api/v1/integrations').json()['mail_accounts']) == konten_vorher
            bild('08-admin')
            seite.set_viewport_size({'width': 390, 'height': 900})
            pruef['390_zugaenge_kein_ueberlauf'] = ueberlauf() <= 0
            bild('09-zugaenge-390')
            pruef['nur_get_an_graph'] = {a['methode'] for a in graph.anfragen if a['pfad'].startswith('/v1.0/')} == {'GET'}
        except Exception:
            bild('fehler')
            print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
            raise
        finally:
            browser.close()
            uv.should_exit = True
            graph.stop()

    falsch = [k for k, v in pruef.items() if v is False]
    ergebnis['nicht_bestanden'] = falsch
    ergebnis['ok'] = not falsch and not ergebnis['konsole']
    (args.ausgabe / 'microsoft-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(f"Prüfungen: {len(pruef)} · nicht bestanden: {falsch or 'keine'} · Konsole: {ergebnis['konsole'] or 'leer'}")
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
