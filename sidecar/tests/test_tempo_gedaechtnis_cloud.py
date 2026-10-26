"""Paket T: Gedächtnisantworten über die Cloud nur mit gültiger Einwilligung der Rolle `antwort`.

Alles synthetisch; die Cloud ist eine Attrappe, die festhält, was sie gesehen hätte.
"""
import copy
import json

import pytest

from icarus_memory import gedaechtnis_cloud, model_roles, satzantwort, working_memory_answers
from icarus_memory.model import Kind, Provenance, Sensitivity, SourceType
from icarus_memory.model_roles import RollenWahl, provider_fuer
from icarus_memory.providers import ProviderError, Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401  (Fixture)
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation

TEXT = 'Vorgang ORKA-17: Die Abnahme im Werk Süd ist am 14. November 2026 um 10 Uhr.'
QUESTION = 'Wann ist die Abnahme für ORKA-17?'
EINWILLIGUNG = '2026-10-26T09:00:00+00:00'
WAHL = {'modell': '', 'cloud': True, 'anbieter': 'anthropic', 'cloud_einwilligung': EINWILLIGUNG}


class Cloud:
    """Attrappe eines Cloudanbieters: nur `complete`, nicht lokal; antwortet auf die Auswahl mit allen S-Quellen."""

    name = 'anthropic'
    model = 'synthetisch-cloud'
    is_local = False

    def __init__(self, einwilligung=EINWILLIGUNG):
        self.calls = []
        self.cloud_einwilligung = gedaechtnis_cloud.markierung('antwort', 'anthropic', einwilligung)

    def complete(self, messages, tools):
        assert tools == []
        self.calls.append(copy.deepcopy(messages))
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            ids = [row['id'] for row in data['sources'] if row['id'].startswith('S')]
            return Reply(text='```json\n' + json.dumps({'status': 'source_reports', 'ids': ids}) + '\n```')
        raise ProviderError('Sätze: synthetisch nicht beantwortet')


def _welt(core, tmp_path, monkeypatch, wahl=WAHL, cloud=None):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    cloud = cloud or Cloud()
    agent = app.state.agent
    agent._provider = cloud
    agent._working_memory_search = None
    app.state.settings.model_roles = {'antwort': dict(wahl)} if wahl is not None else {}
    response = client.post('/episodes', json={'title': 'orka-17.txt', 'body': TEXT,
                                              'occurred_at': '2026-10-02T10:00:00+02:00'})
    assert response.status_code == 201
    source = response.json()['id']
    store = WorkingMemoryStore(app.state.episodes)
    snapshot = store.pending(episode_ids=[source])[0]
    assert store.commit(snapshot, [{'start': 0, 'end': len(TEXT), 'kind': 'fact'}], model='synthetisch')
    return app, client, cloud


def test_mit_einwilligung_waehlt_die_cloud_die_quellen_und_sagt_es(core, tmp_path, monkeypatch):
    app, client, cloud = _welt(core, tmp_path, monkeypatch)
    try:
        antwort = _ask(client, _conversation(client), QUESTION)
        kontext = antwort['metadata']['context']
        assert kontext['answer_contract']['status'] == 'working_reports'
        assert TEXT in antwort['content']
        # Frage und Textstelle gingen an den Anbieter, und die Antwort sagt das ehrlich.
        auswahl = json.loads(cloud.calls[0][-1]['content'])
        assert auswahl['question'] == QUESTION and TEXT in json.dumps(auswahl, ensure_ascii=False)
        assert kontext['gedaechtnis_cloud'] == {'anbieter': 'anthropic', 'modell': 'synthetisch-cloud',
                                                'gesendet': ['frage', 'textstellen']}
        assert kontext['answer_contract']['model_egress'] == 'external'
        # Die JSON-Pflicht steht in der Systemanweisung, das Schema dazu.
        assert 'ausschließlich mit einem einzigen JSON-Objekt' in cloud.calls[0][0]['content']
        # Sätze liefen ebenfalls über den eingegrenzten Cloudanbieter (zweiter Aufruf); ihr Scheitern führt zu Zitaten.
        assert len(cloud.calls) == 2
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('wahl', [
    None,  # keine Rollenwahl
    {**WAHL, 'cloud': False, 'anbieter': '', 'cloud_einwilligung': ''},  # Schalter aus
    {**WAHL, 'cloud_einwilligung': ''},  # ohne Einwilligung
    {**WAHL, 'cloud_einwilligung': 'gestern'},  # unlesbare Einwilligung
    {**WAHL, 'cloud_einwilligung': '2026-10-27T09:00:00+00:00'},  # andere Einwilligung als die des Anbieters
    {**WAHL, 'anbieter': 'openai'},  # anderer Anbieter als der gebaute
    {**WAHL, 'local_only': True},  # ausdrücklich nur lokal
])
def test_ohne_gueltige_einwilligung_geht_nichts_in_die_cloud(core, tmp_path, monkeypatch, wahl):
    app, client, cloud = _welt(core, tmp_path, monkeypatch, wahl=wahl)
    try:
        antwort = _ask(client, _conversation(client), QUESTION)
        assert cloud.calls == []
        assert TEXT not in antwort['content']
        assert antwort['metadata']['context'].get('answer_contract', {}).get('status') == 'local_only'
        assert 'gedaechtnis_cloud' not in antwort['metadata']['context']
    finally:
        client.close()
        _close_app(app)


def test_ohne_markierten_anbieter_keine_cloud(core, tmp_path, monkeypatch):
    """Ein nicht lokaler Standardanbieter (etwa aus der Umgebung) ist nicht der Anbieter der Einwilligung."""
    cloud = Cloud()
    del cloud.cloud_einwilligung
    app, client, cloud = _welt(core, tmp_path, monkeypatch, cloud=cloud)
    try:
        antwort = _ask(client, _conversation(client), QUESTION)
        assert cloud.calls == [] and TEXT not in antwort['content']
    finally:
        client.close()
        _close_app(app)


def test_widerruf_mitten_in_der_antwort_stoppt_den_naechsten_versand(core, tmp_path, monkeypatch):
    app, client, cloud = _welt(core, tmp_path, monkeypatch)
    original = cloud.complete

    def nach_der_auswahl_widerrufen(messages, tools):
        antwort = original(messages, tools)
        app.state.settings.model_roles = {'antwort': {**WAHL, 'cloud': False, 'anbieter': '', 'cloud_einwilligung': ''}}
        return antwort

    cloud.complete = nach_der_auswahl_widerrufen
    try:
        antwort = _ask(client, _conversation(client), QUESTION)
        assert len(cloud.calls) == 1  # die Sätze gingen nicht mehr hinaus
        assert TEXT in antwort['content']  # die schon gewählten Belege stehen wörtlich da
    finally:
        client.close()
        _close_app(app)


def test_ausgangspruefung_haelt_sensibles_zurueck(core, tmp_path, monkeypatch):
    app, client, cloud = _welt(core, tmp_path, monkeypatch)
    app.state.agent._store.record(kind=Kind.STATE, statement='Die Abnahme im Werk Süd ist am 14. November 2026',
                                  provenance=Provenance(source_type=SourceType.USER_STATED),
                                  sensitivity=Sensitivity.SENSITIVE)
    try:
        antwort = _ask(client, _conversation(client), QUESTION)
        assert cloud.calls == []
        assert antwort['metadata']['context']['answer_contract']['status'] == 'working_selection_failed'
    finally:
        client.close()
        _close_app(app)


def test_bestaetigte_eintraege_gehen_nie_in_die_cloud(core, tmp_path, monkeypatch):
    _, _, _, _, accept = core
    accept('project:orka', 'Bestätigt: ORKA-17 Abnahme verschoben, siehe Protokoll ORKA-17.')
    app, client, cloud = _welt(core, tmp_path, monkeypatch)
    try:
        _ask(client, _conversation(client), QUESTION)
        assert cloud.calls
        gesehen = json.dumps(cloud.calls, ensure_ascii=False)
        assert 'Bestätigt: ORKA-17' not in gesehen
        assert all(not row['id'].startswith('K') for row in json.loads(cloud.calls[0][-1]['content'])['sources'])
    finally:
        client.close()
        _close_app(app)


def test_prepare_und_saetze_nehmen_keinen_blossen_cloudanbieter(core):
    """Nur ein `GedaechtnisCloud` (vom Agenten nach geprüfter Einwilligung gebaut) oder ein lokaler Anbieter."""
    _, _, episodes, claims, _ = core
    cloud = Cloud()
    assert working_memory_answers.prepare(QUESTION, episodes, claims, cloud) is None
    versuch = satzantwort.formulieren(QUESTION, [object()], cloud, jetzt=None)
    assert versuch.status == 'zitate' and versuch.grund == 'kein lokales Modell'
    assert cloud.calls == []
    assert gedaechtnis_cloud.erlaubt(gedaechtnis_cloud.GedaechtnisCloud(cloud, lambda m: None))
    assert not gedaechtnis_cloud.erlaubt(cloud) and not gedaechtnis_cloud.erlaubt(None)


def test_eingegrenzter_anbieter_nimmt_nur_json_und_prueft_vor_jedem_versand():
    cloud = Cloud()
    erlaubt = [True]

    def pruefen(messages):
        if not erlaubt[0]:
            raise RuntimeError('widerrufen')

    eng = gedaechtnis_cloud.GedaechtnisCloud(cloud, pruefen)
    nachrichten = [{'role': 'system', 'content': 'Anweisung'},
                   {'role': 'user', 'content': json.dumps({'question': 'x', 'sources': [{'id': 'S1'}]})}]
    assert json.loads(eng.complete_json(nachrichten, schema={'type': 'object'}).text) == {
        'status': 'source_reports', 'ids': ['S1']}
    assert nachrichten[0]['content'] == 'Anweisung'  # die Eingabe bleibt unverändert
    with pytest.raises(ProviderError):
        eng.complete(nachrichten, [])
    erlaubt[0] = False
    with pytest.raises(ProviderError):
        eng.complete_json(nachrichten, schema={'type': 'object'})
    assert len(cloud.calls) == 1
    for kaputt in ('kein json', '[1, 2]', '```\n{"a": 1}\n``` danach', None):
        with pytest.raises(ProviderError):
            gedaechtnis_cloud.json_aus(kaputt)


def test_rollen_markieren_nur_den_cloudanbieter_mit_einwilligung_und_schluessel():
    wahl = RollenWahl(cloud=True, anbieter='anthropic', cloud_einwilligung=EINWILLIGUNG)
    mit = provider_fuer('antwort', None, {'antwort': wahl}, umgebung={'ANTHROPIC_API_KEY': 'synthetisch'})
    assert mit.cloud_einwilligung == ('antwort', 'anthropic', EINWILLIGUNG)
    # Ohne Schlüssel: Rückfall auf den Standard, und der bekommt keine Marke.
    standard = Cloud()
    del standard.cloud_einwilligung
    ohne = provider_fuer('antwort', standard, {'antwort': wahl}, umgebung={})
    assert ohne is standard and not hasattr(ohne, 'cloud_einwilligung')
    # Ohne Einwilligung: nie eine Marke.
    ohne_einwilligung = provider_fuer('antwort', None, {'antwort': RollenWahl(cloud=True, anbieter='anthropic')},
                                      umgebung={'ANTHROPIC_API_KEY': 'synthetisch'})
    assert ohne_einwilligung is None


def test_einwilligungssatz_nennt_frage_und_textstellen():
    satz = model_roles.ROLLEN['antwort'].cloud_satz
    for wort in ('Fragen', 'Textstellen', 'Absender', 'Betreff', 'Gedächtnis'):
        assert wort in satz
