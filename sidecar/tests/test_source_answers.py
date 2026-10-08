"""Source display is original text, never an accepted claim or model memory."""
import json

import pytest

from tests.test_context_identity import core, AT
from tests.test_knowledge_time import change_source
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory import source_answers


QUESTION = 'Was steht zu "AURORA-4711" in meinen Quellen?'
BODY = 'Für AURORA-4711: Abgabe am 14. Oktober, sofern die Freigabe vorliegt. Keine feste Zusage.'


def raw(episodes, body=BODY):
    return episodes.record(EpisodeKind.DOCUMENT, 'ORIGINAL_PRIVATE_TITLE', body,
        Provenance(source_type=SourceType.DOCUMENT, source_ref='upload:private.txt'), at=AT)[0]


def test_explicit_source_literal_only():
    assert source_answers.literal_query(QUESTION) == 'AURORA-4711'
    assert source_answers.literal_query('Was steht zu „AURORA-4711“ in meinen Quellen?') == 'AURORA-4711'
    for question in ('Wann ist Aurora?', 'Was steht zu "A" in Quellen?',
                     'Was steht zu "Aurora" und "Atlas" in Quellen?',
                     'Was ist "Aurora"?', 'Was steht zu "AURORA\n4711" in Quellen?'):
        assert source_answers.literal_query(question) is None


def test_originalstellen_request_reaches_evidence_without_a_model_call(core):
    from icarus_memory.memory_routing import route
    agent, provider, episodes, claims, _ = core
    source = raw(episodes)
    question = 'Zeige Originalstellen zu „AURORA-4711“'
    assert source_answers.literal_query(question) == 'AURORA-4711'
    assert route(question) == 'memory_evidence'
    turn = agent.answer_memory(question)
    assert turn.context['answer_contract']['status'] == 'source_report'
    assert turn.context['source_answer']['refs'][0]['episode_id'] == source.id
    assert BODY in turn.reply and provider.calls == []


def test_readonly_original_answer_and_reference_only_metadata(core):
    agent, provider, episodes, claims, _ = core
    source = raw(episodes)
    before = claims.revision
    answer = source_answers.prepare(QUESTION, episodes, claims)
    assert BODY not in json.dumps(answer)
    assert source.title not in json.dumps(answer)
    text, links, status = source_answers.render(answer, episodes, claims)
    assert status == 'source_report'
    assert BODY in text and 'nicht bestätigt' in text
    assert 'Quellenzeit: unbekannt' in text
    assert links == [{'episode_id': source.id, 'label': 'Originalquelle 1 öffnen'}]
    assert claims.revision == before and provider.calls == []


@pytest.mark.parametrize('change', ['ignored', 'metadata', 'new_claim', 'corruption'])
def test_old_answer_cannot_survive_source_or_knowledge_change(core, change):
    agent, provider, episodes, claims, accept = core
    source = raw(episodes)
    answer = source_answers.prepare(QUESTION, episodes, claims)
    assert answer['refs']
    if change == 'ignored':
        episodes.ignore(source.id)
    elif change == 'metadata':
        change_source(episodes, source.id, source_ref='changed:PRIVATE_NEW_REF')
    elif change == 'new_claim':
        # Same original body deduplicates to the already selected source.
        claim, linked = accept('project:aurora', BODY)
        assert linked.id == source.id
        claims.retract(claim.id, reason='wrong', at=AT)
    else:
        with episodes._lock, episodes._conn:
            episodes._conn.execute('UPDATE episodes SET body=? WHERE id=?', ('CORRUPT', source.id))
    text, links, status = source_answers.render(answer, episodes, claims)
    assert status == 'source_unavailable' and links == []
    assert BODY not in text and source.title not in text and 'PRIVATE_NEW_REF' not in text


def test_utf8_casefold_excerpt_uses_original_character_offsets(core):
    _, _, episodes, claims, _ = core
    body = 'ä' * 900 + ' STRAẞE-29: Bedingung nicht erfüllt. ' + 'ü' * 900
    source = raw(episodes, body)
    answer = source_answers.prepare('Was steht zu "strasse-29" in meinen Quellen?', episodes, claims)
    ref = answer['refs'][0]
    assert ref['end'] - ref['start'] <= 800
    assert 'STRAẞE-29' in source.body[ref['start']:ref['end']]
    text, _, _ = source_answers.render(answer, episodes, claims)
    assert source.body[ref['start']:ref['end']] in text
    assert 'Ausschnitt' in text


def test_corrupt_lineage_fails_closed_and_display_never_becomes_model_history(core):
    agent, _, episodes, claims, _ = core
    raw(episodes)
    answer = source_answers.prepare(QUESTION, episodes, claims)
    answer['refs'][0]['start'] = -1
    text, links, status = source_answers.render(answer, episodes, claims)
    assert status == 'source_unavailable' and links == [] and BODY not in text
    agent.load_history([{'role': 'assistant', 'content': BODY,
        'context': {'source_answer': 'malformed', 'answer_mode': 'memory_evidence'}}])
    assert BODY not in str(agent._history)


def test_withdrawal_during_collection_drops_original_before_render(core, monkeypatch):
    _, _, episodes, claims, _ = core
    source = raw(episodes)
    answer = source_answers.prepare(QUESTION, episodes, claims)
    original = source_answers._resolve
    calls = 0
    def withdrawing(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 1:
            episodes.ignore(source.id)
        return result
    monkeypatch.setattr(source_answers, '_resolve', withdrawing)
    text, links, status = source_answers.render(answer, episodes, claims)
    assert status == 'source_unavailable' and links == []
    assert BODY not in text and source.title not in text


def test_grown_document_is_rejected_before_snapshot_parsing(core, monkeypatch):
    _, _, episodes, claims, _ = core
    source = raw(episodes)
    answer = source_answers.prepare(QUESTION, episodes, claims)
    with episodes._lock, episodes._conn:
        document = json.loads(episodes._conn.execute('SELECT document FROM episodes WHERE id=?', (source.id,)).fetchone()[0])
        document['tags'] = ['x' * source_answers.MAX_DOCUMENT_BYTES]
        episodes._conn.execute('UPDATE episodes SET document=? WHERE id=?', (json.dumps(document), source.id))
    monkeypatch.setattr(episodes, '_from_row', lambda row: pytest.fail('oversize source parsed'))
    text, links, status = source_answers.render(answer, episodes, claims)
    assert status == 'source_unavailable' and links == [] and BODY not in text
