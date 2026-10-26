"""Paket T: echter Zwischenstand einer Gesprächsantwort, Vorwärmen und warmes Antwortmodell (synthetisch)."""
import json

import httpx
import pytest

from icarus_memory import gespraech_fortschritt, ollama_memory, zeitmessung
from icarus_memory.hintergrund import AMPEL
from icarus_memory.providers import OpenAICompatible, Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401  (Fixture)
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation

TEXT = 'Vorgang ORKA-17: Die Abnahme im Werk Süd ist am 14. November 2026 um 10 Uhr.'
QUESTION = 'Wann ist die Abnahme für ORKA-17?'


def test_fortschritt_fuehrt_nur_den_namen_des_schritts_und_nur_solange_es_laeuft():
    stand = gespraech_fortschritt.Fortschritt()
    assert stand.lesen('g1') == {'laeuft': False, 'schritt': None, 'satz': None}
    stand.beginne('g1')
    assert stand.lesen('g1')['satz'] == 'Liest deine Frage …'
    stand.setze('g1', 'antwort_modell')
    assert stand.lesen('g1') == {'laeuft': True, 'schritt': 'antwort_modell', 'satz': 'Wählt Quellen …'}
    stand.setze('g1', 'erfunden')  # unbekannte Schritte ändern nichts
    assert stand.lesen('g1')['schritt'] == 'antwort_modell'
    stand.setze('g2', 'suche')  # ein Gespräch ohne laufende Antwort bekommt keinen Stand
    assert stand.lesen('g2')['laeuft'] is False
    stand.ende('g1')
    assert stand.lesen('g1')['laeuft'] is False


def test_zeitmessung_meldet_den_beginn_jedes_abschnitts_nur_dem_beobachter():
    gesehen = []
    zeiten = zeitmessung.Zeiten()
    with zeitmessung.beobachten(gesehen.append):
        with zeitmessung.messen(zeiten, 'suche'):
            pass
        zeitmessung.beginne(zeiten, 'antwort_modell').ende()
    with zeitmessung.messen(zeiten, 'saetze_modell'):
        pass
    assert gesehen == ['suche', 'antwort_modell']

    def kaputt(_):
        raise RuntimeError('Beobachter fällt aus')

    with zeitmessung.beobachten(kaputt):
        zeitmessung.melde('suche')  # wirft nicht


def _welt(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    app.state.agent._working_memory_search = None
    response = client.post('/episodes', json={'title': 'orka-17.txt', 'body': TEXT,
                                              'occurred_at': '2026-10-02T10:00:00+02:00'})
    source = response.json()['id']
    store = WorkingMemoryStore(app.state.episodes)
    assert store.commit(store.pending(episode_ids=[source])[0], [{'start': 0, 'end': len(TEXT), 'kind': 'fact'}],
                        model='synthetisch')
    return app, client, provider


def test_waehrend_der_antwort_steht_der_echte_schritt_bereit(core, tmp_path, monkeypatch):
    app, client, provider = _welt(core, tmp_path, monkeypatch)
    gesehen = []
    conversation = _conversation(client)

    def complete_json(messages, *, max_tokens, schema):
        # Während das lokale Modell arbeitet, fragt die Oberfläche den Stand ab (ohne Sperre des Gesprächs).
        gesehen.append(client.get(f'/api/v1/conversations/{conversation}/fortschritt').json())
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in data['sources']]}))
        return Reply(text='kein json')

    provider.complete_json = complete_json
    try:
        _ask(client, conversation, QUESTION)
        assert gesehen[0] == {'laeuft': True, 'schritt': 'antwort_modell', 'satz': 'Wählt Quellen …'}
        assert gesehen[1] == {'laeuft': True, 'schritt': 'saetze_modell', 'satz': 'Formuliert …'}
        danach = client.get(f'/api/v1/conversations/{conversation}/fortschritt').json()
        assert danach == {'laeuft': False, 'schritt': None, 'satz': None}
        # Kein Fragetext im Stand.
        assert QUESTION not in json.dumps(gesehen, ensure_ascii=False)
    finally:
        client.close()
        _close_app(app)


def _ollama(monkeypatch, loaded=()):
    calls = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.method == 'GET':
            return httpx.Response(200, json={'models': [{'name': n} for n in loaded]})
        return httpx.Response(200, json={'response': ''})

    def make_client(*, timeout, trust_env, follow_redirects):
        assert trust_env is False and follow_redirects is False
        return httpx.Client(transport=httpx.MockTransport(handle), timeout=timeout,
                            trust_env=trust_env, follow_redirects=follow_redirects)

    monkeypatch.setattr(ollama_memory, '_ollama_client', make_client)
    monkeypatch.setattr(ollama_memory, '_VORGEWAERMT', {})
    return calls


def test_vorwaermen_laedt_das_lokale_antwortmodell_einmal_je_minute(monkeypatch):
    calls = _ollama(monkeypatch)
    lokal = OpenAICompatible('lokal-antwort:9b', base_url='http://127.0.0.1:11434/v1')
    uhr = iter([100.0, 130.0, 200.0])
    assert ollama_memory.vorwaermen(lokal, uhr=lambda: next(uhr)) == 'geladen'
    assert calls == [('POST', '/api/generate', {'model': 'lokal-antwort:9b', 'keep_alive': '5m'})]
    assert ollama_memory.vorwaermen(lokal, uhr=lambda: next(uhr)) == 'kuerzlich'
    assert ollama_memory.vorwaermen(lokal, beschaeftigt=lambda: True, uhr=lambda: next(uhr)) == 'beschaeftigt'
    assert len(calls) == 1


def test_vorwaermen_eines_eigenen_modells_entlaedt_erst_die_anderen(monkeypatch):
    calls = _ollama(monkeypatch, loaded=['kingfisher-pruefung:latest'])
    lokal = OpenAICompatible('kingfisher-antwort', base_url='http://127.0.0.1:11434/v1')
    assert ollama_memory.vorwaermen(lokal) == 'geladen'
    assert ('POST', '/api/generate', {'model': 'kingfisher-pruefung:latest', 'keep_alive': 0}) in calls
    assert calls[-1] == ('POST', '/api/generate', {'model': 'kingfisher-antwort:latest', 'keep_alive': '5m'})


@pytest.mark.parametrize('anbieter', [
    None,
    OpenAICompatible('cloud-antwort', api_key='synthetisch'),  # Cloud
    OpenAICompatible('lokal-antwort:9b', base_url='http://127.0.0.1:8080/v1'),  # lokal, aber kein Ollama
    OpenAICompatible('lokal-antwort:9b', base_url='http://ollama.example.invalid:11434/v1'),  # Ollama, nicht lokal
])
def test_ohne_lokales_ollama_modell_kein_einziger_aufruf(monkeypatch, anbieter):
    calls = _ollama(monkeypatch)
    assert ollama_memory.vorwaermen(anbieter) == 'kein_lokales_modell'
    ueber_cloud = OpenAICompatible('lokal-antwort:cloud', base_url='http://127.0.0.1:11434/v1')
    ueber_cloud.ueber_ollama_cloud = True
    assert ollama_memory.vorwaermen(ueber_cloud) == 'kein_lokales_modell'
    assert calls == []


def test_vorwaermen_route_wartet_nicht_und_ruft_ohne_lokales_modell_nichts(core, tmp_path, monkeypatch):
    calls = _ollama(monkeypatch)
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        # Die Attrappe ist lokal, aber kein Ollama: kein Aufruf.
        assert client.post('/api/v1/gespraech/vorwaermen').json() == {'ergebnis': 'kein_lokales_modell',
                                                                       'cloud': False}
        app.state.agent._provider = OpenAICompatible('lokal-antwort:9b', base_url='http://127.0.0.1:11434/v1')
        with AMPEL.vordergrund():  # ein Modellaufruf läuft: nicht dazwischen
            assert client.post('/api/v1/gespraech/vorwaermen').json()['ergebnis'] == 'beschaeftigt'
        assert gespraech_fortschritt.vorwaermen(app, im_hintergrund=False) == 'geladen'
        assert calls == [('POST', '/api/generate', {'model': 'lokal-antwort:9b', 'keep_alive': '5m'})]
    finally:
        client.close()
        _close_app(app)


def test_antwortmodell_bleibt_im_gespraech_fuenf_minuten_sonst_15_sekunden(monkeypatch):
    calls = _ollama(monkeypatch, loaded=['kingfisher-antwort:latest', 'kingfisher-frage:latest'])
    antwort = OpenAICompatible('kingfisher-antwort', base_url='http://127.0.0.1:11434/v1')
    frage = OpenAICompatible('kingfisher-frage', base_url='http://127.0.0.1:11434/v1')
    with ollama_memory.im_gespraech(antwort):
        with ollama_memory.managed_model(antwort):
            pass
        with ollama_memory.managed_model(frage):
            pass
    with ollama_memory.managed_model(antwort):
        pass
    halten = [body['keep_alive'] for method, _, body in calls if method == 'POST' and body['keep_alive'] != 0]
    assert halten == ['5m', '15s', '15s']
    # Die RAM-Regel bleibt: vor jedem Aufruf werden die anderen eigenen Modelle entladen.
    assert ('POST', '/api/generate', {'model': 'kingfisher-frage:latest', 'keep_alive': 0}) in calls
