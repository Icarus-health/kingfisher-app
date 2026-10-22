#!/usr/bin/env python3
"""Browserprobe „Gesendete Mails auch einlesen“ (Paket B1): in der echten Oberfläche mit echtem Sidecar.

Aufbau: frischer Datenordner, Zeitzone Europe/Berlin, ein skriptbares lokales Modell, eine IMAP-Attrappe mit fünf
synthetischen Mails im Posteingang und einer eigenen Mail in „Gesendet“. Das Postfach ist wie ein Konto von vor dem
Umbau mit nur dem Posteingang gestartet und fertig gelesen. Nur synthetische Daten (Lena Probe, Anna Berg).

Geprüft in Chromium (Für Techniker → Zeitplan und Hintergrund → Ältere Mails einlesen):

* Der Satz zum Umfang kommt vom Sidecar („Nur der Posteingang; …“), darunter der Knopf „Gesendete Mails auch einlesen“.
* Antwortet das Postfach nicht, steht der Grund als Alert am Knopf; der Knopf bleibt.
* Der Klick trägt Gesendet nach: Status „Gesendete Mails werden jetzt mit eingelesen.“, der Satz zum Umfang wird
  „Posteingang und Gesendet; …“, der Knopf verschwindet, der Stand sagt „Gesendete Mails werden nachgelesen“ statt
  „wird durchgesehen“; nach dem nächsten Takt „ist gelesen: 6 Mails“ und die eigene Mail steht im Gedächtnis.
* 1280 und 390 px ohne seitliches Scrollen; die Konsole bleibt ohne Fehler.

Aufruf: `python scripts/probe_gesendet_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `gesendet-probe.json` liegen danach in DIR.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_fremdprobe3_ui import UMGEBUNG, sidecar  # noqa: E402
from probe_satzantwort_ui import CHROMIUM, freier_port  # noqa: E402

ADRESSE = 'lena.probe@example.org'
ZUSAGE = 'Ich schicke dir die Unterlagen bis Freitag.'
NUR_POSTEINGANG = 'Nur der Posteingang; gesendete und archivierte Mails sind bei diesem Konto nicht dabei.'
MIT_GESENDET = 'Posteingang und Gesendet; ohne Spam und Papierkorb.'
NEU = 'Gesendete Mails werden jetzt mit eingelesen.'
NACHGELESEN = ('Postfach Probe-Post: Der Posteingang ist gelesen (5 Mails). '
               'Gesendete Mails werden nachgelesen: bisher keine gefunden.')


def main() -> int:  # noqa: PLR0915 - eine Probe, Schritt für Schritt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from tests.imap_attrappe import PASSWORT, ImapAttrappe, probe_mail, probe_postfach
    gesendet = [probe_mail(f'Lena Probe <{ADRESSE}>', 'Unterlagen', f'Hallo Anna,\n\n{ZUSAGE}\n\nLena',
                           an='Anna Berg <anna.berg@example.org>', minuten=50)]
    attrappe = ImapAttrappe(nachrichten=probe_postfach(), gesendet=gesendet, uidvalidity=7)
    daten = Path(tempfile.mkdtemp(prefix='gesendet-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(attrappe.zertifikat))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import mail_intake_routes
    from icarus_memory.mail_intake import Intake
    mail_intake_routes.ZEITGRENZE = 2.0  # ein schweigendes Postfach soll in der Probe nicht 15 s dauern

    app = sidecar(daten)
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

    def takte(anzahl=3):
        app.state.scheduler.stop()  # im Takt der Probe, kein zweiter Durchgang dazwischen
        for _ in range(anzahl):
            app.state.scheduler._run_mail_intake()

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        kontext = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='de-DE', timezone_id='Europe/Berlin')
        seite = kontext.new_page()
        seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
        seite.goto(basis + '/today')
        api = seite.request

        def bild(name, ganz=False):
            pfad = args.ausgabe / f'gesendet-{name}.png'
            seite.screenshot(path=str(pfad), full_page=ganz)
            ergebnis['bilder'].append(str(pfad))

        def breite_pruefen(name):
            seite.set_viewport_size({'width': 390, 'height': 844})
            seite.wait_for_timeout(500)
            masse = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            pruef[f'{name}_390'] = masse
            assert masse[0] <= masse[1], masse
            bild(f'{name}-390')
            seite.set_viewport_size({'width': 1280, 'height': 900})
            seite.wait_for_timeout(300)

        app.state.settings.einrichtung = {'name': 'Lena', 'schritte': {}, 'abgeschlossen': True}

        # -- Ein Konto von vor dem Umbau: verbunden, mit nur dem Posteingang gestartet, fertig gelesen -----------------
        antwort = api.post(basis + '/api/v1/integrations/mail', data={
            'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': attrappe.port, 'user': ADRESSE,
            'sender': ADRESSE, 'password': PASSWORT})
        assert antwort.status == 201, antwort.text()
        konto = api.get(basis + '/api/v1/integrations').json()['mail_accounts'][0]['id']
        Intake(app.state.episodes).start(konto, ['INBOX'])
        app.state.settings.schedule.mail_accounts.append(konto)
        app.state.settings.schedule.enabled = True
        takte(3)
        stand = api.get(basis + '/api/v1/mail/stand').json()['accounts'][0]
        pruef['stand_vorher'] = stand
        assert stand['zustand'] == 'aktuell' and '5 Mails' in stand['satz'], stand

        # -- Für Techniker → Zeitplan und Hintergrund → Ältere Mails einlesen ------------------------------------------
        seite.goto(basis + '/settings#technik-hintergrund')
        einlesen = seite.locator('details.mail-abruf-einlesen')
        einlesen.locator('summary').wait_for(timeout=20000)
        einlesen.locator('summary').click()
        karte = einlesen.locator('.mail-intake-account').first
        karte.get_by_text(NUR_POSTEINGANG).wait_for(timeout=20000)
        knopf = karte.get_by_role('button', name='Gesendete Mails auch einlesen')
        assert knopf.count() == 1, 'ein Knopf, wo nur der Posteingang läuft'
        pruef['vorher'] = karte.inner_text()
        assert NUR_POSTEINGANG in pruef['vorher'] and 'Gesendete Mails auch einlesen' in pruef['vorher']
        bild('1-knopf')
        breite_pruefen('1-knopf')

        # -- Das Postfach schweigt: der Grund als Alert, der Knopf bleibt --------------------------------------------------
        attrappe.modus = 'stumm_nach_anmeldung'
        knopf.click()
        alert = einlesen.get_by_role('alert')
        alert.wait_for(timeout=20000)
        pruef['fehler'] = alert.inner_text()
        assert 'antwortet gerade nicht' in pruef['fehler'], pruef['fehler']
        assert 'Das hat nicht geklappt' not in pruef['fehler']
        assert karte.get_by_role('button', name='Gesendete Mails auch einlesen').count() == 1
        bild('2-fehler', ganz=True)
        attrappe.modus = 'annehmen'

        # -- Der Klick trägt Gesendet nach ---------------------------------------------------------------------------------
        karte.get_by_role('button', name='Gesendete Mails auch einlesen').click()
        status = karte.get_by_role('status').filter(has_text=NEU)
        status.wait_for(timeout=20000)
        karte.get_by_text(MIT_GESENDET).wait_for(timeout=20000)
        seite.wait_for_timeout(500)
        pruef['nachher'] = karte.inner_text()
        assert NEU in pruef['nachher'] and MIT_GESENDET in pruef['nachher'], pruef['nachher']
        assert karte.get_by_role('button', name='Gesendete Mails auch einlesen').count() == 0, 'Gesendet ist dabei: kein Knopf'
        assert NACHGELESEN in pruef['nachher'], pruef['nachher']
        assert 'wird durchgesehen' not in pruef['nachher']
        pruef['ordner'] = [f['folder'] for f in api.get(basis + '/api/v1/mail/intake').json()['accounts'][0]['folders']]
        assert sorted(pruef['ordner']) == ['Gesendet', 'INBOX'], pruef['ordner']
        bild('3-nachgetragen')
        breite_pruefen('3-nachgetragen')

        # -- Nächster Takt: die eigene Mail ist im Gedächtnis, der Stand ist wieder „gelesen“ ---------------------------
        takte(3)
        titel = {e.title for e in app.state.episodes.all_episodes(50)}
        pruef['im_gedaechtnis'] = sorted(titel)
        assert 'Unterlagen' in titel, titel
        stand = api.get(basis + '/api/v1/mail/stand').json()['accounts'][0]
        pruef['stand_nachher'] = stand
        assert stand['zustand'] == 'aktuell' and '6 Mails' in stand['satz'], stand
        seite.reload()
        einlesen = seite.locator('details.mail-abruf-einlesen')
        einlesen.locator('summary').wait_for(timeout=20000)
        einlesen.locator('summary').click()
        karte = einlesen.locator('.mail-intake-account').first
        karte.get_by_text('ist gelesen: 6 Mails').wait_for(timeout=20000)
        assert karte.get_by_role('button', name='Gesendete Mails auch einlesen').count() == 0
        pruef['gelesen'] = karte.inner_text()
        bild('4-gelesen')

        # Der absichtlich ausgelöste 503 erscheint als Chromiums eigene Netzmeldung: genau einmal, sonst nichts.
        erwartet = [z for z in ergebnis['konsole'] if 'status of 503' in z]
        assert len(erwartet) == 1, ergebnis['konsole']
        ergebnis['konsole_erwartet'] = erwartet
        ergebnis['konsole'] = [z for z in ergebnis['konsole'] if z not in erwartet]
        ergebnis['ok'] = not ergebnis['konsole']
        browser.close()
    attrappe.schliessen()
    (args.ausgabe / 'gesendet-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']},
                     ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
