#!/usr/bin/env python3
"""Browserprobe für den Vorschlag „Neue Akte?“ (Paket B4): echte Oberfläche, echter Server, Chromium.

Startet den Sidecar als Messinstanz mit einer Attrappe (vier synthetische Mails von zwei Personen über drei Wochen,
in denen „Projekt Atlas“ vorkommt; die Erwähnungen liefert ein Regel-Skriptmodell statt eines Sprachmodells) und
öffnet die Oberfläche in Chromium (Playwright). Geprüft wird:

* Die Akte `projekt:n:atlas` zeigt oben „Neue Akte? Daraus eine Akte machen? In 4 Mails seit … mit Anna Keller und
  Ben Braun.“ mit den Textstellen und zwei Knöpfen. Vor dem Klick ist nichts angelegt.
* „Nein danke“ antwortet mit einem Satz und „Rückgängig“; danach steht „Doch vorschlagen“ da; „Rückgängig“ holt den
  Vorschlag zurück.
* „Akte anlegen“ legt das Projekt an, öffnet die neue Akte mit dem Satz („Akte „Projekt Atlas“ angelegt, 4 Quellen
  zugeordnet.“) und „Rückgängig“; die Akte hat 4 Quellen, beide Beteiligte und einen Zeitstrahl. „Rückgängig“ löst
  alles wieder und führt zur Akte der Erwähnung zurück.
* Heute zeigt den einen Satz mit „Akte anlegen“ und „Nein danke“; nach dem Klick bleibt die Antwort mit „Akte öffnen“.
* 1280 und 390 px ohne Überlauf; die Konsole bleibt leer.

Aufruf: `python scripts/probe_neue_akte_ui.py --ausgabe DIR [--chromium PFAD]` (vorher `npm run build` in `app/kingfisher`).
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
ICH = 'lea@hartmann-beratung.example'
ANNA = ('Anna Keller', 'anna.keller@nordlicht.example')
BEN = ('Ben Braun', 'ben.braun@nordlicht.example')
STICHTAG = datetime(2026, 10, 22, 8, 30, tzinfo=timezone.utc)
_PROJEKT = re.compile(r'Projekt [A-ZÄÖÜ][\wäöüß-]*')


class ProjektModell:
    """Ein Skriptmodell für die Einordnung: jede Erwähnung „Projekt <Name>“ wird ein Projekt. Kein Sprachmodell."""

    is_local = True
    name = 'probe'
    model = 'projekt-regel'

    def complete_json(self, messages, *, max_tokens, schema):
        from icarus_memory.providers import Reply
        nutzer = json.loads(messages[-1]['content'])
        entities = [{'kind': 'project', 'name': t.group(0), 'start': b['start'] + t.start(), 'end': b['start'] + t.end(),
                     'role': 'mentioned'} for b in nutzer['blocks'] for t in _PROJEKT.finditer(b['text'])]
        return Reply(text=json.dumps({'categories': [], 'entities': entities}))


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def mail(app, nummer: int, von: tuple[str, str], text: str, tage: int):
    from icarus_memory import EpisodeKind, Provenance, SourceType
    kontakte = [{'name': von[0], 'adresse': von[1], 'rolle': 'von', 'ich': False},
                {'name': 'Lea Hartmann', 'adresse': ICH, 'rolle': 'an', 'ich': True}]
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, f'Atlas {nummer}', text, Provenance(SourceType.EMAIL, source_ref=f'probe:<{nummer}@example.invalid>'),
        participants=[f'{von[0]} <{von[1]}>'], contacts=kontakte, occurred_at=STICHTAG - timedelta(days=tage))
    return episode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    import uvicorn
    from icarus_memory.akten_routes import nachfuehren
    from icarus_memory.memory_categories import Categories
    from messlatte.instanz import instanz_starten
    from playwright.sync_api import sync_playwright

    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    with instanz_starten(stichtag=STICHTAG, zeitzone='Europe/Berlin', eigene=(ICH,)) as instanz:
        app = instanz.app
        app.state.settings.mail.user = ICH
        app.state.settings.einrichtung = {'name': 'Lea', 'schritte': {}, 'abgeschlossen': True}  # kein Erststart-Assistent
        texte = [(ANNA, 'Hallo Lea, zu Projekt Atlas gibt es Neues: Der Auftakt steht.', 20),
                 (BEN, 'Hallo Lea, für Projekt Atlas brauche ich noch den Zeitplan.', 12),
                 (ANNA, 'Hallo Lea, Projekt Atlas kommt gut voran, der Entwurf liegt vor.', 6),
                 (BEN, 'Hallo Lea, Projekt Atlas: Können wir nächste Woche sprechen?', 2)]
        quellen = [mail(app, i + 1, von, text, tage) for i, (von, text, tage) in enumerate(texte)]
        Categories(app.state.episodes).run(ProjektModell(), limit=20)
        nachfuehren(app, warten=True)
        verbindung = instanz.episodes._conn

        def projekte() -> list[str]:
            return [p.name for p in app.state.workspace.projects(include_closed=True)]

        def entscheidungen() -> list[tuple]:
            with instanz.episodes._lock:
                return [tuple(z) for z in verbindung.execute(
                    'SELECT kennung, entscheidung FROM akten_vorschlag_entscheidungen').fetchall()]

        vorschlaege = instanz.anfrage('GET', '/api/v1/akten/vorschlaege')
        assert vorschlaege['anzahl'] == 1 and vorschlaege['vorschlaege'][0]['name'] == 'Projekt Atlas', vorschlaege
        kennung = vorschlaege['vorschlaege'][0]['kennung']
        assert projekte() == [] and entscheidungen() == [], 'Ein Vorschlag darf nichts speichern'

        port = freier_port()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        threading.Thread(target=server.run, daemon=True).start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.1)
        basis = f'http://127.0.0.1:{port}'
        pruef = ergebnis['pruefungen']
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
            seite = browser.new_context(viewport={'width': 1280, 'height': 1000}, locale='de-DE').new_page()
            seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
            seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))

            def bild(name, ganz=True):
                pfad = args.ausgabe / f'neue-akte-{name}.png'
                seite.screenshot(path=str(pfad), full_page=ganz)
                ergebnis['bilder'].append(str(pfad))

            def akte(sache):
                seite.goto(basis + '/memory/akte/' + quote(sache, safe=''))
                seite.wait_for_selector('section.akte', timeout=20000)

            def ohne_ueberlauf(name):
                breite = seite.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
                pruef[f'ueberlauf_{name}'] = breite
                assert breite[0] <= breite[1], (name, breite)

            # 1. Die Zeile in der Akte der Erwähnung: Frage, Grund, Textstellen, zwei Knöpfe; nichts angelegt.
            akte('projekt:n:atlas')
            zeile = seite.locator('section.akte-neue[aria-label="Neue Akte?"]')
            zeile.wait_for(timeout=20000)
            pruef['zeile'] = zeile.inner_text()
            assert pruef['zeile'].startswith('Neue Akte?') and 'Daraus eine Akte machen? In 4 Mails seit 2. Oktober mit Anna Keller und Ben Braun.' in pruef['zeile'], pruef['zeile']
            assert zeile.locator('.akte-neue-quellen li').count() == 4
            assert zeile.get_by_role('button', name='Akte anlegen').count() == 1 and zeile.get_by_role('button', name='Nein danke').count() == 1
            assert projekte() == [] and entscheidungen() == []
            ohne_ueberlauf('akte_1280')
            bild('akte-vorschlag')
            # 2. „Nein danke“: gemerkt, Satz mit „Rückgängig“; danach „Doch vorschlagen“; „Rückgängig“ holt ihn zurück.
            zeile.get_by_role('button', name='Nein danke').click()
            meldung = seite.locator('.akte-meldung')
            meldung.wait_for(timeout=10000)
            pruef['nein_danke'] = meldung.inner_text()
            assert pruef['nein_danke'].startswith('Gemerkt: „Projekt Atlas“ wird nicht mehr vorgeschlagen.'), pruef['nein_danke']
            seite.locator('.akte-neue-stand').wait_for(timeout=10000)
            assert 'Doch vorschlagen' in seite.locator('.akte-neue-stand').inner_text()
            assert entscheidungen() == [(kennung, 'abgelehnt')] and projekte() == []
            bild('akte-nein-danke')
            meldung.get_by_role('button', name='Rückgängig').click()
            seite.locator('section.akte-neue[aria-label="Neue Akte?"]').wait_for(timeout=10000)
            assert entscheidungen() == []
            pruef['zurueck_nach_nein'] = seite.locator('.akte-meldung').inner_text()
            # 3. „Akte anlegen“: Projekt da, neue Akte mit Satz und „Rückgängig“, vollständig.
            seite.locator('section.akte-neue').get_by_role('button', name='Akte anlegen').click()
            seite.wait_for_url('**/memory/akte/projekt:p-akte-*', timeout=10000)
            seite.wait_for_selector('section.akte', timeout=20000)
            meldung = seite.locator('.akte-meldung')
            meldung.wait_for(timeout=10000)
            pruef['angelegt'] = meldung.inner_text()
            assert pruef['angelegt'].startswith('Akte „Projekt Atlas“ angelegt, 4 Quellen zugeordnet.'), pruef['angelegt']
            assert projekte() == ['Projekt Atlas'] and entscheidungen() == [(kennung, 'angenommen')]
            assert all(app.state.episodes.get(q.id).project_id for q in quellen)
            seite.locator('.akte-neue-stand').wait_for(timeout=10000)
            assert 'Aus einem Vorschlag angelegt, 4 Quellen zugeordnet.' in seite.locator('.akte-neue-stand').inner_text()
            kopf = seite.locator('.akte-kopf').inner_text()
            pruef['neue_akte_kopf'] = kopf
            assert 'Projekt Atlas' in kopf and 'Aus 4 Quellen' in kopf, kopf
            zusammenhaenge = seite.locator('.akte-beteiligte').inner_text()
            assert 'Anna Keller' in zusammenhaenge and 'Ben Braun' in zusammenhaenge, zusammenhaenge
            assert seite.locator('.akte-strahl, .akte-spur').count() >= 1, 'Zeitstrahl fehlt'
            bild('akte-angelegt')
            # 4. „Rückgängig“ löst alles und führt zur Akte der Erwähnung zurück.
            meldung.get_by_role('button', name='Rückgängig').click()
            seite.wait_for_url('**/memory/akte/projekt:n:atlas', timeout=10000)
            seite.locator('section.akte-neue[aria-label="Neue Akte?"]').wait_for(timeout=20000)
            pruef['zurueckgenommen'] = seite.locator('.akte-meldung').inner_text()
            assert pruef['zurueckgenommen'].startswith('Zurückgenommen: 4 Quellen gelöst, Projekt „Projekt Atlas“ entfernt.'), pruef['zurueckgenommen']
            assert projekte() == [] and entscheidungen() == []
            assert all(app.state.episodes.get(q.id).project_id is None for q in quellen)
            bild('akte-zurueckgenommen')
            # 5. Heute: der eine Satz mit zwei Knöpfen; die Antwort bleibt stehen.
            seite.goto(basis + '/today')
            seite.locator('.today-page h1').wait_for(timeout=15000)
            karte = seite.locator('.today-attention-item').filter(has_text='Neue Akte?')
            karte.wait_for(timeout=20000)
            pruef['heute'] = karte.inner_text()
            assert 'In 4 Mails seit 2. Oktober mit Anna Keller und Ben Braun geht es um „Projekt Atlas“. Daraus eine Akte machen?' in pruef['heute'], pruef['heute']
            assert seite.locator('.today-attention-item').filter(has_text='Neue Akte?').count() == 1
            ohne_ueberlauf('heute_1280')
            bild('heute-vorschlag', ganz=False)
            karte.get_by_role('button', name='Akte anlegen').click()
            hinweis = seite.locator('.today-notice').filter(has_text='Akte öffnen')
            hinweis.wait_for(timeout=10000)
            pruef['heute_antwort'] = hinweis.inner_text()
            assert pruef['heute_antwort'].startswith('Akte „Projekt Atlas“ angelegt, 4 Quellen zugeordnet.')
            assert projekte() == ['Projekt Atlas']
            seite.wait_for_timeout(1500)
            assert seite.locator('.today-attention-item').filter(has_text='Neue Akte?').count() == 0, 'Der Punkt ist nach dem Klick weg'
            bild('heute-angelegt', ganz=False)
            hinweis.get_by_role('link', name='Akte öffnen').click()
            seite.wait_for_url('**/memory/akte/projekt:p-akte-*', timeout=10000)
            seite.wait_for_selector('section.akte', timeout=20000)
            # Zurück auf Anfang für die schmale Probe.
            instanz.anfrage('POST', f'/api/v1/akten/vorschlaege/{kennung}/zuruecknehmen')
            assert projekte() == []
            # 6. Schmal: 390 px, Akte und Heute ohne Überlauf.
            seite.set_viewport_size({'width': 390, 'height': 844})
            akte('projekt:n:atlas')
            seite.locator('section.akte-neue').wait_for(timeout=20000)
            seite.wait_for_timeout(600)
            ohne_ueberlauf('akte_390')
            breite = seite.evaluate("(() => { const k = document.querySelector('section.akte-neue'); return k.scrollWidth - k.clientWidth; })()")
            pruef['ueberlauf_zeile_390'] = breite
            assert breite <= 1, breite
            bild('akte-390')
            seite.goto(basis + '/today')
            seite.locator('.today-attention-item').filter(has_text='Neue Akte?').wait_for(timeout=20000)
            seite.wait_for_timeout(600)
            ohne_ueberlauf('heute_390')
            bild('heute-390', ganz=False)
            browser.close()
        server.should_exit = True
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'ergebnis.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1))
    print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
