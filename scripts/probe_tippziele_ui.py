#!/usr/bin/env python3
"""Browserprobe: Tippziele am Handy (Persona-Prüfung, Paket H, H3, docs/16-gestaltung.md „Handy“).

Meldet jedes sichtbare Bedienelement der Hauptseiten, dessen wirksame Trefffläche bei 390 px mit grobem Zeiger
(`pointer: coarse`: Playwright `has_touch`, `is_mobile`) kleiner als 44 × 44 CSS-px ist. WCAG 2.5.8 verlangt 24 px,
Apple 44; Kingfisher nimmt am Handy 44. Gemessen wird die Fläche, die ein Tipp trifft (`scripts/tippziele.js`), nicht der
Kasten: Eine vergrößerte Fläche über Innenabstand oder Pseudo-Element zählt mit, ein Nachbar darüber zieht ab.

Echter Sidecar mit der Messlatte-Welt („Lea Hartmann“, nur synthetische Daten, Regel-Einordnung statt Modell, kein
Netz), dazu zwei Postfächer und ein Kalender-Abo als Einträge unter Zugänge und zwei Aufgaben, die Kingfisher selbst
angelegt hat (mit „Rückgängig“). Gebaute Oberfläche (`npx vite build`), Chromium über Playwright.

Aufruf: `python scripts/probe_tippziele_ui.py --ausgabe DIR [--farbschema dark] [--basis http://127.0.0.1:PORT]`.
Mit `--basis` misst die Probe eine schon laufende Instanz. Rückgabe 0, wenn kein Ziel zu klein ist.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
TIPPZIELE_JS = (Path(__file__).resolve().parent / 'tippziele.js').read_text()
MINDEST = 44


class Still:
    """Ein lokales Modell, das nichts weiß (kein Netz, kein Prozess); die Seiten brauchen keines."""

    is_local = True
    name = 'probe'
    model = 'probe-modell'
    supports_json = True

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='Das habe ich so nicht im Gedächtnis.', model=self.model)

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.providers import Reply
        return Reply(text=json.dumps({'status': 'no_relevant_sources', 'ids': []}), model=self.model)


def welt_starten(bereit: threading.Event, ende: threading.Event, ergebnis: dict) -> None:
    """Die Messlatte-Welt unter uvicorn, solange `ende` nicht gesetzt ist."""
    import uvicorn
    from messlatte import aufnahme, handlungen
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from icarus_memory import EpisodeKind, Provenance, SourceType, aufgaben_von_selbst, mail_stand, server
    from icarus_memory.akten_routes import nachfuehren
    from icarus_memory.config import CalendarSourceSettings, MailAccountSettings
    from icarus_memory.kontakte import fuer_mail
    from icarus_memory.task_review import current_task_context

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ich = welt.nutzer.adressen[0]
    still = Still()
    server.provider_from_env = lambda: still
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=still, eigene=tuple(welt.nutzer.adressen)) as instanz:
        app = instanz.app
        auf = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        handlungen.ausfuehren(instanz, [welt], auf.episoden)
        mail_stand._verbunden = lambda app, konto: True
        s = app.state.settings
        s.mail.user = ich
        s.einrichtung = {'name': 'Lea', 'schritte': {}, 'abgeschlossen': True}
        s.mail_accounts.append(MailAccountSettings(id='mail-uni', label='uni-beispiel.example', imap_host='imap.uni-beispiel.example', user=ich, sender=ich))
        s.mail_accounts.append(MailAccountSettings(id='mail-gmail', label='Gmail / Google Workspace', imap_host='imap.gmail.com',
                                                   user='lea.probe@gmail.example', sender='lea.probe@gmail.example'))
        s.calendar_sources.append(CalendarSourceSettings(id='calendar-uni', label='Uni Stundenplan', kind='ical',
                                                         url='https://ical.uni-beispiel.example/stundenplan.ics'))
        nachfuehren(app, warten=True)
        # Zwei direkte Bitten an Lea: Kingfisher legt sie als Aufgaben an (mit „Rückgängig“ in der Zeile).
        for n, (titel, bitte, von) in enumerate((
                ('Folien Seminar', 'Kannst du mir bitte bis Donnerstag die Folien für das Seminar schicken?', 'Miriam Kessler <miriam.kessler@kessler-diaet.example>'),
                ('Rechnung September', 'Könntest du mir bitte die Rechnung für September noch einmal zusenden?', 'Nadine Roth <n.roth@tagungsservice-rheinblick.example>')), 1):
            emp = [{'adresse': ich, 'name': 'Lea Hartmann', 'rolle': 'an'}]
            e, _ = app.state.episodes.record(EpisodeKind.MESSAGE, titel, f'Hallo Lea,\n\n{bitte}\n\nViele Grüße', Provenance(SourceType.EMAIL, source_ref=f'mail-uni:<t{n}@probe.example>'),
                                             participants=[von, f'Lea Hartmann <{ich}>'], contacts=fuer_mail(von, emp, eigene=[ich]),
                                             tags=[f'mail:message:t{n}'], occurred_at=welt.stichtag - timedelta(hours=2 + n))
            with app.state.proposals.transaction():
                app.state.proposals._record_task_candidates(e.id, e.digest, [{'title': f'{titel} erledigen', 'quote': bitte}],  # noqa: SLF001
                                                            proposed_by='probe/local/task-review-v1', task_context=current_task_context(app.state.episodes, e.id))
        aufgaben_von_selbst.schritt_fuer(app)
        nachfuehren(app, warten=True)
        uv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=0, log_level='warning'))
        threading.Thread(target=uv.run, daemon=True).start()
        for _ in range(200):
            if uv.started:
                break
            time.sleep(0.1)
        if getattr(app.state, 'scheduler', None) is not None:
            app.state.scheduler.stop()
        port = uv.servers[0].sockets[0].getsockname()[1]
        ergebnis.update(basis=f'http://127.0.0.1:{port}', stichtag=welt.stichtag)
        bereit.set()
        ende.wait()
        uv.should_exit = True
        time.sleep(0.5)


# Seiten und Zustände, je (Name, Pfad, Schritte). Schritte laufen nach dem Laden, etwa ein Segment oder „Mehr“ antippen.
SEITEN = [
    ('heute', '/today', []),
    ('mehr', '/today', [('tippen', '.handy-leiste button[aria-controls=handy-mehr]')]),
    ('gespraeche', '/conversations', []),
    ('aufgaben', '/vorhaben', []),
    ('aufgaben-warten', '/vorhaben?view=waiting', []),
    ('aufgaben-erledigt', '/vorhaben?view=done', []),
    ('aufgaben-entscheidungen', '/vorhaben?view=decisions', []),
    ('aufgaben-ziele', '/vorhaben?view=goals', []),
    ('projekte', '/vorhaben?view=projects', []),
    ('aufgaben-pruefen', '/vorhaben?pruefen=1', []),
    ('aufgabe', '/vorhaben', [('tippen', '.task-row .g-zeile-ziel, .task-row button.task-title')]),
    ('nachrichten', '/nachrichten', []),
    ('mail', '/nachrichten', [('tippen', '.inbox-row.inbox-open')]),
    ('kalender-liste', '/calendar', []),
    ('kalender-woche', '/calendar', [('segment', 'Woche')]),
    ('kalender-monat', '/calendar', [('segment', 'Monat')]),
    ('kalender-tag', '/calendar', [('segment', 'Tag')]),
    ('kalender-jahr', '/calendar', [('segment', 'Jahr')]),
    ('termin', '/calendar', [('segment', 'Liste'), ('tippen', '.calendar-entry')]),
    ('gedaechtnis', '/memory', []),
    ('gedaechtnis-bereiche', '/memory?tab=areas', []),
    ('menschen', '/memory?tab=people', []),
    ('dokumente', '/memory?tab=documents', []),
    ('organisationen', '/memory?tab=organizations', []),
    ('akte', '/memory?tab=people', [('tippen', '.memory-directory .g-zeile, .memory-directory button')]),
    ('einstellungen', '/settings', []),
    ('einstellungen-darf', '/settings#darf', []),
    ('einstellungen-ich', '/settings#ich', []),
    ('einstellungen-sicherung', '/settings#sicherung', []),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    parser.add_argument('--farbschema', choices=('light', 'dark'), default='light')
    parser.add_argument('--basis', help='eine schon laufende Instanz messen statt eine zu starten')
    parser.add_argument('--nur', help='nur diese Seiten (Namen, durch Komma getrennt)')
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone
    from playwright.sync_api import sync_playwright

    ende = threading.Event()
    welt: dict = {}
    if args.basis:
        welt.update(basis=args.basis.rstrip('/'), stichtag=datetime(2026, 9, 29, 7, 35, tzinfo=timezone(timedelta(hours=2))))
    else:
        bereit = threading.Event()
        threading.Thread(target=welt_starten, args=(bereit, ende, welt), daemon=True).start()
        if not bereit.wait(600):
            print('Die Welt ist nicht bereit geworden.')
            return 2
    basis = welt['basis']
    nur = set(args.nur.split(',')) if args.nur else None
    ergebnis: dict = {'mindest': MINDEST, 'seiten': {}, 'konsole': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        kontext = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, locale='de-DE',
                                      timezone_id='Europe/Berlin', color_scheme=args.farbschema)
        kontext.clock.install(time=welt['stichtag'])
        seite = kontext.new_page()
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
        try:
            assert seite.evaluate("() => matchMedia('(pointer: coarse)').matches"), 'kein grober Zeiger'
            for name, pfad, schritte in SEITEN:
                if nur and name not in nur:
                    continue
                seite.goto(basis + pfad)
                seite.wait_for_load_state('networkidle')
                seite.wait_for_timeout(1200)
                fehlt = []
                for art, ziel in schritte:
                    if art == 'segment':
                        knopf = seite.locator('.calendar-ansicht button', has_text=ziel).first
                    else:
                        knopf = seite.locator(ziel).first
                    if not knopf.count():
                        fehlt.append(ziel)
                        continue
                    knopf.scroll_into_view_if_needed()
                    knopf.tap()
                    seite.wait_for_timeout(1200)
                messung = seite.evaluate(TIPPZIELE_JS, {'min': MINDEST})
                messung['fehlt'] = fehlt
                ergebnis['seiten'][name] = messung
                if messung['klein']:
                    seite.screenshot(path=str(args.ausgabe / f'tippziele-{name}-{args.farbschema}.jpg'), type='jpeg', quality=60, full_page=True)
        finally:
            browser.close()
            ende.set()
    klein = {n: m['klein'] for n, m in ergebnis['seiten'].items() if m['klein']}
    ergebnis['ok'] = not klein and not ergebnis['konsole']
    (args.ausgabe / f'tippziele-{args.farbschema}.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1, default=str))
    for n, liste in klein.items():
        print(f'{n}:')
        for z in liste:
            print(f"  {z['w']} × {z['h']}  {z['art']}  „{z['name']}“{'  (im Satz)' if z.get('inline') else ''}")
    gezaehlt = sum(m['gezaehlt'] for m in ergebnis['seiten'].values())
    fehlend = {n: m['fehlt'] for n, m in ergebnis['seiten'].items() if m['fehlt']}
    if fehlend:
        print('Nicht gefunden (Zustand nicht erreicht):', fehlend)
    print(f"Seiten: {len(ergebnis['seiten'])} · Ziele gemessen: {gezaehlt} · unter {MINDEST} px: {sum(map(len, klein.values()))} · Konsole: {len(ergebnis['konsole'])} · ok: {ergebnis['ok']}")
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
