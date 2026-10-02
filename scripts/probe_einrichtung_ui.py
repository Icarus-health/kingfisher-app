#!/usr/bin/env python3
"""Browserprobe zur Einrichtung (docs/48-fremdprobe.md): die Befunde 6, 7, 8, 10, 11, 19, 25, 26 und 27.

Echter Sidecar (`create_app()` unter uvicorn, frisches Datenverzeichnis, eigenes Benutzerverzeichnis), echte
Oberfläche (`npm run build`), Chromium über Playwright. Dazu als echte TLS-Dienste auf 127.0.0.1 eine IMAP-Attrappe
(`sidecar/tests/imap_attrappe.py`) und eine CalDAV-Attrappe (`sidecar/tests/caldav_attrappe.py`), beide hinter dem
Anbieter „Probe-Post“ für `example.org`; Ollama als Attrappe im Prozess (`tests/ollama_fake.py`), deren Prüfung das
erste Prüfmodell durchfallen lässt. Kein Mac-Helfer, kein Docker, kein Netz. Nur synthetische Zugänge
(`lena.probe@example.org`).

Geprüft wird im Browser:

* 26: Ohne Helfer hat die Einrichtung sechs Schritte („Schritt 1 von 6“), ohne „Beim Anmelden“; meldet sich ein
  Mac-Helfer, ist die Frage wieder da (sieben).
* 27: Bei 1280 px steht die Schrittleiste in einer Zeile, „Fertig“ bricht nicht um (mit sechs und sieben Punkten).
* 25: „Einstellungen → …“ sind Verweise, die dorthin springen (Fertig-Seite, Freigaben, leere Wetterkachel im Briefing).
* 19: Fahrzeiten lassen sich ohne Startort und ohne Kartendienst nicht einschalten; die Karte bietet das Feld für den
  Startort an und sagt, was fehlt; mit Kartendienst geht es, und die Marke steht sofort auf „An“.
* 6: Meetings ohne Mac-Helfer: Vorgabeordner mit einem Klick, ohne Fenster; Dokumente: falscher Pfad bekommt einen Satz,
  ein echter Ordner wird gelesen.
* 7: Kalender mit der Mailadresse: Anbieter erkannt, Passwort des Postfachs gilt, Kalender gefunden; falsches Passwort,
  unbekannter Anbieter und Google mit je einem Satz; unter Zugänge derselbe Weg.
* 8: Sicherung ohne Helfer: ein Passwortfeld mit „anzeigen“, Download, die Datei lässt sich wiederherstellen.
* 10 und 11: „Dieser Rechner“ ohne Modellnamen, „Messlatte“ und „nachts“ im Vordergrund, mit selbst ermittelter
  Ausstattung, Größe und Dauer, einem Knopf; das Prüfmodell fällt durch, die übrigen werden trotzdem geladen, der Stand
  sagt „Prüfung nicht bestanden“, „Anderes Modell nehmen“ macht es bereit.
* die Konsole bleibt ohne Fehler, außer den absichtlich ausgelösten Fehlantworten (422), die getrennt stehen.

Aufruf: `python scripts/probe_einrichtung_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build`).
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
SICHERUNGSPASSWORT = 'ein-langes-probe-passwort'

ZEILE_JS = """(auswahl) => {
  const punkte = [...document.querySelectorAll(auswahl)];
  const oben = new Set(punkte.map(p => Math.round(p.getBoundingClientRect().top)));
  const namen = punkte.map(p => { const s = p.querySelector('.erststart-punkt-name'); const r = s.getBoundingClientRect();
    return {name: s.textContent, hoehe: Math.round(r.height), zeilen: s.getClientRects().length}; });
  return {zeilen: oben.size, namen, seite: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""


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

    from tests.caldav_attrappe import CaldavAttrappe
    from tests.dns_attrappe import Namensdienst
    from tests.imap_attrappe import PASSWORT, ImapAttrappe
    imap, caldav, dns = ImapAttrappe(), CaldavAttrappe(), Namensdienst()
    arbeit = Path(tempfile.mkdtemp(prefix='probe-einrichtung-'))
    zuhause, daten = arbeit / 'home', arbeit / 'daten'
    zuhause.mkdir()
    # Beide Attrappen haben ein eigenes, selbst ausgestelltes Zertifikat; der Sidecar vertraut beiden wie echten.
    buendel = arbeit / 'zertifikate.pem'
    buendel.write_text(imap.zertifikat.read_text() + caldav.zertifikat.read_text())
    # Eine fremde Domain fragt der Sidecar am Namensdienst nach ihrem Mailserver; hier antwortet eine Attrappe.
    os.environ.update(ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(buendel), HOME=str(zuhause),
                      KINGFISHER_DNS=f'127.0.0.1:{dns.port}')
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'ICARUS_ORS_KEY',
                 'ICARUS_GOOGLE_ROUTES_KEY', 'KINGFISHER_ORDNER', 'KINGFISHER_USER_NAME'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import mail_anmeldung, ordner_lokal, providers_mail
    from icarus_memory.model_recommendation import KATALOG
    from icarus_memory.providers_mail import MailProvider
    from icarus_memory.recovery_bundle import restore_bundle
    from icarus_memory.server import create_app
    from tests.ollama_fake import FakeOllama

    providers_mail.PROVIDERS = (*providers_mail.PROVIDERS, MailProvider(
        id='probepost', label='Probe-Post', imap_host='127.0.0.1', smtp_host='127.0.0.1', imap_port=imap.port,
        domains=('example.org',), caldav_url=caldav.start))
    mail_anmeldung.ZEITGRENZE = 3.0
    ordner_lokal.im_container = lambda: False  # die Probe läuft wie ein Sidecar direkt auf dem Rechner

    from icarus_memory import server_finden
    from tests.autoconfig_attrappe import kein_netz
    server_finden.TRANSPORT = kein_netz()  # eine fremde Domain wird nur über die DNS-Attrappe gesucht, nie im Netz

    app = create_app()
    ollama = FakeOllama()
    app.state.ollama_transport = ollama.transport
    app.state.ollama_inventar.vergiss()
    durchgefallen: list[str] = []

    def modell_pruefung(modell: str, rolle: str) -> dict:
        # Das erste Prüfmodell fällt durch (Befund 11); jedes weitere besteht.
        bestanden = not (rolle == 'pruefung' and not durchgefallen)
        if not bestanden:
            durchgefallen.append(modell)
        return {'verifiziert': bestanden, 'latenz_ms': 12, 'profil': None}
    app.state.modell_pruefung = modell_pruefung

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
    modellnamen = sorted({e.name for e in KATALOG})

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        kontext = browser.new_context(viewport={'width': 1280, 'height': 1000}, accept_downloads=True)
        seite = kontext.new_page()
        erwartet = re.compile(r'/api/v1/(integrations/calendar/anmelden|folder-sync/lokal|transcript-sync/lokal)$')

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
            pfad = args.ausgabe / f'einrichtung-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def schritt(name: str, titel: str) -> None:
            seite.goto(f'{basis}/willkommen?schritt={name}')
            seite.get_by_role('heading', name=titel).wait_for(timeout=15000)

        def freigabe(titel: str):
            return seite.locator('.erststart-freigaben > li').filter(has=seite.locator('strong', has_text=titel))

        try:
            # -- 26 und 27: ohne Helfer sechs Schritte in einer Zeile ------------------------------------------
            pruef['26_stand_ohne_helfer'] = seite.request.get(basis + '/api/v1/einrichtung').json()['autostart_verfuegbar'] is False
            schritt('name', 'Wie heißt du?')
            pruef['26_zaehler'] = seite.locator('.erststart-zaehler').inner_text()
            punkte = seite.locator('.erststart-punkte li')
            pruef['26_sechs_schritte'] = pruef['26_zaehler'] == 'Schritt 1 von 6' and punkte.count() == 6 \
                and seite.locator('.erststart-punkte', has_text='Beim Anmelden').count() == 0
            zeile = seite.evaluate(ZEILE_JS, '.erststart-punkte li')
            pruef['27_sechs_eine_zeile'] = zeile['zeilen'] == 1 and all(n['zeilen'] == 1 for n in zeile['namen']) and zeile['seite'] <= 0
            bild('01-sechs-schritte')
            seite.request.post(basis + '/api/v1/autostart/helfer', data={'plattform': 'macos', 'eingerichtet': False})
            seite.reload()
            seite.get_by_role('heading', name='Wie heißt du?').wait_for(timeout=15000)
            pruef['26_mit_helfer_sieben'] = seite.locator('.erststart-zaehler').inner_text() == 'Schritt 1 von 7' \
                and seite.locator('.erststart-punkte', has_text='Beim Anmelden').count() == 1
            zeile = seite.evaluate(ZEILE_JS, '.erststart-punkte li')
            pruef['27_zeile'] = zeile
            fertig = next(n for n in zeile['namen'] if n['name'] == 'Fertig')
            pruef['27_sieben_eine_zeile'] = zeile['zeilen'] == 1 and fertig['zeilen'] == 1 and zeile['seite'] <= 0
            bild('02-sieben-schritte-1280')

            # -- 25: Fertig-Seite ohne Verbindungen: der Weg zu den Zugängen ist ein Klick --------------------------
            schritt('fertig', 'Fertig – dein erstes Briefing entsteht jetzt')
            zugaenge = seite.locator('.erststart-inhalt a.verweis', has_text='Einstellungen → Zugänge')
            zugaenge.wait_for(timeout=15000)
            zugaenge.click()
            seite.wait_for_url(re.compile(r'/settings#zugaenge$'), timeout=15000)
            seite.locator('#settings-zugaenge:not([hidden])').wait_for(timeout=15000)
            pruef['25_fertig_springt_zu_zugaengen'] = True

            # -- 10 und 11: Dieser Rechner -----------------------------------------------------------------------
            schritt('modell', 'Kingfisher auf diesem Rechner einrichten')
            karte = seite.locator('.rechner-karte')
            karte.get_by_role('button', name='Laden starten').wait_for(timeout=20000)
            vorne = seite.evaluate("""() => { const k = document.querySelector('.rechner-karte').cloneNode(true);
                k.querySelectorAll('details').forEach(d => d.remove()); return k.innerText; }""")
            pruef['10_vorne'] = vorne
            pruef['10_ohne_modellnamen'] = not [n for n in modellnamen if n in vorne] \
                and not any(w in vorne for w in ('Messlatte', 'nachts', 'gemeldet'))
            pruef['10_faehigkeiten'] = all(t in vorne for t in ('Deine Fragen beantworten', 'Im Hintergrund einordnen', 'Antworten prüfen'))
            pruef['10_ausstattung_selbst'] = 'GB Arbeitsspeicher' in vorne
            pruef['10_groesse_und_dauer'] = bool(re.search(r'Einmal laden: etwa [\d,]+ GB, je nach Internetleitung \d+ bis \d+ Minuten', vorne))
            pruef['10_ein_knopf'] = karte.get_by_role('button').count() == 1
            bild('03-dieser-rechner')
            karte.get_by_role('button', name='Laden starten').click()
            # Fremdprobe 2, Befund 7: ein Satz, der stimmt (eine Aufgabe fiel durch), nie „Fast alles“.
            seite.get_by_text('Teilweise eingerichtet: 4 von 5 Aufgaben.', exact=False).wait_for(timeout=60000)
            pruef['11_kein_fast_alles'] = seite.get_by_text('Fast alles').count() == 0
            marken = {li.locator('strong').inner_text(): li.locator('.rechner-marke').inner_text()
                      for li in karte.locator('.rechner-faehigkeiten li').all()}
            pruef['11_marken'] = marken
            pruef['11_status_passend'] = marken.get('Antworten prüfen') == 'Prüfung nicht bestanden' \
                and marken.get('Deine Fragen beantworten') == 'Bereit' and marken.get('Im Hintergrund einordnen') == 'Bereit'
            geladen = [b['model'] for m, pfad, b in ollama.anfragen if pfad == '/api/pull']
            pruef['11_geladen'] = geladen
            pruef['11_uebrige_trotzdem_geladen'] = len(geladen) >= 4 and durchgefallen != []
            problem = karte.locator('.rechner-problem')
            pruef['11_satz'] = problem.inner_text()
            pruef['11_kein_fachwort'] = 'Messlatte' not in pruef['11_satz'] and 'Alternativen' not in pruef['11_satz']
            bild('04-pruefung-nicht-bestanden')
            problem.get_by_role('button', name='Anderes Modell nehmen').click()
            seite.get_by_text('Eingerichtet und geprüft.').wait_for(timeout=60000)
            pruef['11_danach_bereit'] = karte.locator('.rechner-faehigkeiten li', has_text='Antworten prüfen') \
                .locator('.rechner-marke').inner_text() == 'Bereit'
            karte.locator('details.rechner-techniker summary').click()
            pruef['10_namen_nur_fuer_techniker'] = any(n in karte.locator('details.rechner-techniker').inner_text() for n in modellnamen)
            bild('05-anderes-modell')

            # -- 7: Kalender wie Mail ----------------------------------------------------------------------------
            antwort = seite.request.post(basis + '/api/v1/integrations/mail', data={
                'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': imap.port, 'user': ADRESSE,
                'sender': ADRESSE, 'password': PASSWORT})
            assert antwort.ok, antwort.text()
            schritt('kalender', 'Deinen Kalender verbinden')
            formular = seite.locator('form.kalender-adresse')
            formular.get_by_text('Erkannt: Probe-Post').wait_for(timeout=15000)
            pruef['7_adresse_steht_da'] = seite.locator('#kalender-adresse').input_value() == ADRESSE
            pruef['7_passwort_des_postfachs'] = formular.get_by_text('dasselbe Passwort wie für dein Postfach').count() == 1
            bild('06-kalender-erkannt')
            # Erst mit falschem Passwort: ein Satz, nichts verbunden.
            formular.get_by_role('button', name='Anderes Passwort eingeben').click()
            seite.locator('#kalender-passwort').fill('erfunden')
            formular.get_by_role('button', name='Kalender verbinden').click()
            pruef['7_falsch'] = formular.locator('[role=alert]').inner_text(timeout=15000)
            pruef['7_falsch_nicht_verbunden'] = 'abgelehnt' in pruef['7_falsch'] \
                and seite.request.get(basis + '/api/v1/integrations').json()['calendar_sources'] == []
            seite.locator('#kalender-passwort').fill(PASSWORT)
            formular.get_by_role('button', name='Kalender verbinden').click()
            # Nach dem Verbinden bleibt der Satz stehen; statt eines zweiten Knopfs zum Verbinden steht
            # „Weiteren Kalender verbinden“ da (Fremdprobe 3, Befund 7).
            weiterer = seite.get_by_role('button', name='Weiteren Kalender verbinden')
            weiterer.wait_for(timeout=15000)
            quellen = seite.request.get(basis + '/api/v1/integrations').json()['calendar_sources']
            pruef['7_verbunden'] = [q['label'] for q in quellen] == ['Probe-Post: Privat']
            pruef['7_satz_bleibt'] = seite.locator('.erststart-ok', has_text='Verbunden: dein Kalender „Privat“.').count() == 1
            pruef['7_kein_zweites_verbinden'] = seite.get_by_role('button', name=re.compile('^Kalender (suchen und )?verbinden$')).count() == 0
            bild('07-kalender-verbunden')
            weiterer.click()
            seite.locator('#kalender-adresse').fill('lena.probe@eigene-domain.example')
            # Fremdprobe 2, Befund 5: erst selbst suchen (beim Mailserver der Domain), dann nach der Adresse fragen.
            formular.get_by_text('Kingfisher sucht deinen Kalender selbst beim Mailserver deiner Domain', exact=False).wait_for(timeout=15000)
            pruef['7_unbekannt_sucht_selbst'] = seite.locator('#kalender-url').count() == 0
            seite.locator('#kalender-passwort').fill(PASSWORT)
            formular.get_by_role('button', name='Kalender suchen und verbinden').click()
            formular.get_by_text('Für diesen Anbieter brauche ich die Adresse deines Kalenders.').wait_for(timeout=20000)
            pruef['7_unbekannt_fragt_adresse'] = seite.locator('#kalender-url').count() == 1 \
                and formular.get_by_text('überspringen', exact=False).count() >= 1
            seite.locator('#kalender-adresse').fill('lena.probe@gmail.com')
            # Befund 2: Google geht ohne Passwort über die geheime iCal-Adresse (Einzelheiten in probe_google_ui.py).
            seite.get_by_text('Dein Kalender geht ohne Passwort über seine Adresse.').wait_for(timeout=5000)
            pruef['7_google_ehrlich'] = seite.locator('form.google-kalender-adresse').count() == 1 \
                and formular.get_by_role('button', name='Kalender verbinden').count() == 0
            bild('08-kalender-google')

            # -- 19: Fahrzeiten ----------------------------------------------------------------------------------
            schritt('freigaben', 'Was darf Kingfisher noch?')
            fahrt = freigabe('Fahrzeiten')
            fahrt.get_by_role('button', name='Einrichten').click()
            schalter = fahrt.get_by_role('switch')
            schalter.wait_for(timeout=15000)
            pruef['19_ohne_startort_gesperrt'] = schalter.is_disabled() \
                and fahrt.get_by_text('Für die Wegezeit fehlt noch dein Startort.').count() == 1
            fahrt.locator('#wegezeit-startort').fill('Musterstraße 1, 65183 Wiesbaden')
            fahrt.get_by_role('button', name='Startort speichern').click()
            fahrt.get_by_text('keine Apple Karten').wait_for(timeout=15000)
            pruef['19_ohne_dienst_gesperrt'] = schalter.is_disabled() \
                and fahrt.get_by_role('link', name=re.compile('Eigener Kartendienst')).count() == 1
            bild('09-fahrzeiten-ohne-dienst')
            seite.request.get(basis + '/api/v1/wegezeit/mac/anfragen')  # ein Mac-Arbeiter meldet sich: Apple Karten
            fahrt.get_by_role('button', name='Zuklappen').click()
            fahrt.get_by_role('button', name='Einrichten').click()
            schalter = fahrt.get_by_role('switch')
            schalter.wait_for(timeout=15000)
            seite.wait_for_function("() => { const s = [...document.querySelectorAll('.erststart-freigaben input[role=switch]')]; return s.length && !s[0].disabled; }", timeout=15000)
            schalter.click()
            fahrt.get_by_text('Wegezeit wird berechnet.').wait_for(timeout=15000)
            pruef['19_marke_sofort_an'] = fahrt.locator('.erststart-schalter').inner_text() == 'An'
            bild('10-fahrzeiten-an')

            # -- 6: Meetings ohne Mac-Helfer ---------------------------------------------------------------------
            meet = freigabe('Meetings')
            meet.get_by_role('button', name='Einrichten').click()
            vorgabe = meet.locator('button', has_text='Documents/Kingfisher/Transkripte')
            vorgabe.wait_for(timeout=15000)
            pruef['6_kein_fenster'] = 'Fenster' not in meet.inner_text()
            bild('11-meetings-ohne-helfer')
            vorgabe.click()
            meet.get_by_text('Freigegeben: ~/Documents/Kingfisher/Transkripte.').wait_for(timeout=15000)
            pruef['6_vorgabe_angelegt'] = (zuhause / 'Documents' / 'Kingfisher' / 'Transkripte').is_dir()
            meet.get_by_role('button', name='Zuklappen').click()
            seite.wait_for_function("() => [...document.querySelectorAll('.erststart-freigaben > li')].some(li => li.textContent.includes('Meetings') && li.querySelector('.erststart-schalter').textContent === 'An')", timeout=15000)
            pruef['6_meetings_an'] = True
            bild('12-meetings-an')

            # -- 25: Verweise statt Text -------------------------------------------------------------------------
            verweis = seite.locator('.erststart-inhalt a.verweis', has_text='Einstellungen → Was Kingfisher darf').first
            pruef['25_freigaben_ziel'] = verweis.get_attribute('href')
            schritt('fertig', 'Fertig – dein erstes Briefing entsteht jetzt')
            seite.get_by_role('button', name='Zum Briefing').wait_for(timeout=15000)
            verweise = seite.locator('.erststart-inhalt a.verweis')
            pruef['25_fertig_verweise'] = [(verweise.nth(i).inner_text(), verweise.nth(i).get_attribute('href'))
                                           for i in range(verweise.count())]
            pruef['25_fertig_ohne_weg_als_text'] = 'Einstellungen →' not in seite.evaluate(
                "() => { const k = document.querySelector('.erststart-inhalt').cloneNode(true); "
                "k.querySelectorAll('a.verweis').forEach(a => a.remove()); return k.innerText; }")
            seite.goto(basis + '/today?briefing=1')
            kachel = seite.locator('.weather-route-card a.verweis')
            kachel.wait_for(timeout=20000)
            pruef['25_briefing_text'] = kachel.inner_text()
            kachel.click()
            seite.wait_for_url(re.compile(r'/settings#darf$'), timeout=15000)
            seite.locator('#settings-darf:not([hidden])').wait_for(timeout=15000)
            pruef['25_briefing_springt'] = True
            pruef['25_freigaben_springt'] = pruef['25_freigaben_ziel'] == '/settings#darf'

            # -- 6: Dokumente ohne Helfer, unter Zugänge ---------------------------------------------------------
            ordner = arbeit / 'unterlagen'
            ordner.mkdir()
            (ordner / 'Vertrag.md').write_text('# Vertrag\nKündbar bis 30.11.')
            vorher = time.time() - 60
            os.utime(ordner / 'Vertrag.md', (vorher, vorher))
            seite.goto(basis + '/settings#zugaenge')
            seite.locator('#settings-zugaenge:not([hidden])').wait_for(timeout=15000)
            seite.locator('summary', has_text='Dokumente automatisch aufnehmen').click()
            # Der getippte Pfad steht nur noch eingeklappt für Techniker (Fremdprobe 2, Befund 30); geprüft wird er weiter.
            dokumente = seite.locator('.ordner-im-browser').filter(has=seite.locator('#ordner-pfad-dokumente'))
            dokumente.locator('summary', has_text='Für Techniker: Pfad eintippen').click()
            feld = seite.locator('#ordner-pfad-dokumente')
            feld.wait_for(timeout=15000)
            feld.fill(str(arbeit / 'gibt-es-nicht'))
            seite.get_by_role('button', name='Diesen Pfad verwenden').click()
            pruef['6_falscher_pfad'] = seite.locator('.ordner-im-browser [role=alert]').inner_text(timeout=15000)
            feld.fill(str(ordner))
            seite.get_by_role('button', name='Diesen Pfad verwenden').click()
            seite.get_by_text(f'Freigegeben: {ordner}. 1 Datei gelesen').wait_for(timeout=15000)
            pruef['6_dokument_gelesen'] = 'gibt es hier nicht' in pruef['6_falscher_pfad']
            bild('13-dokumente-im-browser')

            # -- 7: derselbe Weg unter Zugänge -------------------------------------------------------------------
            seite.get_by_role('button', name='Kalender hinzufügen').click()
            neu = seite.locator('.kalender-hinzufuegen')
            neu.get_by_text('Erkannt: Probe-Post').wait_for(timeout=15000)
            pruef['7_zugaenge_gleicher_weg'] = neu.locator('#kalender-adresse').input_value() == ADRESSE \
                and neu.locator('details.kalender-techniker').count() == 1
            bild('14-zugaenge-kalender')

            # -- 8: Sicherung ohne Helfer ------------------------------------------------------------------------
            seite.goto(basis + '/settings#sicherung')
            seite.locator('#settings-sicherung:not([hidden])').wait_for(timeout=15000)
            seite.get_by_role('button', name='Sicherung öffnen').click()
            feld = seite.locator('#sicherung-passwort')
            feld.wait_for(timeout=15000)
            text = seite.locator('#settings-sicherung').inner_text()
            pruef['8_kein_leeres_formular'] = 'Sicherungshelfer ist nicht erreichbar' not in text \
                and seite.locator('#settings-sicherung input[type=password], #settings-sicherung #sicherung-passwort').count() == 1
            feld.fill(SICHERUNGSPASSWORT)
            seite.get_by_role('button', name='anzeigen').click()
            pruef['8_anzeigen'] = feld.get_attribute('type') == 'text'
            with seite.expect_download(timeout=60000) as laden:
                seite.get_by_role('button', name='Sicherung herunterladen').click()
            datei = arbeit / laden.value.suggested_filename
            laden.value.save_as(str(datei))
            seite.get_by_text('Gesichert und geprüft.').wait_for(timeout=15000)
            wieder = restore_bundle(datei, arbeit / 'wiederhergestellt', SICHERUNGSPASSWORT)
            pruef['8_datei'] = datei.name
            pruef['8_wiederherstellbar'] = (wieder / 'data' / 'episodes.sqlite3').exists() and datei.stat().st_size > 0
            bild('15-sicherung')
        except Exception:
            bild('fehler')
            print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
            raise
        finally:
            browser.close()
            uv.should_exit = True
            imap.schliessen()
            caldav.schliessen()

    falsch = [k for k, v in pruef.items() if v is False]
    ergebnis['nicht_bestanden'] = falsch
    ergebnis['ok'] = not falsch and not ergebnis['konsole']
    (args.ausgabe / 'einrichtung-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(f"Prüfungen: {len(pruef)} · nicht bestanden: {falsch or 'keine'} · Konsole: {ergebnis['konsole'] or 'leer'}")
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
