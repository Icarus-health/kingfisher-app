#!/usr/bin/env python3
"""Browserprobe für die Einstellungen in zwei Ebenen (M3, docs/47-einstellungen.md): echte Oberfläche, echter Sidecar,
ein Ollama aus Attrappe, leerer Bestand, kein Netz.

Geprüft wird in Chromium (Playwright):

* Breite: bei 390, 768 und 1280 px läuft keiner der fünf Bereiche (und „Für Techniker“, alle Abschnitte aufgeklappt) über
  den Bildschirmrand hinaus; die Seitenleiste deckt keinen Reiter zu; Bilder je Breite und Bereich.
* Vorne kein Fachwort: Der sichtbare Text der vier vorderen Bereiche enthält keines der Wörter aus `FACHWOERTER`
  (gelesen aus `gliederung.ts`, eine Quelle).
* Vier Reiter vorne, „Für Techniker“ abgesetzt dahinter, mit dem Satz, dass nichts geändert werden muss; beim Öffnen der
  Seite ist dort nichts geladen (kein Abruf der Modellkarte), erst beim Aufklappen.
* Was Kingfisher darf: fünf Schalter, alle aus; bei jedem ein Satz, was den Rechner verlässt. Die Quellen zum
  Anklicken: ein Klick fügt hinzu, der zweite entfernt (Abruf als Attrappe). Wetter ohne Ort öffnet nur die Suche.
  Wegezeit lässt sich erst einschalten, wenn sie rechnen kann (Startort und Kartendienst, Befund 19). Cloud ohne Zugang sagt das in einem Satz; mit Zugang
  braucht es die Zustimmung, und ein Klick nimmt es zurück.
* Kingfisher und du: Name und Startort speichern und bleiben nach dem Neuladen; Zeitzone steht da.
* Alte Verweise (`#world`, `#model`, `#memory`) kommen am neuen Ort an.

Aufruf: `python scripts/probe_einstellungen_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar und Wurzel).
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
BREITEN = (390, 768, 1280)
VORNE = ('zugaenge', 'darf', 'ich', 'sicherung')
ALLE = VORNE + ('technik',)
RSS = b'''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Probe</title>
<item><title>Eine Meldung</title><link>https://nachrichten.example/1</link><guid>1</guid>
<pubDate>Wed, 30 Sep 2026 08:00:00 +0000</pubDate><description>Text</description></item></channel></rss>'''

ABLAUF_JS = """() => {
  const w = document.documentElement.clientWidth, aus = [];
  for (const el of document.querySelectorAll('.settings-shell *')) {
    if (el.closest('.sidebar')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    if (r.right > w + 1 || r.left < -1) { const weg = []; for (let p = el.parentElement, i = 0; p && i < 4; p = p.parentElement, i++) weg.push(p.tagName.toLowerCase() + '.' + String(p.className).split(' ')[0]); aus.push(el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0] + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + ' in ' + weg.join(' < ')); }
  }
  return { seite: document.documentElement.scrollWidth - w, aus: aus.slice(0, 12), breite: w };
}"""
UEBERLAPP_JS = """() => {
  const leiste = document.querySelector('.sidebar').getBoundingClientRect();
  const knoepfe = [...document.querySelectorAll('.settings-section-nav button')].map(b => b.getBoundingClientRect());
  const schnitt = knoepfe.filter(r => r.left < leiste.right - 1 && r.right > leiste.left + 1 && r.top < leiste.bottom - 1 && r.bottom > leiste.top + 1);
  return { leiste: [Math.round(leiste.left), Math.round(leiste.right), Math.round(leiste.top), Math.round(leiste.bottom)], verdeckt: schnitt.length, knoepfe: knoepfe.length };
}"""


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def fachwoerter_aus_gliederung() -> list[str]:
    quelltext = (WURZEL / 'app' / 'kingfisher' / 'src' / 'Einstellungen' / 'gliederung.ts').read_text(encoding='utf-8')
    block = quelltext.split('export const FACHWOERTER', 1)[1].split('];', 1)[0]
    return re.findall(r'"([^"]+)"', block)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausgabe', type=Path, required=True)
    parser.add_argument('--chromium', default=CHROMIUM)
    args = parser.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)

    daten = tempfile.mkdtemp(prefix='probe-einstellungen-')
    os.environ.update(ICARUS_DATA_DIR=daten, ICARUS_PROVIDER='ollama', ICARUS_MODEL='standard-modell',
                      ICARUS_BASE_URL='http://127.0.0.1:11434/v1')
    for name in ('ICARUS_SIDECAR_TOKEN', 'ICARUS_ORS_KEY', 'ICARUS_GOOGLE_ROUTES_KEY', 'OPENAI_API_KEY', 'LLM_API_KEY', 'ANTHROPIC_API_KEY', 'KINGFISHER_USER_NAME'):
        os.environ.pop(name, None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import providers, world_sources
    from icarus_memory.server import create_app
    from icarus_memory.welt_briefing_routes import dienst as welt_dienst
    from tests.ollama_fake import FakeOllama

    fake = FakeOllama(installiert=['standard-modell', 'bge-m3'], cloud=[])
    providers.verfuegbare_modelle = lambda *a, **k: [n if ':' in n else n + ':latest' for n in fake.installiert]
    world_sources._validate_url = lambda url: url          # kein Netz: die Adresse gilt, der Abruf ist eine Attrappe
    app = create_app()
    app.state.ollama_transport = fake.transport
    app.state.ollama_inventar.vergiss()
    welt_dienst(app)._abrufen = lambda url: RSS
    port = freier_port()
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    faden = threading.Thread(target=server.run, daemon=True)
    faden.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    basis = f'http://127.0.0.1:{port}'
    ergebnis: dict = {'ok': False, 'pruefungen': {}, 'konsole': [], 'bilder': []}
    pruef = ergebnis['pruefungen']
    fach = fachwoerter_aus_gliederung()
    anfragen: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        seite = browser.new_context(viewport={'width': 1280, 'height': 1000}).new_page()
        seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
        seite.on('request', lambda r: anfragen.append(r.url))

        def oeffne(kennung: str = 'zugaenge', breite: int = 1280):
            seite.set_viewport_size({'width': breite, 'height': 1000})
            seite.goto(basis + '/settings#' + kennung)
            seite.reload()
            seite.wait_for_selector('.settings-section-nav')
            alt = {'world': 'darf', 'model': 'technik', 'memory': 'technik'}
            panel = kennung if kennung in ALLE else 'technik' if kennung.startswith('technik') else alt.get(kennung, 'zugaenge')
            seite.wait_for_selector(f'#settings-{panel}:not([hidden])')
            time.sleep(0.6)

        def bild(name: str):
            pfad = args.ausgabe / f'einstellungen-{name}.png'
            seite.screenshot(path=str(pfad), full_page=True)
            ergebnis['bilder'].append(str(pfad))

        def schalter(beschriftung: str):
            return seite.get_by_role('switch', name=re.compile(re.escape(beschriftung)))

        # 1. Reiter: vier vorne, „Für Techniker“ abgesetzt; beim Öffnen ist hinten nichts geladen
        oeffne('zugaenge')
        reiter = [b.inner_text() for b in seite.locator('.settings-section-nav button').all()]
        pruef['reiter'] = reiter
        assert reiter == ['Zugänge', 'Was Kingfisher darf', 'Kingfisher und du', 'Sicherung', 'Für Techniker'], reiter
        assert seite.locator('.settings-section-hinten').inner_text() == 'Für Techniker'
        pruef['technik_beim_oeffnen_nicht_geladen'] = not any('/models/recommendation' in a for a in anfragen)
        assert pruef['technik_beim_oeffnen_nicht_geladen'], 'Die Modellkarte darf nicht geladen sein, bevor jemand sie aufschlägt'

        # 2. Kein Fachwort vorne (sichtbarer Text, eingeklappte Bereiche zählen nicht)
        for bereich in VORNE:
            oeffne(bereich)
            text = seite.locator(f'#settings-{bereich}').inner_text()
            funde = [w for w in fach if re.search(rf'(?<![\wäöüÄÖÜß]){re.escape(w)}(?![\wäöüÄÖÜß])', text, re.I)]
            pruef[f'fachwoerter_{bereich}'] = funde
            assert not funde, f'{bereich}: Fachwort vorne: {funde}'

        # 3. Was Kingfisher darf: fünf Schalter, alle aus, je ein Satz
        oeffne('darf')
        titel = ['Morgens das Wetter holen', 'Eine Meldung aus der Welt zeigen', 'Wegezeit berechnen', 'Beim Anmelden starten', 'Cloud für Fragen und Antworten nutzen']
        for name in titel:
            s = schalter(name)
            s.wait_for(timeout=15000)
            assert not s.is_checked(), f'{name} muss aus sein'
        pruef['fuenf_schalter_alle_aus'] = True
        darf_text = seite.locator('#settings-darf').inner_text()
        assert darf_text.count('verlässt') + darf_text.count('verlassen') >= 5, 'bei jedem Schalter steht, was den Rechner verlässt'
        assert 'Es verlässt nichts den Rechner. Kingfisher öffnet sich' in darf_text
        bild('darf-aus-1280')

        # 4. Quellen zum Anklicken: ein Klick fügt hinzu, der zweite entfernt
        assert seite.get_by_role('group', name='Quellen zum Anklicken').count() == 0, 'ohne Schalter keine Quellen'
        schalter('Eine Meldung aus der Welt zeigen').click()
        gruppe = seite.get_by_role('group', name='Quellen zum Anklicken')
        gruppe.wait_for(timeout=15000)
        knoepfe = gruppe.get_by_role('button')
        namen = [k.locator('strong').inner_text() for k in knoepfe.all()]
        pruef['vorgaben'] = namen
        assert namen == ['tagesschau', 'Deutschlandfunk', 'heise online', 'ZEIT ONLINE'], namen
        assert all(k.get_attribute('aria-pressed') == 'false' for k in knoepfe.all())
        assert 'noch nicht abgerufen' in seite.locator('#settings-darf').inner_text()
        bild('darf-quellen-1280')
        tages = knoepfe.nth(0)
        tages.click()
        seite.wait_for_function("document.querySelector('.welt-vorgabe-knopf').getAttribute('aria-pressed') === 'true'", timeout=15000)
        stand = seite.request.get(basis + '/api/v1/welt/briefing').json()
        pruef['nach_klick_eins'] = [f['label'] for f in stand['feeds']]
        assert [f['label'] for f in stand['feeds']] == ['tagesschau'] and stand['aktiv'] is True
        knoepfe.nth(0).click()
        seite.wait_for_function("document.querySelector('.welt-vorgabe-knopf').getAttribute('aria-pressed') === 'false'", timeout=15000)
        stand = seite.request.get(basis + '/api/v1/welt/briefing').json()
        pruef['nach_klick_zwei'] = [f['label'] for f in stand['feeds']]
        assert stand['feeds'] == [], 'der zweite Klick entfernt die Quelle'
        # eigene Quelle: ohne https getippt, Kingfisher ergänzt
        seite.get_by_label('Eigene Quelle: Adresse').fill('nachrichten.example/rss.xml')
        seite.get_by_role('button', name='Quelle hinzufügen').click()
        seite.wait_for_selector('.welt-liste >> text=nachrichten.example', timeout=15000)
        pruef['eigene_quelle'] = seite.locator('.welt-liste').first.inner_text()
        stand = seite.request.get(basis + '/api/v1/welt/briefing').json()
        assert stand['feeds'][0]['url'] == 'https://nachrichten.example/rss.xml'
        seite.get_by_role('button', name='Entfernen').first.click()
        seite.wait_for_function("!document.querySelector('.welt-liste')", timeout=15000)
        schalter('Eine Meldung aus der Welt zeigen').click()
        seite.wait_for_function("!document.querySelector('.welt-vorgabe-knopf')", timeout=15000)

        # 5. Wetter ohne Ort: der Schalter öffnet nur die Suche, gespeichert wird nichts
        schalter('Morgens das Wetter holen').click()
        seite.get_by_label('Für welchen Ort soll das Wetter gelten?').wait_for(timeout=15000)
        assert seite.request.get(basis + '/api/v1/wetter/einstellungen').json()['aktiv'] is False
        pruef['wetter_ohne_ort_nur_suche'] = True
        schalter('Morgens das Wetter holen').click()

        # 6. Wegezeit: Einschalten erst, wenn es rechnen kann (Fremdprobe, Befund 19). Ohne Startort ist der Schalter
        # gesperrt, und die Karte bietet das Feld an; mit Startort, aber ohne Kartendienst sagt sie das in einem Satz.
        assert schalter('Wegezeit berechnen').is_disabled(), 'ohne Startort lässt sich die Wegezeit nicht einschalten'
        seite.wait_for_selector('#settings-darf >> text=Für die Wegezeit fehlt noch dein Startort')
        assert seite.locator('#wegezeit-startort').count() == 1, 'das Feld für den Startort steht auf der Karte'
        pruef['wegezeit_ohne_startort_gesperrt'] = True
        bild('darf-wegezeit-1280')
        oeffne('ich')
        seite.get_by_label('Von wo startest du meistens?').fill('Musterstraße 1, 65183 Wiesbaden')
        seite.get_by_label('Von wo startest du meistens?').locator('xpath=ancestor::form').get_by_role('button', name='Speichern').click()
        seite.wait_for_selector('#settings-ich >> text=Startort gespeichert')
        seite.get_by_label('Wie soll Kingfisher dich nennen?').fill('Lea')
        seite.get_by_label('Wie soll Kingfisher dich nennen?').locator('xpath=ancestor::form').get_by_role('button', name='Speichern').click()
        seite.wait_for_selector('#settings-ich >> text=Kingfisher grüßt dich künftig mit')
        ich_text = seite.locator('#settings-ich').inner_text()
        pruef['zeitzone'] = re.search(r'Zeitzone: \S+', ich_text).group(0)
        assert 'Zeitzone: Europe/Berlin' in ich_text and 'Kreis' in ich_text
        bild('ich-1280')
        oeffne('ich')
        assert seite.get_by_label('Von wo startest du meistens?').input_value() == 'Musterstraße 1, 65183 Wiesbaden'
        assert seite.get_by_label('Wie soll Kingfisher dich nennen?').input_value() == 'Lea'
        pruef['name_und_startort_bleiben'] = True
        oeffne('darf')
        schalter('Wegezeit berechnen').wait_for()
        seite.wait_for_selector('#settings-darf >> text=keine Apple Karten')
        assert schalter('Wegezeit berechnen').is_disabled(), 'ohne Kartendienst lässt sich die Wegezeit nicht einschalten'
        assert seite.locator('#settings-darf').get_by_role('link', name=re.compile('Eigener Kartendienst')).count() == 1
        pruef['wegezeit_ohne_dienst_gesperrt'] = True
        # Ein Techniker hinterlegt den Schlüssel; danach geht der Schalter.
        assert seite.request.put(basis + '/api/v1/wegezeit/schluessel',
                                 data={'dienst': 'openrouteservice', 'schluessel': 'probe-schluessel-123'}).ok
        oeffne('darf')
        schalter('Wegezeit berechnen').click()
        seite.wait_for_selector('#settings-darf >> text=Wegezeit wird berechnet.')
        assert schalter('Wegezeit berechnen').is_checked()
        seite.wait_for_selector('#settings-darf >> text=Startort: Musterstraße 1')
        schalter('Wegezeit berechnen').click()
        seite.wait_for_function("!document.querySelector('#wegezeit-mittel')", timeout=15000)

        # 7. Cloud: ohne Zugang ein Satz, mit Zugang Zustimmung, ein Klick zurück
        schalter('Cloud für Fragen und Antworten nutzen').click()
        seite.wait_for_selector('#settings-darf >> text=Dafür braucht es einen Zugang bei einem Cloudanbieter')
        rollen = seite.request.get(basis + '/api/v1/models/roles').json()
        assert not any(r['wirksam']['quelle'] == 'cloud' for r in rollen['rollen'])
        pruef['cloud_ohne_zugang'] = True
        seite.get_by_role('button', name='Verstanden').click()
        os.environ['OPENAI_API_KEY'] = 'sk-synthetisch-fuer-die-probe'
        oeffne('darf')
        schalter('Cloud für Fragen und Antworten nutzen').click()
        einschalten = seite.get_by_role('button', name='Cloud einschalten')
        einschalten.wait_for(timeout=15000)
        assert einschalten.is_disabled(), 'ohne Zustimmung geht nichts'
        seite.get_by_label(re.compile('Ich willige ein')).check()
        assert not einschalten.is_disabled()
        bild('darf-cloud-frage-1280')
        einschalten.click()
        seite.wait_for_selector('#settings-darf >> text=Fragen und Antworten laufen jetzt über')
        rollen = seite.request.get(basis + '/api/v1/models/roles').json()
        in_cloud = sorted(r['rolle'] for r in rollen['rollen'] if r['wirksam']['quelle'] == 'cloud')
        pruef['cloud_an_fuer'] = in_cloud
        assert in_cloud == ['antwort', 'frage'], in_cloud
        schalter('Cloud für Fragen und Antworten nutzen').click()
        seite.wait_for_selector('#settings-darf >> text=bleiben wieder auf diesem Rechner')
        rollen = seite.request.get(basis + '/api/v1/models/roles').json()
        assert not any(r['wirksam']['quelle'] == 'cloud' for r in rollen['rollen'])
        pruef['cloud_wieder_aus'] = True
        os.environ.pop('OPENAI_API_KEY', None)

        # 8. Für Techniker: der Satz, alles eingeklappt, Laden erst beim Aufklappen
        anfragen.clear()
        oeffne('technik')
        text = seite.locator('#settings-technik').inner_text()
        assert 'Hier muss nichts geändert werden' in text
        offene = seite.locator('.einstellungen-aufklapp[open]').count()
        pruef['technik_offen_beim_start'] = offene
        assert offene == 0 and seite.locator('.einstellungen-aufklapp').count() == 16  # mit „Microsoft-Anmeldung vorbereiten“ (M5) und „Updates ohne App“
        assert not any('/models/recommendation' in a for a in anfragen)
        bild('technik-zu-1280')
        seite.locator('#technik-modelle > summary').click()
        seite.wait_for_selector('.model-recommendation', timeout=15000)
        assert any('/models/recommendation' in a for a in anfragen)
        pruef['technik_laedt_beim_aufklappen'] = True

        # 9. Alte Verweise kommen am neuen Ort an
        oeffne('world')
        assert seite.locator('#settings-darf:not([hidden])').count() == 1
        oeffne('model')
        assert seite.locator('#settings-technik:not([hidden])').count() == 1 and seite.locator('#technik-modelle[open]').count() == 1
        oeffne('memory')
        assert seite.locator('#technik-suchindex[open]').count() == 1
        pruef['alte_verweise'] = True

        # 10. Breite: alle Bereiche bei 390, 768 und 1280 px; „Für Techniker“ mit allen Abschnitten aufgeklappt
        for breite in BREITEN:
            for bereich in ALLE:
                oeffne(bereich, breite)
                if bereich == 'technik':
                    for summary in seite.locator('.einstellungen-aufklapp > summary').all():
                        summary.click()
                    time.sleep(1.5)
                messung = seite.evaluate(ABLAUF_JS)
                ueber = seite.evaluate(UEBERLAPP_JS)
                pruef[f'breite_{breite}_{bereich}'] = {'seite': messung['seite'], 'aus': messung['aus'], 'verdeckt': ueber['verdeckt']}
                bild(f'{bereich}-{breite}')
                assert messung['seite'] <= 0, f'{bereich} bei {breite}: Seite {messung["seite"]} px breiter als das Fenster, {messung["aus"]}'
                assert not messung['aus'], f'{bereich} bei {breite}: ragt hinaus: {messung["aus"]}'
                assert ueber['verdeckt'] == 0, f'{bereich} bei {breite}: Seitenleiste deckt Reiter zu: {ueber}'

        browser.close()
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'einstellungen-ergebnis.json').write_text(json.dumps(ergebnis, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in ergebnis.items() if k != 'pruefungen'}, indent=2, ensure_ascii=False))
    print('Prüfungen:', len(pruef), '· Konsole:', ergebnis['konsole'] or 'leer')
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
