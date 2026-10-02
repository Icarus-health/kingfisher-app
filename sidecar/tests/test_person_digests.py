"""Local AI overviews are derived, cited, scoped and invalidated on source changes."""
import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from icarus_memory.server import create_app
from icarus_memory.episodes import EpisodeKind
from icarus_memory.graph import person_id, person_id_fuer
from icarus_memory.model import Provenance, SourceType, now
from tests.ollama_fake import FakeOllama


class Local:
    is_local = True
    model = 'test-local'
    base_url = 'http://127.0.0.1:11434/v1'
    def __init__(self): self.calls = 0; self.context = None
    def complete_json(self, messages, **kwargs):
        self.calls += 1
        self.context = json.loads(messages[1]['content'])
        self.context['sources'] = [json.loads(m['content'].split('\n', 1)[1]) for m in messages[2:-1]]
        source = self.context['sources'][0]
        return SimpleNamespace(text=json.dumps({'points':[{'text':'Laut Quelle wird Atlas besprochen.',
            'citations':[{'source_id':source['source_id'],'quote':source['text'][:80]}]}],
            'questions':[], 'conflicts':[]}),tool_calls=[],model=self.model)


def setup(monkeypatch):
    app = create_app()
    provider = Local()
    app.state.agent = SimpleNamespace(provider=provider)
    client = TestClient(app)
    episode = add(app, 'Ada', 'Ada bespricht das Projekt Atlas.')
    return app, client, provider, episode


def add(app, person, text):
    return app.state.episodes.record(EpisodeKind.MESSAGE, 'Besprechung', text,
        Provenance(source_type=SourceType.EMAIL, source_ref=f'mail:{text}', captured_at=now()),
        participants=[person])[0]


def endpoint(person='Ada'): return '/api/v1/memory/person-digests/' + person_id(person)


def test_real_generation_is_cached_persisted_and_never_becomes_knowledge(monkeypatch):
    app, c, provider, episode = setup(monkeypatch)
    assert c.get(endpoint()).json()['status'] == 'missing'
    assert provider.calls == 0
    result = c.post(endpoint(), json={}).json()
    assert result['status'] == 'ready'
    citation = result['digest']['points'][0]['citations'][0]
    assert citation['episode_ids'] == [episode.id]
    assert citation['status'] == 'observed'
    assert result['digest']['model'] == 'test-local'
    assert c.post(endpoint(), json={}).json()['digest'] == result['digest']
    assert provider.calls == 1
    assert app.state.claims.all_claims() == []
    assert len(app.state.episodes.all_episodes()) == 1
    # Fresh app/store connections read the cache, not just in-process state.
    again = create_app(); again.state.agent = SimpleNamespace(provider=Local())
    assert TestClient(again).get(endpoint()).json()['digest'] == result['digest']


def test_context_excludes_other_people_and_cache_invalidates(monkeypatch):
    app, c, provider, _ = setup(monkeypatch)
    add(app, 'Bea', 'Bea hat ein geheimes anderes Vorhaben.')
    assert c.post(endpoint(), json={}).status_code == 200
    assert 'geheimes' not in json.dumps(provider.context)
    add(app, 'Ada', 'Ada berichtet: Atlas ist abgeschlossen.')
    response = c.get(endpoint()).json()
    assert response['status'] == 'stale' and response['digest'] is None


def test_rejects_fabricated_quotes_and_tool_calls_without_cache(monkeypatch):
    app, c, provider, _ = setup(monkeypatch)
    for result in [SimpleNamespace(text=json.dumps({'points':[{'text':'Erfunden','citations':[{'source_id':'S1','quote':'Kein Originalzitat'}]}],'questions':[],'conflicts':[]}),tool_calls=[]),
                   SimpleNamespace(text='{}',tool_calls=[{'name':'send_mail'}])]:
        provider.complete_json = lambda *args, **kwargs: result
        assert c.post(endpoint(), json={}).status_code == 503
        assert c.get(endpoint()).json()['digest'] is None


def test_no_cloud_and_changes_during_model_call_are_rejected(monkeypatch):
    app, c, provider, _ = setup(monkeypatch)
    provider.is_local = False
    assert c.post(endpoint(), json={}).status_code == 503
    assert provider.calls == 0
    provider.is_local = True
    original = provider.complete_json
    def changing(*args, **kwargs):
        reply = original(*args, **kwargs)
        add(app, 'Ada', 'Neue Information nach Beginn der Verdichtung.')
        return reply
    provider.complete_json = changing
    assert c.post(endpoint(), json={}).status_code == 409
    assert c.get(endpoint()).json()['digest'] is None


def test_auth_required_for_read_and_generation(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'test-token')
    c = TestClient(create_app())
    assert c.get(endpoint()).status_code == 401
    assert c.post(endpoint(), json={}).status_code == 401


def test_group_uses_only_confirmed_members_and_undo_invalidates(monkeypatch):
    from icarus_memory.person_merges import preview
    from icarus_memory.graph import build
    app, c, provider, _ = setup(monkeypatch)
    add(app, 'Ada <ada@example.org>', 'Ada sagt: Atlas braucht noch eine Freigabe.')
    add(app, 'Ada <ada@privat.example>', 'Ada schreibt privat: Atlas ist wichtig.')
    add(app, 'Andere Ada', 'Nicht zugeordnete Information geheim.')
    raw = build(episodes=app.state.episodes,workspace=app.state.workspace,tasks=app.state.tasks,
                store=app.state.store,knowledge=app.state.claims,group_people=False)
    # Zwei Adressen sind zwei Personen, bis der Nutzer sie zusammenführt.
    group = app.state.claims.person_merges.confirm(preview(raw, [person_id_fuer('a:ada@example.org'), person_id_fuer('a:ada@privat.example')], 'Ada'), confirmed=True)
    path = '/api/v1/memory/person-digests/' + group['id']
    assert c.post(path,json={}).status_code == 200
    assert len(provider.context['sources']) == 2
    assert 'geheim' not in json.dumps(provider.context)
    app.state.claims.person_merges.undo(group['id'], confirmed=True)
    assert c.get(path).status_code == 404


def test_retracted_claim_is_history_not_current_source(monkeypatch):
    from icarus_memory.proposals import Evidence
    from icarus_memory.person_digest_context import collect
    from icarus_memory.person_digests import validate
    app, c, provider, episode = setup(monkeypatch)
    proposal, _ = app.state.knowledge_service.propose(subject_ref=person_id('Ada'),predicate='works_on',value='Atlas',
        statement=episode.body,rationale='Wörtlicher Beleg',evidence=[Evidence(episode.id,episode.body,episode.digest)])
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[])
    context = collect(app, person_id('Ada'))
    assert any(source['status'] == 'confirmed' for source in context['sources'])
    app.state.claims.retract(claim.id, reason='Diese Zuordnung war falsch.')
    context = collect(app, person_id('Ada'))
    assert [source['status'] for source in context['sources']] == ['historical']
    source = context['sources'][0]
    bad = SimpleNamespace(text=json.dumps({'points':[{'text':'Ada arbeitet an Atlas.',
         'citations':[{'source_id':source['source_id'],'quote':source['text']}]}], 'questions':[], 'conflicts':[]}),tool_calls=[])
    with pytest.raises(ValueError): validate(bad, context, 'test-local')


def test_excluded_sources_and_ai_summaries_never_reenter_context(monkeypatch):
    from icarus_memory.person_digest_context import collect
    app, c, provider, original = setup(monkeypatch)
    removed = add(app, 'Ada', 'Diese alte Aussage wurde ausdrücklich ausgeschlossen.')
    app.state.episodes.ignore(removed.id)
    app.state.episodes.record(EpisodeKind.SUMMARY, 'KI-Text', 'Erfundene KI-Behauptung',
        Provenance(source_type=SourceType.INFERENCE, captured_at=now()), participants=['Ada'])
    context = collect(app, person_id('Ada'))
    assert len(context['sources']) == 1
    assert context['sources'][0]['episode_ids'] == [original.id]


def test_context_marks_truncated_material_and_source_limit(monkeypatch):
    from icarus_memory.person_digest_context import collect, MAX_SOURCES, MAX_SOURCE_CHARS
    app, c, provider, _ = setup(monkeypatch)
    for i in range(15): add(app, 'Ada', str(i) + 'Langer Text ' * 250)
    context = collect(app, person_id('Ada'))
    assert context['source_count'] == MAX_SOURCES
    assert context['total_source_count'] == 16
    assert context['truncated'] is True
    assert all(len(source['text']) <= MAX_SOURCE_CHARS for source in context['sources'])


def test_ignored_evidence_cannot_survive_as_active_claim_or_cached_overview(monkeypatch):
    from icarus_memory.proposals import Evidence
    from icarus_memory.person_digest_context import collect
    app, c, provider, episode = setup(monkeypatch)
    proposal, _ = app.state.knowledge_service.propose(subject_ref=person_id('Ada'),predicate='works_on',value='Atlas',
        statement=episode.body,rationale='Wörtlicher Beleg',evidence=[Evidence(episode.id,episode.body,episode.digest)])
    app.state.knowledge_service.accept(proposal.id, supersedes=[])
    assert c.post(endpoint(),json={}).status_code == 200
    # A lower-level importer can exclude a source before claim propagation.
    app.state.episodes.ignore(episode.id)
    context = collect(app, person_id('Ada'))
    assert context['sources'] == []
    assert c.get(endpoint()).json()['digest'] is None


def test_shared_episode_is_not_treated_as_individual_person_material(monkeypatch):
    from icarus_memory.person_digest_context import collect
    app, c, provider, own = setup(monkeypatch)
    app.state.episodes.record(EpisodeKind.MESSAGE, 'Gemeinsames Meeting', 'Bea ist Geschäftsführerin und zieht nach Berlin.',
        Provenance(source_type=SourceType.EMAIL, captured_at=now()), participants=['Ada', 'Bea'])
    context = collect(app, person_id('Ada'))
    assert [source['episode_ids'] for source in context['sources']] == [[own.id]]


def test_validator_enforces_section_and_word_limits(monkeypatch):
    from icarus_memory.person_digest_context import collect
    from icarus_memory.person_digests import validate
    app, _, _, _ = setup(monkeypatch)
    context = collect(app, person_id('Ada'))
    source = context['sources'][0]
    item = {'text': 'Laut Quelle ist Atlas ein Thema.', 'citations':[{'source_id':source['source_id'], 'quote':source['text']}]}
    with pytest.raises(ValueError):
        validate(SimpleNamespace(text=json.dumps({'points':[item]*4,'questions':[],'conflicts':[]}),tool_calls=[]),context,'test')
    long = {**item, 'text': 'a ' * 170}
    with pytest.raises(ValueError):
        validate(SimpleNamespace(text=json.dumps({'points':[long],'questions':[],'conflicts':[]}),tool_calls=[]),context,'test')


def test_unverifiable_item_is_discarded_without_losing_independent_supported_point(monkeypatch):
    from icarus_memory.person_digest_context import collect
    from icarus_memory.person_digests import validate
    app, _, _, _ = setup(monkeypatch)
    context = collect(app, person_id('Ada'))
    source = context['sources'][0]
    good = {'text': 'Laut Quelle ist Atlas ein Thema.', 'citations':[{'source_id':source['source_id'], 'quote':source['text']}]}
    bad = {'text': 'Unbelegte Frage?', 'citations':[{'source_id':source['source_id'], 'quote':'Dieses Zitat existiert nicht.'}]}
    result = validate(SimpleNamespace(text=json.dumps({'points':[good],'questions':[bad],'conflicts':[]}),tool_calls=[]),context,'local')
    assert result['points'] == [{**good, 'citations':[{**good['citations'][0], **{k:source[k] for k in ('title','status','occurred_at','recorded_at','episode_ids')}}]}]
    assert result['questions'] == []
    assert result['discarded_items'] == 1


def test_digest_prefers_already_qualified_local_text_model_within_budget(monkeypatch):
    from datetime import datetime, timezone
    from icarus_memory.providers import OpenAICompatible
    from icarus_memory.person_digests import choose_provider
    app, _, _, _ = setup(monkeypatch)
    base = OpenAICompatible('small',base_url='http://127.0.0.1:11434/v1')
    app.state.agent = SimpleNamespace(provider=base)
    app.state.ollama_transport = FakeOllama(installiert=['small']).transport
    def profile(model,size,verified=True):
        return {'model':model,'size_bytes':size,'verified':verified,'endpoint':base.base_url,
                'checked_at':datetime.now(timezone.utc).isoformat(),'capabilities':['text','tools']}
    app.state.settings.routing_profiles = [profile('small',3_000_000_000),
        profile('better-local',9_000_000_000),profile('too-large',20_000_000_000),profile('unchecked',9_500_000_000,False)]
    chosen = choose_provider(app)
    assert chosen.model == 'better-local' and chosen.is_local and chosen.base_url == base.base_url
    app.state.settings.routing_profiles = []
    assert choose_provider(app) is base


def test_digest_date_is_shared_by_prompt_and_cache_fingerprint(monkeypatch):
    from icarus_memory.person_digests import fingerprint, messages
    provider = SimpleNamespace(base_url='http://127.0.0.1:11434/v1', model='local')
    context = {'fingerprint':'same-sources', 'person':'Ada', 'members':[], 'sources':[],
               'truncated':False, 'as_of':'2026-09-09'}
    payload = json.loads(messages(context)[1]['content'])
    assert payload['as_of'] == context['as_of']
    tomorrow = {**context, 'as_of':'2026-09-10'}
    assert fingerprint(context, provider) != fingerprint(tomorrow, provider)


def test_digest_does_not_select_expired_or_foreign_endpoint_profiles(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from icarus_memory.providers import OpenAICompatible
    from icarus_memory.person_digests import choose_provider
    app, _, _, _ = setup(monkeypatch)
    base = OpenAICompatible('base-local',base_url='http://127.0.0.1:11434/v1')
    app.state.agent = SimpleNamespace(provider=base)
    app.state.ollama_transport = FakeOllama(installiert=['base-local']).transport
    now = datetime.now(timezone.utc)
    app.state.settings.routing_profiles = [
        {'model':'expired', 'size_bytes':9_000_000_000, 'verified':True,
         'endpoint':base.base_url, 'checked_at':(now - timedelta(days=15)).isoformat(),
         'capabilities':['text']},
        {'model':'foreign', 'size_bytes':9_500_000_000, 'verified':True,
         'endpoint':'http://127.0.0.1:12345/v1', 'checked_at':now.isoformat(),
         'capabilities':['text']},
    ]
    assert choose_provider(app) is base
