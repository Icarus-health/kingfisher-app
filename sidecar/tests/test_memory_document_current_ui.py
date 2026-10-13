from icarus_memory.graph import build
from icarus_memory.backends import MemoryBackend
from icarus_memory.store import SelfModelStore
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore


def test_graph_retains_history_but_identifies_current_document_for_directory(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    workspace = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    store = SelfModelStore(MemoryBackend(), subject_id='synthetic')
    try:
        old = episodes.record(EpisodeKind.DOCUMENT, 'Earlier', 'Old original',
                              Provenance(SourceType.DOCUMENT), source_key='document:ui')[0]
        episodes.advance_source_head('document:ui', None, old.id)
        new = episodes.record(EpisodeKind.DOCUMENT, 'Current', 'New original',
                              Provenance(SourceType.DOCUMENT), source_key='document:ui')[0]
        episodes.advance_source_head('document:ui', old.id, new.id)
        before = episodes._conn.total_changes
        result = {node.id: node for node in build(episodes=episodes, tasks=tasks, workspace=workspace, store=store).nodes}
        assert result['episode:' + old.id].attributes['source_current'] is False
        assert result['episode:' + new.id].attributes['source_current'] is True
        assert episodes._conn.total_changes == before
    finally:
        episodes.close(); tasks.close(); workspace.close()
