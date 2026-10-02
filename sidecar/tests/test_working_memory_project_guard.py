"""Wrong model selections must not cross explicit source project boundaries."""
import json
import pytest
from icarus_memory.providers import Reply
from icarus_memory.working_memory_answers import prepare, render, choices, choose, _fresh
from tests.test_memory_project_names import stores, _source
from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import classifier, run_working
from tests.test_conversation_retraction import _close_app

class First:
    is_local = True
    def __init__(self, status='source_reports'):
        self.status = status
    def complete_json(self, messages, **kwargs):
        rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status': self.status, 'ids': [rows[0]['id']]}))


def test_wrong_project_cannot_be_delivered_even_when_model_selects_it(stores):
    episodes, claims = stores
    _source(episodes, 'Projekt Lindenhof: Eva verschickt die Baupläne am 9. Dezember 2026.')
    answer = prepare('Wann verschickt Eva die Baupläne für Sonnenfeld?', episodes, claims, First())
    text, links, status = render(answer, episodes, claims)
    assert status == 'working_unknown'
    assert not links and '9. Dezember' not in text


def test_omitted_project_peer_requires_choice_without_manual_assignment(stores):
    episodes, claims = stores
    first = _source(episodes, 'Die Schlüsselübergabe für Projekt Lindenhof ist am 9. Dezember 2026.')
    second = _source(episodes, 'Die Schlüsselübergabe für Projekt Sonnenfeld ist am 18. Dezember 2026.')
    answer = prepare('Wann ist die Schlüsselübergabe?', episodes, claims, First())
    assert answer['uncertainty'] == 'scope'
    assert {ref['episode_id'] for ref in answer['refs']} == {first.id, second.id}
    options = choices(answer, episodes)
    assert len(options) == 2
    chosen = choose(answer, 0, episodes, claims)
    assert chosen['status'] == 'reports' and len(chosen['refs']) == 1
    episodes.ignore(first.id)
    assert not _fresh(chosen, episodes, claims)


def test_explicit_assignment_change_invalidates_answer(stores):
    episodes, claims = stores
    source = _source(episodes, 'Die Schlüsselübergabe ist am 9. Dezember 2026.', project='lindenhof')
    answer = prepare('Wann ist die Schlüsselübergabe?', episodes, claims, First(),
                     projects=[('lindenhof', 'Lindenhof'), ('sonnenfeld', 'Sonnenfeld')])
    assert _fresh(answer, episodes, claims)
    episodes.link_project(source.id, 'sonnenfeld')
    assert not _fresh(answer, episodes, claims)


@pytest.mark.parametrize('question', [
    'Wann sind die Schlüsselübergaben für beide Projekte?',
    'Vergleiche die Schlüsselübergabe der Projekte.',
])
def test_explicit_comparisons_do_not_force_single_project_choice(stores, question):
    episodes, claims = stores
    _source(episodes, 'Die Schlüsselübergabe für Projekt Lindenhof ist am 9. Dezember 2026.')
    _source(episodes, 'Die Schlüsselübergabe für Projekt Sonnenfeld ist am 18. Dezember 2026.')
    answer = prepare(question, episodes, claims, First())
    assert answer['uncertainty'] == 'none'


def test_same_project_correction_is_not_project_ambiguity(stores):
    episodes, claims = stores
    _source(episodes, 'Projekt Lindenhof: Die Schlüsselübergabe ist am 9. Dezember 2026.')
    _source(episodes, 'Projekt Lindenhof: Die Schlüsselübergabe wurde auf den 18. Dezember 2026 verschoben.')
    answer = prepare('Wann ist die Schlüsselübergabe?', episodes, claims, First())
    assert answer['uncertainty'] == 'none'


def test_unrelated_project_candidate_does_not_force_clarification(stores):
    episodes, claims = stores
    wanted = _source(episodes, 'Projekt Lindenhof: Eva bestätigt die Schlüsselübergabe am 9. Dezember 2026.')
    _source(episodes, 'Projekt Sonnenfeld: Eva bestätigt die Baupläne.')
    class SelectWanted(First):
        def complete_json(self, messages, **kwargs):
            rows = json.loads(messages[-1]['content'])['sources']
            ids = [r['id'] for r in rows if 'Schlüsselübergabe' in r['text']]
            return Reply(text=json.dumps({'status':'reports', 'ids':ids}))
    answer = prepare('Wann ist die Schlüsselübergabe mit Eva?', episodes, claims, SelectWanted())
    assert answer['uncertainty'] == 'none'
    assert [r['episode_id'] for r in answer['refs']] == [wanted.id]


def test_qualifier_present_in_original_is_not_assumed_to_be_project(stores):
    episodes, claims = stores
    source = _source(episodes, 'Projekt Lindenhof: Die Schlüssel für Eigentümer liegen am Empfang.')
    answer = prepare('Wo liegen die Schlüssel für Eigentümer?', episodes, claims, First())
    assert [r['episode_id'] for r in answer['refs']] == [source.id]


def test_multiword_project_name_and_explicit_comparison(stores):
    episodes, claims = stores
    source = _source(episodes, 'Projekt Neue Mitte: Die Abnahme ist am 9. Dezember 2026.')
    answer = prepare('Wann ist die Abnahme für Neue Mitte?', episodes, claims, First())
    assert [r['episode_id'] for r in answer['refs']] == [source.id]


def test_negated_project_mention_is_not_an_assignment(stores):
    episodes, claims = stores
    source = _source(episodes, 'Die Abnahme betrifft nicht Projekt Lindenhof, sondern Sonnenfeld.')
    answer = prepare('Was ist zur Abnahme für Sonnenfeld bekannt?', episodes, claims, First())
    assert [r['episode_id'] for r in answer['refs']] == [source.id]


def test_comparison_source_is_not_reduced_to_its_first_project(stores):
    episodes, claims = stores
    source = _source(episodes, 'Projekt Lindenhof und Sonnenfeld: Die Schlüsselübergabe ist gemeinsam.')
    answer = prepare('Wann ist die Schlüsselübergabe für Sonnenfeld?', episodes, claims, First())
    assert [r['episode_id'] for r in answer['refs']] == [source.id]


@pytest.mark.parametrize('status', ['reports', 'person', 'time'])
def test_project_clarification_survives_http_and_withdrawal(core, tmp_path, monkeypatch, status):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    classifier(provider)
    original = provider.complete_json
    def select_one(messages, **kwargs):
        if 'sources' in json.loads(messages[-1]['content']):
            return First(status).complete_json(messages, **kwargs)
        return original(messages, **kwargs)
    provider.complete_json = select_one
    try:
        one = _upload(client, 'Die Schlüsselübergabe für Projekt Lindenhof ist am 9. Dezember 2026.')
        two = _upload(client, 'Die Schlüsselübergabe für Projekt Sonnenfeld ist am 18. Dezember 2026.')
        run_working(app)
        cid = _conversation(client)
        reply = _ask(client, cid, 'Wann ist die Schlüsselübergabe?')
        context = reply['metadata']['context']
        assert context['answer_contract']['status'] == 'working_unclear'
        assert context['working_answer']['uncertainty'] == 'scope'
        assert {r['episode_id'] for r in context['source_links']} == {one, two}
        assert client.post(f'/api/v1/episodes/{one}/ignore').status_code == 200
        old = client.get(f'/api/v1/conversations/{cid}').json()['messages'][-1]
        assert old['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert '9. Dezember' not in old['content']
    finally:
        client.close()
        _close_app(app)


def test_person_name_alone_does_not_pull_unrelated_project_topic(stores):
    episodes, claims = stores
    _source(episodes, 'Projekt Lindenhof: Eva bestätigt die Schlüsselübergabe.')
    _source(episodes, 'Projekt Sonnenfeld: Eva lehnt die Baupläne ab.')
    answer = prepare('Was sagt Eva?', episodes, claims, First())
    assert answer['uncertainty'] == 'none'


def test_project_choices_use_original_project_names_instead_of_upload_filenames(stores):
    episodes,claims=stores
    _source(episodes,'Die Bauabnahme für Projekt Neue Mitte ist am 9. Dezember 2026.',title='scan-123.txt')
    _source(episodes,'Die Bauabnahme für Projekt Sonnenfeld ist am 18. Dezember 2026.',title='scan-456.txt')
    answer=prepare('Wann ist die Bauabnahme?',episodes,claims,First())
    assert {option['label'] for option in choices(answer,episodes)}=={'Projekt Neue Mitte','Projekt Sonnenfeld'}
