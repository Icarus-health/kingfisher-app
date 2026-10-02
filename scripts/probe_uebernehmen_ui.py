#!/usr/bin/env python3
"""Browserprobe für „In die Akte übernehmen“: echte Oberfläche, echter Server, ein skriptbares Modell.

Startet den Sidecar mit der synthetischen Welt der Messlatte und dem Skriptmodell der Satzantwort-Probe,
stellt eine Frage über die Konversations-API und öffnet das Gespräch in Chromium (Playwright):

* unter der Antwort stehen still „Stimmt nicht?“ und „In die Akte übernehmen“ in einer Zeile (nicht unter der Frage),
* der Klick öffnet die Rückfrage: die Sätze als Auswahl (Vorgabe: die ohne Hinweis; der Satz mit der überholten
  Quelle trägt den Hinweis und ist nicht vorgewählt), die Akte, eine Notiz,
* „Vorschlagen“ zeigt „Vorgeschlagen.“ und die Vorschlagskarte; bis dahin ist **nichts** Wissen (kein Claim),
* nach dem Neuladen findet die Rückfrage den Vorschlag wieder,
* „Bestätigen“ legt die Aussage an („In der Akte von …“), die Akte zeigt sie im Abschnitt „Angenommen“ mit Beleg,
* „Nicht speichern“ lässt nichts zurück,
* die Konsole bleibt leer.

Aufruf: `python scripts/probe_uebernehmen_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
Screenshots und `uebernehmen-probe.json` liegen danach in DIR; sie enthalten nur synthetische Texte.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL, WURZEL / 'scripts'):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from probe_satzantwort_ui import CHROMIUM, FRAGEN, Skript, freier_port  # noqa: E402

SATZ_SAUBER = 'Die neue Einreichfrist endet am 12. November 2026 um 12 Uhr.'
SATZ_WANDEL = 'Die Einreichfrist wurde von 15. Oktober 2026 auf 12. November 2026 verlängert.'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from messlatte import aufnahme
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=Skript(),
                         eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufnehmen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufnehmen.fehlgeschlagen == 0, aufnehmen
        from icarus_memory.akten_routes import nachfuehren
        nachfuehren(instanz.app, warten=True)
        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(instanz.app, host='127.0.0.1', port=port, log_level='warning'))
        faden = threading.Thread(target=server.run, daemon=True)
        faden.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        app = instanz.app

        def zustand():
            return {'claims': len(app.state.claims.all_claims()), 'offen': app.state.proposals.counts().get('pending', 0)}

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            seite = browser.new_context(viewport={'width': 1100, 'height': 900}).new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            seite.goto(basis + '/today')  # setzt die Sitzung für /api

            def bild(name):
                pfad = args.ausgabe / f'uebernehmen-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            def frage_stellen():
                kennung = seite.request.post(basis + '/api/v1/conversations', data={}).json()['conversation']['id']
                antwort = seite.request.post(f'{basis}/api/v1/conversations/{kennung}/messages',
                                             data={'message': FRAGEN['wandel'], 'answer_mode': 'auto'})
                assert antwort.status == 201, antwort.text()
                return kennung

            assert zustand() == {'claims': 0, 'offen': 0}
            kennung = frage_stellen()

            # 1. still, in einer Zeile mit „Stimmt nicht?“, nur unter der Antwort
            seite.goto(f'{basis}/conversations/{kennung}')
            seite.wait_for_selector('.satzantwort', timeout=15000)
            link = seite.get_by_role('button', name='In die Akte übernehmen')
            assert link.count() == 1 and seite.get_by_role('button', name='Stimmt nicht?').count() == 1
            assert seite.locator('article.message.user button:has-text("In die Akte übernehmen")').count() == 0
            zeile = seite.locator('.antwort-rueckkanal')
            assert zeile.count() == 1 and zeile.get_by_role('button').count() == 2, 'beide Links in einer Zeile'
            pruef['zeile'] = zeile.inner_text()
            bild('1-still')

            # 2. Rückfrage: Vorgabe, Hinweis, Akte
            link.click()
            form = seite.get_by_role('form', name='In die Akte übernehmen')
            form.wait_for(timeout=5000)
            seite.get_by_label(SATZ_SAUBER).wait_for(timeout=5000)
            sauber, wandel = seite.get_by_label(SATZ_SAUBER), seite.get_by_label(SATZ_WANDEL)
            assert sauber.is_checked() and not wandel.is_checked(), 'Vorgabe: der Satz ohne Hinweis'
            text = form.inner_text()
            pruef['rueckfrage'] = text
            assert 'überholt' in text and 'Welche Sätze sollen in die Akte' in text, text
            assert form.get_by_role('button', name='Vorschlagen').is_enabled()
            form.get_by_label('Notiz', exact=False).fill('Für die Planung im November')
            bild('2-rueckfrage')
            # Ohne Auswahl kein Vorschlag.
            sauber.uncheck()
            assert form.get_by_role('button', name='Vorschlagen').is_disabled()
            sauber.check()

            # 3. Vorschlagen: „Vorgeschlagen.“, Karte, und noch kein Wissen
            form.get_by_role('button', name='Vorschlagen').click()
            seite.get_by_text('Vorgeschlagen.', exact=True).wait_for(timeout=5000)
            karte = seite.get_by_role('region', name='Gedächtnisvorschlag')
            karte.wait_for(timeout=5000)
            assert karte.count() == 1 and SATZ_SAUBER in karte.inner_text() and 'Beleg:' in karte.inner_text()
            pruef['karte'] = karte.inner_text()
            assert zustand() == {'claims': 0, 'offen': 1}, zustand()
            bild('3-vorgeschlagen')

            # 4. Neuladen: die Rückfrage findet den Vorschlag wieder, die Sätze bleiben, nichts wird doppelt
            seite.reload()
            seite.wait_for_selector('.satzantwort', timeout=15000)
            seite.get_by_role('button', name='In die Akte übernehmen').click()
            seite.get_by_text('Schon vorgeschlagen:').wait_for(timeout=5000)
            assert seite.get_by_role('region', name='Gedächtnisvorschlag').count() == 1
            assert 'Liegt schon zur Entscheidung vor.' in seite.get_by_role('form', name='In die Akte übernehmen').inner_text()
            assert not seite.get_by_label(SATZ_SAUBER).is_checked(), 'ein Satz mit Vorschlag ist nicht vorgewählt'
            bild('4-neu-geladen')

            # 5. Noch ein Satz, der Hinweis trägt: nur mit Hinweis vorgeschlagen, und „Nicht speichern“ lässt nichts zurück
            form = seite.get_by_role('form', name='In die Akte übernehmen')
            seite.get_by_label(SATZ_WANDEL).check()
            form.get_by_role('button', name='Vorschlagen').click()
            zweite = seite.get_by_role('region', name='Gedächtnisvorschlag').filter(has_text=SATZ_WANDEL)
            zweite.wait_for(timeout=5000)
            assert 'überholt' in zweite.inner_text(), zweite.inner_text()
            assert seite.get_by_role('region', name='Gedächtnisvorschlag').count() == 2, 'der erste bleibt sichtbar'
            assert zustand() == {'claims': 0, 'offen': 2}, zustand()
            zweite.get_by_role('button', name='Nicht speichern').click()
            zweite.get_by_text('Nicht gespeichert.').wait_for(timeout=5000)
            assert zustand() == {'claims': 0, 'offen': 1}, zustand()
            bild('5-abgelehnt')

            # 6. Bestätigen: die Aussage steht in der Akte
            erste = seite.get_by_role('region', name='Gedächtnisvorschlag').filter(has_text=SATZ_SAUBER)
            erste.get_by_role('button', name='Bestätigen').click()
            erste.get_by_text('In der Akte von', exact=False).wait_for(timeout=5000)
            assert zustand() == {'claims': 1, 'offen': 0}, zustand()
            sache = app.state.claims.all_claims()[0].subject_ref
            pruef['sache'] = sache
            bild('6-angenommen')
            erste.get_by_role('button', name='Akte öffnen').click()
            seite.get_by_role('heading', name='Angenommen').wait_for(timeout=10000)
            teil = seite.locator('.akte-angenommen')
            akte_text = teil.inner_text()
            pruef['akte'] = akte_text
            assert SATZ_SAUBER in akte_text and 'Angenommen am' in akte_text and 'Quelle' in akte_text, akte_text
            assert SATZ_WANDEL not in akte_text and teil.locator('blockquote').count() >= 1
            bild('7-akte')

            # 7. Die alte Antwort gilt nach der Annahme als veraltet (Quelle ist jetzt Wissen): nichts bricht.
            seite.goto(f'{basis}/conversations/{kennung}')
            seite.wait_for_selector('article.message.assistant', timeout=10000)
            pruef['veraltet'] = seite.locator('.messages').inner_text()
            bild('8-veraltet')
            seite.get_by_text('Mit aktuellem Stand neu beantworten').wait_for(timeout=10000)
            assert seite.get_by_role('button', name='In die Akte übernehmen').count() == 0
            bild('8-veraltet')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'uebernehmen-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']}, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
