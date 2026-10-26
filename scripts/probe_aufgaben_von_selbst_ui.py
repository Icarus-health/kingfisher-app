#!/usr/bin/env python3
"""Browserprobe „Aufgaben von selbst“ (Paket A, 26.10.2026): in der echten Oberfläche mit echtem Sidecar.

Aufbau: frischer Datenordner, Zeitzone Europe/Berlin, eine eigene Adresse in den Einstellungen, ein Projekt „Flyer
Herbstfest“ mit zwei früheren Mails von Anna (die Absenderregel greift). Neue Post: eine Bitte von Anna an Lena allein,
eine eigene Zusage an Jonas; dazu unsichere: eine Bitte, in der Lena nur in Kopie steht, eine Rundmail an fünf, eine
Bitte aus dem Altbestand (40 Tage alt). Die Vorschläge liegen so da, wie die Aufgabenerkennung sie ablegt (geprüft,
Kontextbindung). Nur synthetische Daten (Lena Probe, Anna Berg, Jonas Keller).

Geprüft in Chromium:

* Der Durchlauf legt genau die zwei eindeutigen an; der Altbestand, die Kopie und die Rundmail bleiben Vorschläge.
* Heute: eine Zeile „2 Aufgaben aus der Post angelegt. Ansehen · Rückgängig“ (nicht jede einzeln).
* Aufgaben: „Von Kingfisher angelegt · aus der Mail von Anna Berg vom …“ mit Person und Projekt; „Rückgängig“ nimmt die
  Aufgabe zurück, der Hinweis holt sie wieder; nach dem Zurücknehmen legt ein neuer Durchlauf sie nicht wieder an.
* Zur Prüfung: Person und Frist vorbefüllt, „Alle 3 übernehmen“ in einem Klick, „Rückgängig“ für die ganze Gruppe.
* Einstellungen → Was Kingfisher darf: „Aufgaben aus Mails selbst anlegen“ ist an, aus- und wieder einschaltbar.
* 1280 und 390 px ohne seitliches Scrollen, hell und dunkel; die Konsole bleibt ohne Fehler.

Aufruf: `python scripts/probe_aufgaben_von_selbst_ui.py --ausgabe DIR [--chromium PFAD]`; vorher `npx vite build` in
`app/kingfisher`. Bilder (jpg) und `aufgaben-von-selbst-probe.json` liegen danach in DIR.
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
JONAS = 'Jonas Keller <jonas.keller@example.org>'
BITTE = 'Kannst du mir bitte die Druckdaten für den Flyer schicken?'
ZUSAGE = 'Ich schicke dir das Angebot bis Freitag.'


def main() -> int:  # noqa: PLR0915 - eine Probe, Schritt für Schritt
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    daten = Path(tempfile.mkdtemp(prefix='aufgaben-von-selbst-'))
    os.environ.update(UMGEBUNG, ICARUS_DATA_DIR=str(daten))
    for name in ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import EpisodeKind, Provenance, SourceType, aufgaben_von_selbst
    from icarus_memory.config import MailAccountSettings
    from icarus_memory.kontakte import fuer_mail
    from icarus_memory.proposals import ProposalKind
    from icarus_memory.task_review import current_task_context

    app = sidecar(daten)
    app.state.settings.einrichtung = {'name': 'Lena', 'schritte': {}, 'abgeschlossen': True}
    app.state.settings.mail_accounts.append(MailAccountSettings(id='probe', label='Probe-Post', imap_host='127.0.0.1', user=ICH, sender=ICH))
    episodes, tasks, proposals, workspace = app.state.episodes, app.state.tasks, app.state.proposals, app.state.workspace
    jetzt = datetime.now(timezone.utc)
    zaehler = [0]

    def mail(titel, text, *, von, an=(), cc=(), stunden=2):
        zaehler[0] += 1
        empfaenger = [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'an'} for a in an]
        empfaenger += [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'cc'} for a in cc]
        # Wie die Aufnahme: mit der eigenen Kennung der Mail (Kopfzeile), damit der Verlauf prüfbar ist.
        episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f'probe:{zaehler[0]}'),
                                     participants=[von, *an, *cc], contacts=fuer_mail(von, empfaenger, eigene=[ICH]),
                                     tags=[f'mail:message:m{zaehler[0]}'], occurred_at=jetzt - timedelta(hours=stunden))
        return episode

    def vorschlag(episode, titel, zitat):
        with proposals.transaction():
            proposals._record_task_candidates(episode.id, episode.digest, [{'title': titel, 'quote': zitat}],  # noqa: SLF001
                                              proposed_by='probe/local/task-review-v1',
                                              task_context=current_task_context(episodes, episode.id))

    projekt = workspace.add_project('Flyer Herbstfest', Provenance(SourceType.USER_STATED))
    for i in range(2):
        frueher = mail(f'Flyer, Entwurf {i + 1}', f'Hier der Entwurf {i + 1} für den Flyer.', von=ANNA, an=[LENA], stunden=24 * (20 + i))
        episodes.link_project(frueher.id, projekt.id)
    bitte = mail('Druckdaten', f'Hallo Lena,\n\n{BITTE}\n\nAnna', von=ANNA, an=[LENA], stunden=3)
    vorschlag(bitte, 'Druckdaten an Anna schicken', BITTE)
    zusage = mail('Angebot', f'Hallo Jonas,\n\n{ZUSAGE}\n\nLena', von=LENA, an=[JONAS], stunden=2)
    vorschlag(zusage, 'Angebot an Jonas schicken', ZUSAGE)
    kopie_text = 'Lena, kannst du bitte die Rechnung 4711 bis Freitag prüfen?'
    kopie = mail('Rechnung 4711', kopie_text, von=ANNA, an=[JONAS], cc=[LENA], stunden=4)
    vorschlag(kopie, 'Rechnung 4711 prüfen', kopie_text)
    rund_text = 'Bitte tragt euch bis Mittwoch in die Liste für das Sommerfest ein.'
    rund = mail('Sommerfest', rund_text, von=JONAS, an=[LENA, ANNA, 'Mia Sommer <mia@example.org>', 'Ole Wind <ole@example.org>', 'Tom Hall <tom@example.org>'], stunden=5)
    vorschlag(rund, 'In die Liste für das Sommerfest eintragen', rund_text)
    alt_text = 'Kannst du mir die Fotos vom Frühjahr schicken?'
    alt = mail('Fotos', alt_text, von=ANNA, an=[LENA], stunden=24 * 40)
    vorschlag(alt, 'Fotos vom Frühjahr an Anna schicken', alt_text)

    bericht = aufgaben_von_selbst.schritt_fuer(app)
    assert bericht == {'geprueft': 5, 'angelegt': 2, 'vorschlaege': 3}, bericht
    angelegt = {t.title: t for t in tasks.open_tasks()}
    assert set(angelegt) == {'Druckdaten an Anna schicken', 'Angebot an Jonas schicken'}, set(angelegt)
    assert angelegt['Druckdaten an Anna schicken'].project_id == projekt.id

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
    ergebnis: dict = {'ok': False, 'pruefungen': {'durchlauf': bericht}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])

        def kontext_fuer(schema):
            k = browser.new_context(viewport={'width': 1280, 'height': 900}, locale='de-DE', timezone_id='Europe/Berlin',
                                    color_scheme=schema)
            s = k.new_page()
            s.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            s.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            return s

        seite = kontext_fuer('light')

        def bild(name, s=None):
            pfad = args.ausgabe / f'aufgaben-von-selbst-{name}.jpg'
            (s or seite).screenshot(path=str(pfad), type='jpeg', quality=78)
            ergebnis['bilder'].append(pfad.name)

        def breite_pruefen(name, s=None):
            s = s or seite
            s.set_viewport_size({'width': 390, 'height': 844})
            s.wait_for_timeout(500)
            masse = s.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            pruef[f'{name}_390'] = masse
            assert masse[0] <= masse[1], (name, masse)
            bild(f'{name}-390', s)
            s.set_viewport_size({'width': 1280, 'height': 900})
            s.wait_for_timeout(300)

        def hinweis():
            h = seite.locator('.g-hinweis')
            h.wait_for(timeout=15000)
            return h

        # -- Heute: eine Zeile ---------------------------------------------------------------------------------
        seite.goto(basis + '/today')
        zeile = seite.locator('.today-von-selbst')
        zeile.wait_for(timeout=30000)
        pruef['heute'] = zeile.inner_text()
        assert pruef['heute'].startswith('2 Aufgaben aus der Post angelegt.'), pruef['heute']
        assert zeile.get_by_role('link', name='Ansehen').count() == 1 and zeile.get_by_role('button', name='Rückgängig').count() == 1
        bild('1-heute')
        breite_pruefen('1-heute')

        # -- Aufgaben: Herkunft, Person, Projekt, Rückgängig und wieder da ------------------------------------------
        seite.goto(basis + '/vorhaben?view=mine')
        anlage = seite.locator('.task-row small.task-anlage')
        anlage.first.wait_for(timeout=20000)
        texte = anlage.all_inner_texts()
        pruef['zeilen'] = texte
        assert any(t.startswith('Von Kingfisher angelegt · aus der Mail von Anna Berg vom ') for t in texte), texte
        assert any(t.startswith('Von Kingfisher angelegt · aus deiner Mail an Jonas Keller vom ') for t in texte), texte
        zeile_anna = seite.locator('.task-row', has_text='Druckdaten an Anna schicken')
        pruef['zeile_anna'] = zeile_anna.inner_text()
        assert 'Anna Berg' in pruef['zeile_anna'] and 'Flyer Herbstfest' in pruef['zeile_anna'], pruef['zeile_anna']
        bild('2-aufgaben')
        breite_pruefen('2-aufgaben')
        druck_id = angelegt['Druckdaten an Anna schicken'].id
        zeile_anna.get_by_role('button', name='Rückgängig: Druckdaten an Anna schicken').click()
        h = hinweis()
        pruef['zurueck_hinweis'] = h.inner_text()
        assert 'Zurückgenommen. Kingfisher legt diese Aufgabe nicht wieder an.' in pruef['zurueck_hinweis'], pruef['zurueck_hinweis']
        seite.wait_for_timeout(600)
        assert tasks.get(druck_id) is None
        assert seite.locator('.task-row', has_text='Druckdaten an Anna schicken').count() == 0
        bild('3-zurueckgenommen')
        h.get_by_role('button', name='Rückgängig').click()
        seite.locator('.task-row', has_text='Druckdaten an Anna schicken').first.wait_for(timeout=15000)
        assert tasks.get(druck_id) is not None
        pruef['wiederhergestellt'] = True
        # Noch einmal zurücknehmen; ein neuer Vorschlag aus derselben Mail kommt nicht wieder.
        aufgaben_von_selbst.durchlauf_fuer(app).zuruecknehmen(druck_id)
        vorschlag(bitte, 'Druckdaten an Anna schicken', 'die Druckdaten für den Flyer')
        assert aufgaben_von_selbst.schritt_fuer(app)['angelegt'] == 0
        assert not [t for t in tasks.open_tasks() if t.title == 'Druckdaten an Anna schicken']
        assert not [v for v in proposals.pending(ProposalKind.TASK, limit=-1) if v.statement == 'Druckdaten an Anna schicken']
        pruef['kommt_nicht_wieder'] = True

        # -- Detail: dieselbe Zeile, Person führt zur Akte -----------------------------------------------------------
        angebot = angelegt['Angebot an Jonas schicken']
        seite.goto(basis + f'/vorhaben?view=mine&task={angebot.id}')
        detail = seite.locator('.task-detail small.task-anlage')
        detail.wait_for(timeout=20000)
        pruef['detail'] = detail.inner_text()
        assert seite.locator('.task-detail a.task-person', has_text='Jonas Keller').count() == 1
        bild('4-detail')

        # -- Zur Prüfung: vorbefüllt, Alle übernehmen, Rückgängig für die Gruppe -------------------------------------
        seite.goto(basis + '/vorhaben?view=mine&pruefen=1')
        alle = seite.locator('.task-vorschlaege-alle button')
        alle.wait_for(timeout=20000)
        pruef['alle_knopf'] = alle.inner_text()
        anzahl = seite.locator('.task-vorschlag').count()
        assert pruef['alle_knopf'] == f'Alle {anzahl} übernehmen', (pruef['alle_knopf'], anzahl)
        meta = seite.locator('.task-vorschlag', has_text='Rechnung 4711 prüfen').locator('.task-vorschlag-meta').inner_text()
        pruef['vorschlag_meta'] = meta
        assert 'Anna Berg' in meta and 'Frist' in meta and 'Projekt „Flyer Herbstfest“' in meta, meta
        bild('5-pruefen')
        breite_pruefen('5-pruefen')
        offen_vorher = len(proposals.pending(ProposalKind.TASK, limit=-1))
        alle.click()
        h = hinweis()
        pruef['alle_hinweis'] = h.inner_text()
        assert f'{anzahl} Aufgaben übernommen.' in pruef['alle_hinweis'], pruef['alle_hinweis']
        seite.wait_for_timeout(600)
        bild('6-alle-uebernommen')
        h.get_by_role('button', name='Rückgängig').click()
        seite.wait_for_function("() => (document.querySelector('.g-hinweis')?.innerText || '').includes('wieder zur Prüfung')", timeout=15000)
        pruef['gruppe_zurueck'] = seite.locator('.g-hinweis').inner_text()
        assert len(proposals.pending(ProposalKind.TASK, limit=-1)) == offen_vorher

        # -- Einstellungen: der Schalter -------------------------------------------------------------------------
        seite.goto(basis + '/settings#darf')
        schalter = seite.get_by_role('switch', name='Aufgaben aus Mails selbst anlegen')
        schalter.wait_for(timeout=20000)
        assert schalter.is_checked()
        bereich = seite.locator('section.darf-zeile[aria-label="Aufgaben aus Mails selbst anlegen"]')
        bereich.scroll_into_view_if_needed()
        bild('7-schalter')
        breite_pruefen('7-schalter')
        bereich.locator('label').click()
        bereich.get_by_role('status').wait_for(timeout=10000)
        pruef['schalter_aus'] = bereich.get_by_role('status').inner_text()
        assert tasks.auto_an() is False
        bereich.locator('label').click()
        seite.wait_for_function("() => document.querySelector('section.darf-zeile[aria-label=\"Aufgaben aus Mails selbst anlegen\"] input').checked", timeout=10000)
        assert tasks.auto_an() is True

        # -- Heute: alle zurück und wieder; dunkel -------------------------------------------------------------------
        seite.goto(basis + '/today')
        zeile = seite.locator('.today-von-selbst')
        zeile.wait_for(timeout=30000)
        pruef['heute_nachher'] = zeile.inner_text()
        zeile.get_by_role('button', name='Rückgängig').click()
        h = hinweis()
        pruef['heute_zurueck'] = h.inner_text()
        assert 'zurückgenommen' in pruef['heute_zurueck'], pruef['heute_zurueck']
        seite.wait_for_timeout(500)
        assert seite.locator('.today-von-selbst').count() == 0
        h.get_by_role('button', name='Rückgängig').click()
        seite.locator('.today-von-selbst').wait_for(timeout=15000)
        pruef['heute_wieder'] = seite.locator('.today-von-selbst').inner_text()

        dunkel = kontext_fuer('dark')
        dunkel.goto(basis + '/today')
        dunkel.locator('.today-von-selbst').wait_for(timeout=30000)
        bild('8-heute-dunkel', dunkel)
        dunkel.goto(basis + '/vorhaben?view=mine')
        dunkel.locator('.task-row small.task-anlage').first.wait_for(timeout=20000)
        bild('9-aufgaben-dunkel', dunkel)
        breite_pruefen('9-aufgaben-dunkel', dunkel)

        ergebnis['ok'] = not ergebnis['konsole']
        browser.close()
    (args.ausgabe / 'aufgaben-von-selbst-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']},
                     ensure_ascii=False, indent=2))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
