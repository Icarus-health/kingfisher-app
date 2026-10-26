#!/usr/bin/env python3
"""Browserprobe für „Projekte von selbst“ (Paket P, docs/66-automatik.md): echte Oberfläche, echter Server, Chromium.

Startet den Sidecar als Messinstanz mit der synthetischen Welt der Messlatte (`messlatte/welt`, Stichtag 29.09.2026,
Uhr eingefroren) und ergänzt synthetische Mails: vier zu „Umbau Praxis“ von Anna Keller und Ben Braun (klar), drei zu
„Projekt Gartenhaus“ nur von Carla Fuchs (unklar). Die Erwähnungen liefert ein Regel-Skriptmodell statt eines Sprachmodells.
Geprüft wird:

* Kingfisher legt „Umbau Praxis“ selbst an (wie nach dem Mail-Durchlauf), „Gartenhaus“ bleibt die Frage „Neue Akte?“.
* Eine neue Mail von Anna ohne Projektnamen kommt nach Absender in „Umbau Praxis“.
* Heute zeigt „Neues Projekt: Umbau Praxis, aus 4 Mails mit Anna Keller und Ben Braun · Ansehen · Rückgängig“ und
  daneben die eine Frage zu Gartenhaus.
* „Ansehen“ öffnet die Akte mit „Von Kingfisher angelegt. …“ und „Beteiligte: Anna Keller und Ben Braun“; Annas Akte
  zeigt „Projekte: Umbau Praxis“; die Quelle der neuen Mail „Zugeordnet nach Absender · Ändern · Rückgängig“.
* „Rückgängig“ an der Quelle löst nur diese Mail; „Rückgängig“ auf Heute entfernt das Projekt, sagt es im Hinweis und
  es kommt nach einem weiteren Lauf nicht wieder.
* 1280 und 390 px ohne Überlauf, hell und dunkel (`--farbschema dark`); die Konsole bleibt leer.

Aufruf: `python scripts/probe_projekte_automatik_ui.py --ausgabe DIR [--chromium PFAD] [--farbschema dark]`
(vorher `npx vite build` in `app/kingfisher`).
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
ANNA = ('Anna Keller', 'anna.keller@praxis-umbau.example')
BEN = ('Ben Braun', 'ben.braun@tischlerei-braun.example')
CARLA = ('Carla Fuchs', 'carla.fuchs@garten-fuchs.example')
_NAMEN = re.compile(r'Umbau Praxis|Projekt [A-ZÄÖÜ][\wäöüß-]*')


class ProjektModell:
    """Ein Skriptmodell für die Einordnung: „Umbau Praxis“ und „Projekt <Name>“ werden Projekte. Kein Sprachmodell."""

    is_local = True
    name = 'probe'
    model = 'projekt-regel'

    def complete_json(self, messages, *, max_tokens, schema):
        from icarus_memory.providers import Reply
        nutzer = json.loads(messages[-1]['content'])
        entities = [{'kind': 'project', 'name': t.group(0), 'start': b['start'] + t.start(), 'end': b['start'] + t.end(),
                     'role': 'mentioned'} for b in nutzer['blocks'] for t in _NAMEN.finditer(b['text'])]
        return Reply(text=json.dumps({'categories': [], 'entities': entities}))


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    parser.add_argument('--farbschema', choices=('light', 'dark'), default='light')
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)
    dunkel = args.farbschema == 'dark'

    import uvicorn
    from messlatte import aufnahme, handlungen
    from messlatte.akten import RegelEinordnung
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welten
    from playwright.sync_api import sync_playwright

    welt = lade_welten([str(WURZEL / 'messlatte' / 'welt')])[0]
    ich = welt.nutzer.adressen[0]
    ergebnis: dict = {'ok': False, 'farbschema': args.farbschema, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = aufnahme.aufnehmen(instanz, list(welt.quellen), welt.stichtag, modell=RegelEinordnung())
        assert aufgenommen.fehlgeschlagen == 0, aufgenommen
        handlungen.ausfuehren(instanz, [welt], aufgenommen.episoden)
        app = instanz.app
        app.state.settings.mail.user = ich
        app.state.settings.einrichtung = {'name': 'Lea', 'schritte': {}, 'abgeschlossen': True}
        from icarus_memory import EpisodeKind, Provenance, SourceType, projekt_automatik
        from icarus_memory.akten_routes import nachfuehren
        from icarus_memory.memory_categories import Categories

        zaehler = [0]

        def mail(von, titel, text, tage):
            zaehler[0] += 1
            kontakte = [{'name': von[0], 'adresse': von[1], 'rolle': 'von', 'ich': False},
                        {'name': 'Lea Hartmann', 'adresse': ich, 'rolle': 'an', 'ich': True}]
            episode, _ = app.state.episodes.record(
                EpisodeKind.MESSAGE, titel, text,
                Provenance(SourceType.EMAIL, source_ref=f'probe:<p{zaehler[0]}@example.invalid>'),
                participants=[f'{von[0]} <{von[1]}>'], contacts=kontakte, occurred_at=welt.stichtag - timedelta(days=tage))
            return episode

        umbau = [mail(ANNA, 'Umbau Praxis: Auftakt', 'Hallo Lea, für den Umbau Praxis steht der Termin mit dem Architekten.', 18),
                 mail(BEN, 'Umbau Praxis: Holz', 'Hallo Lea, zum Umbau Praxis: Das Holz für den Empfang ist bestellt.', 12),
                 mail(ANNA, 'Umbau Praxis: Pläne', 'Hallo Lea, die Pläne für den Umbau Praxis liegen bei.', 6),
                 mail(BEN, 'Umbau Praxis: Montage', 'Hallo Lea, Umbau Praxis: Die Montage beginnt am Montag.', 2)]
        garten = [mail(CARLA, f'Gartenhaus {i}', f'Hallo Lea, zu Projekt Gartenhaus noch eine Idee ({i}).', tage)
                  for i, tage in ((1, 9), (2, 5), (3, 3))]
        Categories(app.state.episodes).run(ProjektModell(), limit=20, source_ids=[e.id for e in umbau + garten])
        nachfuehren(app, warten=True)
        # Wie nach einem Mail-Durchlauf: der erste Takt setzt den Stand der Absenderregel und legt Klares an.
        bericht = projekt_automatik.schritt_fuer(app)
        pruef = ergebnis['pruefungen']
        pruef['erster_takt'] = bericht
        projekte = {p.name: p for p in app.state.workspace.projects(include_closed=True)}
        assert 'Umbau Praxis' in projekte and not any('Gartenhaus' in n for n in projekte), list(projekte)
        projekt = projekte['Umbau Praxis']
        assert all(app.state.episodes.get(e.id).project_id == projekt.id for e in umbau)
        neu = mail(ANNA, 'Fliesen geliefert', 'Hallo Lea, die Fliesen sind da. Passt Donnerstag?', 0)
        pruef['zweiter_takt'] = projekt_automatik.schritt_fuer(app)
        assert app.state.episodes.get(neu.id).project_id == projekt.id, 'Absenderregel'
        nachfuehren(app, warten=True)

        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        threading.Thread(target=server.run, daemon=True).start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            kontext = browser.new_context(viewport={'width': 1280, 'height': 1000}, locale='de-DE',
                                          color_scheme=args.farbschema)
            seite = kontext.new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
            endung = '-dunkel' if dunkel else ''

            def bild(name, ganz=False):
                pfad = args.ausgabe / f'projekte-{name}{endung}.png'
                seite.screenshot(path=str(pfad), full_page=ganz)
                ergebnis['bilder'].append(str(pfad))

            def ohne_ueberlauf(name):
                breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
                pruef[f'ueberlauf_{name}'] = breite
                assert breite[0] <= breite[1], (name, breite)

            def heute():
                seite.goto(basis + '/today')
                zeile = seite.locator('.today-neue-projekte')
                zeile.wait_for(timeout=30000)
                seite.locator('.today-attention-list, .today-empty').first.wait_for(timeout=30000)
                return zeile

            # 1. Heute: die Zeile mit Grund, daneben die eine Frage zum unklaren Gartenhaus.
            zeile = heute()
            pruef['heute_zeile'] = zeile.inner_text()
            assert 'Neues Projekt: Umbau Praxis, aus 4 Mails mit Anna Keller und Ben Braun' in pruef['heute_zeile'], pruef['heute_zeile']
            assert zeile.get_by_role('link', name='Ansehen').count() == 1 and zeile.get_by_role('button', name='Rückgängig').count() == 1
            # Die Frage zum unklaren Gartenhaus bleibt Frage; an einem vollen Tag (die Welt hat genug Dringendes) steht sie
            # hinter den drei wichtigsten Punkten zurück (leises Gewicht wie bisher), deshalb über die Schnittstelle.
            offen = instanz.anfrage('GET', '/api/v1/akten/vorschlaege')
            pruef['offene_fragen'] = [v['name'] for v in offen['vorschlaege']]
            assert pruef['offene_fragen'] == ['Projekt Gartenhaus'], pruef['offene_fragen']
            frage = seite.locator('.today-attention-item').filter(has_text='Neue Akte?')
            pruef['heute_frage'] = frage.inner_text() if frage.count() else '(nicht unter den drei wichtigsten)'
            ohne_ueberlauf('heute_1280')
            seite.locator('.today-attention').scroll_into_view_if_needed()
            bild('heute-1280')
            # 2. „Ansehen“: die Akte nennt die Herkunft mit Grund und die Beteiligten.
            zeile.get_by_role('link', name='Ansehen').click()
            seite.wait_for_url('**/memory/akte/projekt:*', timeout=10000)
            seite.locator('section.akte .akte-neue-stand').wait_for(timeout=30000)
            pruef['akte_herkunft'] = seite.locator('.akte-neue-stand').inner_text()
            assert pruef['akte_herkunft'].startswith('Von Kingfisher angelegt. In 4 Mails seit '), pruef['akte_herkunft']
            assert 'Anna Keller und Ben Braun' in pruef['akte_herkunft'] and 'Rückgängig' in pruef['akte_herkunft']
            pruef['akte_beteiligte'] = seite.locator('.akte-verbunden').inner_text()
            assert pruef['akte_beteiligte'] == 'Beteiligte: Anna Keller und Ben Braun', pruef['akte_beteiligte']
            ohne_ueberlauf('akte_1280')
            bild('akte-1280')
            # 3. Die neue Mail: „Zugeordnet nach Absender · Ändern · Rückgängig“; Rückgängig löst nur sie.
            seite.locator('.akte-verlauf-auf > summary').click()
            seite.get_by_role('button', name='Quelle: Fliesen geliefert').first.click()
            auto = seite.locator('.source-project-auto')
            auto.wait_for(timeout=20000)
            pruef['quelle_auto'] = auto.inner_text()
            assert pruef['quelle_auto'].startswith('Zugeordnet nach Absender · Ändern · Rückgängig'), pruef['quelle_auto']
            auto.scroll_into_view_if_needed()
            bild('quelle-absender')
            auto.get_by_role('button', name='Ändern').click()
            assert seite.evaluate("document.activeElement && document.activeElement.tagName") == 'SELECT'
            auto.get_by_role('button', name='Rückgängig').click()
            meldung = seite.locator('.g-hinweis')
            meldung.wait_for(timeout=10000)
            meldung.hover()
            pruef['quelle_zurueck'] = meldung.inner_text()
            assert pruef['quelle_zurueck'].startswith('Wieder keinem Projekt zugeordnet. Kingfisher ordnet diese Mail nicht wieder zu.')
            assert app.state.episodes.get(neu.id).project_id is None
            assert all(app.state.episodes.get(e.id).project_id == projekt.id for e in umbau)
            # 4. Annas Akte nennt ihr Projekt (abgeleitet), ihr Profil ebenso.
            seite.goto(basis + '/memory/akte/' + quote(f'person:a:{ANNA[1]}', safe=''))
            seite.locator('section.akte .akte-verbunden').wait_for(timeout=30000)
            pruef['person_projekte'] = seite.locator('.akte-verbunden').inner_text()
            assert pruef['person_projekte'] == 'Projekte: Umbau Praxis', pruef['person_projekte']
            ohne_ueberlauf('person_1280')
            bild('person-1280')
            # 5. Schmal: Heute und die Akte bei 390 px.
            seite.set_viewport_size({'width': 390, 'height': 844})
            zeile = heute()
            seite.wait_for_timeout(500)
            ohne_ueberlauf('heute_390')
            zeile.scroll_into_view_if_needed()
            bild('heute-390')
            seite.goto(basis + '/memory/akte/' + quote(f'projekt:{projekt.id}', safe=''))
            seite.locator('section.akte .akte-neue-stand').wait_for(timeout=30000)
            seite.wait_for_timeout(500)
            ohne_ueberlauf('akte_390')
            bild('akte-390')
            # 6. „Rückgängig“ auf Heute: Projekt weg, Hinweis sagt es, ein weiterer Lauf bringt es nicht zurück.
            seite.set_viewport_size({'width': 1280, 'height': 1000})
            zeile = heute()
            zeile.get_by_role('button', name='Rückgängig').click()
            meldung = seite.locator('.g-hinweis')
            meldung.wait_for(timeout=10000)
            meldung.hover()
            pruef['heute_zurueck'] = meldung.inner_text()
            assert 'Projekt „Umbau Praxis“ entfernt. Kingfisher legt es nicht wieder an.' in pruef['heute_zurueck'], pruef['heute_zurueck']
            seite.locator('.today-neue-projekte').wait_for(state='detached', timeout=10000)
            bild('heute-zurueckgenommen')
            assert 'Umbau Praxis' not in {p.name for p in app.state.workspace.projects(include_closed=True)}
            pruef['dritter_takt'] = projekt_automatik.schritt_fuer(app)
            assert 'Umbau Praxis' not in {p.name for p in app.state.workspace.projects(include_closed=True)}
            assert all(app.state.episodes.get(e.id).project_id is None for e in umbau)
            browser.close()
        server.should_exit = True
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / f'ergebnis{"-dunkel" if dunkel else ""}.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1))
    print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
