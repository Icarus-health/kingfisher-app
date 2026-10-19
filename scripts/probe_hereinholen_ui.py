#!/usr/bin/env python3
"""Browserprobe „Hereinholen“: abgelaufene Anmeldung und Pause, in der echten Oberfläche mit echtem Sidecar.

Aufbau: frischer Datenordner, Zeitzone Europe/Berlin, ein skriptbares lokales Modell, eine IMAP-Attrappe mit fünf
synthetischen Mails. Das Passwort liegt in der verschlüsselten Schlüsseldatei des Datenordners. Nur synthetische Daten
(Lena Probe, Anna Berg, Jonas Keller).

Geprüft in Chromium:

* Anmeldung abgelaufen (das Passwort wurde beim Anbieter geändert): Heute, der Assistent und „Für Techniker“ sagen
  denselben Satz, „Melde dich unter Einstellungen → Zugänge neu an.“, ohne „Du musst nichts tun“ und ohne Text des
  Servers; „Einstellungen → Zugänge“ ist ein Verweis. Er führt zu Zugänge, dort steht am Postfach „Neu anmelden“. Ein
  falsches Passwort wird mit Satz am Knopf abgelehnt, das richtige sagt „Angemeldet“, kein zweites Postfach entsteht;
  nach dem nächsten Abruf ist der Satz weg. 390 px ohne seitliches Scrollen; die Konsole bleibt leer.
* Pause (falls `--pause`): siehe `pause_pruefen`.

Aufruf: `python scripts/probe_hereinholen_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `hereinholen-probe.json` liegen danach in DIR.
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
SATZ = ('Postfach Probe-Post lässt Kingfisher nicht mehr hinein: Die Anmeldung ist abgelaufen oder das Passwort hat '
        'sich geändert. Melde dich unter Einstellungen → Zugänge neu an.')


def main() -> int:  # noqa: PLR0915 - eine Probe, Schritt für Schritt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from tests.imap_attrappe import PASSWORT, ImapAttrappe, probe_postfach
    attrappe = ImapAttrappe(nachrichten=probe_postfach(), uidvalidity=7)
    daten = Path(tempfile.mkdtemp(prefix='hereinholen-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(attrappe.zertifikat))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright

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

    def takte(anzahl=2):
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
            pfad = args.ausgabe / f'hereinholen-{name}.png'
            seite.screenshot(path=str(pfad), full_page=ganz)
            ergebnis['bilder'].append(str(pfad))

        app.state.settings.einrichtung = {'name': 'Lena', 'schritte': {}, 'abgeschlossen': True}

        # -- Postfach verbinden und einlesen --------------------------------------------------------------------------
        antwort = api.post(basis + '/api/v1/integrations/mail', data={
            'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': attrappe.port, 'user': ADRESSE,
            'sender': ADRESSE, 'password': PASSWORT})
        assert antwort.status == 201, antwort.text()
        konto = api.get(basis + '/api/v1/integrations').json()['mail_accounts'][0]['id']
        umfang = api.get(f'{basis}/api/v1/mail/intake/{konto}/preview').json()
        assert api.post(f'{basis}/api/v1/mail/intake/{konto}/start', data={'folders': umfang['folders']}).ok
        takte()
        assert api.get(basis + '/api/v1/mail/stand').json()['accounts'][0]['zustand'] == 'aktuell'

        # -- Das Passwort wird beim Anbieter geändert ----------------------------------------------------------------
        attrappe.passwort = 'neues-geheimnis'
        takte(1)
        stand = api.get(basis + '/api/v1/mail/stand').json()['accounts'][0]
        pruef['stand'] = stand
        assert stand['zustand'] == 'fehler' and stand['satz'] == SATZ and stand['verweis'] == 'zugaenge', stand

        seite.goto(basis + '/today')
        postfach = seite.locator('.today-postfach')
        postfach.get_by_text('lässt Kingfisher nicht mehr hinein').wait_for(timeout=20000)
        text = postfach.inner_text()
        pruef['heute'] = text
        assert SATZ in text, text
        assert 'Du musst nichts tun' not in text and 'AUTHENTICATIONFAILED' not in text and 'Authentication' not in text
        link = postfach.get_by_role('link', name='Einstellungen → Zugänge')
        assert link.count() == 1
        bild('1-heute')
        seite.set_viewport_size({'width': 390, 'height': 844})
        seite.wait_for_timeout(500)
        breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
        pruef['heute_390'] = breite
        assert breite[0] <= breite[1], breite
        bild('1-heute-390')
        seite.set_viewport_size({'width': 1280, 'height': 900})

        # Der Assistent sagt dasselbe (eine Aussage je Postfach), mit demselben Verweis.
        seite.goto(basis + '/willkommen?schritt=mail')
        einlesen = seite.get_by_label('Mails einlesen')
        einlesen.get_by_text('lässt Kingfisher nicht mehr hinein').wait_for(timeout=20000)
        pruef['assistent'] = einlesen.inner_text()
        assert SATZ in pruef['assistent'] and 'stockt gerade' not in pruef['assistent']
        assert einlesen.get_by_role('link', name='Einstellungen → Zugänge').count() == 1
        bild('2-assistent')

        # „Für Techniker“ → Zeitplan und Hintergrund → Was zuletzt lief: derselbe Satz.
        seite.goto(basis + '/settings#technik-hintergrund')
        verlauf = seite.locator('details.mail-abruf-verlauf')
        verlauf.locator('summary').wait_for(timeout=20000)
        verlauf.locator('summary').click()
        verlauf.get_by_text('lässt Kingfisher nicht mehr hinein').wait_for(timeout=20000)
        pruef['techniker'] = verlauf.inner_text()
        assert SATZ in pruef['techniker']
        assert verlauf.get_by_role('link', name='Einstellungen → Zugänge').count() == 1
        bild('3-techniker')

        # -- Der Verweis führt zu Zugänge, dort: Neu anmelden ---------------------------------------------------------
        seite.goto(basis + '/today')
        seite.locator('.today-postfach').get_by_role('link', name='Einstellungen → Zugänge').click()
        seite.wait_for_url('**/settings#zugaenge', timeout=10000)
        knopf = seite.get_by_role('button', name='Neu anmelden')
        knopf.wait_for(timeout=20000)
        pruef['zugaenge'] = seite.locator('.neu-anmelden-stand').inner_text()
        assert SATZ in pruef['zugaenge']
        bild('4-zugaenge')
        knopf.click()
        formular = seite.get_by_role('form', name='Probe-Post neu anmelden')
        formular.get_by_label(f'Neues Passwort für {ADRESSE}').fill('immer-noch-falsch')
        formular.get_by_role('button', name='Anmelden').click()
        abgelehnt = formular.get_by_role('alert')
        abgelehnt.wait_for(timeout=20000)
        pruef['falsch'] = abgelehnt.inner_text()
        assert 'abgelehnt' in pruef['falsch'] and 'AUTHENTICATIONFAILED' not in pruef['falsch'], pruef['falsch']
        bild('5-falsch')
        formular.get_by_label(f'Neues Passwort für {ADRESSE}').fill('neues-geheimnis')
        formular.get_by_role('button', name='Anmelden').click()
        bestaetigt = seite.get_by_text('Angemeldet. Kingfisher liest Probe-Post gleich weiter.')
        bestaetigt.wait_for(timeout=20000)
        pruef['angemeldet'] = True
        assert seite.get_by_role('button', name='Neu anmelden').count() == 0
        konten = api.get(basis + '/api/v1/integrations').json()['mail_accounts']
        assert [k['id'] for k in konten] == [konto], 'kein zweites Postfach'
        bild('6-angemeldet')
        seite.set_viewport_size({'width': 390, 'height': 844})
        seite.wait_for_timeout(500)
        breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
        pruef['zugaenge_390'] = breite
        assert breite[0] <= breite[1], breite
        seite.set_viewport_size({'width': 1280, 'height': 900})

        takte(1)
        stand = api.get(basis + '/api/v1/mail/stand').json()['accounts'][0]
        pruef['danach'] = stand['satz']
        assert stand['zustand'] == 'aktuell', stand
        seite.goto(basis + '/today')
        seite.locator('.today-page h1').wait_for(timeout=15000)
        seite.wait_for_timeout(1500)
        assert seite.get_by_text('lässt Kingfisher nicht mehr hinein').count() == 0

        # Das absichtlich falsche Passwort antwortet 422; der Browser vermerkt das als Ladefehler. Sonst nichts.
        abgelehnt = [z for z in ergebnis['konsole'] if 'status of 422' in z]
        assert len(abgelehnt) == 1, ergebnis['konsole']
        ergebnis['konsole'] = [z for z in ergebnis['konsole'] if 'favicon' not in z and z not in abgelehnt]
        assert not ergebnis['konsole'], ergebnis['konsole']
        ergebnis['ok'] = True
        browser.close()
    (args.ausgabe / 'hereinholen-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    attrappe.schliessen()
    uv.should_exit = True
    print(json.dumps({'ok': ergebnis['ok'], 'bilder': len(ergebnis['bilder'])}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
