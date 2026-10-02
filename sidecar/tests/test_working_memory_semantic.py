"""Bedeutungssuche im Arbeitsstand: findet Umschreibungen, bleibt entziehbar und optional."""
import json
import re

import pytest

from icarus_memory import working_memory_semantic
from icarus_memory.providers import Reply
from icarus_memory.working_memory_semantic import WorkingMemorySemantic
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import classifier, run_working

SOURCE = 'Die Zugangskarte liegt im Schrank neben dem Empfang.'
PARAPHRASE = 'Wo finde ich den Ausweis zum Reinkommen?'


class ConceptEmbedder:
    """Ein Begriff je Dimension; Synonyme teilen eine Dimension."""
    is_local = True
    model_key = 'fake:concepts'
    CONCEPTS = {'zugangskarte': 'zutritt', 'ausweis': 'zutritt', 'reinkommen': 'zutritt',
                'schrank': 'ort', 'empfang': 'ort', 'finde': 'ort', 'liegt': 'ort',
                'lieferung': 'ware', 'ware': 'ware', 'verzögert': 'spaet', 'später': 'spaet'}
    DIMENSIONS = sorted(set(CONCEPTS.values())) + ['rest']

    def __init__(self):
        self.calls = 0
        self.fail = False

    def embed(self, texts):
        self.calls += 1
        if self.fail:
            raise RuntimeError('Ollama nicht erreichbar')
        vectors = []
        for text in texts:
            words = re.findall(r'\w+', text.casefold())
            concepts = {self.CONCEPTS.get(word, 'rest') for word in words}
            vectors.append([1.0 if dimension in concepts else 0.0 for dimension in self.DIMENSIONS])
        return vectors


@pytest.fixture
def meaning(monkeypatch):
    embedder = ConceptEmbedder()
    search = WorkingMemorySemantic(embedder, threshold=0.6)
    monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda provider: search)
    return embedder, search


def _selector_all(provider):
    classify = provider.complete_json

    def complete_json(messages, **kwargs):
        data = json.loads(messages[-1]['content'])
        if 'sources' not in data:
            return classify(messages, **kwargs)
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [row['id'] for row in data['sources']]}))
    provider.complete_json = complete_json


def test_paraphrase_without_shared_words_finds_the_source(core, tmp_path, monkeypatch, meaning):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        source = _upload(client, SOURCE)
        run_working(app)
        answer = _ask(client, _conversation(client), PARAPHRASE)
        working = answer['metadata']['context']['working_answer']
        assert SOURCE in answer['content']
        assert [ref['episode_id'] for ref in working['semantic_basis']] == [source]
        assert answer['metadata']['context']['answer_contract']['status'] == 'working_reports'
    finally:
        client.close()
        _close_app(app)


def test_without_opt_in_the_paraphrase_is_not_found(core, tmp_path, monkeypatch):
    monkeypatch.delenv('ICARUS_MEMORY_SEMANTIC', raising=False)
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        answer = _ask(client, _conversation(client), PARAPHRASE)
        assert SOURCE not in answer['content']
        assert 'working_answer' not in answer['metadata']['context']
    finally:
        client.close()
        _close_app(app)


def test_withdrawn_source_disappears_from_meaning_search_and_old_answer(core, tmp_path, monkeypatch, meaning):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        source = _upload(client, SOURCE)
        run_working(app)
        conversation = _conversation(client)
        assert SOURCE in _ask(client, conversation, PARAPHRASE)['content']
        app.state.episodes.ignore(source)
        old = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert SOURCE not in old['content']
        assert old['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        _, search = meaning
        assert search.search(app.state.episodes, PARAPHRASE) == []
    finally:
        client.close()
        _close_app(app)


def test_saved_answer_stays_readable_when_the_embedder_is_down(core, tmp_path, monkeypatch, meaning):
    embedder, _ = meaning
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        conversation = _conversation(client)
        assert SOURCE in _ask(client, conversation, PARAPHRASE)['content']
        embedder.fail = True
        calls = embedder.calls
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        # Das Anzeigen prüft die gespeicherten Treffer, ohne neu einzubetten.
        assert SOURCE in reopened['content']
        assert embedder.calls == calls
    finally:
        client.close()
        _close_app(app)


def test_new_semantic_only_source_invalidates_saved_selection_without_embedding(core, tmp_path, monkeypatch, meaning):
    embedder, _ = meaning
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        conversation = _conversation(client)
        assert SOURCE in _ask(client, conversation, PARAPHRASE)['content']
        _upload(client, 'Die Zugangskarte liegt jetzt beim Empfang.')
        run_working(app)
        embedder.fail = True
        before = embedder.calls
        reopened = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert SOURCE not in reopened['content']
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert embedder.calls == before
    finally:
        client.close()
        _close_app(app)


def test_legacy_semantic_answer_without_inventory_fails_closed(core, tmp_path, monkeypatch, meaning):
    from icarus_memory.working_memory_answers import prepare, render
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        answer = prepare(PARAPHRASE, app.state.episodes, app.state.claims, provider)
        assert answer['semantic_basis']
        answer.pop('semantic_inventory')
        text, _, status = render(answer, app.state.episodes, app.state.claims)
        assert SOURCE not in text
        assert status == 'working_unavailable'
    finally:
        client.close()
        _close_app(app)


def test_semantic_inventory_change_during_search_does_not_certify_old_results(core, tmp_path, monkeypatch, meaning):
    from icarus_memory.working_memory_answers import prepare
    _, search = meaning
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        original = search.search
        def interleaved(episodes, query, limit=12):
            refs = original(episodes, query, limit)
            _upload(client, 'Die Zugangskarte liegt jetzt beim Empfang.')
            run_working(app)
            return refs
        monkeypatch.setattr(search, 'search', interleaved)
        assert prepare(PARAPHRASE, app.state.episodes, app.state.claims, provider) is None
    finally:
        client.close()
        _close_app(app)


def test_embedder_failure_keeps_word_search_working(core, tmp_path, monkeypatch, meaning):
    embedder, search = meaning
    embedder.fail = True
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        answer = _ask(client, _conversation(client), 'Wo liegt die Zugangskarte?')
        assert SOURCE in answer['content']
        assert 'semantic_basis' not in answer['metadata']['context']['working_answer']
        assert search.status == 'unavailable'
    finally:
        client.close()
        _close_app(app)


def test_corrected_source_replaces_original_in_meaning_search(core, tmp_path, monkeypatch, meaning):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        source = _upload(client, SOURCE)
        run_working(app)
        state = client.get(f'/api/v1/memory/working/{source}/correction').json()
        corrected_text = 'Die Zugangskarte liegt jetzt am Empfang in der Schublade.'
        corrected = client.post(f'/api/v1/memory/working/{source}/correction',
                                json={'fingerprint': state['fingerprint'], 'body': corrected_text}).json()['episode_id']
        _, search = meaning
        assert [ref['episode_id'] for ref in search.search(app.state.episodes, PARAPHRASE)] == [corrected]
    finally:
        client.close()
        _close_app(app)


def test_opt_in_requires_flag_and_local_model(monkeypatch):
    class Local:
        is_local = True
        base_url = 'http://127.0.0.1:11434/v1'

    class Cloud:
        is_local = False
    monkeypatch.delenv('ICARUS_MEMORY_SEMANTIC', raising=False)
    assert working_memory_semantic.for_provider(Local()) is None
    monkeypatch.setenv('ICARUS_MEMORY_SEMANTIC', '1')
    assert working_memory_semantic.for_provider(Cloud()) is None
    assert working_memory_semantic.for_provider(Local()) is not None
    with pytest.raises(ValueError):
        WorkingMemorySemantic(Cloud())
