#!/usr/bin/env python3
"""Browserprobe für die Befunde der ersten Stunde aus der Fremdprobe 2 (docs/51-fremdprobe-2.md, Befunde 10 bis 22,
26 bis 29), in der echten Oberfläche mit echtem Sidecar.

Aufbau: frischer Datenordner, Zeitzone Europe/Berlin, ein skriptbares lokales Modell (wählt bei der Gedächtnisantwort
die passenden Belege, sonst ein kurzer Satz), ein leeres IMAP-Postfach (Attrappe) mit Passwort in der verschlüsselten
Schlüsseldatei des Datenordners. Nur synthetische Daten (Lena Probe, Anna Berg, Projekt Atlas).

Geprüft in Chromium:

* Heute: eine Uhr; „Strg K“ unter Linux, „⌘ K“ mit einem Mac, kein Hinweis auf einem Touchgerät (10, 11);
  kein Zähler „0“ im Briefing (10); die Tageszeile nennt Hintergrundfehler ohne „gehakt“ und sagt „Du musst nichts
  tun“ (15); eigene Gesprächszeilen und eine hochgeladene Datei sind keine relevanten Nachrichten (22).
* Gespräch: unter der belegten Antwort „Gestützt auf“ mit dem lesbaren Hinweis und einem Klick zur Quelle; unter einer
  Antwort ohne Beleg „Ohne Beleg: …“; unter der eigenen Nachricht „So ist deine Nachricht gespeichert“; die linke
  Spalte widerspricht nicht (13); nach „Melden“ ein Satz, was geschieht (12); kein „Stimmt nicht?“ unter dem
  Gedächtnisvorschlag (14).
* Mail: nach „Aktualisieren“ „Gerade abgerufen um …“ (18); derselbe Satz zum Postfach auf Heute, unter „Was zuletzt
  lief“ und unter „Stand aller Bereiche“ (17).
* Verarbeitung & Verlauf: kein „Wenn du sie aktivierst“, keine Kacheln vorne (16).
* Akte Anna Berg (nur ein Name, keine Adresse): Karte „Kreis“ mit „Noch kein Vorschlag“ und drei Knöpfen, Klick
  speichert (19); „Noch kein Kontakt belegt“ (21); nach „Bestätigen“ des Geburtstags im Gespräch „Steht an“ in der
  Akte und der Eintrag im Kalender (20).
* Einstellungen: „wie es dir antworten soll“ (26); Für Techniker: eine Aussage zur Ausstattung, keine Kostenwarnung
  ohne Modell außerhalb des Rechners, „1 gespeichertes Dokument“, kein „Fehler · Nichts zu tun“ (27 bis 29).
* 390 px ohne seitliches Scrollen auf Heute, Gespräch, Akte, Nachrichten; die Konsole bleibt leer.

Aufruf: `python scripts/probe_fremdprobe2_alltag_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `fremdprobe2-alltag-probe.json` liegen danach in DIR.
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
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_satzantwort_ui import CHROMIUM, freier_port  # noqa: E402

KRANZ = 'Dr. Kranz leitet Projekt Atlas.'
FRAGE_KRANZ = 'Was weißt du über Dr. Kranz?'
FRAGE_OHNE = 'Wie spät ist es in Tokio?'
GEBURTSTAG = 'Anna Berg hat am 12. Oktober Geburtstag.'
UMGEBUNG = {'ICARUS_SIDECAR_TOKEN': 'alltag-probe', 'ICARUS_MEMORY_SEMANTIC': '', 'KINGFISHER_TIMEZONE': 'Europe/Berlin',
            'ICARUS_SECRETS_PASSPHRASE': 'synthetische-passphrase-nur-fuer-die-probe', 'KINGFISHER_USER_NAME': 'Lena'}


class Auswahl:
    """Ein lokales Modell: wählt bei der Gedächtnisantwort die Belege mit „Kranz“, sonst ein kurzer Satz."""

    is_local = True
    name = 'auswahl'
    model = 'auswahl-probe'
    supports_json = True

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.evidence_answer import INSTRUCTIONS
        from icarus_memory.providers import Reply
        if messages[0]['content'] != INSTRUCTIONS:
            return Reply(text='{}', model=self.model)
        daten = json.loads(messages[1]['content'].split('\n', 1)[1])
        wort = 'Kranz' if messages[-1]['content'] == FRAGE_KRANZ else '\0'
        ids = [zeile['evidence_id'] for zeile in daten['evidence'] if wort in zeile['statement']]
        return Reply(text=json.dumps({'version': 1, 'kind': 'evidence' if ids else 'unknown', 'evidence_ids': ids}),
                     model=self.model)

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='In Tokio ist es acht Stunden später als in Berlin.', model=self.model)


def sidecar(daten: Path):
    from icarus_memory import MemoryBackend, SelfModelStore, secrets
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.claims import ClaimStore
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.policy import Policy
    from icarus_memory.proposals import ProposalStore
    from icarus_memory.server import create_app
    # Passwörter in der verschlüsselten Datei des Datenordners, nie im Schlüsselbund des Rechners.
    secrets.Keychain._detect = lambda self: 'file'
    episodes, claims = EpisodeStore(daten / 'episodes.sqlite3'), ClaimStore(daten / 'knowledge.sqlite3')
    proposals, audit = ProposalStore(daten / 'proposals.sqlite3'), AuditLog(daten / 'audit.sqlite3')
    agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='probe'), policy=Policy(), audit=audit, tools={},
                  provider=Auswahl(), knowledge=claims, episodes=episodes, max_rounds=1)
    return create_app(agent._store, agent=agent, audit=audit, proposals=proposals, episodes=episodes, knowledge=claims)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from tests.imap_attrappe import PASSWORT, ImapAttrappe
    attrappe = ImapAttrappe()
    daten = Path(tempfile.mkdtemp(prefix='alltag-probe-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(attrappe.zertifikat))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import logbuch, server as server_modul
    from icarus_memory.graph import person_id_fuer
    server_modul.POSTFACH_ZEITGRENZE = 3.0

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
    ROH = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}|conversation:|:message:|claim:|\be-[0-9a-f]{12}\b')

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        kontext = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='de-DE')
        seite = kontext.new_page()
        seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
        seite.goto(basis + '/today')  # setzt die Sitzung für /api
        api = seite.request

        def bild(name, ganz=False):
            pfad = args.ausgabe / f'alltag-{name}.png'
            seite.screenshot(path=str(pfad), full_page=ganz)
            ergebnis['bilder'].append(str(pfad))

        def schmal_ohne_scrollen(name):
            seite.set_viewport_size({'width': 390, 'height': 844})
            seite.wait_for_timeout(600)
            breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            pruef[f'390_{name}'] = breite
            assert breite[0] <= breite[1], (name, breite)
            bild(f'{name}-390')
            seite.set_viewport_size({'width': 1280, 'height': 900})

        # -- Ausgangslage: Name, Einrichtung abgeschlossen, ein leeres Postfach -------------------------------------
        app.state.settings.einrichtung = {'name': 'Lena', 'schritte': {}, 'abgeschlossen': True}  # kein Erststart-Assistent
        # Eine hochgeladene Datei und Gesprächszeilen: beides keine relevanten Nachrichten (Befund 22).
        assert api.post(basis + '/api/v1/sources/documents', data={
            'filename': 'Besprechung-Atlas.md', 'body': 'Besprechung Atlas mit Anna Berg und Tom Weiler.', 'project_id': None}).ok
        # Wie nach „Merke dir …“ mit einem Modell: Die eigene Gesprächszeile nennt Anna Berg als Beteiligte. Sie hat
        # nie selbst geschrieben; die Akte darf daraus keinen Kontakt machen (Befund 21).
        from datetime import datetime, timezone
        from icarus_memory.episodes import EpisodeKind
        from icarus_memory.model import Provenance, SourceType
        app.state.episodes.record(EpisodeKind.MESSAGE, 'Gespräch', 'Anna Berg kommt zur Abstimmung Atlas.',
                                  Provenance(source_type=SourceType.CHAT, source_ref='conversation:probe:message:anna'),
                                  occurred_at=datetime.now(timezone.utc), participants=['Anna Berg'])
        # Drei Hintergrundschritte, die nicht fertig wurden (Befund 15).
        for was in ('gedaechtnis', 'zusagen', 'verdichtung'):
            logbuch.vermerke('fehler', was=was)

        # -- Gespräch A: Merksatz zu Dr. Kranz, als Wissen bestätigt; Gedächtnisvorschlag zum Geburtstag ----------
        a = api.post(basis + '/api/v1/conversations', data={'title': 'Projekt Atlas'}).json()['conversation']['id']
        gesendet = api.post(f'{basis}/api/v1/conversations/{a}/messages', data={'message': KRANZ}).json()
        quelle_id = next(m['id'] for m in gesendet['messages'] if m['role'] == 'user' and m['content'] == KRANZ)
        karte = api.post(f'{basis}/api/v1/conversations/{a}/memory-candidates', data={
            'source_message_id': quelle_id, 'subject_ref': 'person:kranz', 'predicate': 'leads',
            'value': 'Projekt Atlas', 'statement': KRANZ}).json()
        kandidat = karte['memory_candidates'][-1]['candidate']['id']
        assert api.post(f'{basis}/api/v1/conversations/{a}/memory-candidates/{kandidat}/accept',
                        data={'replace_conflicts': False}).status == 200
        merke = api.post(f'{basis}/api/v1/conversations/{a}/messages', data={'message': f'Merke dir: {GEBURTSTAG}'}).json()
        merke_id = next(m['id'] for m in merke['messages'] if m['role'] == 'user' and m['content'].endswith(GEBURTSTAG))
        api.post(f'{basis}/api/v1/conversations/{a}/memory-candidates', data={
            'source_message_id': merke_id, 'subject_ref': person_id_fuer('n:anna berg'), 'predicate': 'geburtstag',
            'value': '12. Oktober', 'statement': GEBURTSTAG})

        # Ein offener Vorschlag, damit Heute nicht leer ist (dann steht die Tageszeile da).
        tom = api.post(f'{basis}/api/v1/conversations/{a}/messages',
                       data={'message': 'Tom Weiler übernimmt die Abstimmung mit dem Druckhaus.'}).json()
        tom_id = next(m['id'] for m in tom['messages'] if m['role'] == 'user' and m['content'].startswith('Tom Weiler'))
        api.post(f'{basis}/api/v1/conversations/{a}/memory-candidates', data={
            'source_message_id': tom_id, 'subject_ref': 'person:tom-weiler', 'predicate': 'uebernimmt',
            'value': 'Abstimmung Druckhaus', 'statement': 'Tom Weiler übernimmt die Abstimmung mit dem Druckhaus.'})

        # 13: belegte Antwort und Antwort ohne Beleg.
        belegt = api.post(f'{basis}/api/v1/conversations/{a}/messages',
                          data={'message': FRAGE_KRANZ, 'answer_mode': 'memory_evidence'}).json()['messages'][-1]
        assert 'quellen' in belegt['metadata'].get('context', {}), json.dumps(belegt, ensure_ascii=False)[:1500]
        hinweis = belegt['metadata']['context']['quellen'][0]['text']
        pruef['13_hinweis'] = hinweis
        api.post(f'{basis}/api/v1/conversations/{a}/messages', data={'message': FRAGE_OHNE, 'answer_mode': 'chat'})
        seite.goto(f'{basis}/conversations/{a}')
        artikel = seite.locator('.messages .message.assistant')
        artikel.last.wait_for(timeout=15000)
        beleg_artikel = seite.locator('.messages .message.assistant', has_text='Gespeicherte Aussagen mit Quellenbezug').last
        gruppe = beleg_artikel.get_by_role('group', name='Worauf die Antwort sich stützt')
        gruppe.wait_for(timeout=10000)
        pruef['13_gestuetzt_auf'] = gruppe.inner_text()
        assert 'Gestützt auf' in gruppe.inner_text() and hinweis in gruppe.inner_text(), gruppe.inner_text()
        ohne = seite.locator('.messages .message.assistant', has_text='In Tokio').last
        pruef['13_ohne_beleg'] = ohne.inner_text()
        assert 'Ohne Beleg: Diese Antwort stützt sich auf keine Quelle aus deinem Gedächtnis.' in ohne.inner_text()
        eigene = seite.locator('.messages .message.user').first
        pruef['13_eigene_nachricht'] = eigene.get_by_role('button', name='So ist deine Nachricht gespeichert').count() == 1
        assert pruef['13_eigene_nachricht']
        assert seite.get_by_text('Gesprächsquelle ansehen').count() == 0
        links = seite.locator('.context-list').inner_text()
        pruef['13_linke_spalte'] = links
        assert 'Keine aktuell verwendbaren' not in links
        sichtbar = seite.locator('.messages').inner_text()
        assert not ROH.search(sichtbar), ROH.search(sichtbar)
        bild('gespraech-beleg', ganz=True)
        gruppe.get_by_role('button', name='Quelle 1 öffnen', exact=True).click()
        seite.wait_for_function("id => document.activeElement && document.activeElement.id === 'message-' + id",
                                arg=quelle_id, timeout=5000)
        pruef['13_klick_zur_quelle'] = True

        # 14: kein „Stimmt nicht?“ unter dem Gedächtnisvorschlag, wohl aber unter den Antworten.
        vorschlag = seite.locator('.messages .message.assistant', has=seite.get_by_role('region', name='Gedächtnisvorschlag'),
                                  has_text=GEBURTSTAG).last
        pruef['14_vorschlag_ohne_stimmt_nicht'] = vorschlag.get_by_role('button', name='Stimmt nicht?').count() == 0
        pruef['14_antwort_mit_stimmt_nicht'] = ohne.get_by_role('button', name='Stimmt nicht?').count() == 1
        assert pruef['14_vorschlag_ohne_stimmt_nicht'] and pruef['14_antwort_mit_stimmt_nicht']

        # 12: Melden sagt, was geschieht.
        ohne.get_by_role('button', name='Stimmt nicht?').click()
        ohne.get_by_role('button', name='Falsch', exact=True).click()
        ohne.get_by_role('button', name='Melden').click()
        gemeldet = ohne.locator('.stimmt-nicht-gemerkt')
        gemeldet.wait_for(timeout=5000)
        pruef['12_gemeldet'] = gemeldet.inner_text()
        assert 'bleibt auf diesem Rechner' in pruef['12_gemeldet'] and 'nicht wieder machen' in pruef['12_gemeldet']
        # Fremdprobe 3, Befund 11: vorne keine Fachwörter des Rückkanals.
        assert not re.search(r'Prüffrage|Messlatte|[Ww]er Kingfisher verbessert', pruef['12_gemeldet']), pruef['12_gemeldet']
        assert gemeldet.get_by_role('link', name='Einstellungen → Für Techniker → Rückmeldungen').count() == 1
        bild('gespraech-gemeldet')

        # 20: Geburtstag bestätigen, dann Akte und Kalender.
        vorschlag.get_by_role('button', name='Bestätigen', exact=True).click()
        vorschlag.get_by_text('Als Wissen bestätigt.').wait_for(timeout=10000)
        schmal_ohne_scrollen('gespraech')

        # -- Akte Anna Berg (19, 20, 21) --------------------------------------------------------------------------
        seite.goto(basis + '/memory/people/Anna%20Berg')
        kreis = seite.get_by_role('region', name='Kreis')
        try:
            kreis.wait_for(timeout=15000)
        except Exception:
            bild('akte-fehlt', ganz=True)
            raise AssertionError(seite.locator('main').inner_text()[:800])
        pruef['19_kreis'] = kreis.inner_text()
        assert 'Noch kein Vorschlag; du kannst den Kreis selbst festlegen.' in pruef['19_kreis']
        assert 'vorgeschlagen' not in pruef['19_kreis'] and 'Warum:' not in pruef['19_kreis']
        assert kreis.get_by_role('button').count() == 3
        steht_an = seite.get_by_role('region', name='Steht an')
        steht_an.wait_for(timeout=10000)
        pruef['20_akte'] = steht_an.inner_text()
        assert 'Geburtstag am 12. Oktober' in pruef['20_akte']
        kopf = seite.locator('.profile-heading').inner_text()
        pruef['21_kopf'] = kopf
        assert 'Noch kein Kontakt belegt' in kopf and 'belegter Kontakt' not in kopf
        bild('akte', ganz=True)
        kreis.get_by_role('button', name='Innerer Kreis').click()
        kreis.get_by_text('Gespeichert: Innerer Kreis.').wait_for(timeout=5000)
        pruef['19_gespeichert'] = True
        schmal_ohne_scrollen('akte')

        seite.goto(basis + '/calendar')
        seite.get_by_role('button', name='Monat', exact=True).click()
        jahr = time.localtime().tm_year
        seite.get_by_role('button', name=re.compile(rf'^12\.10\.{jahr}, ')).click()
        eintrag = seite.locator('.calendar-entry', has_text='Geburtstag: Anna Berg')
        eintrag.wait_for(timeout=10000)
        pruef['20_kalender'] = eintrag.inner_text()
        assert 'nur in Kingfisher' in pruef['20_kalender'] and eintrag.get_by_role('button', name='Vorbereiten').count() == 0
        bild('kalender')

        # -- Nachrichten (18) und Mailstand (17) --------------------------------------------------------------------
        # Das Postfach erst jetzt: Ein neuer Zugang baut den Assistenten neu (dann ohne das Auswahlmodell der Probe).
        antwort = api.post(basis + '/api/v1/integrations/mail', data={
            'label': 'Privat', 'imap_host': '127.0.0.1', 'imap_port': attrappe.port, 'user': 'lena.probe@example.org',
            'sender': 'lena.probe@example.org', 'password': PASSWORT})
        assert antwort.ok, antwort.text()
        konto = antwort.json()['mail_accounts'][-1]['id']
        seite.goto(basis + '/nachrichten')
        seite.locator('.inbox-empty').wait_for(timeout=15000)
        seite.get_by_role('button', name='Aktualisieren').click()
        abgerufen = seite.locator('.inbox-abgerufen')
        abgerufen.wait_for(timeout=15000)
        pruef['18_aktualisiert'] = abgerufen.inner_text()
        assert re.fullmatch(r'Gerade abgerufen um \d{2}:\d{2}: Der Posteingang ist leer\.', pruef['18_aktualisiert'])
        bild('nachrichten')
        schmal_ohne_scrollen('nachrichten')
        stand = api.get(basis + '/api/v1/mail/stand').json()['accounts']
        satz = next(s['satz'] for s in stand if s['account_id'] == konto)
        pruef['17_satz'] = satz
        assert satz.startswith('Postfach Privat ist verbunden und leer, abgerufen um ')
        # Beide Sätze nennen dieselbe Uhrzeit, in der Zeitzone des Nutzers (nicht der des Browsers).
        assert re.search(r'um (\d{2}:\d{2})', satz)[1] == re.search(r'um (\d{2}:\d{2})', pruef['18_aktualisiert'])[1], \
            (satz, pruef['18_aktualisiert'])

        # -- Heute (10, 11, 15, 17, 22) -----------------------------------------------------------------------------
        seite.goto(basis + '/today')
        seite.locator('.today-page h1').wait_for(timeout=15000)
        seite.wait_for_timeout(1500)
        heute = seite.locator('main').inner_text()
        pruef['11_uhren'] = seite.locator('time').count()
        assert pruef['11_uhren'] == 1, 'eine Uhr'
        pruef['11_taste_linux'] = seite.locator('.command-bar kbd').inner_text()
        assert pruef['11_taste_linux'] == 'Strg K'
        pruef['15_tageszeile'] = [z for z in heute.splitlines() if 'Hintergrund' in z]
        assert any('Du musst nichts tun' in z for z in pruef['15_tageszeile']) and 'gehakt' not in heute, heute
        seite.locator('.today-postfach').get_by_text(satz).wait_for(timeout=10000)
        pruef['17_heute'] = True
        bild('heute')
        seite.get_by_role('button', name='Briefing öffnen').click()
        schublade = seite.get_by_role('region', name='Briefing')
        schublade.locator('.drawer-card').first.wait_for(timeout=5000)
        zaehler = [b.inner_text() for b in schublade.locator('.drawer-card header b').all()]
        pruef['10_zaehler'] = zaehler
        assert '0' not in zaehler
        nachrichten = schublade.locator('.drawer-card', has_text='RELEVANTE NACHRICHTEN').inner_text()
        pruef['22_relevante_nachrichten'] = nachrichten
        assert 'Quelle aufgenommen' not in nachrichten and 'Quellen aufgenommen' not in nachrichten and 'Gesprächsquelle' not in nachrichten
        bild('briefing')
        seite.goto(basis + '/today')
        seite.locator('.today-page h1').wait_for(timeout=15000)
        schmal_ohne_scrollen('heute')

        # -- Verarbeitung & Verlauf (16) ----------------------------------------------------------------------------
        seite.goto(basis + '/memory')
        seite.get_by_role('button', name='Verarbeitung & Verlauf').click()
        seite.get_by_role('heading', name='Automatisches Sortieren').wait_for(timeout=15000)
        bereich = seite.get_by_role('region', name='Verarbeitung und Verlauf')
        vorne = bereich.inner_text()
        pruef['16_vorne'] = vorne[:600]
        assert 'Wenn du sie aktivierst' not in vorne and 'Aktiv mit' not in vorne
        assert not seite.get_by_text('Prüflauf durchgeführt').is_visible()
        bild('verarbeitung')

        # -- Einstellungen (19, 26) und Für Techniker (17, 27 bis 29) -----------------------------------------------
        seite.goto(basis + '/settings#ich')
        seite.get_by_text('wie es dir antworten soll').first.wait_for(timeout=15000)
        ich = seite.locator('main').inner_text()
        pruef['26_es'] = 'wie er dir' not in ich
        pruef['19_einstellungen'] = 'In jeder Akte einer Person steht die Karte „Kreis“' in ich
        assert pruef['26_es'] and pruef['19_einstellungen']
        seite.goto(basis + '/settings#technik-hintergrund')
        verlauf = seite.locator('details.mail-abruf-verlauf')
        verlauf.wait_for(timeout=15000)
        verlauf.locator('summary').click()
        lief = verlauf.inner_text()
        pruef['17_techniker'] = lief
        pruef['28_kosten'] = 'Kosten verursacht' not in lief
        assert satz in lief and pruef['28_kosten'] and 'Fehler · Nichts zu tun' not in lief
        bild('techniker-zeitplan')
        seite.goto(basis + '/settings#technik-stand')
        seite.get_by_text('gespeichertes Dokument').first.wait_for(timeout=15000)
        stand_text = seite.locator('.setup-overview').inner_text()
        pruef['27_dokumente'] = '1 gespeichertes Dokument' in stand_text
        pruef['17_stand_aller_bereiche'] = satz in stand_text
        assert pruef['27_dokumente'] and pruef['17_stand_aller_bereiche'] and 'Sicherungshelfer ist gerade' not in stand_text
        seite.goto(basis + '/settings#technik-modelle')
        geraet = seite.get_by_role('region', name='Gerät und lokale Modelle')
        geraet.get_by_text('Angaben erneut prüfen').wait_for(timeout=15000)
        seite.wait_for_timeout(1500)
        geraet_text = geraet.inner_text()
        pruef['27_ausstattung'] = geraet_text[:300]
        assert 'noch unbekannt' not in geraet_text and 'noch nicht gemeldet' not in geraet_text
        assert re.search(r'GB Arbeitsspeicher, (selbst gemessen|im Container gemessen)', geraet_text), geraet_text
        bild('techniker-geraet')

        # -- Tastenhinweis auf dem Mac und auf dem Telefon (11) ------------------------------------------------------
        for name, optionen, erwartet in (
                ('mac', {'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'}, '⌘ K'),
                ('telefon', {'viewport': {'width': 390, 'height': 844}, 'has_touch': True, 'is_mobile': True}, None)):
            anderer = browser.new_context(**{'viewport': {'width': 1280, 'height': 900}, **optionen})
            neu = anderer.new_page()
            neu.goto(basis + '/today')
            neu.locator('.command-bar').wait_for(timeout=15000)
            taste = neu.locator('.command-bar kbd')
            pruef[f'11_taste_{name}'] = taste.inner_text() if taste.count() else None
            assert pruef[f'11_taste_{name}'] == erwartet, (name, pruef[f'11_taste_{name}'])
            anderer.close()
        browser.close()
    uv.should_exit = True
    attrappe.schliessen()
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'fremdprobe2-alltag-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2),
                                                                encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': len(ergebnis['bilder'])},
                     ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
