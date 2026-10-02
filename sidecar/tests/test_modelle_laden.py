"""Laden im Hintergrund (Fremdprobe 2, Befunde 6 und 7): ein Klick, der Lauf hängt an keiner Seite, eine Größe aus
einer Quelle, ehrliche Sätze solange er läuft und danach."""
from __future__ import annotations

import threading

from icarus_memory.model_pull import LAEDT_SATZ
from icarus_memory.model_recommendation import empfehle_alle, Geraet, orchester_bedarf
from tests.ollama_fake import FakeOllama
from tests.test_model_roles_routes import app_und_client, bereit, geraet  # noqa: F401 - Fixture


def test_ein_klick_laedt_alle_offenen_aufgaben_nacheinander(app_und_client):
    app, client = app_und_client
    geraet(client, 32)
    fake = bereit(app, FakeOllama())
    assert client.post('/api/v1/models/laden', json={}).status_code == 422  # nur bestätigt
    antwort = client.post('/api/v1/models/laden', json={'bestaetigt': True})
    assert antwort.status_code == 202
    app.state.pull_manager.warte()
    stand = client.get('/api/v1/models/laden').json()
    assert stand['laeuft'] is False and stand['prozent'] == 100 and stand['satz'] == ''
    assert stand['fehlgeschlagen'] == [] and sorted(stand['eingerichtet']) == sorted(
        ['frage', 'antwort', 'pruefung', 'hintergrund', 'einbettung'])
    # Ein Modell, das zwei Aufgaben haben, wird nur einmal geholt.
    geholt = [b['model'] for m, p, b in fake.anfragen if p == '/api/pull']
    assert len(geholt) == len(set(geholt))
    rollen = {z['rolle']: z['status'] for z in client.get('/api/v1/models/recommendation').json()['rollen']}
    assert set(rollen.values()) == {'eingerichtet'}


def test_die_groesse_kommt_aus_einer_quelle(app_und_client):
    """Was der Lauf als Größe nennt, ist, was die Karte vorher sagt: `orchester.festplatte_noch_gb`."""
    app, client = app_und_client
    geraet(client, 32)
    bereit(app, FakeOllama())
    vorher = client.get('/api/v1/models/recommendation').json()['orchester']
    halt = threading.Event()
    bereit(app, FakeOllama(warte=halt))
    stand = client.post('/api/v1/models/laden', json={'bestaetigt': True}).json()
    assert stand['gesamt_gb'] == round(vorher['festplatte_noch_gb'], 1) and stand['laeuft'] is True
    halt.set()
    app.state.pull_manager.warte()
    erwartet = orchester_bedarf(empfehle_alle(Geraet(arbeitsspeicher_gb=32)), Geraet(arbeitsspeicher_gb=32))
    assert vorher['festplatte_noch_gb'] == erwartet['festplatte_noch_gb']


def test_waehrend_des_ladens_sagt_eine_antwort_ehrlich_wie_weit_es_ist(app_und_client, monkeypatch):
    app, client = app_und_client
    geraet(client, 32)
    halt = threading.Event()
    bereit(app, FakeOllama(warte=halt))
    # Ohne Modell für Antworten: wie auf einem frischen Rechner.
    monkeypatch.setattr(app.state.agent, '_provider', None)
    client.post('/api/v1/models/laden', json={'bestaetigt': True})
    stand = client.get('/api/v1/models/laden').json()
    assert stand['laeuft'] is True and 0 <= stand['prozent'] < 100
    assert stand['satz'] == LAEDT_SATZ.format(prozent=stand['prozent'])
    zug = app.state.agent.send('Was steht heute an?')
    assert zug.reply.startswith(f"Kingfisher lädt noch sein Sprachmodell ({stand['prozent']} %).")
    assert 'Briefing' in zug.reply and 'kein Modell' not in zug.reply and zug.context['modell_laedt'] is True
    # Ein zweiter Klick startet keinen zweiten Lauf.
    assert client.post('/api/v1/models/laden', json={'bestaetigt': True}).status_code == 409
    halt.set()
    app.state.pull_manager.warte()
    assert client.get('/api/v1/models/laden').json()['laeuft'] is False


def test_ein_fehlschlag_haelt_die_uebrigen_nicht_auf_und_niemand_sagt_bereit(app_und_client):
    app, client = app_und_client
    geraet(client, 32)
    bereit(app, FakeOllama(), bestanden=False)
    client.post('/api/v1/models/laden', json={'bestaetigt': True})
    app.state.pull_manager.warte()
    stand = client.get('/api/v1/models/laden').json()
    # Alle fünf wurden versucht, obwohl der erste schon scheiterte; eingerichtet ist keiner.
    assert len(stand['auftraege']) == 5 and stand['laeuft'] is False
    assert sorted(stand['fehlgeschlagen']) == ['antwort', 'einbettung', 'frage', 'hintergrund', 'pruefung']
    assert stand['eingerichtet'] == [] and stand['satz'] == ''
    assert all(a['phase'] in ('fertig', 'fehler') for a in stand['auftraege'])
    rollen = {z['rolle']: z['status'] for z in client.get('/api/v1/models/recommendation').json()['rollen']}
    assert rollen['antwort'] != 'eingerichtet'


def test_nichts_offen_heisst_nichts_laden(app_und_client):
    app, client = app_und_client
    geraet(client, 32)
    bereit(app, FakeOllama())
    client.post('/api/v1/models/laden', json={'bestaetigt': True})
    app.state.pull_manager.warte()
    fake = bereit(app, FakeOllama(installiert=list(FakeOllama().installiert) + [
        a['modell'] for a in client.get('/api/v1/models/laden').json()['auftraege']]))
    client.post('/api/v1/models/laden', json={'bestaetigt': True})
    assert not [p for _, p, _ in fake.anfragen if p == '/api/pull']
