"""Read-only product investigation; mutates only a temporary synthetic directory."""
import json
import tempfile
from pathlib import Path
from icarus_memory.backup import snapshot_all, restore_all
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.model import Provenance, SourceType

root = Path(__file__).parent
with tempfile.TemporaryDirectory(prefix='restore-boundary-', dir=root) as directory:
    data = Path(directory)/'synthetic'
    data.mkdir()
    episodes = EpisodeStore(data/'episodes.sqlite3')
    episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Synthetischer Beleg', 'ORION Testquelle.',
                                 Provenance(SourceType.DOCUMENT, source_ref='synthetic:restore'))
    before = episodes.support_snapshot(episode.id)
    backup = snapshot_all(data, Path(directory)/'snapshots')
    episodes.ignore(episode.id)
    withdrawn = episodes.support_snapshot(episode.id)
    episodes.close()
    restore_all(backup, data)
    episodes = EpisodeStore(data/'episodes.sqlite3')
    restored = episodes.support_snapshot(episode.id)
    result = {'synthetic_only': True, 'scope': 'low-level snapshot_all/restore_all and source state only',
              'before': {'generation': before.generation, 'current': before.current()},
              'withdrawn': {'generation': withdrawn.generation, 'current': withdrawn.current()},
              'restored': {'generation': restored.generation, 'current': restored.current()},
              'withdrawal_survives_old_backup': not restored.current() and restored.generation >= withdrawn.generation}
    episodes.close()
    (root/'restore-boundary-result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
