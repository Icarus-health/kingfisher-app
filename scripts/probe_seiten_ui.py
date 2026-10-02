#!/usr/bin/env python3
"""Browserprobe für alle Seiten bei 390, 768 und 1280 px (Fremdprobe, docs/48-fremdprobe.md, Befunde 1 und 28) und
für die übrigen behobenen Befunde der Fremdprobe.

Echter Sidecar (`create_app()` unter uvicorn, frisches Datenverzeichnis), echte Oberfläche (`npm run build`), Chromium
über Playwright. Nur synthetische Daten. Dazu eine IMAP-Attrappe auf 127.0.0.1 (`sidecar/tests/imap_attrappe.py`), die
nach der Anmeldung schweigt, und ein Ortsdienst des Wetters, der nicht antwortet.

Geprüft wird:

* Breite: Heute, Gespräche (Liste und ein Gespräch), Aufgaben (alle Reiter), Nachrichten, Kalender, Gedächtnis (alle
  Bereiche), Einstellungen und das Briefing laufen bei 390, 768 und 1280 px weder seitlich über, noch ragt ein sichtbares
  Element über den Fensterrand hinaus (abgeschnitten), auch nicht in der Seitenleiste: Sie rollt seit der dritten
  Fremdprobe (Befund 14) nicht mehr seitlich. Die Seitenleiste deckt keine Bedienelemente zu.
* die behobenen Befunde, je ein Abschnitt unten (`befund_*`).
* Konsole: leer. Erwartete Fehlantworten (eine absichtlich schweigende Quelle) stehen getrennt.

Aufruf: `python scripts/probe_seiten_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build`).
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
BREITEN = (390, 768, 1280)

# Kein sichtbares Element darf über den Fensterrand hinausragen, auch nicht in der Seitenleiste (Fremdprobe 3, Befund 14).
# Versteckte zählen nicht (aria-hidden, nur für Vorleser).
UEBERSTAND_JS = """() => {
  const w = document.documentElement.clientWidth, aus = [];
  const name = el => el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0];
  const deko = el => (el.tagName === 'IMG' && el.getAttribute('alt') === '') || el.tagName === 'svg' || el.closest('svg');
  for (const el of document.querySelectorAll('#root *')) {
    if (el.closest('[aria-hidden="true"]') || deko(el)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'absolute' && cs.clip !== 'auto') continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    if (r.right > w + 1 || r.left < -1) { aus.push(name(el) + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + ' über den Fensterrand'); continue; }
    // Abgeschnitten: ragt über einen Vorfahren hinaus, der seitlich abschneidet oder rollt.
    for (let p = el.parentElement; p && p.id !== 'root'; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX; if (o === 'visible') continue;
      const q = p.getBoundingClientRect();
      if (r.right > q.right + 1 || r.left < q.left - 1) aus.push(name(el) + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + ' abgeschnitten in ' + name(p) + ' ' + Math.round(q.left) + '..' + Math.round(q.right));
      break;
    }
  }
  return { seite: document.documentElement.scrollWidth - w, aus: aus.slice(0, 10), breite: w };
}"""

# Liegt die Seitenleiste über einem Bedienelement der Seite? (Bei schmalem Fenster ist sie ein Streifen oben.)
VERDECKT_JS = """() => {
  const leiste = document.querySelector('.sidebar'); if (!leiste) return [];
  const l = leiste.getBoundingClientRect(), weg = [];
  for (const el of document.querySelectorAll('main button, main a, main input, main select, main h1')) {
    if (el.closest('[aria-hidden="true"]')) continue;
    // Was in einem zugeklappten Aufklapper steckt, ist nicht zu sehen (checkVisibility kennt das, getComputedStyle nicht).
    if (el.checkVisibility && !el.checkVisibility()) continue;
    const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (r.left < l.right - 1 && r.right > l.left + 1 && r.top < l.bottom - 1 && r.bottom > l.top + 1) weg.push((el.textContent || el.tagName).trim().slice(0, 40));
  }
  return weg.slice(0, 6);
}"""


class Antworter:
    """Ein lokales Modell mit einer festen Antwort, damit ein Gespräch Zeilen hat (kein Netz, kein Prozess)."""

    is_local = True
    name = 'probe'
    model = 'probe-modell'

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='Das Angebot an die Probe GmbH ist noch offen; fällig ist es heute.', model=self.model)


# Liegen zwei Bedienelemente übereinander (etwa ein Knopf auf einem Auswahlfeld)? Verschachtelte zählen nicht.
UEBERLAPPUNG_JS = """() => {
  const els = [...document.querySelectorAll('main button, main a, main input, main select, main textarea, main summary')].filter(el => {
    if (el.closest('[aria-hidden="true"]')) return false;
    if (el.checkVisibility && !el.checkVisibility()) return false;  // zugeklappter Aufklapper
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2;
  });
  const weg = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = els[i], b = els[j]; if (a.contains(b) || b.contains(a)) continue;
    const r = a.getBoundingClientRect(), s = b.getBoundingClientRect();
    const x = Math.min(r.right, s.right) - Math.max(r.left, s.left), y = Math.min(r.bottom, s.bottom) - Math.max(r.top, s.top);
    if (x > 4 && y > 4) weg.push(((a.textContent || a.tagName).trim().slice(0, 30)) + ' / ' + ((b.textContent || b.tagName).trim().slice(0, 30)));
  }
  return weg.slice(0, 6);
}"""


# Liegt über der Mitte jeder Textzeile der Überschrift im Briefing etwas anderes als die Überschrift selbst?
UEBERDECKT_JS = """() => {
  const kopf = document.querySelector('section.briefing-drawer.open .drawer-heading'); if (!kopf) return ['keine Überschrift'];
  const weg = [];
  // Das Landschaftsbild (Bäume) liegt unter der Schrift; lesbar wird sie nur auf einer fast deckenden Fläche.
  const m = getComputedStyle(kopf).backgroundColor.match(/rgba?\(([^)]+)\)/);
  const alpha = m ? (m[1].split(',').length === 4 ? Number(m[1].split(',')[3]) : 1) : 0;
  if (alpha < 0.8) weg.push('keine lesbare Fläche hinter der Überschrift (Deckkraft ' + alpha + ')');
  for (const el of kopf.querySelectorAll('p, h2, span')) {
    const r = el.getBoundingClientRect();
    for (const x of [r.left + 4, (r.left + r.right) / 2, r.right - 4]) {
      const oben = document.elementFromPoint(x, (r.top + r.bottom) / 2);
      if (!oben || !kopf.contains(oben)) weg.push(el.tagName + ' bei ' + Math.round(x) + ': ' + (oben ? oben.tagName + '.' + oben.className : 'nichts'));
    }
  }
  return weg;
}"""


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    parser.add_argument('--nur-breite', action='store_true', help='Nur die Breite messen (schneller).')
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from tests.imap_attrappe import PASSWORT, ImapAttrappe
    attrappe = ImapAttrappe()
    daten_ordner = tempfile.mkdtemp(prefix='probe-seiten-')
    # Der Sidecar vertraut dem Zertifikat der IMAP-Attrappe wie einem echten (ssl.create_default_context liest das).
    os.environ.update(ICARUS_DATA_DIR=daten_ordner, SSL_CERT_FILE=str(attrappe.zertifikat))
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'KINGFISHER_USER_NAME',
                 'OPENAI_API_KEY', 'LLM_API_KEY', 'ANTHROPIC_API_KEY'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import laufumgebung, mail_anmeldung, mail_intake_routes, providers_mail, server
    from icarus_memory.providers_mail import MailProvider
    from icarus_memory.server import create_app
    # Ein Anbieter „Probe-Post“ für example.org zeigt auf die Attrappe; die Zeitgrenzen sind auf wenige Sekunden gekürzt.
    providers_mail.PROVIDERS = (*providers_mail.PROVIDERS, MailProvider(
        id='probepost', label='Probe-Post', imap_host='127.0.0.1', smtp_host='127.0.0.1', imap_port=attrappe.port,
        domains=('example.org',), hint='Bei Probe-Post muss „IMAP“ eingeschaltet sein.'))
    mail_anmeldung.ZEITGRENZE = 3.0
    mail_intake_routes.ZEITGRENZE = 3.0
    server.POSTFACH_ZEITGRENZE = 2.0
    im_container_vorher = laufumgebung._im_container

    app = create_app()
    app.state.agent._provider = Antworter()
    port = freier_port()
    uv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=uv.run, daemon=True).start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.1)
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'breite': {}, 'konsole': [], 'erwartete_fehlantworten': [],
                      'bilder': []}
    pruef = ergebnis['pruefungen']
    erwartet: list[re.Pattern] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        seite = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()

        def konsole(m) -> None:
            if m.type not in ('error', 'warning'):
                return
            ort = (m.location or {}).get('url', '')
            if m.text.startswith('Failed to load resource') and any(e.search(ort) for e in erwartet):
                ergebnis['erwartete_fehlantworten'].append(f'{m.text} ({ort.removeprefix(basis)})')
            else:
                ergebnis['konsole'].append(f'{m.type}: {m.text} {ort.removeprefix(basis)}'.strip())
        seite.on('console', konsole)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

        def bild(name: str) -> None:
            pfad = args.ausgabe / f'seiten-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def messen(name: str, breite: int) -> None:
            time.sleep(0.4)
            messung = seite.evaluate(UEBERSTAND_JS)
            verdeckt = seite.evaluate(VERDECKT_JS) + seite.evaluate(UEBERLAPPUNG_JS)
            ergebnis['breite'][f'{name}-{breite}'] = {'seite': messung['seite'], 'aus': messung['aus'], 'verdeckt': verdeckt}
            bild(f'{name}-{breite}')

        def seiten_messen(breite: int) -> None:
            seite.set_viewport_size({'width': breite, 'height': 900})
            seite.goto(basis + '/today')
            seite.locator('.today-page h1').wait_for(timeout=20000)
            messen('heute', breite)
            seite.get_by_role('button', name=re.compile('Briefing öffnen')).click()
            seite.locator('section.briefing-drawer.open').wait_for(timeout=5000)
            time.sleep(0.6)  # bis das Briefing ganz hereingeglitten ist
            messen('briefing', breite)
            seite.goto(basis + '/conversations')
            seite.locator('.history-heading h1').wait_for(timeout=10000)
            messen('gespraeche', breite)
            seite.goto(basis + f'/conversations/{gespraech}')
            seite.locator('.thread-header h1').wait_for(timeout=10000)
            seite.locator('article.message').first.wait_for(timeout=10000)
            messen('gespraech', breite)
            for ansicht in ('mine', 'waiting', 'done', 'decisions', 'goals'):
                seite.goto(basis + f'/vorhaben?view={ansicht}')
                seite.locator('.tasks-heading h1').wait_for(timeout=10000)
                time.sleep(0.6)
                messen(f'aufgaben-{ansicht}', breite)
            seite.goto(basis + '/nachrichten')
            seite.locator('.inbox-heading h1').wait_for(timeout=10000)
            seite.locator('.inbox-skeleton').first.wait_for(state='detached', timeout=15000)
            messen('nachrichten', breite)
            seite.goto(basis + '/calendar')
            seite.locator('main h1').first.wait_for(timeout=10000)
            messen('kalender', breite)
            seite.goto(basis + '/memory')
            seite.locator('.memory-filter').wait_for(timeout=10000)
            time.sleep(0.6)
            for knopf in ('Menschen', 'Projekte', 'Organisationen', 'Orte', 'Themen', 'Themenakten', 'Entscheidungen',
                          'Dokumente', 'Aussagen prüfen', 'Verarbeitung & Verlauf'):
                seite.locator('.memory-filter button', has_text=knopf).first.click()
                time.sleep(0.5)
                messen(f'gedaechtnis-{knopf.split()[0].lower()}', breite)
            for bereich in ('zugaenge', 'darf', 'ich', 'sicherung', 'technik'):
                seite.goto(basis + f'/settings#{bereich}')
                seite.reload()
                seite.wait_for_selector(f'#settings-{bereich}:not([hidden])')
                messen(f'einstellungen-{bereich}', breite)

        konto: dict = {}

        def befunde_pruefen() -> None:
            seite.set_viewport_size({'width': 1280, 'height': 900})

            # -- 28: leerer Zustand im Gedächtnis mit Verweis; Auswahl statt Zahlenfeld, Singular -------------------
            seite.goto(basis + '/memory')
            leer = seite.locator('.gedaechtnis-leer').first
            leer.wait_for(timeout=10000)
            pruef['28_leer_satz'] = leer.inner_text()
            pruef['28_leer_verweis'] = leer.get_by_role('link').get_attribute('href') == '/settings#zugaenge'
            leer.get_by_role('link').click()
            seite.wait_for_selector('#settings-zugaenge:not([hidden])', timeout=10000)
            pruef['28_verweis_kommt_an'] = True
            seite.goto(basis + '/settings#technik-suchindex')
            auswahl = seite.locator('#suchindex-jahre')
            auswahl.wait_for(timeout=15000)
            pruef['28_auswahl_statt_zahl'] = auswahl.evaluate('e => e.tagName') == 'SELECT'
            pruef['28_optionen'] = auswahl.locator('option').all_inner_texts()
            abschnitt = seite.locator('#technik-suchindex').inner_text()
            pruef['28_stand'] = seite.locator('#suchindex-stand').inner_text()
            pruef['28_kein_alle_1_quellen'] = not re.search(r'\b1 Quellen|N Jahre|0 = alle', abschnitt)
            auswahl.select_option('2')
            seite.get_by_text('Gespeichert.').first.wait_for(timeout=15000)
            pruef['28_wahl_gilt_sofort'] = seite.request.get(basis + '/api/v1/suchindex').json()['wortteile_jahre'] == 2
            auswahl.select_option('0')
            seite.wait_for_function("document.querySelector('#suchindex-jahre').value === '0' && !document.querySelector('#suchindex-jahre').disabled", timeout=15000)
            pruef['28_wahl_zurueck'] = seite.request.get(basis + '/api/v1/suchindex').json()['wortteile_jahre'] == 0
            bild('28-suchindex')

            # -- 18: Texte passend zum System: im Browser unter Linux „Rechner“, auf dem Mac „Mac“ ---------------------
            pruef['18_system_linux'] = seite.request.get(basis + '/api/v1/system').json()['art']
            seite.goto(basis + '/settings#zugaenge')
            seite.wait_for_selector('#settings-zugaenge:not([hidden])')
            seite.wait_for_function("document.querySelector('.settings-data').innerText.includes('Auf diesem Rechner gespeichert')", timeout=10000)
            pruef['18_rechner_gespeichert'] = 'Auf diesem Rechner gespeichert' in seite.locator('.settings-data').inner_text()
            pruef['18_kein_mac_kalender'] = seite.locator('.mac-calendar').count() == 0
            texte = ''
            for bereich in ('zugaenge', 'darf', 'ich', 'sicherung'):
                seite.goto(basis + f'/settings#{bereich}')
                seite.wait_for_selector(f'#settings-{bereich}:not([hidden])')
                time.sleep(0.8)
                if bereich == 'sicherung':
                    seite.get_by_role('button', name='Sicherung öffnen').click()
                    seite.get_by_text('Sicherungsstatus wird geladen').wait_for(state='detached', timeout=10000)
                texte += seite.locator('main').inner_text() + '\n'
            # Erlaubt bleibt nur, was den Dienst nennt, den es nur auf dem Mac gibt („Apple Karten auf dem Mac“).
            mac_saetze = [z for z in texte.splitlines() if re.search(r'\b(diesem|deinem|am) Mac\b|Mac-App|Mac-Helfer|starten\.command', z)]
            pruef['18_mac_saetze_linux'] = mac_saetze
            pruef['18_kein_mac_satz_linux'] = not mac_saetze
            # Seit der Sicherung ohne Helfer (Befund 8) gibt es unter Linux den Download statt eines Satzes, dass es fehlt.
            pruef['18_sicherung_ehrlich'] = 'Sicherung herunterladen' in texte and 'gibt es nur in der Kingfisher-App' not in texte
            bild('18-sicherung-linux')
            # Dieselbe Seite, wenn der Startweg der Mac-App den Rechner als Mac gemeldet hat (Container auf dem Mac).
            laufumgebung._im_container = lambda: True
            antwort = seite.request.post(basis + '/api/v1/device/profile', data={'platform': 'macos', 'chip': 'Apple M3', 'memory_bytes': 16 * 1024 ** 3})
            assert antwort.ok, antwort.text()
            pruef['18_system_mac'] = seite.request.get(basis + '/api/v1/system').json()['art']
            seite.goto(basis + '/settings#zugaenge')
            seite.reload()  # die Angabe gilt je Seitenaufruf
            seite.wait_for_function("document.querySelector('.settings-data') && document.querySelector('.settings-data').innerText.includes('Auf diesem Mac gespeichert')", timeout=10000)
            pruef['18_mac_gespeichert'] = True
            seite.locator('.mac-calendar').wait_for(timeout=10000)
            pruef['18_mac_kalender_auf_dem_mac'] = True
            bild('18-zugaenge-mac')
            laufumgebung._im_container = im_container_vorher
            (Path(daten_ordner) / 'device-profile.json').unlink()

            # -- 12: „Mails regelmäßig abrufen“: ein Schalter, eine Auswahl, keine Fachwörter -------------------------
            alte = re.findall(r'"([^"]+)"', (WURZEL / 'app/kingfisher/src/mailAbruf.ts').read_text(encoding='utf-8')
                              .split('ALTE_WOERTER', 1)[1].split('];', 1)[0])
            seite.goto(basis + '/settings#technik-hintergrund')
            seite.reload()
            abschnitt = seite.get_by_role('region', name='Mails regelmäßig abrufen')
            schalter = abschnitt.get_by_role('switch', name=re.compile('Mails regelmäßig abrufen'))
            schalter.wait_for(timeout=15000)
            seite.locator('#technik-hintergrund details.mail-abruf-einlesen > summary').click()
            seite.get_by_role('button', name=re.compile('Ordner ansehen')).first.wait_for(timeout=15000)
            for summary in seite.locator('#technik-hintergrund details:not([open]) > summary').all():
                summary.click()
            text = seite.locator('#technik-hintergrund').inner_text()
            pruef['12_alte_woerter'] = [w for w in alte if w in text] + (['INBOX'] if 'INBOX' in text else [])
            pruef['12_keine_alten_woerter'] = not pruef['12_alte_woerter']
            pruef['12_kein_zahlenfeld'] = seite.locator('#technik-hintergrund input[type=number]').count() == 0
            pruef['12_aus_am_anfang'] = not schalter.is_checked()
            bild('12-mails-abrufen-aus')
            schalter.click()
            seite.get_by_text('Gespeichert. An. Kingfisher ruft die Mails aus Probe-Post alle 30 Minuten ab.').wait_for(timeout=10000)
            plan = seite.request.get(basis + '/api/v1/schedule').json()
            pruef['12_an_mit_vorgabe'] = plan['enabled'] is True and plan['interval_minutes'] == 30 and plan['mail_accounts'] == [konto['id']]
            wie_oft = abschnitt.get_by_label('Wie oft')
            pruef['12_auswahl'] = wie_oft.locator('option').all_inner_texts()
            wie_oft.select_option(label='täglich')
            seite.get_by_text('Gespeichert. An. Kingfisher ruft die Mails aus Probe-Post täglich ab.').wait_for(timeout=10000)
            pruef['12_taeglich'] = seite.request.get(basis + '/api/v1/schedule').json()['interval_minutes'] == 1440
            bild('12-mails-abrufen-an')
            schalter.click()
            seite.get_by_text(re.compile('Gespeichert. Aus.')).wait_for(timeout=10000)
            pruef['12_wieder_aus'] = seite.request.get(basis + '/api/v1/schedule').json()['enabled'] is False

            # -- 22 und 14: Postfach schweigt. Gruß sofort, Post lädt nach; Nachrichten nennen das Postfach -----------
            attrappe.modus = 'stumm'
            server.POSTFACH_ZEITGRENZE = 4.0
            beginn = time.monotonic()
            seite.goto(basis + '/today')
            seite.locator('.today-page h1').wait_for(timeout=10000)
            pruef['22_gruss_nach_s'] = round(time.monotonic() - beginn, 2)
            pruef['22_gruss_sofort'] = pruef['22_gruss_nach_s'] < 2.0
            pruef['22_post_laedt_sichtbar'] = seite.get_by_text('Deine Post wird gerade geholt').count() == 1
            bild('22-heute-post-laedt')
            hinweis = seite.locator('details.today-connection-note')
            hinweis.wait_for(timeout=15000)
            hinweis.locator('summary').click()
            hinweis.get_by_text('Probe-Post antwortet gerade nicht', exact=False).wait_for(timeout=15000)
            pruef['22_post_danach_s'] = round(time.monotonic() - beginn, 2)
            pruef['22_grund'] = hinweis.inner_text()
            pruef['22_grund_nennt_postfach'] = 'Probe-Post antwortet gerade nicht' in pruef['22_grund']
            pruef['22_laedt_nicht_mehr'] = seite.get_by_text('Deine Post wird gerade geholt').count() == 0
            bild('22-heute-grund')
            beginn = time.monotonic()
            seite.goto(basis + '/nachrichten')
            fehler = seite.locator('.inbox-error')
            fehler.wait_for(timeout=15000)
            pruef['14_nach_s'] = round(time.monotonic() - beginn, 2)
            pruef['14_sofort'] = pruef['14_nach_s'] < 1.5
            pruef['14_text'] = fehler.inner_text()
            pruef['14_nennt_postfach'] = pruef['14_text'].startswith('Probe-Post antwortet gerade nicht.') and 'lokale' not in pruef['14_text']
            pruef['14_verweis'] = fehler.get_by_role('link', name=re.compile('Postfach prüfen')).get_attribute('href') == '/settings#zugaenge'
            bild('14-nachrichten-postfach-schweigt')
            fehler.get_by_role('link', name=re.compile('Postfach prüfen')).click()
            seite.wait_for_selector('#settings-zugaenge:not([hidden])', timeout=10000)
            pruef['14_verweis_kommt_an'] = True
            attrappe.modus = 'annehmen'

            # -- 20 und 24: Briefing deutsch, kein Spieler ohne Audio, Überschrift nicht verdeckt ------------------------
            for breite in BREITEN:
                seite.set_viewport_size({'width': breite, 'height': 900})
                seite.goto(basis + '/today?briefing=1')
                seite.locator('section.briefing-drawer.open').wait_for(timeout=15000)
                time.sleep(1.0)
                text = seite.locator('section.briefing-drawer').inner_text()
                pruef[f'20_deutsch_{breite}'] = not re.search(r'MORNING|Morning|Dashboard', text) \
                    and seite.locator('.drawer-heading p').inner_text() == 'BRIEFING' \
                    and seite.get_by_role('button', name='Zurück zu Heute').count() == 1
                pruef[f'20_kein_spieler_ohne_audio_{breite}'] = seite.locator('.audio-briefing').count() == 0 \
                    and 'Lokales Audio ist derzeit nicht verfügbar' not in text
                pruef[f'24_ueberdeckt_{breite}'] = seite.evaluate(UEBERDECKT_JS)
                pruef[f'24_lesbar_{breite}'] = not pruef[f'24_ueberdeckt_{breite}']
                bild(f'20-briefing-{breite}')
            pruef['20_audio_status'] = seite.request.get(basis + '/api/v1/audio/status').json()
            seite.get_by_role('button', name='Zurück zu Heute').click()
            seite.locator('section.briefing-drawer.open').wait_for(state='detached', timeout=5000)
            pruef['20_zurueck_zu_heute'] = seite.locator('.today-page h1').is_visible()

            # -- 15: die eigene Frage als Quelle, in Alltagssprache ---------------------------------------------------
            seite.set_viewport_size({'width': 1280, 'height': 900})
            seite.goto(basis + f'/conversations/{gespraech}')
            frage = seite.locator('article.message.user').first
            frage.get_by_role('button', name='So ist deine Nachricht gespeichert').click()
            ansicht = frage.locator('section[aria-label="Profilquelle"]')
            ansicht.locator('.eigene-frage-satz').wait_for(timeout=10000)
            vorne = ansicht.inner_text()  # eingeklappt zählt nur die Überschrift „Für Techniker“
            pruef['15_vorne'] = vorne
            pruef['15_kein_fachwort'] = not [w for w in ('keine bestätigte Aussage', 'Einordnung', 'Sortierergebnis',
                                                       'Quelle ausschließen', 'Angabe berichtigen', 'Herkunft') if w in vorne]
            pruef['15_ein_satz'] = len([t for t in re.split(r'[.!?](?:\s|$)', ansicht.locator('.eigene-frage-satz').inner_text()) if t.strip()]) == 1
            pruef['15_knoepfe'] = ansicht.get_by_role('button').all_inner_texts()
            pruef['15_knoepfe_erkennbar'] = 'Wortlaut berichtigen' in pruef['15_knoepfe'] and 'Nicht mehr verwenden' in pruef['15_knoepfe']
            bild('15-gespraechsquelle')
            ansicht.locator('details.quelle-technik > summary').click()
            pruef['15_technik_im_aufklapper'] = 'keine bestätigte Aussage' in ansicht.locator('details.quelle-technik').inner_text()
            ansicht.locator('details.quelle-technik > summary').click()
            stand = seite.request.get(basis + f'/api/v1/conversations/{gespraech}').json()
            episode = next(l['episode_id'] for m in stand['messages'] for l in ((m.get('metadata') or {}).get('context') or {}).get('source_links', []))
            ansicht.get_by_role('button', name='Nicht mehr verwenden').click()
            pruef['15_rueckfrage'] = ansicht.get_by_role('group', name='Nicht mehr verwenden').inner_text()
            ansicht.get_by_role('button', name='Ja, nicht mehr verwenden').click()
            seite.get_by_text('Grundlage geändert oder ausgeschlossen').first.wait_for(timeout=10000)
            pruef['15_nicht_mehr_verwendet'] = seite.request.get(basis + f'/api/v1/episodes/{episode}').json().get('state') == 'ignored'
            # Zurück wie vorher (für die übrigen Prüfungen); in der Oberfläche heißt das „Wieder verwenden“.
            assert seite.request.post(basis + f'/api/v1/episodes/{episode}/reopen').ok
            pruef['15_wieder_verwendet'] = seite.request.get(basis + f'/api/v1/episodes/{episode}').json().get('state') != 'ignored'

            # -- 16: Rückmeldungen ohne Kommandozeilenbefehl, mit dem Satz, was aus einer Meldung wird ------------------
            antwort = seite.request.post(basis + '/api/v1/rueckmeldungen', data={
                'conversation_id': gespraech, 'message_id': stand['messages'][-1]['id'], 'art': 'falsch', 'richtig': 'Das Angebot ist verschickt.'})
            pruef['16_meldung_angelegt'] = antwort.ok
            seite.goto(basis + '/settings#technik-rueckmeldungen')
            seite.reload()
            rueck = seite.locator('section.rueckmeldungen')
            rueck.get_by_role('button', name='Als Prüffragen speichern').wait_for(timeout=15000)
            text = rueck.inner_text()
            pruef['16_text'] = text
            pruef['16_kein_befehl'] = not re.search(r'python|--fragen|messlatte lokal', text)
            pruef['16_was_daraus_wird'] = 'Was daraus wird: Jede Meldung wird eine Prüffrage.' in text
            bild('16-rueckmeldungen')

            # -- 31: Sicherung mit einem Passwortfeld und „anzeigen“ ---------------------------------------------------
            seite.goto(basis + '/settings#sicherung')
            seite.reload()
            seite.get_by_role('button', name='Sicherung öffnen').click()
            formular = seite.get_by_role('form', name='Sicherung erstellen')
            formular.wait_for(timeout=10000)
            feld = formular.get_by_label('Sicherungspasswort')
            pruef['31_ein_feld'] = formular.locator('input').count() == 1 and seite.get_by_text('Passwort wiederholen').count() == 0
            feld.fill('geheim')
            pruef['31_verdeckt'] = feld.get_attribute('type') == 'password'
            pruef['31_hinweis_kurz'] = formular.locator('#sicherung-passwort-hinweis').inner_text()
            formular.get_by_role('button', name='anzeigen').click()
            pruef['31_angezeigt'] = feld.get_attribute('type') == 'text' and feld.input_value() == 'geheim' \
                and formular.get_by_role('button', name='verbergen').get_attribute('aria-pressed') == 'true'
            feld.fill('ein-langes-probe-passwort-16')
            pruef['31_hinweis_lang'] = formular.locator('#sicherung-passwort-hinweis').inner_text()
            bild('31-sicherung')
            formular.get_by_role('button', name='verbergen').click()
            pruef['31_wieder_verdeckt'] = feld.get_attribute('type') == 'password'

            # -- 32: Ortsdienst des Wetters schweigt: ein Satz in der Oberfläche, keine Fehlantwort in der Konsole -----
            from icarus_memory.wetter import WetterFehler
            from icarus_memory.wetter_routes import dienst as wetter_dienst

            def ortsdienst_stumm(*_a, **_k):
                raise WetterFehler('keine Antwort')
            wetter_dienst(app)._holen = ortsdienst_stumm
            vorher = len(ergebnis['konsole'])
            seite.goto(basis + '/settings#darf')
            seite.reload()
            seite.get_by_role('switch', name=re.compile('Morgens das Wetter holen')).click()
            seite.locator('#wetter-suche').fill('Mainz')
            seite.get_by_role('button', name='Suchen').click()
            satz = seite.get_by_text('Der Ortsdienst antwortet gerade nicht. Bitte später erneut versuchen.')
            satz.wait_for(timeout=10000)
            time.sleep(0.5)
            pruef['32_satz_sichtbar'] = True
            pruef['32_konsole_leer'] = len(ergebnis['konsole']) == vorher
            bild('32-ortssuche-stumm')

        try:
            seite.goto(basis + '/willkommen')  # setzt die Sitzung für /api
            antwort = seite.request.put(basis + '/api/v1/einrichtung', data={'name': 'Lena', 'abgeschlossen': True})
            assert antwort.ok, antwort.text()
            # Ein paar synthetische Einträge, damit die Seiten Zeilen haben und nicht nur leere Zustände.
            for titel in ('Angebot an die Probe GmbH schicken', 'Rückruf bei Lena Beispiel wegen des Termins am Donnerstag'):
                antwort = seite.request.post(basis + '/api/v1/tasks', data={'title': titel, 'due': time.strftime('%Y-%m-%d')})
                assert antwort.ok, antwort.text()
            antwort = seite.request.post(basis + '/api/v1/integrations/mail', data={
                'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': attrappe.port,
                'user': 'lena.probe@example.org', 'sender': 'lena.probe@example.org', 'password': PASSWORT})
            assert antwort.ok, antwort.text()
            konto['id'] = antwort.json()['mail_accounts'][-1]['id']
            gespraech = seite.request.post(basis + '/api/v1/conversations', data={}).json()['conversation']['id']
            antwort = seite.request.post(f'{basis}/api/v1/conversations/{gespraech}/messages',
                                         data={'message': 'Was ist mit dem Angebot an die Probe GmbH?', 'answer_mode': 'auto'})
            assert antwort.status == 201, antwort.text()

            for breite in BREITEN:
                seiten_messen(breite)
            for name, messung in ergebnis['breite'].items():
                pruef[f'breite_{name}'] = messung['seite'] <= 0 and not messung['aus'] and not messung['verdeckt']
            if not args.nur_breite:
                befunde_pruefen()
        except Exception:
            bild('fehler')
            print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
            raise
        finally:
            browser.close()
            uv.should_exit = True
            attrappe.schliessen()

    ergebnis['ok'] = all(v is True for v in pruef.values() if isinstance(v, bool)) and not ergebnis['konsole']
    (args.ausgabe / 'seiten-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    schlecht = {k: v for k, v in ergebnis['breite'].items() if v['seite'] > 0 or v['aus'] or v['verdeckt']}
    print(json.dumps({'schlecht': schlecht, 'konsole': ergebnis['konsole'],
                      'erwartete_fehlantworten': ergebnis['erwartete_fehlantworten'],
                      'pruefungen': {k: v for k, v in pruef.items() if not k.startswith('breite_')}},
                     ensure_ascii=False, indent=2))
    print('Breite geprüft:', len(ergebnis['breite']), '· nicht in Ordnung:', len(schlecht), '· ok:', ergebnis['ok'])
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
