#!/usr/bin/env python3
"""Browserprobe für den Rest von M4 „Privat ist gleichberechtigt“: echte Oberfläche, echter Server.

Startet den Sidecar mit der synthetischen Welt der Messlatte (`messlatte/welt`, Szenario `privat`, Stichtag der Welt,
Regel-Einordnung) und öffnet die Oberfläche in Chromium (Playwright). Geprüft wird:

* **Geburtstag:** Die Akte der Mutter zeigt die Karte „Geburtstag“ mit Vorschlag und Beleg; vor dem Klick gibt es
  keine Aussage. Nach Kreis bestätigen und „Stimmt, übernehmen“ steht im Briefing „Morgen hat Gabriele Geburtstag.“
  Die Nachbarin (Kontakt, Geburtstag im Kalender) hat keine Karte, und im Briefing steht sie nie.
* **Wiederkehrendes:** Die Akte der Stadtwerke zeigt „Monatlich: Abschlag, 94,00 €“ als Vorschlag.
* **Sammelbestätigung:** Unter „Kingfisher und du“ steht „Alle 21 als Kollegen festlegen“; die Rückfrage ist ein
  Satz („21 Personen als Kollegen festlegen?“), „Abbrechen“ speichert nichts, „Ja, festlegen“ legt alle 21 fest und
  keinen aus dem inneren Kreis, „Liste zurücknehmen“ lässt sie wieder offen.
* **Anhänge:** Die Akte der Zahnarztpraxis zeigt die Rechnung aus dem PDF-Anhang als Quelle mit Seite, und die Frist
  daraus steht unter „Zur Prüfung“ mit dem Datum aus dem PDF; ein gescannter Anhang sagt ehrlich, dass er nicht
  gelesen ist.
* **Cloud-Ordner:** Unter Einstellungen → Dokumente stehen die synchronisierten Ordner (OneDrive, Google Drive,
  iCloud Drive) zum Anklicken, die es gibt; freigegeben ist erst, was angeklickt wird.
* Schmales Fenster ohne Überlauf der Karten; die Konsole bleibt leer.

Aufruf: `python scripts/probe_privat_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build` in `app/kingfisher`).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import tempfile
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
JUTTA = 'person:a:jutta.rehberg@t-online.example'
STADTWERKE = 'organisation:stadtwerketaunusstein'
ZAHNARZT = 'organisation:zahnarztlindqvist'


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def cloud_ordner(home: Path) -> None:
    """Synthetische Cloud-Ordner wie auf einem Mac (nur Namen und eine Datei; keine echten Daten)."""
    for teil in ('Library/CloudStorage/OneDrive-Hochschule', 'Library/CloudStorage/GoogleDrive-lea@beispiel.example/Meine Ablage',
                 'Library/Mobile Documents/com~apple~CloudDocs'):
        ordner = home / teil
        ordner.mkdir(parents=True, exist_ok=True)
        datei = ordner / 'Notiz.md'
        datei.write_text('# Notiz\n\nSynthetisch.\n', encoding='utf-8')
        alt = time.time() - 60
        os.utime(datei, (alt, alt))


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
    home = Path(tempfile.mkdtemp(prefix='privat-probe-home-'))
    cloud_ordner(home)
    alt_home = os.environ.get('HOME')
    os.environ['HOME'] = str(home)   # Path.home() für die bekannten Orte; der Sidecar läuft hier nicht im Container
    try:
        with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
            aufgenommen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
            assert aufgenommen.fehlgeschlagen == 0, aufgenommen
            handlungen.ausfuehren(instanz, [welt], aufgenommen.episoden)
            app = instanz.app
            app.state.settings.mail.user = welt.nutzer.adressen[0]
            app.state.settings.einrichtung = {'name': 'Lea', 'schritte': {}, 'abgeschlossen': True}   # kein Erststart-Assistent
            from icarus_memory.akten_routes import nachfuehren
            nachfuehren(app, warten=True)
            instanz.anfrage('POST', '/api/v1/wiederkehrendes/vorschlagen')
            pruefen(instanz, app, args, ergebnis, aufgenommen)
    finally:
        if alt_home is not None:
            os.environ['HOME'] = alt_home
    ergebnis['ok'] = not ergebnis['konsole'] and ergebnis.get('fertig', False)
    (args.ausgabe / 'privat-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder'],
                      'pruefungen': ergebnis['pruefungen']}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


def pruefen(instanz, app, args, ergebnis: dict, aufgenommen) -> None:
    import uvicorn
    from playwright.sync_api import sync_playwright

    verbindung = instanz.episodes._conn

    def kreise() -> dict:
        with instanz.episodes._lock:
            return {z[0]: z[1] for z in verbindung.execute('SELECT sache, kreis FROM personen_kreis')}

    def aussagen(praedikat: str) -> list:
        return [c for c in app.state.claims.all_claims(include_inactive=False) if c.predicate == praedikat]

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
            pfad = args.ausgabe / f'privat-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def akte(sache):
            seite.goto(basis + '/memory/akte/' + quote(sache, safe=''))
            seite.wait_for_selector('section.akte', timeout=20000)

        # 1. Geburtstag: Vorschlag mit Beleg in der Akte der Mutter, noch keine Aussage.
        akte(MAMA)
        karte = seite.locator('section.kreis-karte[aria-label="Geburtstag"]')
        karte.wait_for(timeout=20000)
        pruef['geburtstag_vorher'] = karte.inner_text()
        assert 'Vorschlag: Gabriele Hartmann hat am 30. September Geburtstag.' in pruef['geburtstag_vorher']
        assert 'Beleg: „alles Gute zum Geburtstag!“' in pruef['geburtstag_vorher'], pruef['geburtstag_vorher']
        assert aussagen('geburtstag') == []
        bild('geburtstag-vorschlag')
        # Kreis bestätigen und Geburtstag übernehmen, wie ein Mensch.
        seite.locator('section.kreis-karte[aria-label="Kreis"]').get_by_role('button', name='Innerer Kreis').click()
        seite.wait_for_selector('text=Gespeichert: Innerer Kreis.', timeout=10000)
        karte.get_by_role('button', name='Stimmt, übernehmen').click()
        seite.wait_for_selector('text=Steht fest: Gabriele Hartmann hat am 30. September Geburtstag.', timeout=10000)
        pruef['geburtstag_nachher'] = karte.inner_text()
        assert len(aussagen('geburtstag')) == 1
        bild('geburtstag-angenommen')
        # 2. Briefing am Stichtag: „Morgen hat Gabriele Geburtstag.“
        daten = instanz.anfrage('GET', '/api/v1/tag/briefing?nachladen=true')
        pruef['briefing_daten'] = {'geburtstage': daten.get('geburtstage'), 'fehler': daten.get('fehler'),
                                   'zeilen': [z['art'] for z in (daten.get('tageslage') or {}).get('zeilen', [])]}
        seite.goto(basis + '/today')
        zeile = seite.locator('li.tageslage-geburtstag')
        try:
            zeile.wait_for(timeout=20000)
        except Exception:
            bild('briefing-fehler')
            print(json.dumps(pruef['briefing_daten'], ensure_ascii=False))
            raise
        pruef['briefing_zeile'] = zeile.inner_text()
        assert 'Morgen hat Gabriele Geburtstag.' in pruef['briefing_zeile'] and 'Geburtstag' in pruef['briefing_zeile']
        bild('briefing')
        # 3. Die Nachbarin (Kontakt; Geburtstag nur im Kalender) hat keine Karte.
        akte(JUTTA)
        seite.locator('section.kreis-karte[aria-label="Kreis"]').wait_for(timeout=20000)
        seite.wait_for_timeout(800)
        assert seite.locator('section.kreis-karte[aria-label="Geburtstag"]').count() == 0
        # 4. Wiederkehrendes bei den Stadtwerken.
        akte(STADTWERKE)
        wk = seite.locator('section.kreis-karte[aria-label="Wiederkehrend"]')
        wk.wait_for(timeout=20000)
        pruef['wiederkehrend'] = wk.inner_text()
        assert 'Vorschlag: Monatlich: Abschlag, 94,00 € (Stadtwerke Taunusstein)' in pruef['wiederkehrend'], pruef['wiederkehrend']
        bild('wiederkehrend')
        # 5. Sammelbestätigung unter „Kingfisher und du“.
        vorher = kreise()
        seite.goto(basis + '/settings#ich')
        seite.reload()
        knopf = seite.get_by_role('button', name='Alle 21 als Kollegen festlegen')
        knopf.wait_for(timeout=20000)
        knopf.click()
        frage = seite.locator('.kreis-frage')
        pruef['rueckfrage'] = frage.locator('p').inner_text()
        assert pruef['rueckfrage'] == '21 Personen als Kollegen festlegen?'
        bild('sammel-frage')
        frage.get_by_role('button', name='Abbrechen').click()
        assert kreise() == vorher, 'Abbrechen darf nichts speichern'
        knopf.click()
        seite.locator('.kreis-frage').get_by_role('button', name='Ja, festlegen').click()
        seite.wait_for_selector('text=21 Personen als Kollegen festgelegt.', timeout=20000)
        nachher = kreise()
        neu = {s: k for s, k in nachher.items() if s not in vorher}
        pruef['sammel_neu'] = len(neu)
        assert len(neu) == 21 and set(neu.values()) == {'kollegen'}, neu
        assert nachher[MAMA] == 'innerer_kreis'
        seite.wait_for_selector('text=Zuletzt 21 Personen gesammelt als Kollegen festgelegt.', timeout=10000)
        bild('sammel-fertig')
        seite.get_by_role('button', name='Liste zurücknehmen').click()
        seite.wait_for_selector('text=Zurückgenommen: 21 Personen sind wieder offen.', timeout=10000)
        assert kreise() == vorher
        pruef['sammel_zurueck'] = True
        weiter_teil_3_und_4(seite, basis, instanz, app, pruef, bild, akte)
        # Schmales Fenster: Die Karten laufen nicht über.
        seite.set_viewport_size({'width': 390, 'height': 900})
        akte(MAMA)
        seite.locator('section.kreis-karte[aria-label="Geburtstag"]').wait_for(timeout=20000)
        breite = seite.evaluate("(() => Math.max(...[...document.querySelectorAll('section.kreis-karte')]"
                                ".map(k => k.scrollWidth - k.clientWidth)))()")
        pruef['ueberlauf_390px'] = breite
        assert breite <= 1, breite
        bild('schmal')
        browser.close()
    server.should_exit = True
    faden.join(timeout=5)
    ergebnis['fertig'] = True


def weiter_teil_3_und_4(seite, basis, instanz, app, pruef, bild, akte) -> None:
    """Anhänge (Teil 3) und Cloud-Ordner (Teil 4)."""
    # Anhänge: die PDF-Rechnung als Quelle in der Akte der Praxis, der Scan ehrlich ungelesen.
    akte('organisation:physiobrunnenhof')
    seite.wait_for_selector('text=Rechnung-PB-2026-118.pdf', timeout=20000)
    pruef['akte_mit_anhang'] = seite.locator('section.akte').inner_text()[:600]
    bild('anhang-akte')
    akte('organisation:hausverwaltungrosenhof')
    seite.wait_for_selector('text=Rechnung-Hausmeister-Scan.pdf', timeout=20000)
    scan = next(e for e in instanz.episodes.each_episode() if e.title.startswith('Rechnung-Hausmeister-Scan.pdf'))
    assert 'Gescannte Rechnung „Rechnung-Hausmeister-Scan.pdf“ (1 Seite), noch nicht gelesen.' in scan.body
    # Ein Klick auf die Zeile öffnet die Quelle; dort steht ehrlich, dass der Scan nicht gelesen ist.
    seite.get_by_text('Quelle: Rechnung-Hausmeister-Scan.pdf').first.click()
    seite.wait_for_selector('text=noch nicht gelesen', timeout=20000)
    pruef['scan_quelle'] = 'noch nicht gelesen sichtbar'
    bild('anhang-scan')
    # Die Art der Akte nennt den Anhang nicht als zweiten Betreff.
    akte('organisation:physiobrunnenhof')
    art = seite.locator('section.kreis-karte[aria-label="Art der Akte"]')
    art.wait_for(timeout=20000)
    assert '(Anhang zu' not in art.inner_text(), art.inner_text()
    # Die Frist aus dem PDF unter „Zur Prüfung“, Datum aus dem PDF vorausgefüllt, keine Aufgabe ohne Klick.
    instanz.anfrage('POST', '/api/v1/akten/arten/fristen')
    aufgaben_vorher = len(app.state.tasks.all_tasks())
    seite.goto(basis + '/vorhaben?pruefen=1')
    vorschlag = seite.locator('article.mail-task-form').filter(has_text='Zahlung bis 22.10.2026: 147,60 €')
    vorschlag.wait_for(timeout=20000)
    pruef['frist_aus_pdf'] = vorschlag.inner_text()
    vorschlag.get_by_role('button', name='Aufgabe prüfen').click()
    datum = vorschlag.locator('input[type=date]').input_value()
    assert datum == '2026-10-22', datum
    assert len(app.state.tasks.all_tasks()) == aufgaben_vorher
    bild('anhang-frist')
    # Cloud-Ordner: Vorschläge zum Anklicken unter Einstellungen → Dokumente; freigegeben erst mit dem Klick.
    weiter_teil_4(seite, basis, instanz, app, pruef, bild)


def weiter_teil_4(seite, basis, instanz, app, pruef, bild) -> None:
    """Cloud-Ordner (Teil 4): Vorschläge mit lesbarem Namen; vor dem Klick ist nichts freigegeben."""
    seite.goto(basis + '/settings#zugaenge')
    seite.reload()
    # „Dokumente automatisch aufnehmen“ ist eingeklappt; aufklappen wie ein Mensch.
    seite.locator('summary', has_text='Dokumente automatisch aufnehmen').click()
    dokumente = seite.locator('.ordner-im-browser').filter(has=seite.locator('#ordner-pfad-dokumente'))
    knopf = dokumente.get_by_role('button', name='OneDrive (Hochschule) verwenden')
    knopf.wait_for(timeout=20000)
    liste = dokumente.locator('ul.ordner-orte')
    pruef['cloud_orte'] = liste.inner_text()
    for name in ('OneDrive (Hochschule) verwenden', 'Google Drive (lea@beispiel.example) verwenden', 'iCloud Drive verwenden'):
        assert name in pruef['cloud_orte'], pruef['cloud_orte']
    assert 'aus der Cloud, auf diesem Rechner abgeglichen' in pruef['cloud_orte']
    assert instanz.anfrage('GET', '/api/v1/folder-sync')['enabled'] is False   # angezeigt ist nicht freigegeben
    bild('cloud-orte')
    knopf.click()
    seite.wait_for_selector('text=Freigegeben:', timeout=20000)
    stand = instanz.anfrage('GET', '/api/v1/folder-sync')
    assert stand['enabled'] is True and stand['folder'].endswith('OneDrive-Hochschule'), stand
    pruef['cloud_freigegeben'] = stand['folder']
    bild('cloud-freigegeben')


if __name__ == '__main__':
    raise SystemExit(main())
