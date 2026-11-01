"""Kleine lokale Profile prüfen alle Originalkandidaten oder liefern keine Teilantwort."""
from copy import deepcopy
import json

import pytest

from icarus_memory import absatzauswahl, local_context_profile as context, providers
from icarus_memory.providers import OpenAICompatible, ProviderError, Reply
from icarus_memory import working_memory_answers as wma


def rows(count=6, size=4300):
    return [dict(id=('K7' if count > 1 and i == count - 1 else f'S{i + 1}'), kind='fact',
                 text=f'Kandidat {i}: NICHT erledigt.', context=f'Original {i}: ' + chr(65 + i) * size,
                 source_ref=f'synthetic:{i}', sender=f'Person {i} <p{i}@synthetic.example>') for i in range(count)]


def schema_for(candidates):
    return {'type': 'object', 'additionalProperties': False, 'required': ['status', 'ids'], 'properties': {
        'status': {'type': 'string', 'enum': list(wma.MODEL_DECISIONS)},
        'ids': {'type': 'array', 'maxItems': wma.MAX_REFS + 12,
                'items': {'type': 'string', 'enum': [r['id'] for r in candidates]}}}}


class Script:
    is_local = True

    def __init__(self, monkeypatch, answers):
        self.provider = OpenAICompatible('synthetic:8k', base_url='http://127.0.0.1:11434/v1')
        monkeypatch.setenv(context.FLAG, self.provider.model)
        monkeypatch.setattr(context, 'verify_profile', lambda _: pytest.fail('Preview must not verify metadata'))
        self.calls = []
        self.answers = answers

    def can_complete_json(self, messages, **kwargs):
        return self.provider.can_complete_json(messages, **kwargs)

    def complete_json(self, messages, **kwargs):
        assert self.can_complete_json(messages, **kwargs) is True
        data = json.loads(messages[-1]['content'])
        assert data['question'] == 'Welche Angaben gelten?'
        assert kwargs['schema']['properties']['ids']['items']['enum'] == [r['id'] for r in data['sources']]
        # Jede Seite und Abschlussvergleich sind unabhängig rückauflösbar.
        restored = absatzauswahl.modell_zeilen_entpacken(data['sources'])
        self.calls.append((restored, deepcopy(kwargs)))
        answer = self.answers(len(self.calls), restored)
        if isinstance(answer, Exception):
            raise answer
        return Reply(text=json.dumps(answer))


def choose(provider, candidates, fresh=lambda: True):
    from icarus_memory.source_selection_pages import select
    return select(provider, 'Welche Angaben gelten?', candidates, 'Wähle passende Originale.',
                  schema_for(candidates), wma.MODEL_DECISIONS, fresh=fresh)


def test_preview_is_pure_exact_builder_and_unselected_unchanged(monkeypatch):
    p = OpenAICompatible('synthetic:8k', base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setenv(context.FLAG, p.model)
    monkeypatch.setattr(context, 'verify_profile', lambda _: pytest.fail('Metadata access in preview'))
    monkeypatch.setattr(p, '_ampel', lambda: pytest.fail('Model preparation in preview'))
    monkeypatch.setattr(p, '_client', lambda _: pytest.fail('HTTP in preview'))
    messages = [{'role': 'user', 'content': 'Äußerst kleine künstliche Frage.'}]
    assert p.can_complete_json(messages, max_tokens=256, schema={'type': 'object'}) is True
    assert p.can_complete_json(messages, schema={'description': 'x' * 17000}) is False
    assert p.can_complete_json([{'role': 'user', 'content': 'x' * 17000}]) is False
    # Logisches JSON passt exakt; die zusätzliche native Optionenstruktur nicht.
    empty = [{'role': 'user', 'content': ''}]
    overhead = len(context._encoded(p._json_payload(empty, 256, None)))
    edge = [{'role': 'user', 'content': 'x' * (16000 - overhead)}]
    assert len(context._encoded(p._json_payload(edge, 256, None))) == 16000
    assert p.can_complete_json(edge) is False
    with pytest.raises(ProviderError):
        p.can_complete_json([{'role': 'user', 'content': [{'type': 'image_url'}]}])
    monkeypatch.delenv(context.FLAG)
    assert p.can_complete_json(messages) is None
    remote = OpenAICompatible('synthetic:8k', base_url='https://synthetic.example/v1')
    monkeypatch.setenv(context.FLAG, p.model)
    assert remote.can_complete_json(messages) is None


def test_all_candidates_global_schema_ids_and_final_conflict(monkeypatch):
    candidates = rows()
    original = deepcopy(candidates)
    script = Script(monkeypatch, lambda n, page: {'status': 'unresolved_conflicting_sources' if n == 3 else 'source_reports',
                                                 'ids': [r['id'] for r in page] if n == 3 else [page[0]['id']]})
    result = choose(script, candidates)
    assert result['status'] == 'conflict' and len(script.calls) == 3
    assert [r for page, _ in script.calls[:2] for r in page] == original == candidates
    assert script.calls[-1][0] == [script.calls[0][0][0], script.calls[1][0][0]]
    assert [r['id'] for r in script.calls[1][0]][-1] == 'K7'


def test_unknown_pages_do_not_erase_only_positive_page(monkeypatch):
    script = Script(monkeypatch, lambda n, page: {'status': 'source_reports' if n == 1 else 'no_relevant_sources',
                                                 'ids': [page[0]['id']] if n == 1 else []})
    assert choose(script, rows()) == {'status': 'reports', 'ids': ['S1']}
    assert len(script.calls) == 2


@pytest.mark.parametrize('status', ['needs_person_choice', 'needs_project_choice', 'needs_missing_time_reference',
                                  'unresolved_conflicting_sources'])
def test_only_unclear_page_keeps_internal_guard_without_final_call(status, monkeypatch):
    script = Script(monkeypatch, lambda n, page: {
        'status': status if n == 1 else 'no_relevant_sources',
        'ids': [page[0]['id'], page[-1]['id']] if n == 1 else []})
    assert choose(script, rows()) == {
        'status': wma.MODEL_DECISIONS[status], 'ids': ['S1', 'S3'], '_page_uncertainty': True}
    assert len(script.calls) == 2


@pytest.mark.parametrize('status', ['needs_person_choice', 'needs_project_choice', 'needs_missing_time_reference',
                                  'unresolved_conflicting_sources'])
def test_final_cannot_erase_unclear_page(status, monkeypatch):
    def answer(n, page):
        return {'status': status if n == 1 else 'source_reports', 'ids': [page[0]['id']]}
    script = Script(monkeypatch, answer)
    result = choose(script, rows())
    assert result['status'] == wma.MODEL_DECISIONS[status]
    assert result['ids'] == ['S1', 'S4']
    assert len(script.calls) == 3


def test_same_unclear_type_survives_final_and_mixed_types_fail(monkeypatch):
    script = Script(monkeypatch, lambda n, page: {'status': 'needs_person_choice', 'ids': [page[0]['id']]})
    assert choose(script, rows())['status'] == 'person'
    assert len(script.calls) == 3
    script = Script(monkeypatch, lambda n, page: {'status': 'needs_person_choice' if n == 1 else 'needs_project_choice',
                                                 'ids': [page[0]['id']]})
    with pytest.raises(ProviderError):
        choose(script, rows())


@pytest.mark.parametrize('failure', ['middle', 'union', 'single', 'pages', 'foreign_id', 'malformed'])
def test_any_failure_discards_all_partial_results(failure, monkeypatch):
    def answer(n, page):
        if failure == 'middle' and n == 2:
            return ProviderError('Synthetic second page failure')
        if failure == 'foreign_id':
            return {'status': 'source_reports', 'ids': ['NOT_ON_THIS_PAGE']}
        if failure == 'malformed':
            return {'status': 'source_reports', 'ids': []}
        return {'status': 'source_reports', 'ids': [r['id'] for r in page]}
    script = Script(monkeypatch, answer)
    candidates = rows(count=6 if failure == 'pages' else 1 if failure == 'single' else 4 if failure == 'union' else 6,
                      size=17000 if failure == 'single' else 8000 if failure == 'pages' else 6000 if failure == 'union' else 4300)
    with pytest.raises((ProviderError, ValueError)):
        choose(script, candidates)
    if failure in {'single', 'pages'}:
        assert script.calls == []
    if failure == 'union':
        assert len(script.calls) == 2


@pytest.mark.parametrize('expire_at', [1, 2])
def test_shared_deadline_blocks_next_page_or_final(expire_at, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(providers.time, 'monotonic', lambda: clock[0])
    def answer(n, page):
        if n == expire_at:
            clock[0] = 61.0
        return {'status': 'source_reports', 'ids': [page[0]['id']]}
    script = Script(monkeypatch, answer)
    with pytest.raises(ProviderError, match='deadline'):
        choose(script, rows())
    assert len(script.calls) == expire_at


def test_inherited_earlier_deadline_is_not_extended(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(providers.time, 'monotonic', lambda: clock[0])
    def answer(n, page):
        clock[0] = 2.0
        return {'status': 'source_reports', 'ids': [page[0]['id']]}
    script = Script(monkeypatch, answer)
    with providers.json_request_deadline(1.0), pytest.raises(ProviderError, match='deadline'):
        choose(script, rows())
    assert len(script.calls) == 1


@pytest.mark.parametrize('late', ['last_page', 'final'])
def test_late_last_reply_is_not_accepted_as_a_complete_answer(late, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(providers.time, 'monotonic', lambda: clock[0])
    def answer(n, page):
        if n == (2 if late == 'last_page' else 3):
            clock[0] = 61.0
        return {'status': 'no_relevant_sources' if late == 'last_page' and n == 2 else 'source_reports',
                'ids': [] if late == 'last_page' and n == 2 else [page[0]['id']]}
    script = Script(monkeypatch, answer)
    with pytest.raises(ProviderError, match='deadline'):
        choose(script, rows())


def test_fresh_callback_blocks_additional_page(monkeypatch):
    valid = [True]
    def answer(n, page):
        valid[0] = False
        return {'status': 'source_reports', 'ids': [page[0]['id']]}
    script = Script(monkeypatch, answer)
    with pytest.raises(ProviderError):
        choose(script, rows(), fresh=lambda: valid[0])
    assert len(script.calls) == 1


def test_small_fit_and_unselected_remote_keep_one_original_call(monkeypatch):
    for local in (True, False):
        script = Script(monkeypatch, lambda n, page: {'status': 'source_reports', 'ids': [page[0]['id']]})
        script.is_local = local
        if not local:
            script.can_complete_json = lambda *a, **kw: pytest.fail('Remote preview must not run')
            def complete(messages, **kw):
                script.calls.append(messages)
                return Reply(text='{"status":"source_reports","ids":["S1"]}')
            script.complete_json = complete
        assert choose(script, rows(count=1, size=100)) == {'status': 'reports', 'ids': ['S1']}
        assert len(script.calls) == 1


def test_four_pages_plus_final_and_copy_references_are_strictly_page_local(monkeypatch):
    candidates = rows(count=8, size=1000)
    for i, row in enumerate(candidates):
        if i % 2 == 0:
            row['context'] = f'Original {i}: ' + chr(65 + i) * 12000
        row['sender'] = 'Künstliche Fachstelle mit langer Quellenangabe ' * 12
        row['participants'] = [row['sender']]
    def answer(n, page):
        return {'status': 'source_reports', 'ids': [page[-1]['id']] if n < 5 else [r['id'] for r in page]}
    script = Script(monkeypatch, answer)
    result = choose(script, candidates)
    assert len(script.calls) == 5 and result['ids'] == ['S2', 'S4', 'S6', 'K7']
    assert [r for page, _ in script.calls[:4] for r in page] == candidates


@pytest.fixture
def real_sources(tmp_path):
    from datetime import datetime, timezone
    from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
    from icarus_memory.claims import ClaimStore
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from icarus_memory.working_memory_analysis import _blocks
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        originals = []
        for n in range(6):
            body = '\n\n'.join(f'Angaben gelten für Kalkulation {n}, Absatz {i}: NICHT erledigt. '
                               + 'Unveränderte künstliche Bedingung. ' * 18 for i in range(2))
            episode, _ = episodes.record(EpisodeKind.MESSAGE, f'Kalkulation {n}', body,
                Provenance(SourceType.DOCUMENT, source_ref=f'synthetic:{n}'),
                occurred_at=datetime(2026, 10, 31, tzinfo=timezone.utc))
            originals.append(episode)
        store = WorkingMemoryStore(episodes)
        for snapshot in store.pending(limit=20):
            assert store.commit(snapshot, [{'start': s, 'end': e, 'kind': 'fact'}
                                           for s, e in _blocks(snapshot.episode.body)], model='synthetic')
        yield episodes, claims, originals
    finally:
        claims.close()
        episodes.close()


@pytest.mark.parametrize('change_at', [1, 2])
@pytest.mark.parametrize('change', ['withdraw', 'metadata'])
def test_real_store_basis_change_prevents_next_page_or_final(real_sources, monkeypatch, change, change_at):
    episodes, claims, originals = real_sources
    def answer(n, page):
        if n == change_at:
            if change == 'withdraw':
                episodes.ignore(originals[-1].id)
            else:
                episodes.add_contacts(originals[-1].id, [], participants=['Changed <changed@synthetic.example>'])
        return {'status': 'source_reports', 'ids': [page[0]['id']]}
    script = Script(monkeypatch, answer)
    result = wma.prepare('Welche Angaben gelten?', episodes, claims, script, semantic_search=None)
    assert result['status'] == 'unavailable' and result['refs'] == []
    assert len(script.calls) == change_at
    if change_at == 2:
        assert sum(len(page) for page, _ in script.calls) == 6, 'Nächster Aufruf wäre der Gesamtvergleich'


@pytest.mark.parametrize('fail', [False, True])
def test_real_prepare_never_returns_partial_failure_and_runs_global_checks_after_final(real_sources, monkeypatch, fail):
    episodes, claims, _ = real_sources
    checked = []
    original = wma.adjust_selection
    def identity(question, full_rows, ids, **kwargs):
        checked.append(deepcopy(full_rows))
        return original(question, full_rows, ids, **kwargs)
    monkeypatch.setattr(wma, 'adjust_selection', identity)
    def answer(n, page):
        if fail and n == 2:
            return ProviderError('Synthetic failure after positive first page')
        return {'status': 'source_reports', 'ids': [page[0]['id']] if n < 3 else [r['id'] for r in page]}
    script = Script(monkeypatch, answer)
    result = wma.prepare('Welche Angaben gelten?', episodes, claims, script, semantic_search=None)
    if fail:
        assert result['status'] == 'selection_failed' and result['refs'] == []
        assert len(script.calls) == 2 and checked == []
        assert wma.render(result, episodes, claims)[2] == 'working_selection_failed'
    else:
        assert len(script.calls) == 3 and len(result['refs']) == 2
        assert len(checked) == 1 and len(checked[0]) == 6
        assert all(row['context'] == episodes.get(ref['episode_id']).body
                   for row, ref in zip(checked[0], result['basis']))


@pytest.mark.parametrize('scenario', ['current_change', 'own_with_foreign_promise'])
def test_preselection_freshness_is_neutral_until_global_selection_policies(tmp_path, monkeypatch, scenario):
    from datetime import datetime, timedelta, timezone
    from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
    from icarus_memory.claims import ClaimStore
    from icarus_memory.kontakte import fuer_mail
    from icarus_memory.working_memory_store import WorkingMemoryStore
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    at = datetime(2026, 10, 31, tzinfo=timezone.utc)
    try:
        if scenario == 'current_change':
            question = 'Was ist der aktuelle Stand meiner Hilfe beim Herbstmarkt?'
            bodies = [('Ich übernehme den Standdienst am Herbstmarkt am 20.09.2026; die Kinderbetreuung ist organisiert.',
                       'commitment', None),
                      ('Ich kann am 27.09.2026 doch nicht beim Herbstmarkt helfen; bitte meine Zusage streichen.',
                       'status', None)]
        else:
            question = 'Bis wann habe ich Nora die Ceder-Kalkulation zugesagt?'
            bodies = [('Ich werde dir die Kalkulation für Projekt Ceder bis zum 3. November 2026 senden.',
                       'commitment', 'Lea <lea@synthetic.example>'),
                      ('Ich werde dir die Unterlagen für Projekt Ceder bis zum 3. November 2026 senden. '
                       'Das ist meine Zusage, keine Bitte an dich.', 'commitment', 'Nora <nora@synthetic.example>')]
        original_ids = []
        for i, (body, kind, sender) in enumerate(bodies):
            contacts = fuer_mail(sender, [{'adresse': 'nora@synthetic.example' if i == 0 else 'lea@synthetic.example',
                                          'rolle': 'an'}], eigene=['lea@synthetic.example']) if sender else []
            episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Synthetischer Quellenbericht', body,
                Provenance(SourceType.EMAIL if sender else SourceType.DOCUMENT, source_ref=f'synthetic:{i}'),
                occurred_at=at + timedelta(days=i), participants=[sender] if sender else [], contacts=contacts)
            original_ids.append(episode.id)
            assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),
                [{'start': 0, 'end': len(body), 'kind': kind}], model='synthetic')
        drafts = []
        original_fresh = wma._fresh
        def fresh(answer, *args):
            if not answer['refs']:
                drafts.append(deepcopy(answer))
            return original_fresh(answer, *args)
        monkeypatch.setattr(wma, '_fresh', fresh)
        class Paged:
            is_local = True
            calls = 0
            def can_complete_json(self, messages, **kwargs):
                return len(json.loads(messages[-1]['content'])['sources']) <= 1
            def complete_json(self, messages, **kwargs):
                self.calls += 1
                page = json.loads(messages[-1]['content'])['sources']
                # Auswahl lässt die mögliche Änderung zunächst weg bzw. wählt
                # nur die eigene Zusage trotz fremder direkter Zusage im Pool.
                chosen = [r['id'] for r in page if r['source_ref'] == 'synthetic:0']
                return Reply(text=json.dumps({'status': 'source_reports' if chosen else 'no_relevant_sources',
                                             'ids': chosen}))
        provider = Paged()
        result = wma.prepare(question, episodes, claims, provider, semantic_search=None)
        assert provider.calls == 2, 'Neutrale Entwurfsfrische darf keine Seite vorzeitig sperren'
        assert len(drafts) == 3 and all(d['refs'] == [] and 'satzantwort' not in d for d in drafts)
        assert all(len(d['basis']) == 2 and d['status'] == 'reports' for d in drafts)
        if scenario == 'current_change':
            assert result['status'] == 'unclear' and result['uncertainty'] == 'conflict'
            assert {r['episode_id'] for r in result['refs']} == set(original_ids)
            assert result['change_review'] is True
        else:
            assert result['status'] == 'reports'
            assert [r['episode_id'] for r in result['refs']] == [original_ids[0]]
        assert original_fresh(result, episodes, claims) is True
    finally:
        claims.close()
        episodes.close()
