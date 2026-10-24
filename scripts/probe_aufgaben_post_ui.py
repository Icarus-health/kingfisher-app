#!/usr/bin/env python3
"""Browserprobe „Aufgaben folgen der Post“ (Paket B6): in der echten Oberfläche mit echtem Sidecar.

Aufbau: frischer Datenordner, Zeitzone Europe/Berlin, ein skriptbares lokales Modell, eine eigene Adresse in den
Einstellungen. Die Mails liegen als Quellen im Gedächtnis (wie nach der Aufnahme: Beteiligte mit Rolle, genaue
Kopfzeilenbezüge), die Aufgaben in der Aufgabenablage. Nur synthetische Daten (Lena Probe, Anna Berg).

Geprüft in Chromium:

* Aufgaben → Erledigt: die Zeile „Erledigt, weil du Anna Berg am … „Druckdaten“ geschickt hast.“ mit „Rückgängig“;
  der Klick stellt die Aufgabe wieder her (steht wieder unter „Meine Aufgaben“, ohne Zeile).
* Aufgaben → Meine Aufgaben: der Vorschlag „Erledigt? „…““ unter „Aus deiner Post“; „Ja, erledigt“ legt die Aufgabe
  mit Grund ab, die Antwort nennt „Rückgängig“.
* Die Akte von Anna Berg zeigt die Änderung unter „Braucht dich“ mit „Rückgängig“; Heute nennt sie einmal („Post“).
* 1280 und 390 px ohne seitliches Scrollen; die Konsole bleibt ohne Fehler.

Aufruf: `python scripts/probe_aufgaben_post_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npm run build` in
`app/kingfisher`. Bilder und `aufgaben-post-probe.json` liegen danach in DIR.
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

ICH = 'lena.probe@example.org'
LENA = f'Lena Probe <{ICH}>'
ANNA = 'Anna Berg <anna.berg@example.org>'
BITTE = 'Könnten Sie mir die Druckdaten für den Flyer bis Freitag schicken?'


def main() -> int:  # noqa: PLR0915 - eine Probe, Schritt für Schritt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    daten = Path(tempfile.mkdtemp(prefix='aufgaben-post-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import EpisodeKind, Provenance, SourceType, aufgaben_post
    from icarus_memory.akten_routes import nachfuehren
    from icarus_memory.config import MailAccountSettings
    from icarus_memory.kontakte import fuer_mail

    app = sidecar(daten)
    app.state.settings.einrichtung = {'name': 'Lena', 'schritte': {}, 'abgeschlossen': True}
    app.state.settings.mail_accounts.append(MailAccountSettings(id='probe', label='Probe-Post', imap_host='127.0.0.1', user=ICH, sender=ICH))
    episodes, tasks = app.state.episodes, app.state.tasks
    jetzt = datetime.now(timezone.utc)

    def mail(titel, text, *, von, an, stunden, kennung, antwort_auf=()):
        empfaenger = [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'an'} for a in an]
        tags = [f'mail:message:{kennung}'] + [f'mail:reply:{k}' for k in antwort_auf]
        episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f'probe:{kennung}'),
                                     participants=[von, *an], contacts=fuer_mail(von, empfaenger, eigene=[ICH]), tags=tags,
                                     occurred_at=jetzt - timedelta(hours=stunden))
        return episode

    aufgaben_post.schritt_fuer(app)  # der Bestand von vor dem Umbau wird nicht neu gedeutet
    bitte = mail('Druckdaten für den Flyer', BITTE, von=ANNA, an=[LENA], stunden=30, kennung='a1')
    task = tasks.add('Druckdaten an Anna schicken', Provenance(SourceType.USER_STATED, source_ref=f'episode:{bitte.id}'),
                     at=jetzt - timedelta(hours=29))
    mail('AW: Druckdaten für den Flyer', 'Hallo Anna, anbei die Druckdaten. Viele Grüße, Lena', von=LENA, an=[ANNA], stunden=2,
         kennung='l1', antwort_auf=['a1'])
    bericht = aufgaben_post.schritt_fuer(app)
    assert bericht['erledigt'] == 1, bericht
    nachfuehren(app, warten=True)

    port = freier_port()
    uv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=uv.run, daemon=True).start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.1)
    if getattr(app.state, 'scheduler', None) is not None:
        app.state.scheduler.stop()  # im Takt der Probe, kein Durchgang dazwischen
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        kontext = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='de-DE', timezone_id='Europe/Berlin')
        seite = kontext.new_page()
        seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

        def bild(name, ganz=False):
            pfad = args.ausgabe / f'aufgaben-post-{name}.png'
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

        # -- Erledigt, mit Grund und Rückgängig -------------------------------------------------------------------------
        seite.goto(basis + '/vorhaben?view=done')
        zeile = seite.locator('.task-row small.task-post')
        zeile.first.wait_for(timeout=20000)
        pruef['erledigt_zeile'] = zeile.first.inner_text()
        assert pruef['erledigt_zeile'].startswith('Erledigt, weil du Anna Berg am ') and '„Druckdaten“ geschickt hast.' in pruef['erledigt_zeile'], pruef['erledigt_zeile']
        assert zeile.first.get_by_role('button', name='Rückgängig').count() == 1
        bild('1-erledigt')
        breite_pruefen('1-erledigt')
        zeile.first.get_by_role('button', name='Rückgängig').click()
        seite.wait_for_timeout(800)
        assert tasks.get(task.id).status.value == 'open' and tasks.get(task.id).erledigt_grund is None
        seite.goto(basis + '/vorhaben?view=mine')
        seite.get_by_role('button', name='Druckdaten an Anna schicken', exact=True).wait_for(timeout=20000)
        assert seite.locator('.task-row small.task-post').count() == 0, 'nach Rückgängig keine Zeile mehr'
        pruef['nach_rueckgaengig'] = 'offen, ohne Zeile'
        bild('2-rueckgaengig')

        # -- Vorschlag „Erledigt?“ mit einem Klick ----------------------------------------------------------------------------
        mail('AW: Flyer', 'Hallo Anna, danke für die Nachricht, ich melde mich dazu.', von=LENA, an=[ANNA], stunden=1,
             kennung='l2', antwort_auf=['a1'])
        bericht = aufgaben_post.schritt_fuer(app)
        assert bericht['vorschlaege'] == 1, bericht
        seite.goto(basis + '/vorhaben?view=mine')
        karte = seite.locator('section.aufgaben-post')
        karte.wait_for(timeout=20000)
        pruef['vorschlag'] = karte.inner_text()
        assert 'Erledigt? „Druckdaten an Anna schicken“' in pruef['vorschlag'], pruef['vorschlag']
        assert 'Ist die Aufgabe damit erledigt?' in pruef['vorschlag']
        bild('3-vorschlag')
        breite_pruefen('3-vorschlag')
        karte.get_by_role('button', name='Ja, erledigt').click()
        status = karte.get_by_role('status')
        status.wait_for(timeout=20000)
        pruef['angenommen'] = status.inner_text()
        assert 'Rückgängig' in pruef['angenommen'], pruef['angenommen']
        assert tasks.get(task.id).status.value == 'done'
        assert tasks.get(task.id).erledigt_grund['satz'].endswith('geantwortet hast.')
        bild('4-angenommen')

        # -- Die Akte: Braucht dich, mit Rückgängig; Heute: einmal „Post“ ----------------------------------------------------------
        seite.goto(basis + '/memory/akte/' + 'person:a:anna.berg@example.org')
        braucht = seite.locator('section.akte-braucht')
        braucht.wait_for(timeout=30000)
        pruef['akte'] = braucht.inner_text()
        assert 'Erledigt, weil du Anna Berg' in pruef['akte'] and 'Rückgängig' in pruef['akte'], pruef['akte']
        bild('5-akte')
        breite_pruefen('5-akte')

        seite.goto(basis + '/today')
        zeile = seite.locator('.today-activity-zeile')
        zeile.wait_for(timeout=30000)
        zeile.click()  # „Tageslage & Verlauf“ ist eine Zeile, die sich öffnet (P1)
        post = seite.locator('.tageslage-zeile.tageslage-aufgaben_post')
        post.wait_for(timeout=30000)
        pruef['heute'] = post.inner_text()
        assert post.count() == 1 and 'Erledigt durch deine Mail an Anna Berg' in pruef['heute'], pruef['heute']
        bild('6-heute')

        ergebnis['ok'] = not ergebnis['konsole']
        browser.close()
    (args.ausgabe / 'aufgaben-post-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']},
                     ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
