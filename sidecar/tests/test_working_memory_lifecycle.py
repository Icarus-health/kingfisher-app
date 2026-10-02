"""Growing working memory survives restart and the existing full backup path."""
import json
from threading import RLock

from icarus_memory.backup import restore_all, snapshot_all
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.restore_boundary import pending
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_worker import run


class Classifier:
    is_local = True
    model = 'synthetic-reference-classifier'

    def __init__(self):
        self.calls = 0

    def complete_json(self, messages, *, max_tokens, schema):
        self.calls += 1
        blocks = json.loads(messages[-1]['content'])['blocks']
        return Reply(text=json.dumps({'items': [
            {'block_id': block['block_id'], 'kind': 'fact'} for block in blocks]}))


def test_growing_corpus_restart_and_full_backup_preserve_classified_and_dismissed_sources(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    episodes = EpisodeStore(data / 'episodes.sqlite3')
    provider, lock = Classifier(), RLock()
    originals = {}
    for n in range(520):
        token = f'quasararchiv{n:04d}'
        episode, _ = episodes.record(EpisodeKind.DOCUMENT, f'Dokument {n}',
            f'Der Schlüssel {token} gehört zum Archiv {n}.',
            Provenance(SourceType.DOCUMENT, source_ref=f'upload:synthetic-{n}.txt'))
        originals[token] = episode.id
    # Restart in the middle of the corpus, including the durable scan cursor.
    for _ in range(20):
        assert run(episodes, provider, lock).ok
    assert provider.calls == 100
    episodes.close()
    episodes = EpisodeStore(data / 'episodes.sqlite3')
    for _ in range(84):
        assert run(episodes, provider, lock).ok
    assert provider.calls == 520
    memory = WorkingMemoryStore(episodes)
    assert memory.pending() == []
    for token in ('quasararchiv0000', 'quasararchiv0260', 'quasararchiv0519'):
        assert memory.search(token)['refs'][0]['episode_id'] == originals[token]
    dismissed = originals['quasararchiv0260']
    assert memory.dismiss(dismissed)
    episodes.close()

    backup = snapshot_all(data, tmp_path / 'snapshots')
    recovered = tmp_path / 'recovered'
    restore_all(backup, recovered)
    # Restoring old data must not restore permission to resume automation.
    assert pending(recovered)
    restored = EpisodeStore(recovered / 'episodes.sqlite3')
    restored_memory = WorkingMemoryStore(restored)
    assert restored_memory.pending() == []
    assert restored_memory.search('quasararchiv0000')['refs'][0]['episode_id'] == originals['quasararchiv0000']
    assert restored_memory.search('quasararchiv0519')['refs'][0]['episode_id'] == originals['quasararchiv0519']
    assert restored_memory.search('quasararchiv0260')['refs'] == []
    assert restored.get(dismissed).body  # Dismissal keeps the original.
    restored.close()
    assert provider.calls == 520  # No reclassification on inspection/reopen.
