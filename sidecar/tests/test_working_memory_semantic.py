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


def test_status_result_is_bound_to_search_call_and_list_api_stays_compatible(core):
    from types import SimpleNamespace
    embedder = ConceptEmbedder()
    search = WorkingMemorySemantic(embedder, threshold=0.6, limit=1)
    refs = [
        {'episode_id': 'old', 'fingerprint': 'a', 'start': 0, 'end': 32, 'kind': 'fact'},
        {'episode_id': 'new', 'fingerprint': 'b', 'start': 0, 'end': 42, 'kind': 'fact'},
    ]
    class Store:
        def __init__(self, episodes): pass
        def inventory(self, limit): return {'refs': refs[:limit], 'truncated': True}
        def resolve(self, ref):
            body = 'Die Zugangskarte liegt im Schrank.' if ref['episode_id'] == 'old' else 'Der Sitzungskalender wurde aktualisiert.'
            return SimpleNamespace(episode=SimpleNamespace(title='Hinweis', body=body))
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(working_memory_semantic, 'WorkingMemoryStore', Store)
        episodes = object()
        original_search = search.search
        def interleaved(*args, **kwargs):
            refs = original_search(*args, **kwargs)
            search.status = 'ok'  # Simulates another caller changing the legacy global view.
            return refs
        search.search = interleaved
        result = search.search_with_status(episodes, PARAPHRASE)
        assert result.status == 'partial'
        assert search.status == 'ok'
        assert isinstance(result.refs, tuple)
        assert search.search(episodes, PARAPHRASE) == list(result.refs)


def test_http_source_answer_discloses_partial_semantic_inventory(core, tmp_path, monkeypatch, meaning):
    embedder, _ = meaning
    search = WorkingMemorySemantic(embedder, threshold=0.6, limit=1)
    monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda provider: search)
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, 'Die Sitzung wurde im Kalender dokumentiert.')
        _upload(client, SOURCE)
        run_working(app)
        answer = _ask(client, _conversation(client), PARAPHRASE)
        working = answer['metadata']['context']['working_answer']
        assert SOURCE in answer['content']
        assert working['semantic_search_status'] == 'partial'
        assert working['limited'] is True
        assert answer['metadata']['context']['answer_contract']['semantic_search_status'] == 'partial'
        assert 'semantische' in answer['content'].casefold()
        embedder.fail = True
        before = embedder.calls
        reopened = client.get(f"/api/v1/conversations/{answer['conversation_id']}").json()['messages'][-1]
        assert SOURCE in reopened['content']
        assert reopened['metadata']['context']['answer_contract']['semantic_search_status'] == 'partial'
        assert embedder.calls == before
        from types import SimpleNamespace
        from icarus_memory import satzantwort, working_memory_answers
        monkeypatch.setattr(satzantwort, 'wiederherstellen', lambda *args: SimpleNamespace(status='nichts'))
        text, _, status = working_memory_answers.render(working, app.state.episodes, app.state.claims)
        assert status == 'working_unknown'
        assert 'keine Information vor' not in text
        assert 'begrenzt' in text
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('coverage', ['partial', 'unavailable'])
def test_http_selector_unknown_does_not_claim_no_information_on_incomplete_search(core, tmp_path, monkeypatch, meaning, coverage):
    embedder, _ = meaning
    if coverage == 'unavailable':
        embedder.fail = True
        question = 'Wo liegt die Zugangskarte?'
    else:
        search = WorkingMemorySemantic(embedder, threshold=0.6, limit=1)
        monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda provider: search)
        question = PARAPHRASE
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    classify = provider.complete_json
    def unknown_when_selecting(messages, **kwargs):
        data = json.loads(messages[-1]['content'])
        if 'sources' in data:
            return Reply(text=json.dumps({'status': 'no_relevant_sources', 'ids': []}))
        return classify(messages, **kwargs)
    provider.complete_json = unknown_when_selecting
    try:
        _upload(client, 'Die Sitzung wurde im Kalender dokumentiert.')
        _upload(client, SOURCE)
        run_working(app)
        answer = _ask(client, _conversation(client), question)
        working = answer['metadata']['context']['working_answer']
        assert working['status'] == 'unknown'
        assert working['semantic_search_status'] == coverage
        assert 'keine Information vor' not in answer['content']
        assert 'begrenzt' in answer['content'] if coverage == 'partial' else 'Bedeutungssuche' in answer['content']
    finally:
        client.close()
        _close_app(app)


def test_legacy_search_fake_status_is_unobserved(core, tmp_path, monkeypatch):
    class LegacySearch:
        status = 'partial'
        def search(self, episodes, query, limit=12):
            return []
    monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda provider: LegacySearch())
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        from icarus_memory.working_memory_answers import prepare
        answer = prepare('Wo liegt die Zugangskarte?', app.state.episodes, app.state.claims, provider)
        assert answer['semantic_search_status'] == 'unobserved'
        assert answer['limited'] is False
    finally:
        client.close()
        _close_app(app)


def test_confirmed_knowledge_fallback_keeps_answer_and_discloses_incomplete_search(core, monkeypatch):
    agent, _, _, _, accept = core
    accept('project:aurora', 'Aurora Lieferort: Basel.')
    from icarus_memory.working_memory_semantic import SemanticSearchResult
    class UnavailableSearch:
        def search_with_status(self, episodes, query, limit=12):
            return SemanticSearchResult((), 'unavailable')
        def search(self, episodes, query, limit=12):
            return []
    monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda provider: UnavailableSearch())
    monkeypatch.setattr(agent, '_meaning_turn', lambda *args, **kwargs: None)
    turn = agent.answer_memory('Welche Lieferortangabe gilt für Aurora?')
    assert turn.context['items']
    assert turn.context['answer_contract']['semantic_search_status'] == 'unavailable'
    assert 'Bedeutungssuche' in turn.reply
    assert 'keine belegte Antwort gefunden' not in turn.reply


@pytest.mark.parametrize('coverage', ['partial', 'unavailable'])
def test_http_empty_fallback_discloses_incomplete_semantic_search(core, tmp_path, monkeypatch, meaning, coverage):
    embedder, _ = meaning
    if coverage == 'unavailable':
        embedder.fail = True
    else:
        monkeypatch.setattr(working_memory_semantic, 'for_provider',
                            lambda provider: WorkingMemorySemantic(embedder, threshold=0.99, limit=1))
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    try:
        _upload(client, 'Die Zugangskarte liegt im Schrank neben dem Empfang.')
        if coverage == 'partial':
            _upload(client, 'Die Lieferung verzögert sich später.')
        run_working(app)
        response = client.post(f"/api/v1/conversations/{_conversation(client)}/messages",
                               json={'message': 'Nenne die Anzahl der Kometen über Island.',
                                     'answer_mode': 'memory_evidence'})
        assert response.status_code == 201
        answer = response.json()['messages'][-1]
        context = answer['metadata']['context']
        assert context.get('answer_contract', {}).get('semantic_search_status') == coverage, answer
        assert ('begrenzt' in answer['content']) if coverage == 'partial' else ('Bedeutungssuche' in answer['content'])
        assert 'keine Information' not in answer['content'].casefold()
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


@pytest.mark.parametrize('failure', ['raises', 'malformed'])
def test_status_capable_adapter_failure_is_unavailable(core, tmp_path, monkeypatch, failure):
    class BrokenSearch:
        def search_with_status(self, *args, **kwargs):
            if failure == 'raises':
                raise RuntimeError('synthetic adapter failure')
            return object()
    monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda provider: BrokenSearch())
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    _selector_all(provider)
    try:
        _upload(client, SOURCE)
        run_working(app)
        answer = _ask(client, _conversation(client), 'Wo liegt die Zugangskarte?')
        working = answer['metadata']['context']['working_answer']
        assert SOURCE in answer['content']
        assert working['semantic_search_status'] == 'unavailable'
        assert working['limited'] is True
        assert 'Bedeutungssuche' in answer['content']
    finally:
        client.close()
        _close_app(app)


def _empty_coverage_search(monkeypatch, coverage):
    from icarus_memory.working_memory_semantic import SemanticSearchResult
    class Search:
        def search_with_status(self, *args, **kwargs):
            return SemanticSearchResult((), coverage)
    monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda provider: Search())


@pytest.mark.parametrize('coverage', ['partial', 'unavailable'])
def test_scoped_followup_keeps_search_coverage_on_no_hit(core, monkeypatch, coverage):
    agent, *_ = core
    _empty_coverage_search(monkeypatch, coverage)
    turn = agent.answer_memory('Und wo?', retrieval_query='Synthetischer Komet')
    assert turn.context['answer_contract']['semantic_search_status'] == coverage
    assert 'begrenzt' in turn.reply if coverage == 'partial' else 'Bedeutungssuche' in turn.reply


@pytest.mark.parametrize('coverage', ['partial', 'unavailable'])
def test_post_search_source_fallback_keeps_coverage(core, monkeypatch, coverage):
    from icarus_memory import source_answers
    agent, *_ = core
    _empty_coverage_search(monkeypatch, coverage)
    monkeypatch.setattr(agent, '_meaning_turn', lambda *args, **kwargs: None)
    calls = []
    def prepared(*args):
        calls.append(args)
        return None if len(calls) == 1 else {'synthetic': True}
    monkeypatch.setattr(source_answers, 'prepare', prepared)
    monkeypatch.setattr(source_answers, 'render', lambda *args: ('Synthetischer Originalbeleg.', [], 'source_reports'))
    turn = agent.answer_memory('Was berichtet der synthetische Komet?')
    assert len(calls) == 2
    assert turn.reply.startswith('Synthetischer Originalbeleg.')
    assert turn.context['answer_contract']['semantic_search_status'] == coverage
    assert 'begrenzt' in turn.reply if coverage == 'partial' else 'Bedeutungssuche' in turn.reply


@pytest.mark.parametrize('coverage', ['partial', 'unavailable'])
def test_clicked_meaning_no_hit_keeps_search_coverage(core, monkeypatch, coverage):
    from icarus_memory import bedeutungen
    agent, *_ = core
    _empty_coverage_search(monkeypatch, coverage)
    monkeypatch.setattr(bedeutungen, 'meaning_choice_current', lambda *args: True)
    scope = {'begriff': 'Komet', 'art': 'absender', 'ref': 'comet@example.invalid',
             'label': 'Komet', 'ids': ['synthetic-source'], 'truncated': False, 'chosen': False}
    monkeypatch.setattr(agent, '_meaning_scope', lambda *args: dict(scope))
    pending = {'query': 'Was ist mit Komet?', 'begriff': 'Komet',
               'options': [{'art': 'absender', 'ref': 'comet@example.invalid', 'label': 'Komet',
                            'ids': ['synthetic-source']}]}
    turn = agent.answer_meaning_choice(pending, 0)
    assert turn.context['answer_contract'].get('semantic_search_status') == coverage
    assert 'noch keine Quelle eingeordnet' not in turn.reply
    assert 'begrenzt' in turn.reply if coverage == 'partial' else 'Bedeutungssuche' in turn.reply
