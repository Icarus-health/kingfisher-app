#!/usr/bin/env python3
"""Browserprobe für „Akten als Ordner“: echte Oberfläche, echter Server, der Mac-Helfer als echter Code am Netz.

Startet den Sidecar mit der synthetischen Welt der Messlatte (`messlatte/welt`) und öffnet Einstellungen →
Für Techniker → „Akten als Ordner“ in Chromium (Playwright). Der Auswahldialog des Mac (osascript) ist durch einen
temporären Ordner ersetzt; alles andere läuft wie im Betrieb: Der Helfer (`scripts/mac_folder_worker.py`,
Rolle `akten`) spricht per HTTP mit dem Server, holt das Archiv und legt es auf der Platte ab.

Geprüft werden: Karte eingeklappt und ohne Ordner, ohne Helfer ein ehrlicher Satz statt der Auswahl, Wahl des Ordners, Stand „zuletzt geschrieben“, „Quellen
mitschreiben“ (Rohtext erscheint erst dann), „Jetzt schreiben“, Trennen (Dateien bleiben), keine Spur der Karte
auf Startseite und im Assistenten, leere Konsole, Handybreite.
Aufruf: `python scripts/probe_akten_ordner_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def helfer_laden():
    spec = importlib.util.spec_from_file_location('mac_folder_worker', WURZEL / 'scripts' / 'mac_folder_worker.py')
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from messlatte import aufnahme
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import TOKEN, instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    worker = helfer_laden()
    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    with tempfile.TemporaryDirectory(prefix='akten-probe-') as mac, \
            instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        mac = Path(mac)
        vault = mac / 'Mein Vault'
        vault.mkdir()
        (vault / 'Eigene Notiz.md').write_text('Das gehört mir.', encoding='utf-8')
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
        api = worker.Api(basis, TOKEN, '/api/v1/akten/export')
        auswahl = worker.Auswahl(mac / 'privat.akten.json')
        waehle = lambda modus: vault if modus == 'waehlen' else worker.waehle_akten_ordner(modus, home=mac)  # noqa: E731

        def helfer_schritt(spiegeln: bool = True) -> dict:
            """Ein Durchgang des Mac-Helfers, genau wie `main_akten` ihn macht."""
            stand = worker.akten_schritt(api, auswahl, waehle)
            if spiegeln and stand.get('abholen') and auswahl.folder is not None and stand.get('ordner') == str(auswahl.folder):
                worker.akten_spiegeln(api, auswahl.folder)
            return stand

        def warte_bis(bedingung, was, sekunden=60):
            ende = time.monotonic() + sekunden
            while time.monotonic() < ende:
                if bedingung():
                    return
                helfer_schritt()
                time.sleep(0.4)
            raise AssertionError(f'Zeit abgelaufen: {was}')

        def stand():
            return api.call('')

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            seite = browser.new_context(viewport={'width': 1100, 'height': 1000}).new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

            def bild(name):
                pfad = args.ausgabe / f'akten-ordner-{name}.png'
                seite.locator('.akten-ordner').screenshot(path=str(pfad))
                ergebnis['bilder'].append(str(pfad))

            def schalten(beschriftung, an):
                """Klickt den Schalter und wartet, bis der Server geantwortet hat (der Haken folgt der Antwort)."""
                feld = seite.get_by_label(beschriftung)
                if feld.is_checked() != an:
                    feld.click()
                ende = time.monotonic() + 15
                while feld.is_checked() != an or feld.is_disabled():
                    assert time.monotonic() < ende, f'{beschriftung} wurde nicht {an}'
                    time.sleep(0.1)

            def ganze_seite(name):
                pfad = args.ausgabe / f'akten-ordner-{name}.png'
                seite.screenshot(path=str(pfad), full_page=True)
                ergebnis['bilder'].append(str(pfad))

            # 0. Keine Spur auf Startseite und im Assistenten
            seite.goto(basis + '/today')
            seite.wait_for_selector('main')
            pruef['startseite_ohne_hinweis'] = 'Akten als Ordner' not in seite.inner_text('body')
            assert pruef['startseite_ohne_hinweis']
            seite.goto(basis + '/willkommen')
            seite.wait_for_selector('main, body')
            time.sleep(0.5)
            pruef['assistent_ohne_hinweis'] = 'Akten als Ordner' not in seite.inner_text('body')
            assert pruef['assistent_ohne_hinweis']

            # 1. Einstellungen → Für Techniker → Akten als Ordner: zuerst eingeklappt
            seite.goto(basis + '/settings#technik')
            seite.reload()
            zusammen = seite.locator('details#technik-akten')
            zusammen.wait_for()
            pruef['eingeklappt'] = zusammen.get_attribute('open') is None
            assert pruef['eingeklappt'] and not seite.locator('.akten-ordner').is_visible()
            zusammen.locator('summary').click()
            # Ohne Helfer und nicht auf dem Mac (diese Probe läuft unter Linux): ein Satz statt einer Auswahl, die nie
            # ankommt (Befund 18). Danach meldet sich der Helfer, wie er es auf dem Mac ständig tut.
            seite.wait_for_selector('.akten-ordner >> text=gibt es nur in der Kingfisher-App auf dem Mac')
            pruef['ohne_helfer_ehrlich'] = seite.locator('.akten-ordner button.primary-action').count() == 0
            assert pruef['ohne_helfer_ehrlich']
            bild('0-ohne-helfer')
            helfer_schritt(spiegeln=False)
            seite.reload()
            seite.locator('details#technik-akten summary').click()
            seite.wait_for_selector('.akten-ordner button.primary-action')
            text = seite.locator('.akten-ordner').inner_text()
            pruef['ohne_ordner'] = text
            assert 'Noch kein Ordner' in text and 'nur zum Lesen' in text and 'Klartext' in text
            assert seite.locator('.akten-ordner button.primary-action').count() == 1       # genau ein gefüllter Knopf
            assert seite.locator('.akten-ordner input[type="text"]').count() == 0           # nichts zu tippen
            bild('1-ohne-ordner')

            # 2. Ordner wählen: die Karte wartet auf den Mac, der Helfer zeigt den Dialog
            seite.get_by_role('button', name='Anderen Ordner wählen').click()
            seite.wait_for_selector('.akten-ordner >> text=Bitte wähle den Ordner im Fenster')
            bild('2-wartet')
            helfer_schritt(spiegeln=False)                                                  # der Dialog liefert den Vault
            warte_bis(lambda: stand()['angekommen'], 'Ordner angekommen')
            seite.wait_for_selector('.akten-ordner >> text=Zuletzt geschrieben', timeout=20000)
            text = seite.locator('.akten-ordner').inner_text()
            pruef['nach_wahl'] = text
            assert 'Mein Vault' in text and 'Kingfisher Akten' in text and 'Dateien' in text, text
            assert seite.locator('.akten-ordner input[type="checkbox"]').first.is_checked()
            assert not seite.locator('.akten-ordner input[type="checkbox"]').nth(1).is_checked()   # Quellen: Vorgabe aus
            ziel = vault / 'Kingfisher Akten'
            dateien = sorted(str(p.relative_to(ziel)) for p in ziel.rglob('*') if p.is_file())
            pruef['dateien_auf_platte'] = len(dateien)
            assert 'index.md' in dateien and '_README.md' in dateien and not any(d.startswith('Quellen/') for d in dateien)
            assert any(d.startswith('Personen/') for d in dateien) and any(d.startswith('Organisationen/') for d in dateien)
            assert (vault / 'Eigene Notiz.md').read_text(encoding='utf-8') == 'Das gehört mir.'
            index = (ziel / 'index.md').read_text(encoding='utf-8')
            pruef['index_anfang'] = index[:400]
            assert index.startswith('---\nart: "katalog"') and '## Personen' in index
            bild('3-geschrieben')

            # 3. Quellen mitschreiben: erst jetzt Rohtext im Ordner
            schalten('Quellen mitschreiben', True)
            seite.wait_for_selector('.akten-ordner >> text=Mit Quellen enthält der Ordner den vollständigen Text')
            warte_bis(lambda: (vault / 'Kingfisher Akten' / 'Quellen').is_dir(), 'Quellen im Ordner')
            quellen = sorted((vault / 'Kingfisher Akten' / 'Quellen').glob('*.md'))
            pruef['quellen_dateien'] = len(quellen)
            assert quellen and '```text' in quellen[0].read_text(encoding='utf-8')
            bild('4-mit-quellen')
            schalten('Quellen mitschreiben', False)
            warte_bis(lambda: not (vault / 'Kingfisher Akten' / 'Quellen').exists(), 'Quellen wieder weg')
            pruef['quellen_wieder_weg'] = True

            # 4. Nichts fließt zurück: eine Datei ändern, „Jetzt schreiben“ stellt den Bestand wieder her
            kopf = next(p for p in (ziel / 'Personen').glob('*.md'))
            kopf.write_text('Ich habe das geändert.', encoding='utf-8')
            (ziel / 'Eigene Datei im Ordner.md').write_text('weg beim nächsten Schreiben', encoding='utf-8')
            seite.get_by_role('button', name='Jetzt schreiben').click()
            seite.wait_for_selector('.akten-ordner >> text=Die Akten wurden neu zusammengestellt')
            warte_bis(lambda: kopf.read_text(encoding='utf-8') != 'Ich habe das geändert.', 'Ordner neu geschrieben')
            pruef['zurueckgesetzt'] = not (ziel / 'Eigene Datei im Ordner.md').exists()
            assert pruef['zurueckgesetzt'] and (vault / 'Eigene Notiz.md').exists()
            bild('5-jetzt-schreiben')

            # 5. Ausschalten und Trennen: nichts wird gelöscht
            schalten('Akten in den Ordner schreiben', False)
            seite.wait_for_selector('.akten-ordner >> text=Ausgeschaltet')
            bild('6-ausgeschaltet')
            seite.get_by_role('button', name='Ordner trennen').click()
            seite.wait_for_selector('.akten-ordner >> text=Noch kein Ordner')
            assert (ziel / 'index.md').is_file() and (vault / 'Eigene Notiz.md').is_file()
            pruef['nach_trennen_bleibt_alles'] = True
            helfer_schritt(spiegeln=False)
            pruef['helfer_vergisst'] = auswahl.folder is None
            assert pruef['helfer_vergisst']

            # 6. Handybreite
            seite.set_viewport_size({'width': 390, 'height': 900})
            seite.wait_for_selector('.akten-ordner')
            # Seit M3 ist die Einstellungsseite nicht mehr breiter als ein Handy; die Karte ragt nicht über ihren Bereich.
            rechts = seite.evaluate("""() => { const r = s => Math.round(document.querySelector(s).getBoundingClientRect().right);
              return {seite: document.documentElement.scrollWidth, bereich: r('#settings-technik'), karte: r('.akten-ordner'), summary: r('details#technik-akten > summary')}; }""")
            pruef['handy'] = rechts
            assert rechts['karte'] <= rechts['bereich'] and rechts['seite'] <= 390, rechts
            bild('7-handy')
            browser.close()
        server.should_exit = True
        faden.join(timeout=5)
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'akten-ordner-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder']}, ensure_ascii=False))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
