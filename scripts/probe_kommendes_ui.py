#!/usr/bin/env python3
"""Browserprobe für „Was brauche ich morgen?“ im Gespräch (echte Oberfläche, echter Server, kein Modell).

Der Sidecar läuft mit einem Anbieter, der bei jedem Aufruf fehlschlägt: Die Antwort darf kein Modell brauchen.
Ein synthetischer Kalender (ein Termin morgen mit Ort und Teilnehmern, einer in fünf Tagen) und eine Mail mit
einer Bitte bis morgen stehen bereit. Geprüft wird in Chromium:

* die Frage geht ohne Modell den neuen Weg (`answer_contract.status` = `kommendes`, `model_called` = false),
* die Antwort nennt den Termin von morgen mit Ort und Teilnehmern und die Frist mit Quelle, nicht den Termin
  in fünf Tagen, und behauptet nie „frei“,
* „Quelle 1 öffnen“ zeigt die Quellenansicht mit dem Betreff der Mail,
* bei 1280 und 390 px kein seitliches Scrollen, und die Konsole bleibt leer.

Aufruf: `python scripts/probe_kommendes_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `kommendes-probe.json` liegen danach in DIR; nur synthetische Texte.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_satzantwort_ui import CHROMIUM, freier_port  # noqa: E402

UMGEBUNG = {'ICARUS_SIDECAR_TOKEN': 'kommendes-probe', 'ICARUS_MEMORY_SEMANTIC': '', 'KINGFISHER_TIMEZONE': 'Europe/Berlin'}
ICH = 'Lena Probe <lena.probe@example.org>'
ANNA = 'Anna Keller <anna.keller@agentur.example>'
BEN = 'Ben Braun <ben.braun@druck.example>'
FRAGE = 'Was brauche ich morgen?'
#: Was nie im sichtbaren Text stehen darf: ISO-Zeiten und Kennungen.
ROH = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}|conversation:|:message:|imap:|\be-[0-9a-f]{12}\b')


class Kaputt:
    """Ein lokaler Anbieter, der nie antworten darf: Die Antwort kommt ohne Modell."""

    is_local = True
    name = 'kaputt'
    model = 'kaputt-probe'
    supports_json = True

    def complete_json(self, messages, **kwargs):
        from icarus_memory.providers import ProviderError
        raise ProviderError('Für diese Probe gibt es kein Modell.')

    def complete(self, messages, tools=None, **kwargs):
        from icarus_memory.providers import ProviderError
        raise ProviderError('Für diese Probe gibt es kein Modell.')


class Kalender:
    def __init__(self, *events):
        self.items = list(events)

    def events(self, **kwargs):
        return self.items


@contextmanager
def instanz():
    with tempfile.TemporaryDirectory(prefix='kommendes-probe-') as temp:
        alt = {k: os.environ.get(k) for k in UMGEBUNG}
        os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=temp)
        try:
            from icarus_memory import MemoryBackend, SelfModelStore
            from icarus_memory.agent import Agent
            from icarus_memory.audit import AuditLog
            from icarus_memory.claims import ClaimStore
            from icarus_memory.episodes import EpisodeStore
            from icarus_memory.policy import Policy
            from icarus_memory.proposals import ProposalStore
            from icarus_memory.server import create_app
            daten = Path(temp)
            episodes, claims = EpisodeStore(daten / 'episodes.sqlite3'), ClaimStore(daten / 'knowledge.sqlite3')
            proposals, audit = ProposalStore(daten / 'proposals.sqlite3'), AuditLog(daten / 'audit.sqlite3')
            agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='probe'), policy=Policy(), audit=audit,
                          tools={}, provider=Kaputt(), knowledge=claims, episodes=episodes, max_rounds=1)
            app = create_app(agent._store, agent=agent, audit=audit, proposals=proposals, episodes=episodes,
                             knowledge=claims)
            try:
                yield app
            finally:
                getattr(app.state, 'scheduler', None) and app.state.scheduler.stop()
                for name in ('audit', 'tasks', 'workspace', 'episodes', 'proposals', 'conversations', 'claims', 'regeln'):
                    close = getattr(getattr(app.state, name, None), 'close', None)
                    if callable(close):
                        close()
        finally:
            for k, v in alt.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def mail(app, titel, abschnitte, teilnehmer, tage=1):
    """Eine eingeordnete Mail (wie in den Tests); `teilnehmer[0]` ist der Absender."""
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.working_memory_store import WorkingMemoryStore
    text = ' '.join(t for t, _ in abschnitte)
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f'imap:probe:INBOX:{titel}'),
        participants=list(teilnehmer), occurred_at=datetime.now(timezone.utc) - timedelta(days=tage))
    store = WorkingMemoryStore(app.state.episodes)
    pending = store.pending(episode_ids=[episode.id])[0]
    items, pos = [], 0
    for teil, art in abschnitte:
        start = text.index(teil, pos)
        items.append({'start': start, 'end': start + len(teil), 'kind': art})
        pos = start + len(teil)
    assert store.commit(pending, items, model='probe')
    return episode


def termin(uid, titel, tage, stunde, ort, teilnehmer):
    from icarus_memory.connectors.calendar import Event
    from icarus_memory.model import user_timezone
    zone = user_timezone() or timezone.utc
    tag = (datetime.now(zone) + timedelta(days=tage)).replace(hour=stunde, minute=0, second=0, microsecond=0)
    return Event(uid, titel, tag, tag + timedelta(minutes=90), location=ort, attendees=list(teilnehmer))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from playwright.sync_api import sync_playwright

    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with instanz() as app:
        from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
        app.state.settings.mail.user = 'lena.probe@example.org'
        morgen = (datetime.now().astimezone() + timedelta(days=1)).strftime('%d.%m.%Y')
        mail(app, 'Druckdaten Projekt Atlas', [(f'Bitte schick mir die Druckdaten bis zum {morgen}.', 'request')],
             [ANNA, ICH], tage=3)
        app.state.calendar = CalendarCollection([NamedCalendar('probe', 'Probekalender', Kalender(
            termin('t1', 'Gespräch Druckerei', 1, 14, 'Druckerei Braun, Werkstraße 4, Mainz', (ANNA, BEN, ICH)),
            termin('t2', 'Weit weg', 5, 10, 'Frankfurt', (BEN, ICH))))])

        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        faden = threading.Thread(target=server.run, daemon=True)
        faden.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            kontext = browser.new_context(viewport={'width': 1280, 'height': 900})
            seite = kontext.new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            seite.goto(basis + '/today')  # setzt die Sitzung für /api
            api = seite.request

            def bild(name):
                pfad = args.ausgabe / f'kommendes-{name}.png'
                seite.screenshot(path=str(pfad), full_page=False)
                ergebnis['bilder'].append(str(pfad))

            assert api.post(basis + '/api/v1/akten/aktualisieren').status == 200
            gespraech = api.post(basis + '/api/v1/conversations', data={'title': 'Morgen'}).json()['conversation']['id']
            antwort = api.post(f'{basis}/api/v1/conversations/{gespraech}/messages', data={'message': FRAGE})
            assert antwort.status == 201, antwort.text()
            letzte_api = next(m for m in reversed(antwort.json()['messages']) if m['role'] == 'assistant')
            vertrag = letzte_api['metadata']['context']['answer_contract']
            assert vertrag['status'] == 'kommendes' and vertrag['model_called'] is False, vertrag
            text = letzte_api['content']
            pruef['antwort'] = text
            assert 'Gespräch Druckerei' in text and 'Druckerei Braun, Werkstraße 4, Mainz' in text, text
            assert 'Anna Keller' in text and 'Ben Braun' in text and 'Weit weg' not in text, text
            assert 'Anna Keller bittet um etwas bis' in text and '[Quelle 1]' in text, text
            assert not re.search(r'\bfrei\b', text), text

            # 1. Breit: Antwort mit Abschnitten und Quellenlink sichtbar.
            seite.goto(f'{basis}/conversations/{gespraech}')
            letzte = seite.locator('.messages .message.assistant').last
            letzte.get_by_text('Was morgen ansteht', exact=False).first.wait_for(timeout=15000)
            sichtbar = seite.locator('.messages').inner_text()
            assert 'Gespräch Druckerei' in sichtbar and 'Druckdaten' in sichtbar and not ROH.search(sichtbar), ROH.search(sichtbar)
            knopf = letzte.get_by_role('button', name='Quelle 1 öffnen', exact=True)
            assert knopf.count() == 1, 'Quelle 1 öffnen fehlt'
            breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            pruef['1280px'] = breite
            assert breite[0] <= breite[1], breite
            letzte.scroll_into_view_if_needed()
            bild('1-antwort-1280')
            knopf.click()
            ansicht = letzte.get_by_role('region', name='Profilquelle')
            ansicht.get_by_role('heading', name='Druckdaten Projekt Atlas').wait_for(timeout=5000)
            pruef['quelle_geoeffnet'] = True
            bild('2-quelle-1280')

            # 2. Schmal: kein seitliches Scrollen.
            seite.set_viewport_size({'width': 390, 'height': 844})
            seite.goto(f'{basis}/conversations/{gespraech}')
            letzte = seite.locator('.messages .message.assistant').last
            letzte.get_by_text('Was morgen ansteht', exact=False).first.wait_for(timeout=15000)
            breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            pruef['390px'] = breite
            assert breite[0] <= breite[1], breite
            letzte.scroll_into_view_if_needed()
            bild('3-antwort-390')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'kommendes-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in ergebnis.items() if k != 'pruefungen'}, ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
