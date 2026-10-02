"""Quellenversionen bleiben nach Neustart eindeutig und verlieren keine Konkurrenzänderung."""
import pytest
from icarus_memory.episodes import EpisodeStore, EpisodeError, EpisodeKind
from icarus_memory.model import Provenance, SourceType


def test_source_version_head_survives_restart_and_rejects_stale_writer(tmp_path):
    path=tmp_path/'episodes.sqlite3'
    first=EpisodeStore(path)
    old=first.record(EpisodeKind.DOCUMENT,'Quelle','Alter Inhalt',Provenance(source_type=SourceType.DOCUMENT))[0]
    new=first.record(EpisodeKind.DOCUMENT,'Quelle','Neuer Inhalt',Provenance(source_type=SourceType.DOCUMENT))[0]
    first.advance_source_head('folder-one/file',None,old.id)
    second=EpisodeStore(path)
    assert second.source_head('folder-one/file')==old.id
    second.advance_source_head('folder-one/file',old.id,new.id)
    with pytest.raises(EpisodeError):
        first.advance_source_head('folder-one/file',old.id,old.id)
    assert first.source_head('folder-one/file')==new.id
    first.advance_source_head('folder-two/file',None,old.id)
    assert second.source_head('folder-two/file')==old.id
    with pytest.raises(EpisodeError):
        first.advance_source_head('missing',None,'unknown')
    assert second.source_head('missing') is None
    assert first.get(old.id).body=='Alter Inhalt'
    first.close();second.close()


def test_changed_file_invalidates_confirmed_evidence_and_preserves_original(tmp_path):
    from icarus_memory.claims import ClaimStore, KnowledgeService
    from icarus_memory.proposals import ProposalStore, Evidence
    from icarus_memory.ingest import ingest_directory
    from icarus_memory.source_versions import track_document
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    claims=ClaimStore(tmp_path/'knowledge.sqlite3')
    proposals=ProposalStore(tmp_path/'proposals.sqlite3')
    service=KnowledgeService(proposals=proposals,claims=claims,episodes=episodes)
    root=tmp_path/'approved';root.mkdir()
    path=root/'project.md';path.write_text('Das Projekt hat Budget.',encoding='utf-8')
    def run():
        return ingest_directory(episodes,root,roots=[root],on_source=lambda root,ref,episode: track_document(episodes,claims,root,ref,episode))
    first=run();old=episodes.get(first.episode_ids[0])
    person=claims.entities.create('person','Alex')
    proposal,_=service.propose(subject_ref=person['id'],predicate='budget',value='zugesagt',statement=old.body,rationale='Quelle',evidence=[Evidence(old.id,old.body,old.digest)])
    claim=service.accept(proposal.id,supersedes=[])
    assert claims.is_usable(claim)
    episodes.close();episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    path.write_text('Das Budget wurde gestrichen.',encoding='utf-8')
    changed=run()
    assert changed.changed==1 and changed.recorded==1
    assert not claims.is_usable(claims.get(claim.id))
    assert episodes.get(old.id).body==old.body
    assert episodes.get(old.id).state.value=='ignored'
    assert episodes.get(changed.episode_ids[0]).state.value=='new'
    assert run().changed==0 and len(episodes.all_episodes())==2
    # Alte Fassungen dürfen durch ein Zurückkopieren nicht wieder gültig werden.
    path.write_text(old.body,encoding='utf-8')
    assert run().changed==1
    assert not claims.is_usable(claims.get(claim.id))
    assert episodes.get(old.id).state.value=='ignored'
    episodes.close();claims.close();proposals.close()


def test_identical_files_have_independent_evidence_and_stable_content_digest(tmp_path):
    from icarus_memory.ingest import ingest_directory
    from icarus_memory.episodes import digest_of
    from icarus_memory.source_versions import track_document
    from icarus_memory.claims import ClaimStore
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3')
    claims=ClaimStore(tmp_path/'claims.sqlite3')
    root=tmp_path/'files';root.mkdir()
    for name in ('a.md','b.md'):
        (root/name).write_text('Gleicher Inhalt',encoding='utf-8')
    def run():
        return ingest_directory(episodes,root,roots=[root],on_source=lambda root,ref,episode:track_document(episodes,claims,root,ref,episode))
    first=run()
    assert first.recorded==2
    a,b=[episodes.get(id) for id in first.episode_ids]
    assert a.digest==b.digest==digest_of('Gleicher Inhalt')
    assert a.id!=b.id and a.provenance.source_ref!=b.provenance.source_ref
    from icarus_memory.claims import KnowledgeService
    from icarus_memory.proposals import ProposalStore, Evidence
    proposals=ProposalStore(tmp_path/'proposals.sqlite3')
    service=KnowledgeService(proposals=proposals,claims=claims,episodes=episodes)
    person=claims.entities.create('person','Alex')
    accepted=[]
    for index,source in enumerate((a,b)):
        proposal,_=service.propose(subject_ref=person['id'],predicate=f'role_{index}',value='Quelle',statement=source.body,rationale='Eigener Beleg',evidence=[Evidence(source.id,source.body,source.digest)])
        accepted.append(service.accept(proposal.id,supersedes=[]))
    assert run().duplicates==2
    (root/'a.md').write_text('Geänderter Inhalt',encoding='utf-8')
    result=run()
    assert result.changed==1 and result.recorded==1 and result.duplicates==1
    assert episodes.get(a.id).state.value=='ignored'
    assert episodes.get(b.id).state.value=='new'
    assert not claims.is_usable(claims.get(accepted[0].id))
    assert claims.is_usable(claims.get(accepted[1].id))
    proposals.close()
    episodes.close();claims.close()


def test_v3_upgrade_preserves_unique_and_ambiguous_existing_heads(tmp_path):
    import sqlite3
    path=tmp_path/'episodes.sqlite3'
    store=EpisodeStore(path)
    provenance=Provenance(source_type=SourceType.DOCUMENT)
    one=store.record(EpisodeKind.DOCUMENT,'Eindeutig','Ein Inhalt',provenance)[0]
    shared=store.record(EpisodeKind.DOCUMENT,'Geteilt','Geteilter Inhalt',provenance)[0]
    store.advance_source_head('one',None,one.id)
    store.advance_source_head('two',None,shared.id)
    store.advance_source_head('three',None,shared.id)
    store.close()
    with sqlite3.connect(path) as connection:
        from tests.working_memory_legacy import drop_intake_extensions
        drop_intake_extensions(connection)
        for table in ('working_memory_terms', 'working_memory_items', 'working_memory_sources', 'working_memory_scan'):
            connection.execute('DROP TABLE ' + table)
        from icarus_memory.support_schema import EPISODE_TRIGGERS
        for trigger in EPISODE_TRIGGERS:
            connection.execute('DROP TRIGGER ' + trigger)
        connection.execute('DROP INDEX idx_source_heads_episode')
        connection.execute('DROP TABLE episode_produced_assertions')
        connection.execute('ALTER TABLE episodes DROP COLUMN support_generation')
        connection.execute('DROP INDEX idx_episodes_digest')
        connection.execute('ALTER TABLE episodes DROP COLUMN source_key')
        connection.execute('ALTER TABLE episodes DROP COLUMN metadata_digest')
        connection.execute('CREATE UNIQUE INDEX idx_episodes_digest ON episodes(digest)')
        connection.execute('PRAGMA user_version=3')
    store=EpisodeStore(path)
    for key, previous in [('one',one),('two',shared),('three',shared)]:
        episode,created=store.record(EpisodeKind.DOCUMENT,previous.title,previous.body,provenance,source_key=key)
        assert not created and episode.id==previous.id
        assert store.source_head(key)==previous.id
    assert len(store.all_episodes())==2
    store.close()


@pytest.mark.parametrize("adapter", ["markdown", "obsidian", "notion", "dateien"])
def test_missing_file_is_excluded_only_after_complete_successful_scan(tmp_path, monkeypatch, adapter):
    from pathlib import Path
    from icarus_memory.ingest import ingest_directory
    from icarus_memory.source_versions import track_document, exclude_missing_documents
    from icarus_memory.claims import ClaimStore, KnowledgeService
    from icarus_memory.proposals import ProposalStore, Evidence
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3');claims=ClaimStore(tmp_path/'claims.sqlite3')
    proposals=ProposalStore(tmp_path/'proposals.sqlite3')
    service=KnowledgeService(proposals=proposals,claims=claims,episodes=episodes)
    root=tmp_path/'files';root.mkdir()
    a=root/'a.md';b=root/'b.md'
    a.write_text('Budget ist zugesagt.',encoding='utf-8');b.write_text('Unabhängige Quelle',encoding='utf-8')
    def run(limit=5000):
        return ingest_directory(episodes,root,adapter=adapter,roots=[root],limit=limit,
            on_source=lambda root,ref,episode:track_document(episodes,claims,root,ref,episode),
            on_complete=lambda root,adapter,observed:exclude_missing_documents(episodes,claims,root,adapter,observed))
    first=run();old=episodes.get(first.episode_ids[0])
    person=claims.entities.create('person','Alex')
    proposal,_=service.propose(subject_ref=person['id'],predicate='budget',value='zugesagt',statement=old.body,rationale='Beleg',evidence=[Evidence(old.id,old.body,old.digest)])
    claim=service.accept(proposal.id,supersedes=[])
    a.unlink()
    assert run(limit=0).errors
    assert claims.is_usable(claims.get(claim.id))
    original=Path.read_text
    def denied(path,*args,**kwargs):
        if path==b: raise PermissionError('Nicht lesbar')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',denied)
    assert run().errors
    assert claims.is_usable(claims.get(claim.id))
    monkeypatch.setattr(Path,'read_text',original)
    original_stat=Path.stat
    def blocked_stat(path,*args,**kwargs):
        if path==a: raise PermissionError('Dateistatus nicht prüfbar')
        return original_stat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'stat',blocked_stat)
    assert run().errors
    assert claims.is_usable(claims.get(claim.id))
    monkeypatch.setattr(Path,'stat',original_stat)
    result=run()
    assert result.removed==1 and not result.errors
    assert not claims.is_usable(claims.get(claim.id))
    assert episodes.get(old.id).body==old.body
    assert episodes.get(old.id).state.value=='ignored'
    assert run().removed==0
    a.write_text(old.body,encoding='utf-8')
    assert run().removed==0
    assert not claims.is_usable(claims.get(claim.id))
    assert episodes.get(old.id).state.value=='ignored'
    episodes.close();claims.close();proposals.close()


def test_unavailable_root_is_not_treated_as_all_files_deleted(tmp_path):
    from icarus_memory.claims import ClaimStore
    from icarus_memory.source_versions import track_document, exclude_missing_documents
    episodes=EpisodeStore(tmp_path/'episodes.sqlite3');claims=ClaimStore(tmp_path/'claims.sqlite3')
    root=tmp_path/'files';root.mkdir()
    episode=episodes.record(EpisodeKind.DOCUMENT,'Quelle','Inhalt',Provenance(source_type=SourceType.DOCUMENT,source_ref='vault:a.md'))[0]
    track_document(episodes,claims,root,'vault:a.md',episode)
    root.rmdir()
    with pytest.raises(FileNotFoundError):
        exclude_missing_documents(episodes,claims,root,'markdown')
    assert episodes.get(episode.id).state.value=='new'
    episodes.close();claims.close()


@pytest.mark.parametrize("adapter,filename,original,replacement", [
    ("markdown", "a.md", "Budget zugesagt", ""),
    ("obsidian", "a.md", "Budget zugesagt", "---\ntitle: Leer\n---\n"),
    ("dateien", "a.txt", "Budget zugesagt", "   "),
    ("notion", "a.md", "# Budget\n\nBudget zugesagt", "# Budget\n"),
    ("notion", "a.csv", "Name,Budget\nAlpha,Ja\nBeta,Nein\n", "Name,Budget\nAlpha,Ja\n"),
    ("notion", "a.csv", "Name,Budget\nAlpha,Ja\n", "Name,Budget\n"),
])
def test_removed_content_invalidates_old_evidence(tmp_path, adapter, filename, original, replacement):
    from icarus_memory.ingest import ingest_directory
    from icarus_memory.source_versions import track_document, exclude_missing_documents
    from icarus_memory.claims import ClaimStore, KnowledgeService
    from icarus_memory.proposals import ProposalStore, Evidence
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    root = tmp_path / 'files'; root.mkdir()
    path = root / filename; path.write_text(original, encoding='utf-8')
    def run():
        return ingest_directory(episodes, root, adapter=adapter, roots=[root],
            on_source=lambda root, ref, episode: track_document(episodes, claims, root, ref, episode),
            on_complete=lambda root, adapter, *manifest: exclude_missing_documents(episodes, claims, root, adapter, *manifest))
    first = run()
    old = episodes.get(first.episode_ids[-1])
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    person = claims.entities.create('person', 'Alex')
    proposal, _ = service.propose(subject_ref=person['id'], predicate='budget', value='Beleg',
        statement=old.body, rationale='Quelle', evidence=[Evidence(old.id, old.body, old.digest)])
    claim = service.accept(proposal.id, supersedes=[])
    # Größenlimit ist kein Beweis dafür, dass alter Inhalt entfernt wurde.
    path.write_text('x' * 600_000, encoding='utf-8')
    assert run().removed == 0
    assert claims.is_usable(claims.get(claim.id))
    path.write_text(replacement, encoding='utf-8')
    second = run()
    assert not second.errors
    assert second.removed == 1
    assert not claims.is_usable(claims.get(claim.id))
    assert episodes.get(old.id).state.value == 'ignored'
    assert episodes.get(old.id).body == old.body
    assert run().removed == 0
    if len(first.episode_ids) > 1:
        assert episodes.get(first.episode_ids[0]).state.value == 'new'
    episodes.close(); claims.close(); proposals.close()


@pytest.mark.parametrize('field,value', [('title', 'Neuer Titel'), ('participants', 'Bea'), ('date', '2026-09-09'), ('tags', 'wichtig')])
def test_metadata_change_with_same_text_creates_new_evidence(tmp_path, field, value):
    from icarus_memory.claims import ClaimStore, KnowledgeService
    from icarus_memory.proposals import ProposalStore, Evidence
    from icarus_memory.ingest import ingest_directory
    from icarus_memory.source_versions import track_document
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    root = tmp_path / 'files'; root.mkdir()
    file = root / 'a.md'
    original = '---\ntitle: Besprechung\nparticipants: Alex\ndate: 2026-09-08\ntags: planung\n---\nBudget zugesagt.'
    file.write_text(original, encoding='utf-8')
    def run():
        return ingest_directory(episodes, root, roots=[root],
            on_source=lambda root, ref, episode: track_document(episodes, claims, root, ref, episode))
    old = episodes.get(run().episode_ids[0])
    person = claims.entities.create('person', 'Alex')
    proposal, _ = service.propose(subject_ref=person['id'], predicate='budget', value='zugesagt',
        statement=old.body, rationale='Quelle', evidence=[Evidence(old.id, old.body, old.digest)])
    claim = service.accept(proposal.id, supersedes=[])
    replacement = '\n'.join(f'{field}: {value}' if line.startswith(f'{field}:') else line for line in original.split('\n'))
    file.write_text(replacement, encoding='utf-8')
    changed = run()
    assert changed.recorded == 1 and changed.changed == 1
    new = episodes.get(changed.episode_ids[0])
    assert old.digest == new.digest and old.body == new.body and old.id != new.id
    assert episodes.get(old.id).state.value == 'ignored'
    assert not claims.is_usable(claims.get(claim.id))
    assert new.state.value == 'new'
    if field == 'title': assert new.title == value
    if field == 'participants': assert new.participants == [value] and old.participants == ['Alex']
    if field == 'date': assert new.occurred_at.date().isoformat() == value
    if field == 'tags': assert new.tags == [value]
    episodes.close(); episodes = EpisodeStore(path)
    assert run().duplicates == 1
    file.write_text(original, encoding='utf-8')
    assert run().changed == 1
    assert episodes.get(old.id).state.value == 'ignored'
    assert not claims.is_usable(claims.get(claim.id))
    episodes.close(); claims.close(); proposals.close()


def test_v4_metadata_upgrade_preserves_ids_and_normalizes_equivalent_metadata(tmp_path):
    import sqlite3
    from datetime import datetime, timezone, timedelta
    path = tmp_path / 'episodes.sqlite3'
    store = EpisodeStore(path)
    provenance = Provenance(source_type=SourceType.DOCUMENT, source_ref='vault:a.md')
    instant = datetime(2026, 9, 8, 8, tzinfo=timezone.utc)
    old, _ = store.record(EpisodeKind.DOCUMENT, 'Quelle', 'Text', provenance,
        source_key='file-a', occurred_at=instant, participants=['Alex', 'Bea'], tags=['eins', 'zwei'])
    store.advance_source_head('file-a', None, old.id)
    store.close()
    with sqlite3.connect(path) as conn:
        from tests.working_memory_legacy import drop_intake_extensions
        drop_intake_extensions(conn)
        for table in ('working_memory_terms', 'working_memory_items', 'working_memory_sources', 'working_memory_scan'):
            conn.execute('DROP TABLE ' + table)
        from icarus_memory.support_schema import EPISODE_TRIGGERS
        for trigger in EPISODE_TRIGGERS:
            conn.execute('DROP TRIGGER ' + trigger)
        conn.execute('DROP INDEX idx_source_heads_episode')
        conn.execute('DROP TABLE episode_produced_assertions')
        conn.execute('ALTER TABLE episodes DROP COLUMN support_generation')
        conn.execute('DROP INDEX idx_episodes_digest')
        conn.execute('ALTER TABLE episodes DROP COLUMN metadata_digest')
        conn.execute('CREATE UNIQUE INDEX idx_episodes_digest ON episodes(digest, source_key)')
        conn.execute('PRAGMA user_version=4')
    store = EpisodeStore(path)
    known, created = store.record(EpisodeKind.DOCUMENT, 'Quelle', 'Text', provenance,
        source_key='file-a', occurred_at=instant.astimezone(timezone(timedelta(hours=2))),
        participants=['Bea', 'Alex'], tags=['zwei', 'eins', 'eins'])
    assert not created and known.id == old.id
    assert known.digest == old.digest and known.participants == old.participants
    assert store.source_head('file-a') == old.id
    changed, created = store.record(EpisodeKind.DOCUMENT, 'Quelle', 'Text', provenance,
        source_key='file-a', occurred_at=instant, participants=['Bea'], tags=['eins', 'zwei'])
    assert created and changed.id != old.id and changed.digest == old.digest
    store.close()
