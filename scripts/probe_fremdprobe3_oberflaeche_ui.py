#!/usr/bin/env python3
"""Browserprobe zur dritten Fremdprobe (docs/52-fremdprobe-3.md), Befunde der Oberfläche: 4, 5, 6, 7, 10, 14 und S3.

Echter Sidecar (`create_app()` unter uvicorn, frisches Datenverzeichnis), echte Oberfläche (`npm run build`), Chromium
über Playwright. Als echte Dienste auf 127.0.0.1, kein Netz nach außen: ein Namensdienst (`tests/dns_attrappe.py`), eine
Autoconfig-Attrappe für `example.org`, eine IMAP-Attrappe und eine CalDAV-Attrappe (ein Termin in Mainz) als Mailserver
der Domain. Ollama antwortet nicht (S3), der Ortsdienst des Wetters zuerst auch nicht (Befund 4). Nur synthetische Daten.

Geprüft wird im Browser, in der Reihenfolge des Assistenten:

* 5: Nach dem Verbinden fragt der Assistent „Soll Kingfisher dein Postfach lena.probe@example.org jetzt einlesen?“ und
  verweist fürs Pausieren auf Heute, nicht unter „Für Techniker“.
* 7: Nach dem Verbinden des Kalenders bleibt der Satz stehen, ein zweites „Kalender suchen und verbinden“ gibt es nicht;
  stattdessen „Weiteren Kalender verbinden“.
* S3: Ohne Ollama sagt „Dieser Rechner“, was fehlt, wo es das gibt und was ohne geht; eine Frage bekommt eine Antwort in
  Alltagssprache statt „einen Anbieter in .env eintragen“.
* 4: Freigaben: Wer das Wetter einschaltet, bekommt „Weiter“ statt „Überspringen“. Findet der Ortsdienst nichts, sagt
  der Schritt in einem Satz, dass das Wetter aus ist; die Leiste zeigt den Schritt danach als erledigt, nicht als
  übersprungen. Mit gefundenem Ort ist das Wetter an, und unter Einstellungen → Was Kingfisher darf auch.
* 6: Die Fertig-Seite nennt nur Zahlen, die stimmen (Termine wie im Gedächtnis).
* 10: Die Akte eines Ortes sagt „Jede Zeile führt zur Quelle.“ ohne „ohne Modell berechnet“.
* 14: Die Navigation bei 390 und 768 px: kein eigener waagerechter Rollbalken, alle Ziele ohne Rollen im Bild, keine
  abgeschnittene Beschriftung; die Seite läuft nicht seitlich über. Auf allen Seiten mit Seitenleiste.
* Die Konsole bleibt leer.

Aufruf: `python scripts/probe_fremdprobe3_oberflaeche_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build`).
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
from urllib.parse import quote

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
ADRESSE = 'lena.probe@example.org'

# Die Seitenleiste als Streifen oben (unter 900 px): rollt sie seitlich, ragt ein Ziel aus dem Bild oder aus der
# Leiste, oder ist eine sichtbare Beschriftung abgeschnitten?
NAVIGATION_JS = """() => {
  const w = document.documentElement.clientWidth, fehler = [];
  const leiste = document.querySelector('.sidebar'); if (!leiste) return {fehler: ['keine Seitenleiste'], ziele: 0};
  const nav = leiste.querySelector('nav');
  if (nav.scrollWidth > nav.clientWidth + 1) fehler.push('nav rollt seitlich: ' + nav.scrollWidth + ' > ' + nav.clientWidth);
  if (leiste.scrollWidth > leiste.clientWidth + 1) fehler.push('Leiste rollt seitlich: ' + leiste.scrollWidth + ' > ' + leiste.clientWidth);
  const l = leiste.getBoundingClientRect();
  const ziele = [...leiste.querySelectorAll('.nav-item')];
  for (const z of ziele) {
    const r = z.getBoundingClientRect(), name = z.textContent.trim();
    if (r.left < -1 || r.right > w + 1) fehler.push(name + ' außerhalb des Fensters');
    if (r.left < l.left - 1 || r.right > l.right + 1 || r.top < l.top - 1 || r.bottom > l.bottom + 1) fehler.push(name + ' außerhalb der Leiste');
    if (r.width < 40 || r.height < 40) fehler.push(name + ' kleiner als ein Finger: ' + Math.round(r.width) + '×' + Math.round(r.height));
    const span = z.querySelector('span'), cs = getComputedStyle(span);
    const sichtbar = !(cs.position === 'absolute' && cs.clip !== 'auto') && span.getBoundingClientRect().width > 1;
    if (sichtbar && (span.scrollWidth > span.clientWidth + 1 || span.getBoundingClientRect().right > r.right + 1))
      fehler.push(name + ': Beschriftung abgeschnitten');
  }
  const aktiv = leiste.querySelector('.nav-item.active span');
  const aktivSichtbar = aktiv && aktiv.getBoundingClientRect().width > 20;
  return {fehler, ziele: ziele.length, aktiv: aktiv ? aktiv.textContent : null, aktivSichtbar,
          seite: document.documentElement.scrollWidth - w,
          beschriftet: ziele.filter(z => z.querySelector('span').getBoundingClientRect().width > 1).length};
}"""


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

    imap, caldav = ImapAttrappe(), CaldavAttrappe()
    autoconfig = AutoconfigAttrappe(autoconfig={'example.org': config_xml('example.org', '127.0.0.1', imap.port)})
    dns = Namensdienst()
    arbeit = Path(tempfile.mkdtemp(prefix='probe-fremdprobe3-'))
    zuhause, daten = arbeit / 'home', arbeit / 'daten'
    zuhause.mkdir(parents=True)
    buendel = arbeit / 'zertifikate.pem'
    buendel.write_text(imap.zertifikat.read_text() + caldav.zertifikat.read_text() + autoconfig.zertifikat.read_text())
    os.environ.update(ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(buendel), HOME=str(zuhause),
                      KINGFISHER_DNS=f'127.0.0.1:{dns.port}', KINGFISHER_TIMEZONE='Europe/Berlin',
                      ICARUS_SECRETS_PASSPHRASE='probe-fremdprobe3-schluessel')
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'KINGFISHER_USER_NAME',
                 'KINGFISHER_ORDNER', 'KINGFISHER_WEATHER_ENABLED', 'KINGFISHER_WEATHER_LOCATION'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import mail_anmeldung, server_finden
    from icarus_memory.server import create_app
    from icarus_memory.wetter import WetterFehler
    from icarus_memory.wetter_routes import dienst as wetter_dienst

    mail_anmeldung.ZEITGRENZE = 3.0
    server_finden.TRANSPORT = autoconfig.transport()

    app = create_app()
    app.state.caldav_transport = caldav.transport('127.0.0.1')

    # Ollama ist nicht installiert: Jede Anfrage an 127.0.0.1:11434 scheitert wie ohne Dienst.
    def ohne_ollama(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('Verbindung abgelehnt', request=request)
    app.state.ollama_transport = httpx.MockTransport(ohne_ollama)
    app.state.ollama_inventar.vergiss()

    # Der Ortsdienst des Wetters antwortet zuerst nicht (wie ohne Netz in der Fremdprobe), später findet er Mainz.
    ortsdienst = {'antwortet': False}

    def holen(url, params, *args, **kwargs):
        if not ortsdienst['antwortet']:
            raise WetterFehler('keine Antwort')
        return {'results': [{'name': 'Mainz', 'latitude': 49.9929, 'longitude': 8.2473, 'admin1': 'Rheinland-Pfalz',
                             'country': 'Deutschland'}]}
    wetter_dienst(app)._holen = holen

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
        kontext = browser.new_context(viewport={'width': 1280, 'height': 900}, timezone_id='Europe/Berlin')
        seite = kontext.new_page()

        def konsole(m) -> None:
            if m.type in ('error', 'warning'):
                ergebnis['konsole'].append(f"{m.type}: {m.text} {(m.location or {}).get('url', '')}".strip())
        seite.on('console', konsole)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

        def bild(name: str) -> None:
            pfad = args.ausgabe / f'fremdprobe3-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def schritt(id_: str) -> str:
            return seite.request.get(basis + '/api/v1/einrichtung').json()['schritte'].get(id_, 'offen')

        try:
            # -- Name ---------------------------------------------------------------------------------------------
            seite.goto(basis + '/willkommen')
            seite.get_by_role('heading', name='Wie heißt du?').wait_for(timeout=20000)
            seite.locator('#erststart-name').fill('Lena')
            seite.get_by_role('button', name='Weiter', exact=True).click()

            # -- 5: Mail verbinden, die Frage nennt das Postfach ------------------------------------------------------
            seite.get_by_role('heading', name='Deine Mail verbinden').wait_for(timeout=15000)
            seite.locator('#erststart-adresse').fill(ADRESSE)
            seite.get_by_text('Erkannt: 127.0.0.1.', exact=False).wait_for(timeout=20000)
            seite.locator('#erststart-passwort').fill(PASSWORT)
            seite.get_by_role('button', name='Postfach verbinden').click()
            seite.get_by_text('Dein Postfach ist verbunden.').wait_for(timeout=20000)
            einlesen = seite.locator('.erststart-einlesen')
            einlesen.get_by_role('button', name='Mails einlesen').wait_for(timeout=15000)
            seite.get_by_text(f'Soll Kingfisher dein Postfach {ADRESSE} jetzt einlesen?', exact=False).wait_for(timeout=10000)
            pruef['5_text'] = einlesen.inner_text()
            pruef['5_nennt_das_postfach'] = f'dein Postfach {ADRESSE}' in pruef['5_text'] \
                and 'die Mails von' not in pruef['5_text']
            pruef['5_pausieren_auf_heute'] = 'auf Heute mit „Pausieren“' in pruef['5_text'] \
                and 'Für Techniker' not in pruef['5_text'] and einlesen.locator('a').count() == 0
            bild('01-mail-frage')
            seite.get_by_role('button', name='Weiter', exact=True).click()

            # -- 7: Kalender, nach dem Verbinden kein zweiter Knopf zum Verbinden -------------------------------------
            seite.get_by_role('heading', name='Deinen Kalender verbinden').wait_for(timeout=15000)
            seite.get_by_role('button', name='Kalender suchen und verbinden').click()
            weiterer = seite.get_by_role('button', name='Weiteren Kalender verbinden')
            weiterer.wait_for(timeout=20000)
            pruef['7_satz_bleibt'] = seite.locator('.erststart-ok', has_text='Verbunden: dein Kalender „Privat“.').count() == 1
            pruef['7_kein_zweites_verbinden'] = seite.get_by_role('button', name=re.compile(r'^Kalender (suchen und )?verbinden$')).count() == 0
            bild('02-kalender-verbunden')
            weiterer.click()
            # Die Adresse des Postfachs steht wieder da, sobald die Karte sie gelesen hat.
            seite.wait_for_function(f"() => document.querySelector('#kalender-adresse')?.value === '{ADRESSE}'", timeout=10000)
            pruef['7_weiterer_oeffnet_den_weg'] = True
            seite.get_by_role('button', name='Weiter', exact=True).click()

            # -- S3: Dieser Rechner ohne Ollama --------------------------------------------------------------------
            seite.get_by_role('heading', name='Kingfisher auf diesem Rechner einrichten').wait_for(timeout=15000)
            ohne = seite.locator('.rechner-ohne-ollama')
            ohne.wait_for(timeout=20000)
            pruef['s3_text'] = ohne.inner_text()
            pruef['s3_sagt_was_fehlt'] = 'kostenlosen Programm Ollama' in pruef['s3_text'] \
                and 'Ohne Ollama liest Kingfisher trotzdem deine Mails und Termine' in pruef['s3_text']
            pruef['s3_link'] = ohne.get_by_role('link', name='Ollama laden').get_attribute('href') == 'https://ollama.com/download'
            pruef['s3_kein_laden_starten'] = seite.get_by_role('button', name='Laden starten').count() == 0
            bild('03-rechner-ohne-ollama')
            seite.get_by_role('button', name='Überspringen').click()

            # -- 4: Freigaben -----------------------------------------------------------------------------------------
            seite.get_by_role('heading', name='Was darf Kingfisher noch?').wait_for(timeout=15000)
            fuss = seite.locator('.erststart-fuss')
            pruef['4_unberuehrt_ueberspringen'] = fuss.get_by_role('button', name='Überspringen').count() == 1
            wetter = seite.locator('.erststart-freigaben > li', has_text='Wetter')
            wetter.get_by_role('button', name='Einrichten').click()
            schalter = wetter.get_by_role('switch')
            schalter.wait_for(timeout=15000)
            schalter.click()
            seite.locator('#wetter-suche').fill('Mainz')
            wetter.get_by_role('button', name='Suchen').click()
            wetter.get_by_text('Der Ortsdienst antwortet gerade nicht.', exact=False).wait_for(timeout=15000)
            pruef['4_weiter_nach_anfassen'] = fuss.get_by_role('button', name='Weiter', exact=True).count() == 1 \
                and fuss.get_by_role('button', name='Überspringen').count() == 0
            hinweis = wetter.locator('.erststart-freigabe-hinweis')
            pruef['4_satz_ohne_ort'] = hinweis.count() == 1 \
                and hinweis.inner_text() == 'Das Wetter ist noch aus, weil noch kein Ort gewählt ist.'
            pruef['4_marke_aus'] = wetter.locator('.erststart-schalter').inner_text() == 'Aus'
            bild('04-freigaben-wetter-ohne-ort')
            wetter.get_by_role('button', name='Zuklappen').click()
            pruef['4_satz_bleibt_zugeklappt'] = wetter.locator('.erststart-freigabe-hinweis').count() == 1
            fuss.get_by_role('button', name='Weiter', exact=True).click()
            seite.get_by_role('heading', name=re.compile('^Fertig')).wait_for(timeout=15000)
            pruef['4_erledigt_nicht_uebersprungen'] = schritt('freigaben') == 'erledigt'
            punkt = seite.locator('.erststart-punkt', has_text='Freigaben')
            pruef['4_leiste'] = punkt.inner_text()
            pruef['4_leiste_erledigt'] = 'ist-erledigt' in (punkt.get_attribute('class') or '') \
                and '(übersprungen)' not in pruef['4_leiste']
            pruef['4_wetter_ehrlich_aus'] = seite.request.get(basis + '/api/v1/wetter/einstellungen').json()['aktiv'] is False

            # -- 6: Fertig, Zahlen wie im Gedächtnis ----------------------------------------------------------------
            # Gleich nach dem Ankommen alle 100 ms nachsehen: Nie darf dort „0“ stehen, solange der Abgleich läuft.
            gesehen: list[str] = []
            for _ in range(40):
                zahlen = seite.locator('.erststart-zahlen')
                text = zahlen.inner_text() if zahlen.count() else ''
                if not gesehen or gesehen[-1] != text:
                    gesehen.append(text)
                if re.search(r'Termine aufgenommen\s+1\b', text):
                    break
                seite.wait_for_timeout(100)
            gedaechtnis = seite.request.get(basis + '/api/v1/calendar-memory').json()
            termine = gedaechtnis['mac_termine'] + sum(q['termine'] for q in gedaechtnis['quellen'])
            pruef['6_gesehen'] = gesehen
            pruef['6_termine_im_gedaechtnis'] = termine
            pruef['6_nie_null'] = termine == 1 and not any(re.search(r'Termine aufgenommen\s+0\b', t) for t in gesehen)
            pruef['6_am_ende_richtig'] = bool(re.search(rf'Termine aufgenommen\s+{termine}\b', gesehen[-1]))
            # Die Mails werden noch nicht eingelesen: dann steht auch keine Zahl dafür da (der Satz darunter sagt es).
            pruef['6_keine_mailzahl_ohne_einlesen'] = 'Mails' not in gesehen[-1]
            bild('05-fertig')

            # Mit gefundenem Ort: an, und unter „Was Kingfisher darf“ ebenfalls an.
            ortsdienst['antwortet'] = True
            wetter_dienst(app)._gemerkt.clear()  # der gemerkte Fehler gälte sonst noch einige Minuten
            punkt.click()
            seite.get_by_role('heading', name='Was darf Kingfisher noch?').wait_for(timeout=15000)
            wetter.get_by_role('button', name='Einrichten').click()
            wetter.get_by_role('switch').click()
            seite.locator('#wetter-suche').fill('Mainz')
            wetter.get_by_role('button', name='Suchen').click()
            wetter.get_by_role('button', name=re.compile('^Mainz')).click()
            wetter.get_by_text('Das Wetter für Mainz steht jetzt im Briefing.').wait_for(timeout=15000)
            pruef['4_mit_ort_an'] = wetter.locator('.erststart-schalter').inner_text() == 'An' \
                and wetter.locator('.erststart-freigabe-hinweis').count() == 0
            bild('06-freigaben-wetter-an')
            seite.goto(basis + '/settings#darf')
            darf = seite.get_by_role('region', name='Morgens das Wetter holen')
            darf.get_by_role('switch').wait_for(timeout=15000)
            pruef['4_einstellungen_an'] = darf.get_by_role('switch').is_checked() and 'Ort: Mainz.' in darf.inner_text()
            bild('07-einstellungen-wetter-an')

            seite.goto(basis + '/willkommen?schritt=fertig')
            seite.get_by_role('button', name='Zum Briefing').click()
            seite.wait_for_url(re.compile(r'/today'), timeout=20000)

            # -- S3: eine Frage ohne Modell, im Gespräch ------------------------------------------------------------
            gespraech = seite.request.post(basis + '/api/v1/conversations', data={'title': 'Probe'}).json()['conversation']['id']
            seite.request.post(basis + f'/api/v1/conversations/{gespraech}/messages', data={'message': 'Was wollte Anna?'})
            seite.goto(basis + f'/conversations/{gespraech}')
            antwort = seite.locator('article.message.assistant').last
            antwort.wait_for(timeout=15000)
            pruef['s3_antwort'] = antwort.inner_text()
            pruef['s3_antwort_alltag'] = 'Ollama' in pruef['s3_antwort'] and '.env' not in pruef['s3_antwort'] \
                and '„Dieser Rechner“' in pruef['s3_antwort']
            bild('08-antwort-ohne-modell')

            # -- 10: Akte eines Ortes ---------------------------------------------------------------------------------
            sachen = seite.request.get(basis + '/api/v1/akten/sachen?art=ort&warten=true').json()['sachen']
            pruef['10_orte'] = [s['name'] for s in sachen]
            mainz = next(s for s in sachen if s['name'] == 'Mainz')
            seite.goto(basis + '/memory/akte/' + quote(mainz['sache'], safe=''))
            hinweis = seite.locator('.mappe-hinweis').first
            hinweis.wait_for(timeout=15000)
            pruef['10_text'] = hinweis.inner_text()
            pruef['10_ohne_fachsprache'] = 'Jede Zeile führt zur Quelle.' in pruef['10_text'] \
                and 'Modell' not in pruef['10_text']
            bild('09-akte-mainz')

            # -- 14: Navigation bei 390 und 768 px --------------------------------------------------------------------
            seiten = {'heute': '/today', 'gespraeche': '/conversations', 'aufgaben': '/vorhaben', 'gedaechtnis': '/memory',
                      'kalender': '/calendar', 'nachrichten': '/nachrichten', 'einstellungen': '/settings'}
            for breite in (390, 768):
                seite.set_viewport_size({'width': breite, 'height': 844})
                for name, pfad in seiten.items():
                    seite.goto(basis + pfad)
                    seite.locator('.sidebar .nav-item.active').wait_for(timeout=15000)
                    seite.wait_for_timeout(400)
                    nav = seite.evaluate(NAVIGATION_JS)
                    pruef[f'14_{breite}_{name}'] = nav
                    pruef[f'14_{breite}_{name}_ok'] = not nav['fehler'] and nav['ziele'] == 7 and nav['aktivSichtbar'] \
                        and nav['seite'] <= 0
                    if name in ('heute', 'kalender'):
                        bild(f'10-navigation-{name}-{breite}')
                # Bei 768 px tragen alle Ziele ihren Namen, bei 390 px nur der aktive.
                pruef[f'14_{breite}_beschriftet'] = pruef[f'14_{breite}_kalender']['beschriftet']
                pruef[f'14_{breite}_beschriftung_wie_gewollt'] = pruef[f'14_{breite}_beschriftet'] == (7 if breite == 768 else 1)
            # Jedes Ziel ist mit einem Klick erreichbar: bei 390 px von Heute zu Einstellungen und zurück.
            seite.set_viewport_size({'width': 390, 'height': 844})
            seite.goto(basis + '/today')
            seite.locator('.sidebar .nav-item', has_text='Einstellungen').click()
            seite.wait_for_url(re.compile(r'/settings'), timeout=10000)
            seite.locator('.sidebar .nav-item', has_text='Kalender').click()
            seite.wait_for_url(re.compile(r'/calendar'), timeout=10000)
            pruef['14_390_klick_erreicht'] = True
        except Exception:
            bild('fehler')
            raise
        finally:
            browser.close()

    uv.should_exit = True
    for dienst in (imap, caldav, autoconfig, dns):
        dienst.schliessen()
    falsch = [k for k, v in pruef.items() if v is False]
    ergebnis['nicht_bestanden'] = falsch
    ergebnis['ok'] = not falsch and not ergebnis['konsole']
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(f"Prüfungen: {len(pruef)} · nicht bestanden: {', '.join(falsch) or 'keine'} · "
          f"Konsole: {'leer' if not ergebnis['konsole'] else len(ergebnis['konsole'])}")
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
