#!/usr/bin/env python3
"""Browserprobe Konten und Bereiche (Paket K, docs/66-automatik.md): echte Oberfläche, echter Sidecar, Attrappen.

Synthetische Konten: zwei Gmail-Postfächer, die früher beide „Gmail / Google Workspace“ hießen, ein Firmenpostfach,
zwei Kalender („Arbeit“ und „Gemeinsam“, ohne Hinweis im Namen). Kein Netz, kein echtes Postfach, kein Modell.

Geprüft wird in Chromium (Playwright):

* Zugänge: die zwei Gmail-Postfächer heißen nach ihrer Adresse; je Konto der Stand in einem Satz („Zuletzt gelesen vor
  4 Min.“, ein Fehler mit „Neu anmelden“); Vorschläge stehen als Vorschlag mit Grund da; „Alle Vorschläge übernehmen“
  antwortet mit Hinweis und Rückgängig; ein Kalender ohne Hinweis fragt „Welcher Bereich?“; ein eigener Bereich lässt sich
  anlegen; ein Klick auf den Namen benennt um, und der Name bleibt nach dem Neuladen.
* Kalender: Filter „Alle · Arbeit · Privat · Verein“; „Arbeit“ zeigt nur den Arbeitstermin und bleibt nach dem Neuladen
  gewählt; ein ausgeblendeter Kalender bleibt nach dem Neuladen ausgeblendet.
* Aufgaben: derselbe Filter; „Privat“ zeigt nur die private Aufgabe.
* Breite 390 px ohne seitliches Rollen; Bilder 1280 und 390 hell, eines dunkel.

Aufruf: `python scripts/probe_konten_ui.py --ausgabe DIR [--chromium PFAD]`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_fremdprobe3_ui import UMGEBUNG, sidecar  # noqa: E402
from probe_satzantwort_ui import CHROMIUM, freier_port  # noqa: E402

ANNA, FAMILIE, FIRMA = 'lena.probe@gmail.com', 'familie.probe@gmail.com', 'lena@winter-catering.example'


def einstellungen(daten: Path, jetzt: datetime) -> None:
    from icarus_memory import config
    vor = lambda minuten: (jetzt - timedelta(minutes=minuten)).isoformat()  # noqa: E731
    (daten / config.DATEINAME).write_text(json.dumps({
        'onboarded': True,
        'einrichtung': {'name': 'Lena', 'schritte': {}, 'abgeschlossen': True},
        'mail_accounts': [
            {'id': 'mail-anna', 'label': 'Gmail / Google Workspace', 'imap_host': 'imap.gmail.com', 'user': ANNA, 'sender': ANNA},
            {'id': 'mail-familie', 'label': 'Gmail / Google Workspace', 'imap_host': 'imap.gmail.com', 'user': FAMILIE,
             'sender': FAMILIE},
            {'id': 'mail-firma', 'label': 'winter-catering.example', 'imap_host': 'imap.winter-catering.example',
             'user': FIRMA, 'sender': FIRMA},
        ],
        'calendar_sources': [
            {'id': 'calendar-arbeit', 'label': 'Arbeit', 'kind': 'ical', 'url': 'https://kalender.winter-catering.example/'},
            {'id': 'calendar-gemeinsam', 'label': 'Gemeinsam', 'kind': 'ical', 'url': 'https://kalender.example/'},
        ],
        'mail_sync_status': {
            'mail-anna': {'last_success': vor(4), 'last_report': {'recorded': 2}},
            'mail-familie': {'last_success': vor(300), 'last_failure': 'anmeldung'},
            'mail-firma': {'last_success': vor(12), 'last_report': {'recorded': 1}},
        },
    }), encoding='utf-8')


def main() -> int:  # noqa: PLR0915 - eine Probe, Schritt für Schritt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    daten = Path(tempfile.mkdtemp(prefix='konten-probe-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)
    jetzt = datetime.now(timezone.utc)
    einstellungen(daten, jetzt)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import EpisodeKind, Provenance, SourceType, mail_stand, server as server_modul
    from icarus_memory.connectors.calendar import Event
    from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar

    # Attrappen: Die Postfächer gelten als offen (kein Passwort im Schlüsselbund nötig), die Kalender liefern je einen Termin.
    mail_stand._verbunden = lambda app, konto: True
    morgen = (datetime.now().astimezone() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

    class Leser:
        def __init__(self, titel, beginn):
            self.titel, self.beginn = titel, beginn

        def events(self, days=7, at=None):
            return [Event(uid=self.titel, summary=self.titel, start=self.beginn, end=self.beginn + timedelta(hours=1))]

    def kalender():
        return CalendarCollection([NamedCalendar('calendar-arbeit', 'Arbeit', Leser('Messe-Abstimmung', morgen)),
                                   NamedCalendar('calendar-gemeinsam', 'Gemeinsam', Leser('Elternabend', morgen + timedelta(hours=8)))])
    bauen = server_modul._build_agent

    def bauen_mit_attrappe(app):
        agent = bauen(app)
        app.state.calendar = kalender()
        return agent
    server_modul._build_agent = bauen_mit_attrappe

    app = sidecar(daten)
    # Mit eigenem Agenten liest `create_app` die Einstellungen nicht; die Probe lädt sie wie ein Start ohne Agent und
    # macht die Namen eindeutig wie `konten_routes.register` beim Start (dort im Test geprüft).
    from icarus_memory import config, konten_routes
    app.state.settings = config.load(daten)
    if konten_routes.namen_eindeutig_machen(app.state.settings):
        config.save(daten, app.state.settings)
    app.state.calendar = kalender()
    episodes, tasks = app.state.episodes, app.state.tasks

    def mail(konto, titel, nummer):
        episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, f'{titel}. Viele Grüße',
                                     Provenance(SourceType.EMAIL, source_ref=f'{konto}:<k{nummer}@probe.example>'),
                                     participants=['Anna Berg <anna.berg@example.org>'], occurred_at=jetzt - timedelta(hours=nummer),
                                     contacts=[{'adresse': 'anna.berg@example.org', 'name': 'Anna Berg', 'rolle': 'von', 'ich': False}])
        return episode
    angebot = mail('mail-firma', 'Angebot Herbstmesse', 1)
    oma = mail('mail-anna', 'Geburtstag von Oma', 2)
    # Paket S: Bei Gmail entscheidet, was im Postfach steht; ein privates Postfach braucht dafür eine Mail.
    mail('mail-familie', 'Sonntagsessen', 3)
    tasks.add('Angebot für die Herbstmesse prüfen', Provenance(SourceType.USER_STATED, source_ref=f'episode:{angebot.id}'))
    tasks.add('Geschenk für Oma besorgen', Provenance(SourceType.USER_STATED, source_ref=f'episode:{oma.id}'))

    port = freier_port()
    uv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=uv.run, daemon=True).start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.1)
    if getattr(app.state, 'scheduler', None) is not None:
        app.state.scheduler.stop()
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])

        def neue_seite(farbe='light'):
            kontext = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='de-DE', timezone_id='Europe/Berlin',
                                          color_scheme=farbe)
            seite = kontext.new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type == 'error' else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            return seite
        seite = neue_seite()

        def bild(name, s=None, ganz=False):
            pfad = args.ausgabe / f'konten-{name}.png'
            (s or seite).screenshot(path=str(pfad), full_page=ganz)
            ergebnis['bilder'].append(str(pfad))

        def schmal(name, s=None):
            s = s or seite
            s.set_viewport_size({'width': 390, 'height': 844})
            s.wait_for_timeout(600)
            masse = s.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            pruef[f'{name}_390'] = masse
            assert masse[0] <= masse[1], (name, masse)
            bild(f'{name}-390', s, ganz=True)
            s.set_viewport_size({'width': 1280, 'height': 900})
            s.wait_for_timeout(300)

        def hinweis(satz=''):
            ort = seite.locator('.g-hinweis', has_text=satz) if satz else seite.locator('.g-hinweis')
            ort.wait_for(timeout=10000)
            return ort

        try:
            schritte(seite, neue_seite, bild, schmal, hinweis, basis, pruef)
        except Exception:
            bild('fehler', ganz=True)
            (args.ausgabe / 'konten-fehler.txt').write_text(seite.inner_text('body'), encoding='utf-8')
            print(json.dumps(ergebnis['konsole'], ensure_ascii=False))
            raise
        ergebnis['ok'] = not ergebnis['konsole']
        browser.close()
    (args.ausgabe / 'konten-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'pruefungen': pruef}, ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


def schritte(seite, neue_seite, bild, schmal, hinweis, basis, pruef) -> None:  # noqa: PLR0915
        # -- Zugänge: Namen, Stand, Vorschläge ----------------------------------------------------------------------------
        seite.goto(basis + '/settings#zugaenge')
        seite.locator('.konto-frage').first.wait_for(timeout=30000)
        namen = seite.locator('.zugang-liste .konto .g-zeile-titel').all_inner_texts()
        pruef['namen'] = namen
        assert namen[:3] == [ANNA, FAMILIE, 'winter-catering.example'], namen
        staende = seite.locator('.zugang-liste .konto-stand').all_inner_texts()
        pruef['staende'] = staende
        assert staende[0] == 'Zuletzt gelesen vor 4 Min.', staende
        assert staende[1].startswith('Lässt Kingfisher nicht mehr hinein'), staende
        assert seite.get_by_text('Passwort deines Postfachs').count() + seite.locator('.neu-anmelden-stand').count() >= 1
        fragen = seite.locator('.konto-frage .konto-frage-satz').all_inner_texts()
        pruef['vorschlaege'] = fragen
        assert 'Vorschlag: Privat. gmail.com ist ein privater Anbieter, und nichts darin klingt nach Arbeit.' in fragen, fragen
        assert any(f == 'Vorschlag: Arbeit. winter-catering.example ist eine Firmenadresse.' for f in fragen), fragen
        assert seite.locator('.konto-wahl', has_text='Welcher Bereich?').count() == 1, 'Gemeinsam: kein Vorschlag, eine Frage'
        bild('1-zugaenge', ganz=True)
        schmal('1-zugaenge')

        seite.get_by_role('button', name='Alle Vorschläge übernehmen').click()
        text = hinweis('Vorschläge übernommen').inner_text()
        pruef['alle_hinweis'] = text
        assert '4 Vorschläge übernommen.' in text and 'Rückgängig' in text, text
        seite.wait_for_timeout(300)
        pillen = seite.locator('.konto-bereich').all_inner_texts()
        pruef['pillen'] = pillen
        assert pillen == ['Privat', 'Privat', 'Arbeit', 'Arbeit'], pillen
        seite.locator('.g-hinweis').get_by_role('button', name='Rückgängig').click()
        seite.wait_for_timeout(800)
        assert seite.locator('.konto-bereich').count() == 0, 'Rückgängig nimmt alle zurück'
        seite.get_by_role('button', name='Alle Vorschläge übernehmen').click()
        hinweis()
        seite.wait_for_timeout(500)

        # Ein Kalender ohne Hinweis: eigener Bereich „Verein“, danach „Privat“ für den gemeinsamen Kalender.
        wahl = seite.locator('.konto-wahl', has_text='Welcher Bereich?')
        wahl.get_by_role('button', name='Eigener Bereich …').click()
        seite.get_by_label('Name des neuen Bereichs').fill('Verein')
        bild('2-eigener-bereich')
        seite.get_by_role('button', name='Anlegen').click()
        text = hinweis('Verein').inner_text()
        assert '„Gemeinsam“ gehört jetzt zum Bereich Verein.' in text, repr(text)
        seite.wait_for_timeout(300)
        assert seite.locator('.konto-bereich').all_inner_texts() == ['Privat', 'Privat', 'Arbeit', 'Arbeit', 'Verein']

        # Umbenennen mit einem Klick auf den Namen; bleibt nach dem Neuladen.
        seite.get_by_role('button', name=f'{FAMILIE} umbenennen').click()
        feld = seite.get_by_label(f'Neuer Name für {FAMILIE}')
        feld.fill('Familie')
        feld.press('Enter')
        text = hinweis('Umbenannt').inner_text()
        pruef['umbenannt'] = text
        assert 'Umbenannt in „Familie“.' in text and 'Rückgängig' in text, text
        seite.reload()
        seite.locator('.konto-bereich').first.wait_for(timeout=30000)
        namen = seite.locator('.zugang-liste .konto .g-zeile-titel').all_inner_texts()
        assert 'Familie' in namen, namen
        bild('3-zugaenge-fertig', ganz=True)

        # -- Kalender: Filter, gemerkt; ausgeblendet bleibt ausgeblendet ----------------------------------------------------
        seite.goto(basis + '/calendar')
        filter_ = seite.get_by_role('tablist', name='Bereich')
        filter_.wait_for(timeout=30000)
        pruef['kalender_filter'] = filter_.inner_text().split('\n')
        assert [t.strip() for t in pruef['kalender_filter'] if t.strip()] == ['Alle', 'Arbeit', 'Privat', 'Verein'], pruef['kalender_filter']
        seite.get_by_role('tab', name='Liste').click()
        seite.get_by_text('Messe-Abstimmung').first.wait_for(timeout=20000)
        filter_.get_by_role('tab', name='Arbeit').click()
        seite.wait_for_timeout(400)
        assert seite.get_by_text('Elternabend').count() == 0 and seite.get_by_text('Messe-Abstimmung').count() >= 1
        bild('4-kalender-arbeit')
        seite.reload()
        seite.get_by_role('tablist', name='Bereich').wait_for(timeout=30000)
        seite.wait_for_timeout(800)
        gewaehlt = seite.get_by_role('tablist', name='Bereich').locator('[aria-selected="true"]').inner_text()
        assert gewaehlt.strip() == 'Arbeit', gewaehlt
        pruef['kalender_gemerkt'] = gewaehlt
        schmal('4-kalender')
        seite.get_by_role('tablist', name='Bereich').get_by_role('tab', name='Alle').click()
        seite.locator('.calendar-source-choice', has_text='Gemeinsam').locator('input').uncheck()
        seite.wait_for_timeout(600)
        seite.reload()
        seite.locator('.calendar-source-choice').first.wait_for(timeout=30000)
        seite.wait_for_timeout(800)
        assert not seite.locator('.calendar-source-choice', has_text='Gemeinsam').locator('input').is_checked()
        assert seite.get_by_text('Elternabend').count() == 0
        pruef['ausgeblendet_bleibt'] = True
        seite.locator('.calendar-source-choice', has_text='Gemeinsam').locator('input').check()
        seite.wait_for_timeout(400)

        # -- Aufgaben: derselbe Filter ------------------------------------------------------------------------------------
        seite.goto(basis + '/vorhaben?view=mine')
        seite.get_by_text('Geschenk für Oma besorgen').first.wait_for(timeout=30000)
        filter_ = seite.get_by_role('tablist', name='Bereich')
        filter_.get_by_role('tab', name='Privat').click()
        seite.wait_for_timeout(400)
        assert seite.get_by_text('Angebot für die Herbstmesse prüfen').count() == 0
        assert seite.get_by_text('Geschenk für Oma besorgen').count() >= 1
        bild('5-aufgaben-privat')
        schmal('5-aufgaben')

        # -- Dunkel -----------------------------------------------------------------------------------------------------------
        dunkel = neue_seite('dark')
        dunkel.goto(basis + '/settings#zugaenge')
        dunkel.locator('.konto-bereich').first.wait_for(timeout=30000)
        dunkel.wait_for_timeout(500)
        bild('6-zugaenge-dunkel', dunkel, ganz=True)


if __name__ == '__main__':
    raise SystemExit(main())
