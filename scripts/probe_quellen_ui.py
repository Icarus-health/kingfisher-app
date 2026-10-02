#!/usr/bin/env python3
"""Browserprobe für den lesbaren Quellenhinweis der belegten Gedächtnisantwort (echte Oberfläche, echter Server).

Vorher stand im Gespräch `Quelle [1]: Gespräch · "conversation:c-…:message:m-…"` und
`Ereigniszeit: 2026-10-01T10:25:07.79…+00:00`. Diese Probe startet den Sidecar mit einem skriptbaren lokalen
Modell (es wählt nur die Belege, wie die Gedächtnisantwort es verlangt), legt zwei bestätigte Einträge an (einen aus
einem Gespräch, einen aus einer Mail von `lena.probe@example.org`) und prüft in Chromium:

* die Antwort nennt die Quelle in Alltagssprache („Gespräch vom 1. Oktober 2026, 12:25 Uhr“, „E-Mail „Angebot
  Projekt Atlas“ von Lena Probe vom 29. September 2026, 09:00 Uhr“), in der Zeitzone des Nutzers,
* im sichtbaren Text des Gesprächs steht keine ISO-Zeit und keine Kennung,
* „Quelle 1 öffnen“ springt in demselben Gespräch zur Nachricht, öffnet aus einem anderen Gespräch das richtige
  Gespräch an der Nachricht und zeigt bei einer Mail die Quellenansicht mit dem Betreff,
* die Kennungen stehen nur hinter „Für Techniker“ (zu Beginn eingeklappt),
* bei 390 px kein seitliches Scrollen, und die Konsole bleibt leer.

Aufruf: `python scripts/probe_quellen_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `quellen-probe.json` liegen danach in DIR; sie enthalten nur synthetische Texte.
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
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_satzantwort_ui import CHROMIUM, freier_port  # noqa: E402

UMGEBUNG = {'ICARUS_SIDECAR_TOKEN': 'quellen-probe', 'ICARUS_MEMORY_SEMANTIC': '', 'KINGFISHER_TIMEZONE': 'Europe/Berlin'}
MAIL_ZEIT = datetime(2026, 9, 29, 7, 0, tzinfo=timezone.utc)
KRANZ = 'Dr. Kranz leitet Projekt Atlas.'
ANGEBOT = 'Das Angebot für Projekt Atlas kostet 48.000 Euro.'
FRAGE_KRANZ = 'Was weißt du über Dr. Kranz?'
FRAGE_ANGEBOT = 'Was kostet das Angebot?'
#: Was nie im sichtbaren Text stehen darf: ISO-Zeiten und Kennungen.
ROH = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}|conversation:|:message:|claim:|imap:|\be-[0-9a-f]{12}\b')


class Auswahl:
    """Ein lokales Modell, das bei der Gedächtnisantwort nur die passenden Belege wählt; sonst ein kurzer Satz."""

    is_local = True
    name = 'auswahl'
    model = 'auswahl-probe'
    supports_json = True
    STICHWORT = {FRAGE_KRANZ: 'Kranz', FRAGE_ANGEBOT: 'Angebot'}

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.evidence_answer import INSTRUCTIONS
        from icarus_memory.providers import Reply
        if messages[0]['content'] != INSTRUCTIONS:
            return Reply(text='{}', model=self.model)
        daten = json.loads(messages[1]['content'].split('\n', 1)[1])
        wort = self.STICHWORT.get(messages[-1]['content'], '\0')
        ids = [zeile['evidence_id'] for zeile in daten['evidence'] if wort in zeile['statement']]
        return Reply(text=json.dumps({'version': 1, 'kind': 'evidence' if ids else 'unknown', 'evidence_ids': ids}),
                     model=self.model)

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='Notiert.', model=self.model)


@contextmanager
def instanz():
    """Ein Sidecar mit eigenem Datenordner und dem Auswahlmodell; die Uhr läuft (Nachrichten brauchen ihre Reihenfolge)."""
    with tempfile.TemporaryDirectory(prefix='quellen-probe-') as temp:
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
                          tools={}, provider=Auswahl(), knowledge=claims, episodes=episodes, max_rounds=1)
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
        from icarus_memory.datumstext import zeitpunkt_text
        from icarus_memory.episodes import EpisodeKind
        from icarus_memory.model import Provenance, SourceType
        from icarus_memory.proposals import Evidence
        # Ein bestätigter Eintrag aus einer Mail (synthetisch).
        text = 'Hallo, das Angebot für Projekt Atlas kostet 48.000 Euro. Viele Grüße, Lena'
        mail, _ = app.state.episodes.record(
            EpisodeKind.MESSAGE, 'Angebot Projekt Atlas', text,
            Provenance(source_type=SourceType.EMAIL, source_ref='imap:lena.probe@example.org:INBOX:7'),
            occurred_at=MAIL_ZEIT, participants=['Lena Probe <lena.probe@example.org>'])
        vorschlag, _ = app.state.knowledge_service.propose(
            subject_ref='project:atlas-angebot', predicate='price', value='48.000 Euro', statement=ANGEBOT,
            evidence=[Evidence(mail.id, text, mail.digest)], rationale='Probe')
        app.state.knowledge_service.accept(vorschlag.id, supersedes=[])

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
            kontext = browser.new_context(viewport={'width': 1100, 'height': 900})
            seite = kontext.new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            seite.goto(basis + '/today')  # setzt die Sitzung für /api
            api = seite.request

            def bild(name):
                pfad = args.ausgabe / f'quellen-{name}.png'
                seite.screenshot(path=str(pfad), full_page=False)
                ergebnis['bilder'].append(str(pfad))

            def frage(gespraech, text):
                antwort = api.post(f'{basis}/api/v1/conversations/{gespraech}/messages', data={'message': text, 'answer_mode': 'memory_evidence'})
                assert antwort.status == 201, antwort.text()
                return antwort.json()['messages'][-1]

            # Gespräch A: der Merksatz, als Wissen bestätigt.
            a = api.post(basis + '/api/v1/conversations', data={'title': 'Projekt Atlas'}).json()['conversation']['id']
            gesendet = api.post(f'{basis}/api/v1/conversations/{a}/messages', data={'message': KRANZ}).json()
            quelle = next(m for m in gesendet['messages'] if m['role'] == 'user' and m['content'] == KRANZ)
            quelle_id = quelle['id']
            pruef['nachrichten'] = [(m['role'], m['status'], m['content'][:40]) for m in gesendet['messages']]
            # So muss der Hinweis heißen: Tag und Uhrzeit der Nachricht in der Zeitzone des Nutzers (Berlin).
            gespraech_hinweis = 'Gespräch vom ' + zeitpunkt_text(quelle['created_at'])
            assert re.fullmatch(r'Gespräch vom \d{1,2}\. \w+ \d{4}(, \d{2}:\d{2} Uhr)?', gespraech_hinweis), gespraech_hinweis
            karte = api.post(f'{basis}/api/v1/conversations/{a}/memory-candidates', data={
                'source_message_id': quelle_id, 'subject_ref': 'person:kranz', 'predicate': 'leads',
                'value': 'Projekt Atlas', 'statement': KRANZ}).json()
            assert 'memory_candidates' in karte, (karte, pruef['nachrichten'])
            kandidat = karte['memory_candidates'][-1]['candidate']['id']
            assert api.post(f'{basis}/api/v1/conversations/{a}/memory-candidates/{kandidat}/accept',
                            data={'replace_conflicts': False}).status == 200

            # 1. Dasselbe Gespräch: Antwort mit „Gespräch vom …“, Klick springt zur Nachricht.
            antwort = frage(a, FRAGE_KRANZ)
            assert 'context' in antwort['metadata'], antwort
            quellen = antwort['metadata']['context'].get('quellen') or []
            assert antwort['metadata']['context']['answer_contract']['status'] == 'evidence', antwort
            assert [(q['conversation_id'], q['message_id']) for q in quellen] == [(a, quelle_id)], quellen
            erwartet = 'Quelle [1]: ' + gespraech_hinweis
            assert erwartet in antwort['content'], antwort['content']
            pruef['gespraech_text'] = antwort['content']
            seite.goto(f'{basis}/conversations/{a}')
            letzte = seite.locator('.messages .message.assistant').last
            letzte.get_by_text('Gespeicherte Aussagen mit Quellenbezug:').wait_for(timeout=15000)
            letzte.scroll_into_view_if_needed()
            sichtbar = seite.locator('.messages').inner_text()
            assert erwartet in sichtbar and not ROH.search(sichtbar), ROH.search(sichtbar)
            technik = letzte.locator('details.quelle-technik')
            assert technik.count() == 1 and technik.get_attribute('open') is None, 'Für Techniker ist eingeklappt'
            assert letzte.locator('[data-quelle="1"]').get_attribute('data-quelle-ref') == f'conversation:{a}:message:{quelle_id}'
            bild('1-gespraech')
            letzte.get_by_role('button', name='Quelle 1 öffnen', exact=True).click()
            seite.wait_for_function("id => document.activeElement && document.activeElement.id === 'message-' + id",
                                    arg=quelle_id, timeout=5000)
            pruef['sprung_im_gespraech'] = True
            bild('2-sprung')
            technik.locator('summary').click()
            assert f'claim:' in technik.inner_text() and quelle_id in technik.inner_text(), technik.inner_text()
            pruef['techniker'] = technik.inner_text()
            bild('3-techniker')

            # 2. Ein anderes Gespräch: der Klick öffnet Gespräch A an der Nachricht.
            b = api.post(basis + '/api/v1/conversations', data={'title': 'Nachfrage'}).json()['conversation']['id']
            frage(b, FRAGE_KRANZ)
            seite.goto(f'{basis}/conversations/{b}')
            letzte = seite.locator('.messages .message.assistant').last
            letzte.get_by_text('Gespeicherte Aussagen mit Quellenbezug:').wait_for(timeout=15000)
            letzte.get_by_role('button', name='Quelle 1 öffnen', exact=True).click()
            seite.wait_for_url(f'**/conversations/{a}#message-{quelle_id}', timeout=5000)
            seite.wait_for_function("id => document.activeElement && document.activeElement.id === 'message-' + id",
                                    arg=quelle_id, timeout=10000)
            pruef['sprung_in_anderes_gespraech'] = seite.url.removeprefix(basis)
            bild('4-anderes-gespraech')

            # 3. Eine Mail: Betreff, Absender und Zeit im Hinweis; der Klick zeigt die Quelle.
            antwort = frage(b, FRAGE_ANGEBOT)
            erwartet = 'Quelle [1]: E-Mail „Angebot Projekt Atlas“ von Lena Probe vom 29. September 2026, 09:00 Uhr'
            assert erwartet in antwort['content'], antwort['content']
            pruef['mail_text'] = antwort['content']
            seite.goto(f'{basis}/conversations/{b}')
            letzte = seite.locator('.messages .message.assistant').last
            letzte.get_by_text(erwartet.removeprefix('Quelle [1]: ')).first.wait_for(timeout=15000)
            # Unter der Antwort steht derselbe Hinweis sichtbar unter „Gestützt auf“ (Fremdprobe 2, Befund 13).
            beleg = letzte.get_by_role('group', name='Worauf die Antwort sich stützt')
            assert 'Gestützt auf' in beleg.inner_text() and erwartet.removeprefix('Quelle [1]: ') in beleg.inner_text(), beleg.inner_text()
            sichtbar = seite.locator('.messages').inner_text()
            assert not ROH.search(sichtbar), ROH.search(sichtbar)
            letzte.get_by_role('button', name='Quelle 1 öffnen', exact=True).click()
            ansicht = letzte.get_by_role('region', name='Profilquelle')
            ansicht.get_by_role('heading', name='Angebot Projekt Atlas').wait_for(timeout=5000)
            pruef['mail_quelle'] = True
            letzte.scroll_into_view_if_needed()
            bild('5-mail')

            # 4. Schmal: kein seitliches Scrollen.
            seite.set_viewport_size({'width': 390, 'height': 844})
            seite.goto(f'{basis}/conversations/{a}')
            seite.locator('.messages .message.assistant').last.get_by_text('Gespeicherte Aussagen mit Quellenbezug:').wait_for(timeout=15000)
            breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            pruef['390px'] = breite
            assert breite[0] <= breite[1], breite
            seite.locator('.messages .message.assistant').last.scroll_into_view_if_needed()
            bild('6-schmal')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'quellen-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']}, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
