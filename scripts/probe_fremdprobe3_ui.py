#!/usr/bin/env python3
"""Browserprobe für die Befunde 1 bis 3, 8, 9, 12, 13 und 15 der Fremdprobe 3 (docs/52-fremdprobe-3.md), in der echten
Oberfläche mit echtem Sidecar.

Aufbau: frischer Datenordner, Zeitzone Europe/Berlin, ein skriptbares lokales Modell, eine IMAP-Attrappe mit fünf
synthetischen Mails (UIDVALIDITY nur bei EXAMINE, wie ein normgerechter Server). Das Passwort liegt in der verschlüsselten
Schlüsseldatei des Datenordners. Nur synthetische Daten (Lena Probe, Anna Berg, Jonas Keller).

Geprüft in Chromium:

* 2: Mit nachgestelltem Befund 1 (die Sitzung setzt UIDVALIDITY nicht wieder ein) scheitern alle fünf Mails. Heute,
  Einstellungen → Zugänge und der Assistent sagen „5 Mails kamen nicht ins Gedächtnis.“ mit Grund und Knopf „Erneut
  versuchen“, nirgends „wird gelesen“; die technische Angabe steht nur aufgeklappt unter „Für Techniker“. Nach dem Klick
  steht sofort, dass Kingfisher es noch einmal versucht.
* 1: Mit der Korrektur aus a771b17 landen nach „Erneut versuchen“ alle Mails im Gedächtnis (Newsletter ausgefiltert),
  das Postfach heißt „ist gelesen“.
* 15: Im Briefing steht keine Zahl ungelesener Nachrichten unter „Heutige Top-Prioritäten“.
* 9: Eine Termin-Quelle zeigt vorne keine Kennung `calendar:…` und keinen Satz „bei aktiver Automatik“; die Kennung steht
  unter „Für Techniker“.
* 3: Lädt das Sprachmodell noch, bietet die Fertig-Seite das Sortieren vorgemerkt an; nach „Zum Briefing“ heißt es unter
  Verarbeitung & Verlauf „An: … sobald das Sprachmodell … bereit ist“.
* 12: Nach „Automatisches Sortieren einschalten“ steht sofort „An:“ und kein „pausiert“ daneben.
* 8: Der Satz zum Warten sagt, dass man nichts tun muss (Heute, wenn er erscheint, und der Stand des Sidecars).
* 13: Unter Für Techniker → Zeitplan steht „alle 30 Minuten“.
* 390 px ohne seitliches Scrollen auf Heute mit der Fehlerzeile; die Konsole bleibt leer.

Aufruf: `python scripts/probe_fremdprobe3_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `fremdprobe3-probe.json` liegen danach in DIR.
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

ADRESSE = 'lena.probe@example.org'
UMGEBUNG = {'ICARUS_SIDECAR_TOKEN': 'fremdprobe3', 'ICARUS_MEMORY_SEMANTIC': '', 'KINGFISHER_TIMEZONE': 'Europe/Berlin',
            'ICARUS_SECRETS_PASSPHRASE': 'synthetische-passphrase-nur-fuer-die-probe', 'KINGFISHER_USER_NAME': 'Lena'}
TERMIN_REF = 'calendar:calendar-38d1718069744e76808c8e351eb567a6:probe-1@attrappe'


class Lokal:
    """Ein lokales Modell, das kurz antwortet und beim Einordnen nichts findet."""

    is_local = True
    name = 'lokal'
    model = 'lokal-probe'
    supports_json = True

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.providers import Reply
        return Reply(text='{}', model=self.model)

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='Gern.', model=self.model)


def sidecar(daten: Path):
    from icarus_memory import MemoryBackend, SelfModelStore, secrets
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.claims import ClaimStore
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.policy import Policy
    from icarus_memory.proposals import ProposalStore
    from icarus_memory.server import create_app
    secrets.Keychain._detect = lambda self: 'file'
    episodes, claims = EpisodeStore(daten / 'episodes.sqlite3'), ClaimStore(daten / 'knowledge.sqlite3')
    proposals, audit = ProposalStore(daten / 'proposals.sqlite3'), AuditLog(daten / 'audit.sqlite3')
    agent = Agent(store=SelfModelStore(MemoryBackend(), subject_id='probe'), policy=Policy(), audit=audit, tools={},
                  provider=Lokal(), knowledge=claims, episodes=episodes, max_rounds=1)
    return create_app(agent._store, agent=agent, audit=audit, proposals=proposals, episodes=episodes, knowledge=claims)


def select_wie_vorher(self, ordner, frisch=True):
    """Befund 1 nachgestellt: `_Sitzung.select` ohne die Korrektur aus a771b17."""
    if not frisch and self.folder == ordner:
        return 'OK'
    self.folder = None
    status = self._imap.select(ordner, readonly=True)[0]
    if status == 'OK':
        self.folder = ordner
    return status


def main() -> int:  # noqa: PLR0915 - eine Probe, Schritt für Schritt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from tests.imap_attrappe import PASSWORT, ImapAttrappe, probe_postfach
    attrappe = ImapAttrappe(nachrichten=probe_postfach(), uidvalidity=7)
    daten = Path(tempfile.mkdtemp(prefix='fremdprobe3-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(attrappe.zertifikat))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import local_model_guard
    from icarus_memory.connectors import mail as mail_modul
    from icarus_memory.local_model_guard import LocalModelIdentity
    from icarus_memory.providers import ProviderError

    korrigiert = mail_modul._Sitzung.select
    modell = {'bereit': False}

    def pruefe_modell(provider):
        if not modell['bereit']:
            raise ProviderError('Das Modell lädt noch.')
        return LocalModelIdentity(provider.model, 'a' * 64)
    local_model_guard.verify_local_model = pruefe_modell

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
            pfad = args.ausgabe / f'fp3-{name}.png'
            seite.screenshot(path=str(pfad), full_page=ganz)
            ergebnis['bilder'].append(str(pfad))

        app.state.settings.einrichtung = {'name': 'Lena', 'schritte': {}, 'abgeschlossen': True}

        # -- Postfach verbinden und einlesen, mit nachgestelltem Befund 1 -------------------------------------------
        antwort = api.post(basis + '/api/v1/integrations/mail', data={
            'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': attrappe.port, 'user': ADRESSE,
            'sender': ADRESSE, 'password': PASSWORT})
        assert antwort.status == 201, antwort.text()
        konto = api.get(basis + '/api/v1/integrations').json()['mail_accounts'][0]['id']
        umfang = api.get(f'{basis}/api/v1/mail/intake/{konto}/preview').json()
        assert api.post(f'{basis}/api/v1/mail/intake/{konto}/start', data={'folders': umfang['folders']}).ok
        mail_modul._Sitzung.select = select_wie_vorher
        takte()

        # -- 2: Heute ----------------------------------------------------------------------------------------------
        seite.goto(basis + '/today')
        karte = seite.get_by_role('region', name='Kingfisher lernt gerade')
        karte.get_by_text('5 Mails kamen nicht ins Gedächtnis.').wait_for(timeout=20000)
        text = karte.inner_text()
        pruef['2_heute'] = text
        assert 'wird gelesen' not in text and '0 von 5' not in text, text
        assert 'Das Postfach hat sie nicht so herausgegeben' in text
        assert 'MailError' not in text and 'kennung' not in text, 'Technik nur aufgeklappt'
        assert karte.get_by_role('button', name='Erneut versuchen').count() == 1
        karte.locator('details.mail-erneut-technik > summary').click()
        pruef['2_techniker'] = karte.locator('details.mail-erneut-technik').inner_text()
        assert '5 × kennung' in pruef['2_techniker'] and 'MailError' in pruef['2_techniker']
        bild('2-heute')
        seite.set_viewport_size({'width': 390, 'height': 844})
        seite.wait_for_timeout(500)
        breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
        pruef['2_heute_390'] = breite
        assert breite[0] <= breite[1], breite
        bild('2-heute-390')
        seite.set_viewport_size({'width': 1280, 'height': 900})

        # -- 2: Einstellungen → Zugänge und Assistent -------------------------------------------------------------
        seite.goto(basis + '/settings#zugaenge')
        zugaenge = seite.get_by_role('region', name='Kingfisher lernt gerade')
        zugaenge.get_by_text('5 Mails kamen nicht ins Gedächtnis.').wait_for(timeout=20000)
        assert zugaenge.get_by_role('button', name='Erneut versuchen').count() == 1
        assert 'wird gelesen' not in zugaenge.inner_text()
        pruef['2_zugaenge'] = True
        bild('2-zugaenge')
        seite.goto(basis + '/willkommen?schritt=mail')
        einlesen = seite.get_by_label('Mails einlesen')
        einlesen.get_by_text('5 Mails kamen nicht ins Gedächtnis.').wait_for(timeout=20000)
        pruef['2_assistent'] = einlesen.inner_text()
        assert 'gelesen.' not in pruef['2_assistent'].split('Gedächtnis.')[0]
        assert einlesen.get_by_role('button', name='Erneut versuchen').count() == 1
        bild('2-assistent')

        # -- 2 und 1: Erneut versuchen mit der Korrektur -----------------------------------------------------------
        mail_modul._Sitzung.select = korrigiert
        seite.goto(basis + '/today')
        karte = seite.get_by_role('region', name='Kingfisher lernt gerade')
        karte.get_by_role('button', name='Erneut versuchen').click()
        karte.get_by_text('Kingfisher versucht es jetzt noch einmal.').wait_for(timeout=10000)
        pruef['2_nach_klick'] = karte.inner_text()
        assert 'kamen nicht ins Gedächtnis' not in pruef['2_nach_klick']
        bild('2-nach-klick')
        takte()
        stand = api.get(basis + '/api/v1/mail/stand').json()['accounts'][0]
        pruef['1_stand'] = stand['satz']
        assert stand['zustand'] == 'aktuell', stand
        titel = {e.title for e in app.state.episodes.all_episodes(50)}
        pruef['1_im_gedaechtnis'] = sorted(titel)
        assert {'Treffen am Montag', 'Bitte: Angebot Vereinsfest bis Freitag', 'Nachtrag: Aufbau'} <= titel, titel
        seite.reload()
        seite.locator('.today-page h1').wait_for(timeout=15000)
        seite.wait_for_timeout(1500)
        assert seite.get_by_text('kamen nicht ins Gedächtnis').count() == 0

        # -- 15: Briefing ohne Zähler als Priorität ----------------------------------------------------------------
        seite.get_by_role('button', name='Briefing öffnen').click()
        schublade = seite.get_by_role('region', name='Briefing')
        schublade.locator('.drawer-card').first.wait_for(timeout=10000)
        prioritaeten = schublade.locator('.drawer-card', has_text='HEUTIGE TOP-PRIORITÄTEN').inner_text()
        pruef['15_prioritaeten'] = prioritaeten
        assert 'ungelesene' not in prioritaeten and 'Quelle: mail' not in prioritaeten, prioritaeten
        bild('15-briefing')

        # -- 9: Termin-Quelle ohne Kennung vorne ------------------------------------------------------------------
        from datetime import datetime, timezone
        from icarus_memory.episodes import EpisodeKind
        from icarus_memory.model import Provenance, SourceType
        from icarus_memory.working_memory_store import WorkingMemoryStore
        termin, _ = app.state.episodes.record(EpisodeKind.EVENT, 'Probe-Termin beim Steuerbüro',
                                           'Termin am 2. Oktober um 10 Uhr in Mainz.',
                                           Provenance(source_type=SourceType.CALENDAR, source_ref=TERMIN_REF),
                                           occurred_at=datetime.now(timezone.utc))
        WorkingMemoryStore(app.state.episodes).fail(app.state.episodes.support_snapshot(termin.id))
        seite.goto(basis + '/memory')
        seite.get_by_role('button', name='Verarbeitung & Verlauf').click()
        eintrag = seite.locator('.memory-status li', has_text='Probe-Termin beim Steuerbüro').first
        eintrag.wait_for(timeout=15000)
        eintrag.get_by_role('button', name='Inhalt öffnen').click()
        quelle = eintrag.locator('section[aria-label="Profilquelle"]')
        quelle.get_by_text('Termin am 2. Oktober').wait_for(timeout=10000)
        vorne = quelle.inner_text()
        pruef['9_vorne'] = vorne
        assert 'calendar:' not in vorne and 'bei aktiver Automatik' not in vorne, vorne
        assert 'Einordnung fehlgeschlagen · Kingfisher versucht es wieder, sobald das automatische Sortieren läuft' in vorne
        bild('9-quelle')
        quelle.locator('details.quelle-technik > summary').last.click()
        pruef['9_techniker'] = quelle.locator('details.quelle-technik').last.inner_text()
        assert TERMIN_REF in pruef['9_techniker']

        # -- 3: Fertig-Seite, während das Sprachmodell noch lädt ---------------------------------------------------
        # Das lokale Modell ist eingetragen, antwortet aber noch nicht (es lädt). Der Neubau beim Verbinden des
        # Postfachs nahm den Anbieter aus der Umgebung; hier wieder das skriptbare lokale Modell.
        app.state.agent._provider = Lokal()
        seite.goto(basis + '/willkommen?schritt=fertig')
        haken = seite.get_by_label(re.compile('Quellen auf diesem Rechner sortieren, sobald das Sprachmodell bereit ist'))
        haken.wait_for(timeout=15000)
        assert haken.is_checked()
        hintergrund = seite.locator('.erststart-hintergrund').inner_text()
        pruef['3_versprechen'] = hintergrund
        assert 'Es ordnet ein, wer wer ist' in hintergrund
        bild('3-fertig')
        seite.get_by_role('button', name='Zum Briefing').click()
        seite.wait_for_url(re.compile(r'/today'), timeout=15000)
        automatik = api.get(basis + '/api/v1/memory/automation').json()
        pruef['3_automatik'] = automatik
        assert automatik['requested'] is True and automatik['state'] == 'local_model_unavailable', automatik
        seite.goto(basis + '/memory')
        seite.get_by_role('button', name='Verarbeitung & Verlauf').click()
        sortieren = seite.get_by_role('region', name='Automatisches Sortieren')
        sortieren.get_by_text(re.compile('^An: .*sobald das Sprachmodell')).wait_for(timeout=15000)
        bereich = seite.get_by_role('region', name='Verarbeitung und Verlauf').inner_text()
        pruef['3_verarbeitung'] = bereich[:700]
        assert 'ist pausiert' not in bereich and 'Pausiert:' not in bereich, bereich[:700]
        bild('3-verarbeitung')

        # -- 12: Einschalten, und der Stand passt sich sofort an ---------------------------------------------------
        modell['bereit'] = True
        assert api.put(basis + '/api/v1/memory/automation', data={'enabled': False}).ok
        seite.get_by_role('button', name='Aktualisieren').click()
        knopf = sortieren.get_by_role('button', name='Automatisches Sortieren einschalten')
        knopf.wait_for(timeout=15000)
        vorher = seite.get_by_role('region', name='Verarbeitung und Verlauf').inner_text()
        pruef['12_vorher'] = vorher[:500]
        knopf.click()
        sortieren.get_by_role('button', name='Automatisches Sortieren pausieren').wait_for(timeout=15000)
        nachher = seite.get_by_role('region', name='Verarbeitung und Verlauf').inner_text()
        pruef['12_nachher'] = nachher[:700]
        assert 'An: Kingfisher sortiert deine Quellen selbst' in nachher
        assert 'ist pausiert' not in nachher, nachher[:700]
        bild('12-eingeschaltet')

        # -- 8: Der Satz zum Warten ----------------------------------------------------------------------------------
        stand_hinten = api.get(basis + '/api/v1/hintergrund').json()
        pruef['8_hintergrund'] = {k: stand_hinten.get(k) for k in ('zustand', 'grund')}
        assert 'Wartet, solange' not in json.dumps(stand_hinten, ensure_ascii=False)
        seite.goto(basis + '/today')
        seite.locator('.today-page h1').wait_for(timeout=15000)
        seite.wait_for_timeout(2500)
        grund = seite.locator('.lernt-grund')
        pruef['8_heute'] = grund.all_inner_texts()
        assert not any('Wartet, solange' in t for t in pruef['8_heute'])
        if any('Pause machst' in t for t in pruef['8_heute']):
            bild('8-heute')

        # -- 13: Zeitplan ------------------------------------------------------------------------------------------
        seite.goto(basis + '/settings#technik-hintergrund')
        abschnitt = seite.get_by_role('region', name='Mails regelmäßig abrufen')
        abschnitt.get_by_text(re.compile('alle 30 Minuten')).first.wait_for(timeout=15000)
        pruef['13_zeitplan'] = abschnitt.inner_text()[:300]
        assert 'vier Stunden ab' not in pruef['13_zeitplan']
        bild('13-zeitplan')
        browser.close()
    uv.should_exit = True
    attrappe.schliessen()
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'fremdprobe3-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': len(ergebnis['bilder'])},
                     ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
