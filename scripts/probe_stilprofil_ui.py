#!/usr/bin/env python3
"""Browserprobe Stilprofil (Paket B5): der eigene Ton aus gesendeten Mails, in der echten Oberfläche mit echtem Sidecar.

Aufbau: frischer Datenordner, Zeitzone Europe/Berlin, ein skriptbares lokales Modell (baut den Entwurf aus dem
Systemhinweis mit den Stilregeln, damit der Ton sichtbar wird; kein echtes Sprachmodell), eine IMAP-Attrappe mit fünf
synthetischen Mails im Posteingang und fünf eigenen in „Gesendet“: vier an Anna Berg allein (Du, kurz, „Hallo Anna“,
„Viele Grüße“) und eine an Anna und Jonas zusammen, die nicht zählen darf. Nur synthetische Daten.

Geprüft in Chromium:

* Nachrichten → Mail von Anna → Antwort schreiben → Schreibstil: die Zeile „Dein Ton an anna.berg@example.org: Du,
  Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch (aus 4 gesendeten Mails).“ mit „Übernehmen“ und
  „Nicht übernehmen“; „4 gesendete Mails ansehen“ öffnet die Belege (ohne die Mail an zwei Empfänger).
* Vor dem Übernehmen wirkt nichts: Der Entwurf des Skriptmodells kommt per Sie; daneben der Hinweis „Ton aus 4
  gesendeten Mails vorgeschlagen, noch nicht übernommen.“ mit „Schreibstil ansehen“.
* „Übernehmen“ antwortet („Übernommen. …“); der nächste Entwurf trägt „Hallo Anna“, Du und „Viele Grüße“; der Hinweis
  ist weg.
* Einstellungen → Kingfisher und du → „Dein Ton je Kreis“: Anna ist bestätigte Kollegin; die Zeile „Dein Ton an
  Kollegen: … (aus 4 gesendeten Mails)“ mit „Übernehmen“; danach „Kollegen: Bestätigt: …“.
* 1280 und 390 px ohne seitliches Scrollen; die Konsole bleibt ohne Fehler.

Aufruf: `python scripts/probe_stilprofil_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `stilprofil-probe.json` liegen danach in DIR.
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

from probe_fremdprobe3_ui import UMGEBUNG  # noqa: E402
from probe_satzantwort_ui import CHROMIUM, freier_port  # noqa: E402

ICH = 'lena.probe@example.org'
ANNA = 'anna.berg@example.org'
TON = ('Dein Ton an anna.berg@example.org: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch '
       '(aus 4 gesendeten Mails).')
HINWEIS = 'Ton aus 4 gesendeten Mails vorgeschlagen, noch nicht übernommen.'
KREIS_TON = 'Dein Ton an Kollegen: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch (aus 4 gesendeten Mails).'


class Skriptmodell:
    """Lokales Skriptmodell: Der Entwurf folgt den Stilregeln aus dem Systemhinweis, sonst förmlich. Kein Sprachmodell."""

    is_local = True
    name = 'lokal'
    model = 'lokal-probe'
    supports_json = True

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        from icarus_memory.providers import Reply
        regeln = {}
        for m in messages:
            if m['role'] == 'system' and 'Stilpräferenzen' in m['content']:
                regeln = json.loads(m['content'][m['content'].index('{'):])
        if not any('Antwortentwurf' in m['content'] for m in messages if m['role'] == 'system'):
            return Reply(text='{}', model=self.model)  # andere Hintergrundaufgaben: nichts gefunden
        du = regeln.get('address') == 'du'
        anrede = 'Hallo Anna,' if regeln.get('anrede_form') == 'vorname' else ('Hallo,' if du else 'Sehr geehrte Frau Berg,')
        satz = 'ja, das passt. Ich schicke dir das Angebot bis Freitag.' if du else 'das passt. Ich schicke Ihnen das Angebot bis Freitag.'
        gruss = regeln.get('gruss') or ('Viele Grüße' if du else 'Mit freundlichen Grüßen')
        return Reply(text=json.dumps({'body': f'{anrede}\n\n{satz}\n\n{gruss}\nLena'}, ensure_ascii=False), model=self.model)

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
                  provider=Skriptmodell(), knowledge=claims, episodes=episodes, max_rounds=1)
    return create_app(agent._store, agent=agent, audit=audit, proposals=proposals, episodes=episodes, knowledge=claims)


def gesendete_mails(probe_mail) -> list[bytes]:
    von = f'Lena Probe <{ICH}>'
    an = f'Anna Berg <{ANNA}>'
    return [
        probe_mail(von, 'Re: Vereinsfest', 'Hallo Anna,\n\nkannst du mir die Gästeliste schicken?\n\nViele Grüße\nLena', an=an, minuten=40),
        probe_mail(von, 'Re: Vereinsfest', 'Hallo Anna,\n\ndanke dir, das passt gut.\n\nViele Grüße\nLena', an=an, minuten=41),
        probe_mail(von, 'Getränke', 'Hallo Anna,\n\nich bringe dir die Liste morgen mit.\n\nViele Grüße\nLena', an=an, minuten=42),
        probe_mail(von, 'Re: Angebot', 'Hallo Anna,\n\nich schaue heute Abend drauf und melde mich bei dir.\n\nViele Grüße\nLena'
                   '\n\nAm 01.10.2026 um 09:10 schrieb Anna Berg:\n> Liebe Lena,\n> könnten Sie mir das Angebot schicken?', an=an, minuten=43),
        probe_mail(von, 'Treffen', 'Hallo ihr beiden,\n\npasst euch Montag?\n\nViele Grüße\nLena',
                   an=f'{an}, Jonas Keller <jonas.keller@example.org>', minuten=44),
    ]


def main() -> int:  # noqa: PLR0915 - eine Probe, Schritt für Schritt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    from tests.imap_attrappe import PASSWORT, ImapAttrappe, probe_mail, probe_postfach
    attrappe = ImapAttrappe(nachrichten=probe_postfach(), gesendet=gesendete_mails(probe_mail), uidvalidity=7)
    daten = Path(tempfile.mkdtemp(prefix='stilprofil-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten), SSL_CERT_FILE=str(attrappe.zertifikat))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import local_model_guard
    from icarus_memory.local_model_guard import LocalModelIdentity
    from icarus_memory.mail_intake import Intake
    local_model_guard.verify_local_model = lambda provider, **_: LocalModelIdentity(provider.model, 'a' * 64)

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
        app.state.scheduler.stop()
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
            pfad = args.ausgabe / f'stilprofil-{name}.png'
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

        # -- Postfach mit Posteingang und Gesendet, eingelesen; Anna als Kollegin bestätigt ------------------------------
        antwort = api.post(basis + '/api/v1/integrations/mail', data={
            'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': attrappe.port, 'user': ICH,
            'sender': ICH, 'password': PASSWORT})
        assert antwort.status == 201, antwort.text()
        konto = api.get(basis + '/api/v1/integrations').json()['mail_accounts'][0]['id']
        # Der Neubau beim Verbinden des Postfachs nimmt den Anbieter aus der Umgebung; hier wieder das Skriptmodell.
        app.state.agent._provider = Skriptmodell()
        Intake(app.state.episodes).start(konto, ['INBOX', 'Gesendet'])
        app.state.settings.schedule.mail_accounts.append(konto)
        app.state.settings.schedule.enabled = True
        takte(4)
        gesendet = app.state.episodes.gesendete_an(konto, ANNA)
        pruef['gesendete_an_anna'] = [e.title for e in gesendet]
        assert len(gesendet) == 4, pruef['gesendete_an_anna']
        kreis = api.put(basis + '/api/v1/kreis', data={'sache': f'person:a:{ANNA}', 'kreis': 'kollegen'})
        assert kreis.status == 200, kreis.text()

        # -- Nachrichten → Mail von Anna → Antwort schreiben → Schreibstil -----------------------------------------------
        seite.goto(basis + '/nachrichten')
        seite.get_by_role('button', name='Neue Mails abrufen').click()
        zeile = seite.locator('.mail-fresh-results button.mail-list-item').filter(has_text='Angebot Vereinsfest').first
        zeile.wait_for(timeout=20000)
        zeile.click()
        leser = seite.locator('article.mail-reader')
        leser.locator('h1').wait_for(timeout=20000)
        leser.locator('details.mail-action-panel > summary').filter(has_text='Antwort schreiben').click()
        leser.locator('details.quiet-details > summary').filter(has_text='Schreibstil').first.click()
        stil = leser.locator('details.mail-style')
        stil.locator('> summary').click()
        stil.get_by_text(TON).wait_for(timeout=20000)
        pruef['ton_zeile'] = stil.locator('.mail-style-ton-satz').inner_text()
        assert pruef['ton_zeile'] == TON, pruef['ton_zeile']
        assert stil.get_by_role('button', name='Übernehmen', exact=True).count() == 1
        assert stil.get_by_role('button', name='Nicht übernehmen').count() == 1
        bild('1-vorschlag')
        stil.scroll_into_view_if_needed()
        breite_pruefen('1-vorschlag')

        belege = stil.locator('details.mail-style-belege')
        assert belege.locator('> summary').inner_text() == '4 gesendete Mails ansehen'
        belege.locator('> summary').click()
        seite.wait_for_timeout(300)
        pruef['belege'] = [a.inner_text() for a in belege.locator('article').all()]
        assert len(pruef['belege']) == 4 and all('Viele Grüße' in b for b in pruef['belege'])
        assert not any('Hallo ihr beiden' in b for b in pruef['belege']), 'die Mail an zwei Empfänger ist kein Beleg'
        assert not any('könnten Sie mir' in b for b in pruef['belege']), 'zitierter Verlauf abgeschnitten'
        belege.scroll_into_view_if_needed()
        bild('2-belege')

        # -- Vor dem Übernehmen wirkt nichts: Entwurf per Sie, Hinweis mit Weg ------------------------------------------
        vorschlag = leser.locator('section.mail-reply-suggestion')
        vorschlag.get_by_role('button', name='Antwort vorschlagen').click()
        vorschlag.locator('textarea').wait_for(timeout=20000)
        pruef['entwurf_vorher'] = vorschlag.locator('textarea').input_value()
        assert 'Sehr geehrte Frau Berg' in pruef['entwurf_vorher'], pruef['entwurf_vorher']
        hinweis = vorschlag.locator('.mail-reply-suggestion-stil')
        pruef['hinweis'] = hinweis.inner_text()
        assert HINWEIS in pruef['hinweis'], pruef['hinweis']
        vorschlag.scroll_into_view_if_needed()
        bild('3-hinweis')
        hinweis.get_by_role('button', name='Schreibstil ansehen').click()
        seite.wait_for_timeout(300)
        assert stil.evaluate('el => el.open'), 'der Weg führt zum aufgeklappten Schreibstil'

        # -- Übernehmen: Antwort in einem Satz, nächster Entwurf mit Ton, Hinweis weg -----------------------------------
        stil.get_by_role('button', name='Übernehmen', exact=True).click()
        status = stil.get_by_role('status').filter(has_text='Übernommen')
        status.wait_for(timeout=20000)
        pruef['uebernommen'] = status.inner_text()
        stil.get_by_text('Bestätigte Regeln für anna.berg@example.org').wait_for(timeout=20000)
        assert stil.locator('.mail-style-ton-satz').count() == 0, 'nach dem Übernehmen kein Vorschlag mehr'
        pruef['regel_anrede'] = stil.locator('select').nth(1).input_value()
        assert pruef['regel_anrede'] == 'du'
        bild('4-uebernommen')
        vorschlag.get_by_role('button', name='Antwort vorschlagen').click()
        seite.wait_for_timeout(300)
        vorschlag.locator('textarea').wait_for(timeout=20000)
        for _ in range(50):
            pruef['entwurf_nachher'] = vorschlag.locator('textarea').input_value()
            if 'Hallo Anna' in pruef['entwurf_nachher']:
                break
            seite.wait_for_timeout(200)
        assert pruef['entwurf_nachher'].startswith('Hallo Anna,') and 'dir' in pruef['entwurf_nachher'] \
            and 'Viele Grüße' in pruef['entwurf_nachher'], pruef['entwurf_nachher']
        assert vorschlag.locator('.mail-reply-suggestion-stil').count() == 0, 'bestätigt: kein Hinweis mehr'
        vorschlag.scroll_into_view_if_needed()
        bild('5-entwurf-mit-ton')

        # -- Einstellungen → Kingfisher und du → Dein Ton je Kreis -----------------------------------------------------
        seite.goto(basis + '/settings#ich')
        karte = seite.locator('.stil-kreise')
        karte.wait_for(timeout=20000)
        karte.get_by_text(KREIS_TON).wait_for(timeout=20000)
        pruef['kreis_vorher'] = karte.inner_text()
        assert 'Innerer Kreis: Noch niemand bestätigt zugeordnet' in pruef['kreis_vorher'], pruef['kreis_vorher']
        karte.scroll_into_view_if_needed()
        bild('6-kreis-vorschlag')
        breite_pruefen('6-kreis-vorschlag')
        karte.get_by_role('button', name='Übernehmen', exact=True).click()
        karte.get_by_role('status').filter(has_text='Übernommen').wait_for(timeout=20000)
        karte.get_by_text('Kollegen: Bestätigt: Du, Anrede mit Vornamen, kurz, ohne Emoji, Gruß „Viele Grüße“, auf Deutsch.').wait_for(timeout=20000)
        pruef['kreis_nachher'] = karte.inner_text()
        assert karte.get_by_role('button', name='Regel zurücknehmen').count() == 1
        bild('7-kreis-bestaetigt')

        # Im Selbstmodell: zwei bestätigte Regeln (Kontakt, Kreis), nichts weiter.
        regeln = [a.structured for a in app.state.store.usable() if (a.structured or {}).get('domain') == 'mail_style']
        pruef['regeln'] = sorted(r['scope_key'] if r['scope_key'].startswith('kreis:') else 'kontakt' for r in regeln)
        assert pruef['regeln'] == ['kontakt', 'kreis:kollegen'], pruef['regeln']

        ergebnis['ok'] = not ergebnis['konsole']
        browser.close()
    attrappe.schliessen()
    (args.ausgabe / 'stilprofil-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']},
                     ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
