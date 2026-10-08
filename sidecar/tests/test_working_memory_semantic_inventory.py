"""Saved semantic selections depend on the full current source/version set."""
import json
from datetime import datetime, timezone

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory import working_memory_answers as answers, working_memory_semantic
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core

OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)
RECENT = datetime(2026, 10, 8, tzinfo=timezone.utc)


def add(episodes, text, *, at=OLD, key='', classified=True):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Original', text,
        Provenance(SourceType.EMAIL, source_ref='mail:local'), source_key=key, at=at)
    if key:
        episodes.advance_source_head(key, episodes.source_head(key), episode.id)
    memory = WorkingMemoryStore(episodes)
    if classified:
        assert memory.commit(memory._snapshot(episode.id),
            [{'start': 0, 'end': len(text), 'kind': 'fact'}], model='classifier')
    return episode


def change(episodes, episode, mutation):
    if mutation == 'withdraw':
        episodes.ignore(episode.id)
    elif mutation == 'head':
        add(episodes, 'Eine neue Fassung liegt vor.', key='mail:version')
    elif mutation == 'generation':
        with episodes.transaction():
            episodes._conn.execute('UPDATE episodes SET support_generation=support_generation+1 WHERE id=?', (episode.id,))
    else:
        current = episodes.get(episode.id)
        if mutation == 'body_document_only':
            current.body = 'Der Text wurde unmittelbar in der Altquelle verändert.'
        elif mutation == 'provenance':
            current.provenance.source_ref = 'mail:changed-origin'
        elif mutation == 'tag':
            current.tags.append('conversation:memory-lookup')
        elif mutation == 'metadata':
            current.participants.append('Andere Person <other@example.invalid>')
        episodes._put(current)


@pytest.mark.parametrize('mutation', ['withdraw', 'head', 'generation', 'body_document_only',
                                     'provenance', 'tag', 'metadata'])
def test_source_changes_invalidate_inventory_without_reclassification(tmp_path, mutation):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        old = add(episodes, 'Der frühere Hinweis bleibt im Original.', key='mail:version')
        before = answers._semantic_inventory(episodes)
        change(episodes, old, mutation)
        assert answers._semantic_inventory(episodes) != before
    finally:
        episodes.close()


def test_new_unclassified_source_changes_saved_semantic_coverage(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        add(episodes, 'Die erste Quelle ist eingeordnet.')
        before = answers._semantic_inventory(episodes)
        add(episodes, 'Eine alte Quelle ist noch nicht eingeordnet.', classified=False)
        assert answers._semantic_inventory(episodes) != before
    finally:
        episodes.close()


def test_saved_answer_detects_old_unselected_source_beyond_2048_without_embeddings(core, monkeypatch):
    _, provider, episodes, claims, _ = core
    from icarus_memory.working_memory_semantic_index import DurableSemanticIndex

    selected = add(episodes, 'Die Zugangskarte liegt im Schrank neben dem Empfang.')
    other = add(episodes, 'Der alte Vermerk betrifft ein anderes Gebäude.')
    with episodes.transaction():
        for n in range(2049):
            add(episodes, f'Der neutrale Inventareintrag lautet Nummer {n}.', at=RECENT)
    recent = WorkingMemoryStore(episodes).inventory()['refs']
    assert selected.id not in {r['episode_id'] for r in recent}
    assert other.id not in {r['episode_id'] for r in recent}

    cache = DurableSemanticIndex(episodes, 'synthetic:' + 'a' * 64)
    try:
        while batch := cache.pending(64):
            if not batch.refs:
                break
            cache.commit(batch, [[1., 0.] if ref['episode_id'] == selected.id else [0., 1.]
                                 for ref in batch.refs])

        class Search:
            calls = 0
            def search_with_status(self, store, query, limit):
                self.calls += 1
                return cache.search([1., 0.], limit=limit)
        semantic = Search()
        monkeypatch.setattr(working_memory_semantic, 'for_provider', lambda unused: semantic)

        def choose(messages, **kwargs):
            sources = json.loads(messages[-1]['content'])['sources']
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': [row['id'] for row in sources]}))
        provider.complete_json = choose
        saved = answers.prepare('Wie gelange ich hinein?', episodes, claims, provider)
        assert saved is not None
        assert [ref['episode_id'] for ref in saved['semantic_basis']] == [selected.id]
        assert answers.render(saved, episodes, claims)[2] == 'working_reports'
        calls = semantic.calls
        change(episodes, other, 'provenance')
        assert answers.render(saved, episodes, claims)[2] == 'working_unavailable'
        assert semantic.calls == calls
    finally:
        cache.close()


def test_inventory_stream_does_not_resolve_plaintext_and_survives_restart(tmp_path, monkeypatch):
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    add(episodes, 'PRIVATE-TEXT-' * 10000)
    monkeypatch.setattr(WorkingMemoryStore, '_snapshot', lambda *args: pytest.fail('Inventory copied a source snapshot'))
    connection = episodes._conn
    class StreamingConnection:
        def execute(self, *args):
            cursor = connection.execute(*args)
            class StreamingCursor:
                def fetchall(self):
                    pytest.fail('Inventory materialized the corpus')
                def __iter__(self):
                    for row in cursor:
                        assert 'PRIVATE-TEXT-' not in str(tuple(row))
                        yield row
            return StreamingCursor()
    episodes._conn = StreamingConnection()
    try:
        before = answers._semantic_inventory(episodes)
        assert before == answers._semantic_inventory(episodes)
    finally:
        episodes._conn = connection
        episodes.close()
    reopened = EpisodeStore(path)
    try:
        assert answers._semantic_inventory(reopened) == before
    finally:
        reopened.close()
