#!/usr/bin/env python3
"""Browserprobe für den Kreis je Person und die Art der Akte (M4): echte Oberfläche, echter Server.

Startet den Sidecar mit der synthetischen Welt der Messlatte (`messlatte/welt`, mit dem Szenario `privat`, Stichtag
der Welt, Regel-Einordnung), führt aus, was der Nutzer der Welt selbst getan hat, und öffnet die Oberfläche in
Chromium (Playwright). Geprüft wird:

* Einstellungen → Kingfisher und du: Statt „kommt später“ steht der echte Stand („Noch für niemanden bestätigt,
  … Vorschläge warten auf dich.“) mit den offenen Vorschlägen; ein Klick führt in die Akte der Person.
* Die Akte der Mutter zeigt die Karte „Kreis“: Vorschlag „Innerer Kreis“ mit Begründung in einem Satz, drei Knöpfe.
  Vor dem Klick ist nichts gespeichert; nach dem Klick steht, was gespeichert ist und was es bewirkt. Eine andere
  Wahl gilt sofort, „Wieder offen lassen“ nimmt sie zurück. Nach dem Neuladen bleibt die Wahl.
* Der Stand unter „Kingfisher und du“ zählt danach eine bestätigte Person und einen Vorschlag weniger.
* Die Akte der Zahnarztpraxis zeigt „Art der Akte“ mit dem Vorschlag „Gesundheit“; ein Klick bestätigt. Eine
  berufliche Akte (Klinikum) zeigt keine solche Karte.
* Die Frist aus der Zahnarztrechnung steht unter „Zur Prüfung“ bei den Vorhaben, mit dem Datum aus der Mail
  vorausgefüllt; eine Aufgabe entsteht erst mit dem Klick.
* Schmales Fenster ohne Überlauf; die Konsole bleibt leer.

Aufruf: `python scripts/probe_kreis_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build` in `app/kingfisher`).
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
MAMA = 'person:a:gabi.hartmann@gmx.example'
ZAHNARZT = 'organisation:zahnarztlindqvist'
KLINIKUM = 'organisation:klinikumalbanus'


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from messlatte import aufnahme, handlungen
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufgenommen.fehlgeschlagen == 0, aufgenommen
        handlungen.ausfuehren(instanz, [welt], aufgenommen.episoden)
        app = instanz.app
        # Die eigene Adresse kennt das Produkt sonst aus den Konten (wie die Stufe Lint und die Stufe Privat).
        app.state.settings.mail.user = welt.nutzer.adressen[0]
        # Der Abgleich der Bezüge läuft sonst im Hintergrund weiter; die Übersicht wäre dann vorläufig (`zaehlt_noch`).
        from icarus_memory.akten_routes import nachfuehren
        nachfuehren(app, warten=True)
        verbindung = instanz.episodes._conn

        def bestaetigt() -> int:
            with instanz.episodes._lock:
                return verbindung.execute('SELECT COUNT(*) FROM personen_kreis').fetchone()[0]

        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        faden = threading.Thread(target=server.run, daemon=True)
        faden.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        pruef = ergebnis['pruefungen']
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            seite = browser.new_context(viewport={'width': 1280, 'height': 1000}).new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

            def bild(name):
                pfad = args.ausgabe / f'kreis-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            def einstellungen():
                seite.goto(basis + '/settings#ich')
                seite.reload()
                seite.wait_for_selector('.kreis-stand p[role=status]', timeout=20000)
                return seite.locator('.kreis-stand p[role=status]').inner_text()

            def akte(sache):
                seite.goto(basis + '/memory/akte/' + quote(sache, safe=''))
                seite.wait_for_selector('section.akte', timeout=20000)

            # 1. Der echte Stand statt „kommt später“, mit den offenen Vorschlägen.
            satz = einstellungen()
            pruef['stand_vorher'] = satz
            assert satz.startswith('Noch für niemanden bestätigt. Offen sind ') and '3 für den inneren Kreis' in satz, satz
            ich_text = seite.locator('.ich').inner_text()
            assert 'kommt später' not in ich_text and 'Kreis' in ich_text
            offen = seite.locator('.kreis-offen button').all_inner_texts()
            pruef['offen_vorher'] = offen
            # Vorne nur der innere Kreis; die Kollegen stehen eingeklappt dahinter.
            assert seite.locator('.kreis-mehr').evaluate('d => d.open') is False
            assert seite.locator('.kreis-stand > .kreis-offen button').count() == 3
            assert any(t.startswith('Gabriele Hartmann') and 'Vorschlag: Innerer Kreis' in t for t in offen), offen
            assert not any('Unbekannt' in t for t in offen), offen   # der Betrugsversuch ist kein Vorschlag
            bild('einstellungen-vorher')
            # 2. Ein Klick führt in die Akte; die Karte zeigt Vorschlag und Begründung.
            seite.locator('.kreis-offen button').filter(has_text='Gabriele Hartmann').click()
            seite.wait_for_url('**/memory/akte/**', timeout=10000)
            karte = seite.locator('section.kreis-karte[aria-label="Kreis"]')
            karte.wait_for(timeout=20000)
            pruef['karte_vorher'] = karte.inner_text()
            assert 'Vorschlag: Innerer Kreis.' in pruef['karte_vorher']
            assert ('Warum: 7 Mails in beide Richtungen seit September 2025, privater Anbieter, ein gemeinsamer Termin, '
                    'Anrede „Mama“.') in pruef['karte_vorher'], pruef['karte_vorher']
            assert karte.locator('.kreis-wahlen button').count() == 3
            assert bestaetigt() == 0, 'Ein Vorschlag darf nichts speichern'
            bild('akte-vorschlag')
            # 3. Bestätigen mit einem Klick; eine andere Wahl gilt sofort; zurücknehmen geht.
            karte.get_by_role('button', name='Innerer Kreis').click()
            seite.wait_for_selector('text=Gespeichert: Innerer Kreis.', timeout=10000)
            assert bestaetigt() == 1
            pruef['nach_klick'] = karte.locator('p[role=status]').inner_text()
            karte.get_by_role('button', name='Kontakte').click()
            seite.wait_for_selector('text=Gespeichert: Kontakte.', timeout=10000)
            assert 'Bestätigt: Kontakte.' in karte.inner_text()
            karte.get_by_role('button', name='Wieder offen lassen').click()
            seite.wait_for_selector('text=Zurückgenommen.', timeout=10000)
            assert bestaetigt() == 0 and 'Vorschlag: Innerer Kreis.' in karte.inner_text()
            karte.get_by_role('button', name='Innerer Kreis').click()
            seite.wait_for_selector('text=Gespeichert: Innerer Kreis.', timeout=10000)
            bild('akte-bestaetigt')
            # 4. Nach dem Neuladen bleibt die Wahl.
            seite.reload()
            karte = seite.locator('section.kreis-karte[aria-label="Kreis"]')
            karte.wait_for(timeout=20000)
            assert 'Bestätigt: Innerer Kreis.' in karte.inner_text(), karte.inner_text()
            # 5. Der Stand zählt mit.
            satz = einstellungen()
            pruef['stand_nachher'] = satz
            assert satz.startswith('Für eine Person bestätigt. ') and '2 für den inneren Kreis' in satz, satz
            assert not any(t.startswith('Gabriele Hartmann') for t in seite.locator('.kreis-offen button').all_inner_texts())
            bild('einstellungen-nachher')
            # 6. Art der Akte: Vorschlag „Gesundheit“ bei der Zahnarztpraxis, keine Karte bei einer beruflichen Akte.
            akte(ZAHNARZT)
            art = seite.locator('section.kreis-karte[aria-label="Art der Akte"]')
            art.wait_for(timeout=20000)
            pruef['art_vorher'] = art.inner_text()
            assert 'Vorschlag: Gesundheit.' in pruef['art_vorher'] and 'Zahnarztpraxis Dr. Lindqvist' in pruef['art_vorher']
            art.get_by_role('button', name='Gesundheit').click()
            seite.wait_for_selector('text=Gespeichert: Gesundheit.', timeout=10000)
            with instanz.episodes._lock:
                assert verbindung.execute('SELECT art FROM akten_arten WHERE sache = ?', (ZAHNARZT,)).fetchone()[0] == 'gesundheit'
            bild('akte-art')
            akte(KLINIKUM)
            seite.wait_for_timeout(1500)
            assert seite.locator('section.kreis-karte').count() == 0
            # 7. Die Frist aus der Rechnung als Vorschlag mit Datum aus der Mail; eine Aufgabe erst mit dem Klick.
            lauf = instanz.anfrage('POST', '/api/v1/akten/arten/fristen')
            pruef['fristen'] = {k: lauf.get(k) for k in ('akten', 'vorgeschlagen')}
            aufgaben_vorher = len(app.state.tasks.all_tasks())
            seite.goto(basis + '/vorhaben?pruefen=1')
            vorschlag = seite.locator('article.mail-task-form').filter(has_text='Zahlung bis 12.10.2026: 86,40 €')
            vorschlag.wait_for(timeout=20000)
            vorschlag.get_by_role('button', name='Aufgabe prüfen').click()
            datum = vorschlag.locator('input[type=date]').input_value()
            pruef['faellig_vorausgefuellt'] = datum
            assert datum == '2026-10-12', datum
            assert len(app.state.tasks.all_tasks()) == aufgaben_vorher
            bild('frist-vorschlag')
            # 8. Schmales Fenster: Die Karte läuft nicht über ihren Rand (die Seitenbreite selbst gehört nicht hierher).
            seite.set_viewport_size({'width': 900, 'height': 1000})
            akte(MAMA)
            seite.locator('section.kreis-karte').first.wait_for(timeout=20000)
            breite = seite.evaluate("(() => { const k = document.querySelector('section.kreis-karte'); "
                                    "return k.scrollWidth - k.clientWidth; })()")
            pruef['ueberlauf_karte_900px'] = breite
            assert breite <= 1, breite
            bild('schmal')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'kreis-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder'],
                      'pruefungen': ergebnis['pruefungen']}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
