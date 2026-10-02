"""Jede Berichtigung bleibt als vollständige Änderung statt als alte Zusage lesbar."""
import json

import pytest

from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import run_working

LIEFERUNG = 'Mainz: Anna liefert den Entwurf am 25. September 2026, wenn die Freigabe vorliegt.'
ANRUF = 'Ben bittet um einen Rückruf zum Mainzer Entwurf.'
GRUSS = 'Viele Grüße'
ORIGINAL = f'{LIEFERUNG}\n\n{ANRUF}\n\n{GRUSS}'
KINDS = {LIEFERUNG: 'conditional', ANRUF: 'request'}


@pytest.fixture
def partial(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)

    def complete_json(messages, *, max_tokens, schema):
        data = json.loads(messages[-1]['content'])
        if 'blocks' in data:
            # Die Grußformel ist irrelevant und bleibt ohne Einordnung.
            return Reply(text=json.dumps({'items': [
                {'block_id': block['block_id'], 'kind': KINDS.get(block['text'], 'irrelevant')}
                for block in data['blocks']]}))
        return Reply(text=json.dumps({'status': 'reports', 'ids': [row['id'] for row in data['sources']]}))
    provider.complete_json = complete_json
    source = _upload(client, ORIGINAL)
    run_working(app)
    assert _items(app, source) == sorted([(LIEFERUNG, 'conditional'), (ANRUF, 'request')])
    yield app, client, source
    client.close()
    _close_app(app)


def _correct(client, source, body):
    state = client.get(f'/api/v1/memory/working/{source}/correction').json()
    response = client.post(f'/api/v1/memory/working/{source}/correction',
                           json={'fingerprint': state['fingerprint'], 'body': body})
    assert response.status_code == 201, response.text
    return response.json()['episode_id']


def _items(app, episode_id):
    body = app.state.episodes.get(episode_id).body
    refs = WorkingMemoryStore(app.state.episodes).source_refs(episode_ids=[episode_id])['refs']
    return sorted((body[ref['start']:ref['end']], ref['kind']) for ref in refs)


def test_changed_paragraph_keeps_complete_corrected_context(partial):
    app, client, source = partial
    changed = LIEFERUNG.replace('25. September', '28. September')
    corrected = _correct(client, source, f'{changed}\n\n{ANRUF}\n\n{GRUSS}')
    assert _items(app, corrected) == [(f'{changed}\n\n{ANRUF}\n\n{GRUSS}', 'change')]
    answer = _ask(client, _conversation(client), 'Wann liefert Anna den Entwurf für Mainz?')
    assert '28. September' in answer['content'] and '25. September' not in answer['content']
    assert 'Änderung · Deine Berichtigung' in answer['content']


def test_changed_neighbour_does_not_certify_old_condition(partial):
    app, client, source = partial
    corrected = _correct(client, source, f'{LIEFERUNG}\n\nBen bittet um einen Rückruf erst nach 14 Uhr.\n\n{GRUSS}')
    assert _items(app, corrected) == [(f'{LIEFERUNG}\n\nBen bittet um einen Rückruf erst nach 14 Uhr.\n\n{GRUSS}', 'change')]


def test_deleting_context_does_not_certify_old_condition(partial):
    app, client, source = partial
    corrected = _correct(client, source, f'{LIEFERUNG}\n\n{GRUSS}')
    assert _items(app, corrected) == [(f'{LIEFERUNG}\n\n{GRUSS}', 'change')]


def test_added_sentence_in_unclassified_text_is_marked_as_change(partial):
    app, client, source = partial
    changed = f'{LIEFERUNG}\n\n{ANRUF}\n\n{GRUSS}, Anna ist ab Montag im Urlaub.'
    corrected = _correct(client, source, changed)
    assert _items(app, corrected) == [(changed, 'change')]


def test_ambiguous_repeated_passage_is_not_guessed(partial):
    app, client, source = partial
    corrected = _correct(client, source, f'{LIEFERUNG}\n\n{LIEFERUNG}\n\n{ANRUF}')
    items = _items(app, corrected)
    assert items == [(f'{LIEFERUNG}\n\n{LIEFERUNG}\n\n{ANRUF}', 'change')]
    # Der doppelte Absatz ist nicht eindeutig zuzuordnen und wird nicht geraten.
    assert all(kind != 'conditional' for _, kind in items)


def test_unclassified_original_keeps_whole_change_behaviour(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        source = _upload(client, ORIGINAL)
        corrected = _correct(client, source, ORIGINAL.replace('25.', '26.'))
        body = app.state.episodes.get(corrected).body
        assert _items(app, corrected) == [(body, 'change')]
    finally:
        client.close()
        _close_app(app)


def test_shortened_paragraph_is_a_change_not_silently_dropped(partial):
    app, client, source = partial
    # Die Bedingung wird gestrichen: Der Rest steht wörtlich im Original,
    # ist aber eine inhaltliche Änderung und muss auffindbar bleiben.
    shortened = 'Mainz: Anna liefert den Entwurf am 25. September 2026'
    corrected = _correct(client, source, f'{shortened}\n\n{ANRUF}\n\n{GRUSS}')
    assert _items(app, corrected) == [(f'{shortened}\n\n{ANRUF}\n\n{GRUSS}', 'change')]


def test_negating_context_does_not_carry_quoted_commitment(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        commitment = 'Ich liefere die Druckdaten morgen.'
        def classify(messages, *, max_tokens, schema):
            data = json.loads(messages[-1]['content'])
            if 'blocks' in data:
                return Reply(text=json.dumps({'items': [{'block_id': block['block_id'], 'kind': 'commitment'}
                                                          for block in data['blocks']]}))
            return Reply(text=json.dumps({'status': 'reports', 'ids': [row['id'] for row in data['sources']]}))
        provider.complete_json = classify
        source = _upload(client, commitment)
        run_working(app)
        changed = 'Die folgende Zusage gilt nicht mehr: ' + commitment
        corrected = _correct(client, source, changed)
        assert _items(app, corrected) == [(changed, 'change')]
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('prefix', ['Die folgende Zusage gilt nicht mehr:',
                                    'Die folgende Zusage gilt nicht mehr.'])
def test_negating_paragraph_does_not_reactivate_old_commitment(partial, prefix):
    app, client, source = partial
    negated = prefix + '\n\n' + LIEFERUNG
    corrected = _correct(client, source, negated + '\n\n' + ANRUF + '\n\n' + GRUSS)
    items = _items(app, corrected)
    assert all(kind != 'conditional' for _, kind in items)
    assert items == [(negated + '\n\n' + ANRUF + '\n\n' + GRUSS, 'change')]


def test_replaced_introductory_context_withdraws_unchanged_commitment(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        commitment = 'Ich liefere die Druckdaten morgen.'
        old = 'Meine aktuelle Zusage:\n\n' + commitment
        def classify(messages, *, max_tokens, schema):
            data = json.loads(messages[-1]['content'])
            if 'blocks' in data:
                return Reply(text=json.dumps({'items': [
                    {'block_id': block['block_id'],
                     'kind': 'commitment' if block['text'] == commitment else 'irrelevant'}
                    for block in data['blocks']]}))
            return Reply(text=json.dumps({'status': 'reports', 'ids': [row['id'] for row in data['sources']]}))
        provider.complete_json = classify
        source = _upload(client, old)
        run_working(app)
        changed = 'Diese Zusage gilt nicht mehr:\n\n' + commitment
        corrected = _correct(client, source, changed)
        assert _items(app, corrected) == [(changed, 'change')]
    finally:
        client.close()
        _close_app(app)
