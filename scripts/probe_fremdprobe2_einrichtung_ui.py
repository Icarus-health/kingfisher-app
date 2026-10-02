#!/usr/bin/env python3
"""Browserprobe zur zweiten Fremdprobe (docs/51-fremdprobe-2.md): der Weg mit `lena.probe@example.org`, Befunde 2 bis 9,
23 bis 25 und 30, mit Blick auf die Bedienzeit (15-Minuten-Kriterium aus docs/41-zielbild.md, M3).

Echter Sidecar (`create_app()` unter uvicorn, frisches Datenverzeichnis), echte Oberfläche (`npm run build`), Chromium
über Playwright. Als echte Dienste auf 127.0.0.1, kein Netz nach außen: ein Namensdienst (`tests/dns_attrappe.py`,
dazu SRV für `verein-probe.example`), eine Autoconfig-Attrappe als HTTPS-Dienst für `example.org`
(`tests/autoconfig_attrappe.py`), eine IMAP-Attrappe (`tests/imap_attrappe.py`) und eine CalDAV-Attrappe
(`tests/caldav_attrappe.py`) als Mailserver der Domain; Ollama als Attrappe, deren Laden angehalten werden kann.
Nur synthetische Daten.

Geprüft wird im Browser, in der Reihenfolge der Fremdprobe:

* 2: `lena.probe@example.org` steht in keinem Katalog; Kingfisher findet den Server selbst (Autoconfig), zeigt
  „Erkannt: …“ und nur das Passwortfeld, im Assistenten, ohne „Welcher Anbieter?“, ohne Servereingabe, ohne Sprung in
  die Einstellungen. Dasselbe über SRV (`verein-probe.example`). Für `eigen-probe.example` (nichts zu finden) stehen
  Servername und Port (993) im Assistenten selbst, mit einem Satz, wo man sie findet.
* 4: Ein falsches Passwort: die Ablehnung steht direkt am Knopf, hat den Fokus, ist im Bild und nennt den Server, nicht
  einen selbst vergebenen Namen. Dasselbe unter Zugänge (Servereinstellungen von Hand).
* 5: Kalender: die Adresse steht schon da, Kingfisher sucht den Kalender beim Mailserver der Domain und nimmt das
  Passwort des Postfachs; nichts zu tippen. Für Outlook der Weg in einem Satz mit Link zu Outlook.
* 6 und 7: „Laden starten“, sofort „Weiter“; das Laden läuft im Hintergrund weiter (Fortschritt auf Fertig und Heute),
  eine Frage bekommt „Kingfisher lädt noch sein Sprachmodell (… %)“, nichts sagt fälschlich „bereit“; danach genau ein
  Satz zum Ergebnis.
* 8: Die Fertig-Seite nennt nur, was verbunden ist. 9: Der Briefing-Kopf nennt die eingestellte Zeitzone, nicht UTC.
* 3, 23, 24: „Postfach hinzufügen“ und „Kalender hinzufügen“ sind beschriftet; die zuletzt getippte Adresse steht im
  Formular; die Karte „Microsoft 365“ hat Innenabstand.
* 30: Ein Ordner für Meetings wird per Auswahl durchgeklickt, nicht getippt.
* 25: Bei 390 px stehen der Name des aktiven Bereichs und im Assistenten der des aktuellen Schritts lesbar da.
* Die Konsole bleibt leer außer den absichtlich ausgelösten Fehlantworten (422), die getrennt stehen.

Aufruf: `python scripts/probe_fremdprobe2_einrichtung_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build`).
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

    import httpx
    from tests.autoconfig_attrappe import AutoconfigAttrappe, config_xml
    from tests.caldav_attrappe import CaldavAttrappe
    from tests.dns_attrappe import Namensdienst
    from tests.imap_attrappe import PASSWORT, ImapAttrappe
    from tests.ollama_fake import FakeOllama

    imap, caldav = ImapAttrappe(), CaldavAttrappe()
    # Die Domain veröffentlicht ihre Einstellungen; ihr Mailserver ist die IMAP-Attrappe.
    autoconfig = AutoconfigAttrappe(autoconfig={'example.org': config_xml('example.org', '127.0.0.1', imap.port)})
    dns = Namensdienst(srv={'_imaps._tcp.verein-probe.example': [(0, 1, imap.port, '127.0.0.1')]})
    arbeit = Path(tempfile.mkdtemp(prefix='probe-fremdprobe2-'))
    zuhause, daten = arbeit / 'home', arbeit / 'daten'
    (zuhause / 'Documents' / 'Mitschriften').mkdir(parents=True)
    buendel = arbeit / 'zertifikate.pem'
    buendel.write_text(imap.zertifikat.read_text() + caldav.zertifikat.read_text() + autoconfig.zertifikat.read_text())
    os.environ.update(ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(buendel), HOME=str(zuhause),
                      KINGFISHER_DNS=f'127.0.0.1:{dns.port}', KINGFISHER_TIMEZONE='Europe/Berlin',
                      ICARUS_SECRETS_PASSPHRASE='probe-fremdprobe2-schluessel')
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'KINGFISHER_USER_NAME',
                 'KINGFISHER_ORDNER'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import mail_anmeldung, ordner_lokal, server_finden
    from icarus_memory.server import create_app

    mail_anmeldung.ZEITGRENZE = 3.0
    ordner_lokal.im_container = lambda: False  # die Probe läuft wie ein Sidecar direkt auf dem Rechner
    server_finden.TRANSPORT = autoconfig.transport()

    app = create_app()
    # Der Kalender liegt beim Mailserver der Domain (`/.well-known/caldav` auf 127.0.0.1).
    app.state.caldav_transport = caldav.transport('127.0.0.1')
    # Ollama: das Laden hält an, bis die Probe es freigibt (so lässt sich prüfen, dass nichts darauf wartet).
    halt = threading.Event()
    ollama = FakeOllama()

    def mit_halt(request: httpx.Request) -> httpx.Response:
        if request.url.path == '/api/pull':
            halt.wait(120)
        return ollama._handle(request)
    app.state.ollama_transport = httpx.MockTransport(mit_halt)
    app.state.ollama_inventar.vergiss()
    app.state.modell_pruefung = lambda modell, rolle: {'verifiziert': True, 'latenz_ms': 12, 'profil': None}

    port = freier_port()
    uv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=uv.run, daemon=True).start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.1)
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': [], 'erwartete_fehlantworten': [],
                      'getippt': []}
    pruef = ergebnis['pruefungen']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        kontext = browser.new_context(viewport={'width': 1280, 'height': 900})
        seite = kontext.new_page()
        erwartet = re.compile(r'/api/v1/(integrations/mail|transcript-sync/lokal|integrations/calendar/anmelden)$')

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
            pfad = args.ausgabe / f'fremdprobe2-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def tippen(selektor: str, text: str, wofuer: str) -> None:
            seite.locator(selektor).fill(text)
            ergebnis['getippt'].append(wofuer)

        def am_knopf(meldung, knopf) -> dict:
            """Steht die Meldung am Knopf, im Bild und mit Fokus?"""
            meldung.wait_for(timeout=15000)
            seite.wait_for_timeout(700)  # Bildlauf
            m, k = meldung.bounding_box(), knopf.bounding_box()
            hoehe = seite.viewport_size['height']
            return {'abstand_px': round(abs(m['y'] - (k['y'] + k['height']))),
                    'im_bild': 0 <= m['y'] and m['y'] + m['height'] <= hoehe,
                    'fokus': meldung.evaluate('e => document.activeElement === e')}

        try:
            # -- Name -------------------------------------------------------------------------------------------
            seite.goto(basis + '/willkommen')
            seite.get_by_role('heading', name='Wie heißt du?').wait_for(timeout=20000)
            tippen('#erststart-name', 'Lena', 'Name')
            seite.get_by_role('button', name='Weiter', exact=True).click()

            # -- 2 und 4: Mail mit eigener Domain -----------------------------------------------------------------
            seite.get_by_role('heading', name='Deine Mail verbinden').wait_for(timeout=15000)
            tippen('#erststart-adresse', ADRESSE, 'Mailadresse')
            seite.get_by_text('Erkannt: 127.0.0.1.', exact=False).wait_for(timeout=20000)
            pruef['2_erkannt_ohne_auswahl'] = seite.locator('#erststart-anbieter').count() == 0
            pruef['2_keine_servereingabe'] = seite.locator('#erststart-server').count() == 0 \
                and seite.get_by_text('IMAP-Server').count() == 0
            pruef['2_nur_passwort'] = seite.locator('#erststart-passwort').count() == 1
            pruef['2_kein_verweis_auf_einstellungen'] = seite.locator('.erststart-inhalt a.verweis').count() == 0
            # Was hinausging: nur die Domain, an den Namensdienst und den Server der Domain.
            pruef['2_nur_die_domain'] = all('@' not in f and 'lena.probe' not in f for f in dns.anfragen) \
                and autoconfig.anfragen == [('autoconfig.example.org', '/mail/config-v1.1.xml')]
            bild('01-mail-erkannt-1280')
            tippen('#erststart-passwort', 'vertippt', 'Passwort (falsch)')
            knopf = seite.get_by_role('button', name='Postfach verbinden')
            knopf.click()
            meldung = seite.locator('form.postfach-adresse [role=alert]')
            pruef['4_assistent'] = am_knopf(meldung, knopf)
            pruef['4_text'] = meldung.inner_text()
            pruef['4_nennt_server'] = pruef['4_text'].startswith('Der Mailserver 127.0.0.1 hat die Anmeldung abgelehnt')
            pruef['4_assistent_ok'] = pruef['4_assistent']['im_bild'] and pruef['4_assistent']['fokus'] \
                and pruef['4_assistent']['abstand_px'] < 120
            bild('02-mail-abgelehnt-1280')
            tippen('#erststart-passwort', PASSWORT, 'Passwort')
            knopf.click()
            seite.get_by_text('Dein Postfach ist verbunden.').wait_for(timeout=20000)
            pruef['2_verbunden'] = seite.url.endswith('/willkommen?schritt=mail') or '/willkommen' in seite.url

            # Dasselbe über SRV; und ohne jeden Fund Servername und Port im Assistenten.
            seite.get_by_role('button', name='Noch ein Postfach verbinden').click()
            seite.locator('#erststart-adresse').fill('lena.probe@verein-probe.example')
            seite.get_by_text('Erkannt: 127.0.0.1.', exact=False).wait_for(timeout=20000)
            pruef['2_srv_erkannt'] = seite.locator('#erststart-anbieter').count() == 0
            seite.locator('#erststart-adresse').fill('lena.probe@eigen-probe.example')
            seite.locator('#erststart-anbieter').wait_for(timeout=20000)
            seite.locator('#erststart-anbieter').select_option('eigen')
            pruef['2_letzte_moeglichkeit'] = seite.locator('#erststart-server').count() == 1 \
                and seite.locator('#erststart-port').input_value() == '993' \
                and seite.get_by_text('oft heißt er imap.', exact=False).count() == 1
            pruef['2_letzte_im_assistenten'] = '/willkommen' in seite.url
            bild('03-mail-nicht-gefunden-1280')
            seite.locator('#erststart-adresse').fill('')
            seite.get_by_role('button', name='Weiter', exact=True).click()

            # -- 5: Kalender beim Mailserver der Domain, Passwort des Postfachs -----------------------------------
            seite.get_by_role('heading', name='Deinen Kalender verbinden').wait_for(timeout=15000)
            formular = seite.locator('form.kalender-adresse')
            formular.get_by_text('Kingfisher sucht deinen Kalender selbst beim Mailserver deiner Domain', exact=False).wait_for(timeout=20000)
            pruef['5_adresse_steht_da'] = seite.locator('#kalender-adresse').input_value() == ADRESSE
            pruef['5_passwort_des_postfachs'] = formular.get_by_text('dasselbe Passwort wie für dein Postfach').count() == 1
            formular.get_by_role('button', name='Kalender suchen und verbinden').click()
            seite.get_by_role('button', name='Weiteren Kalender verbinden').wait_for(timeout=20000)
            pruef['5_satz_bleibt'] = seite.locator('.erststart-ok', has_text='Verbunden: dein Kalender „Privat“.').count() == 1
            pruef['5_ohne_passwort_zuerst'] = bool(caldav.anfragen_an) and caldav.anfragen_an[0][2] is False
            bild('04-kalender-gefunden-1280')
            seite.get_by_role('button', name='Weiteren Kalender verbinden').click()
            seite.locator('#kalender-adresse').fill('lena.probe@outlook.com')
            link = seite.get_by_role('link', name='Zu den Kalendereinstellungen von Outlook')
            link.wait_for(timeout=15000)
            pruef['5_outlook_link'] = link.get_attribute('href', timeout=5000).startswith('https://outlook.live.com/')
            seite.locator('#kalender-adresse').fill(ADRESSE)
            seite.get_by_role('button', name='Weiter', exact=True).click()

            # -- 6 und 7: Laden starten, sofort weiter ---------------------------------------------------------------
            seite.get_by_role('heading', name='Kingfisher auf diesem Rechner einrichten').wait_for(timeout=15000)
            karte = seite.locator('.rechner-karte')
            start = karte.get_by_role('button', name='Laden starten')
            start.wait_for(timeout=20000)
            vorher = karte.inner_text()
            groesse = re.search(r'Einmal laden: etwa ([\d,]+) GB', vorher)
            orchester = seite.request.get(basis + '/api/v1/models/recommendation').json()['orchester']
            pruef['6_groesse_aus_einer_quelle'] = bool(groesse) and float(groesse.group(1).replace(',', '.')) \
                == round(orchester['festplatte_noch_gb'], 1)
            pruef['6_laeuft_im_hintergrund_steht_da'] = 'im Hintergrund' in vorher
            bild('05-dieser-rechner-1280')
            start.click()
            karte.get_by_text('Kingfisher lädt sein Sprachmodell:', exact=False).wait_for(timeout=15000)
            weiter = seite.get_by_role('button', name='Weiter', exact=True)
            pruef['6_weiter_sofort'] = weiter.is_enabled()
            pruef['6_kein_bereit_waehrenddessen'] = karte.get_by_text('Alles eingerichtet').count() == 0 \
                and seite.get_by_text('Kingfisher kann auf diesem Rechner schon Fragen beantworten.').count() == 0
            bild('06-laedt-1280')
            weiter.click()
            seite.get_by_role('heading', name='Was darf Kingfisher noch?').wait_for(timeout=15000)
            stand = seite.request.get(basis + '/api/v1/models/laden').json()
            pruef['6_laedt_weiter'] = stand['laeuft'] is True
            schritte = seite.request.get(basis + '/api/v1/einrichtung').json()['schritte']
            pruef['6_nicht_als_erledigt_vermerkt'] = schritte.get('modell') != 'erledigt'
            seite.get_by_role('button', name='Überspringen').click()

            # -- 8: Fertig ----------------------------------------------------------------------------------------
            seite.get_by_role('heading', name='Fertig – dein erstes Briefing entsteht jetzt').wait_for(timeout=15000)
            seite.get_by_text('Kingfisher lädt sein Sprachmodell:', exact=False).first.wait_for(timeout=15000)
            hintergrund = seite.locator('.erststart-hintergrund').inner_text()
            pruef['8_nur_verbundenes'] = 'Kingfisher liest deine Mails und Termine.' in hintergrund
            pruef['8_kein_bereit_beim_laden'] = seite.get_by_text('Dein Briefing ist bereit').count() == 0
            bild('07-fertig-1280')
            seite.get_by_role('button', name='Zum Briefing').click()

            # -- 9 und 6: Briefing ohne Modell, Kopf mit Zeitzone, Fortschritt auf Heute ---------------------------
            seite.wait_for_url(re.compile(r'/today'), timeout=20000)
            kopf = seite.locator('.drawer-heading span')
            kopf.wait_for(timeout=20000)
            pruef['9_kopf'] = kopf.inner_text()
            pruef['9_zeitzone'] = 'Europe/Berlin' in pruef['9_kopf'] and 'UTC' not in pruef['9_kopf']
            bild('08-briefing-1280')
            seite.get_by_role('button', name='Zurück zu Heute').click()
            seite.get_by_text('Kingfisher lädt sein Sprachmodell:', exact=False).first.wait_for(timeout=15000)
            pruef['6_heute_zeigt_fortschritt'] = True
            gespraech = seite.request.post(basis + '/api/v1/conversations', data={'title': 'Probe'}).json()
            gid = gespraech['conversation']['id']
            antwort = seite.request.post(basis + f'/api/v1/conversations/{gid}/messages',
                                         data={'message': 'Was steht heute an?'}).json()
            texte = json.dumps(antwort, ensure_ascii=False)
            pruef['6_antwort_ehrlich'] = bool(re.search(r'Kingfisher lädt noch sein Sprachmodell \(\d+ %\)', texte))
            bild('09-heute-laedt-1280')
            halt.set()
            app.state.pull_manager.warte(30)
            for _ in range(60):
                if not seite.request.get(basis + '/api/v1/models/laden').json()['laeuft']:
                    break
                time.sleep(0.5)
            stand = seite.request.get(basis + '/api/v1/models/laden').json()
            pruef['7_am_ende'] = (stand['laeuft'], sorted(stand['eingerichtet']), stand['fehlgeschlagen'])
            seite.get_by_text('Kingfisher lädt sein Sprachmodell:', exact=False).first.wait_for(state='detached', timeout=30000)
            pruef['6_heute_ohne_ladezeile_danach'] = True
            seite.goto(basis + '/willkommen?schritt=modell')
            seite.get_by_text('Alles eingerichtet und geprüft.').wait_for(timeout=20000)
            pruef['7_ein_satz'] = seite.get_by_text('Alles eingerichtet und geprüft.').count() == 1 \
                and seite.get_by_text('Fast alles').count() == 0

            # -- 3, 23, 24, 4: Zugänge --------------------------------------------------------------------------
            seite.goto(basis + '/settings#zugaenge')
            seite.locator('#settings-zugaenge:not([hidden])').wait_for(timeout=15000)
            hinzu = seite.get_by_role('button', name='Postfach hinzufügen', exact=True)
            pruef['24_beschriftet'] = hinzu.inner_text().strip() == 'Postfach hinzufügen' \
                and seite.get_by_role('button', name='Kalender hinzufügen', exact=True).inner_text().strip() == 'Kalender hinzufügen'
            ms = seite.locator('section.ms-zugang')
            innen = ms.evaluate('e => [getComputedStyle(e).paddingLeft, getComputedStyle(e).paddingTop]')
            pruef['23_innenabstand'] = innen
            pruef['23_ok'] = all(float(w.removesuffix('px')) >= 16 for w in innen)
            bild('10-zugaenge-1280')
            # Die zuletzt getippte Adresse steht im Formular (Befund 3).
            seite.evaluate("() => sessionStorage.setItem('kingfisher.adresse-entwurf', 'lena.probe@eigen-probe.example')")
            hinzu.click()
            pruef['3_adresse_uebernommen'] = seite.locator('#zugang-postfach-adresse').input_value() == 'lena.probe@eigen-probe.example'
            seite.locator('summary', has_text='Für Techniker: Servereinstellungen von Hand').click()
            technik = seite.locator('form.source-form', has_text='Servereinstellungen')
            pruef['3_auch_in_den_servereinstellungen'] = technik.get_by_label('E-Mail-Adresse').input_value() == 'lena.probe@eigen-probe.example'
            technik.get_by_label('Name').fill('Vertippt2')
            technik.get_by_label('IMAP-Server').fill('127.0.0.1')
            technik.get_by_label('IMAP-Port').fill(str(imap.port))
            technik.get_by_label('Postfachpasswort').fill('vertippt')
            speichern = technik.get_by_role('button', name='Lokal speichern')
            speichern.click()
            meldung = technik.locator('[role=alert]')
            pruef['4_zugaenge'] = am_knopf(meldung, speichern)
            pruef['4_zugaenge_text'] = meldung.inner_text()
            pruef['4_zugaenge_ok'] = pruef['4_zugaenge']['im_bild'] and pruef['4_zugaenge']['fokus'] \
                and pruef['4_zugaenge']['abstand_px'] < 120 and 'Vertippt2' not in pruef['4_zugaenge_text'] \
                and seite.locator('.settings-page > .settings-error').count() == 0
            bild('11-zugaenge-abgelehnt-1280')

            # -- 30: Ordner per Auswahl ------------------------------------------------------------------------------
            meetings = seite.locator('section.transkript-eingang')
            meetings.get_by_role('button', name='Anderen Ordner auswählen …').click()
            meetings.get_by_role('button', name='Documents', exact=True).click()
            meetings.get_by_role('button', name='Mitschriften', exact=True).click()
            meetings.get_by_role('button', name='Diesen Ordner verwenden').click()
            meetings.get_by_text('Freigegeben: ~/Documents/Mitschriften', exact=False).wait_for(timeout=15000)
            pruef['30_ohne_tippen'] = True
            bild('12-ordner-ausgewaehlt-1280')

            # -- 25: 390 px -------------------------------------------------------------------------------------------
            seite.set_viewport_size({'width': 390, 'height': 844})
            seite.goto(basis + '/today')
            aktiv = seite.locator('.sidebar .nav-item.active span')
            aktiv.wait_for(timeout=15000)
            box = aktiv.bounding_box()
            pruef['25_bereich'] = aktiv.inner_text()
            pruef['25_bereich_lesbar'] = box is not None and box['width'] > 20 and 0 <= box['x'] and box['x'] + box['width'] <= 390
            bild('13-heute-390')
            seite.goto(basis + '/willkommen?schritt=kalender')
            name = seite.locator('.erststart-punkt.ist-aktuell .erststart-punkt-name')
            name.wait_for(timeout=15000)
            box = name.bounding_box()
            pruef['25_schritt'] = name.inner_text()
            pruef['25_schritt_lesbar'] = box is not None and box['width'] > 20 and 0 <= box['x'] and box['x'] + box['width'] <= 390
            pruef['25_kein_waagerechtes_rollen'] = seite.evaluate('() => document.documentElement.scrollWidth <= 390')
            bild('14-assistent-390')
        finally:
            browser.close()

    uv.should_exit = True
    for dienst in (imap, caldav, autoconfig, dns):
        dienst.schliessen()
    pruef['getippt_im_assistenten'] = ergebnis['getippt']
    falsch = [k for k, v in pruef.items() if v is False]
    ergebnis['nicht_bestanden'] = falsch
    ergebnis['ok'] = not falsch and not ergebnis['konsole']
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(f"Prüfungen: {len(pruef)} · nicht bestanden: {', '.join(falsch) or 'keine'} · "
          f"Konsole: {'leer' if not ergebnis['konsole'] else len(ergebnis['konsole'])}")
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
