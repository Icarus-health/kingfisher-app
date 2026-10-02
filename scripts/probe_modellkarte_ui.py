#!/usr/bin/env python3
"""Browserprobe für die Modellkarte: echte Oberfläche, echter Sidecar, ein Ollama aus Attrappe (kein Netz, kein Modell).

Geprüft wird in Chromium (Playwright), Einstellungen, Lokale KI:

* die Zeile „Zusammen: … GB Arbeitsspeicher am Tag, … nachts, … Festplatte (frei: …)“ auf einem 32-GB-Gerät, dazu der
  Satz, warum für die Antwort ein kleineres Modell gewählt wurde, und die ruhige Warnung für die Nacht;
* ein knappes Gerät (wenig freier Platz): Warnung zur Festplatte mit Vorschlag; unbekannter Platz wird nicht geraten;
* ein Modell, das Ollama an seinen Server weiterreicht, steht als „läuft in Ollamas Cloud“ da, fehlt in der lokalen
  Auswahl und lässt sich für „Antworten formulieren“ nur mit Einwilligung wählen, für das Ordnen im Hintergrund nie;
* das Laden wird bei zu wenig Platz mit einem Satz abgelehnt; die Konsole bleibt leer.

Aufruf: `python scripts/probe_modellkarte_ui.py --ausgabe DIR [--chromium PFAD]` (PYTHONPATH: sidecar).
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

WURZEL = Path(__file__).resolve().parents[1]
for pfad in (WURZEL / 'sidecar', WURZEL):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
CLOUD = 'deepseek-v4.1-flash:cloud'


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

    daten = tempfile.mkdtemp(prefix='probe-modellkarte-')
    os.environ.update(ICARUS_DATA_DIR=daten, ICARUS_PROVIDER='ollama', ICARUS_MODEL='standard-modell',
                      ICARUS_BASE_URL='http://127.0.0.1:11434/v1')
    os.environ.pop('ICARUS_SIDECAR_TOKEN', None)

    import uvicorn
    from playwright.sync_api import sync_playwright
    from icarus_memory import device_profile, providers
    from icarus_memory.server import create_app
    from tests.ollama_fake import FakeOllama

    fake = FakeOllama(installiert=['standard-modell', 'qwen3.5:9b', 'bge-m3'], cloud=[CLOUD])
    # Die Liste der Einrichtung fragt Ollama über providers; hier kommt sie aus derselben Attrappe.
    providers.verfuegbare_modelle = lambda *a, **k: [n if ':' in n else n + ':latest' for n in fake.installiert] + fake.cloud
    app = create_app()
    app.state.ollama_transport = fake.transport
    app.state.ollama_inventar.vergiss()
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

    def melde(gb: int, frei_gb: int | None):
        bericht = {'platform': 'macos', 'chip': 'Apple M2 Max', 'memory_bytes': gb * 1024**3}
        if frei_gb is not None:
            bericht['disk_free_bytes'] = frei_gb * 1024**3
        antwort = seite.request.post(basis + '/api/v1/device/profile', data=bericht)
        assert antwort.status == 200, antwort.text()

    def karte(name: str):
        seite.goto(basis + '/settings#technik-modelle')
        seite.reload()
        seite.wait_for_selector('.model-rec-total', timeout=15000)
        return seite.locator('.model-recommendation')

    def bild(name: str):
        pfad = args.ausgabe / f'modellkarte-{name}.png'
        seite.locator('.model-recommendation').screenshot(path=str(pfad))
        ergebnis['bilder'].append(str(pfad))

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=['--no-sandbox'])
        seite = browser.new_context(viewport={'width': 1100, 'height': 1100}).new_page()
        seite.on('console', lambda m: ergebnis['konsole'].append(f'{m.type}: {m.text}') if m.type in ('error', 'warning') else None)
        seite.on('pageerror', lambda e: ergebnis['konsole'].append(f'pageerror: {e}'))
        seite.goto(basis + '/today')

        # 1. 32 GB, reichlich Platz: die Zeile, der Satz zur kleineren Wahl, die Warnung für die Nacht
        melde(32, 210)
        wurzel = karte('32')
        zeile = wurzel.locator('.model-rec-total p').first.inner_text()
        pruef['zeile_32'] = zeile
        assert zeile == 'Zusammen: 26 GB Arbeitsspeicher am Tag, 25 GB nachts, 38,6 GB Festplatte (frei: 210 GB).', zeile
        text = wurzel.inner_text()
        assert 'gemma4:12b statt qwen3.6:35b' in text, 'Satz zur kleineren Wahl fehlt'
        assert 'nachts zusammen' in text, 'Satz zur kleineren Wahl für die Nacht fehlt'
        assert wurzel.locator('.model-rec-total .model-rec-warn').count() == 0, 'die Vorauswahl selbst passt, keine Warnung'
        bild('32-gb')

        # 2. Knapper Platz: Warnung zur Festplatte mit Vorschlag
        melde(32, 12)
        wurzel = karte('knapp')
        gesamt = wurzel.locator('.model-rec-total').inner_text()
        pruef['knapp'] = gesamt
        assert '(frei: 12 GB)' in gesamt and 'Festplatte' in gesamt and 'frei sind etwa 12 GB' in gesamt and 'Kleiner:' in gesamt, gesamt
        bild('platz-knapp')

        # 3. Platz unbekannt: gesagt, nicht geraten
        melde(32, None)
        device_profile.freier_platz_gb = lambda *a, **k: None  # auch die eigene Messung weiß es nicht (Container)
        wurzel = karte('unbekannt')
        gesamt = wurzel.locator('.model-rec-total').inner_text()
        pruef['unbekannt'] = gesamt
        assert 'freier Platz unbekannt' in gesamt and 'frei sind etwa' not in gesamt, gesamt

        # 4. Laden bei zu wenig Platz wird mit einem Satz abgelehnt
        melde(32, 6)
        wurzel = karte('ablehnen')
        assert wurzel.get_by_role('button', name='Antworten formulieren: Einrichten').is_visible()
        wurzel.get_by_role('button', name='Antworten formulieren: Einrichten').click()
        wurzel.get_by_role('button', name='Laden und einrichten').click()
        seite.wait_for_selector('.model-rec-note[role=alert]', timeout=15000)
        ablehnung = seite.locator('.model-rec-note').inner_text()
        pruef['ablehnung'] = ablehnung
        assert 'Festplatte' in ablehnung and 'frei sind etwa 6 GB' in ablehnung, ablehnung
        assert not any(pfad == '/api/pull' for _, pfad, _ in fake.anfragen), 'es wurde geladen'
        bild('ablehnung')

        # 5. Cloud über Ollama: benannt, nicht lokal angeboten
        melde(32, 210)
        wurzel = karte('cloud')
        hinweis = wurzel.inner_text()
        assert 'Läuft in Ollamas Cloud, nicht auf diesem Rechner' in hinweis and CLOUD in hinweis, hinweis
        seite.get_by_role('button', name='Modell verwalten').click()
        seite.wait_for_selector('form[aria-label="Lokales Modell einrichten"]', timeout=15000)
        seite.wait_for_function("document.querySelectorAll('select option').length > 3")
        lokal = seite.get_by_label('Installiertes Ollama-Modell').locator('option').all_inner_texts()
        pruef['lokale_auswahl'] = lokal
        assert CLOUD not in lokal and 'qwen3.5:9b' in lokal, lokal
        assert 'Läuft in Ollamas Cloud' in seite.locator('section.compact-model[aria-label="Lokale KI"]').inner_text()
        bild('cloud')

        # 6. Fortgeschrittene: Hintergrund nie, Antwort nur mit Einwilligung
        seite.locator('.model-rec-expert summary').click()
        seite.wait_for_selector('.model-role-card', timeout=15000)
        antwort_karte = seite.locator('.model-role-card', has_text='Antworten formulieren')
        antwort_karte.get_by_role('button', name='Cloud statt dieses Rechners nutzen …').click()
        antwort_karte.get_by_role('combobox', name='Anbieter').select_option('ollama-cloud')
        antwort_karte.get_by_role('combobox', name='Cloud-Modell').select_option(CLOUD)
        senden = antwort_karte.get_by_role('button', name='Cloud zuschalten')
        assert senden.is_disabled(), 'ohne Einwilligung darf nichts gehen'
        assert 'Ollama (USA)' in antwort_karte.inner_text()
        antwort_karte.get_by_role('checkbox').check()
        senden.click()
        seite.wait_for_selector('text=Cloud ist für diese Aufgabe zugeschaltet', timeout=15000)
        pruef['antwort_karte'] = antwort_karte.inner_text()
        assert 'läuft in Ollamas Cloud' in antwort_karte.inner_text()
        hintergrund = seite.locator('.model-role-card', has_text='Im Hintergrund ordnen')
        assert hintergrund.get_by_role('button', name='Cloud statt dieses Rechners nutzen …').count() == 0, 'Hintergrund ohne Cloud'
        optionen = hintergrund.get_by_role('combobox', name='Modell').locator('option').all_inner_texts()
        pruef['hintergrund_auswahl'] = optionen
        assert CLOUD not in optionen, optionen
        assert 'qwen3.6:35b' not in hintergrund.inner_text(), 'das ersetzte große Modell ist kein „passendes“ Angebot'
        bild('fortgeschritten')
        browser.close()
    server.should_exit = True
    faden.join(timeout=5)
    # Die Ablehnung (Schritt 4) meldet der Browser als Ressourcenfehler 422; sie ist gewollt und genau einmal da.
    ablehnungen = [z for z in ergebnis['konsole'] if '422' in z]
    assert len(ablehnungen) == 1, ergebnis['konsole']
    ergebnis['konsole'] = [z for z in ergebnis['konsole'] if z not in ablehnungen]
    ergebnis['ok'] = not ergebnis['konsole']
    (args.ausgabe / 'modellkarte-probe.json').write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': ergebnis['ok'], 'konsole': ergebnis['konsole'], 'bilder': ergebnis['bilder'],
                      'pruefungen': pruef}, ensure_ascii=False, indent=1))
    return 0 if ergebnis['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
