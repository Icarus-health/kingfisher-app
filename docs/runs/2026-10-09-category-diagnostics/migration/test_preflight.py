"""Synthetic offline integration tests; never use a user's data directory."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from icarus_memory import episodes as epmod
from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.backup import UPDATE_SET_PREFIX, snapshot_all, verify_snapshot_set
from icarus_memory.claims import ClaimStore
from icarus_memory.restore_boundary import pending
from icarus_memory.update_backup import outdated

import preflight

BODY_A = 'Synthetisches Original A — unverändert.\nZweite Zeile.'
BODY_B = 'Synthetisches Original B; keine reale Mail.'


def rows(directory, sql):
    connection=sqlite3.connect(directory/'episodes.sqlite3')
    try:return connection.execute(sql).fetchall()
    finally:connection.close()


def version(directory):
    return rows(directory,'PRAGMA user_version')[0][0]


@pytest.fixture
def data(tmp_path, monkeypatch):
    folder=tmp_path/'data';folder.mkdir()
    with monkeypatch.context() as patch:
        patch.setattr(epmod,'_MIGRATIONS',epmod._MIGRATIONS[:19])
        store=epmod.EpisodeStore(folder/'episodes.sqlite3')
        for n,body in enumerate([BODY_A,BODY_B],1):
            episode,_=store.record(EpisodeKind.MESSAGE,f'Synthetic {n}',body,
                Provenance(SourceType.EMAIL,source_ref=f'synthetic:{n}'))
            with store.transaction():
                store._conn.execute('INSERT INTO memory_category_sources(episode_id,fingerprint,taxonomy_version,status,model,retry_after,support_generation) VALUES(?,?,?,?,?,?,?)',
                    (episode.id,f'fp-{n}',1,'failed' if n==1 else 'complete','synthetic',9999999999 if n==1 else None,1))
                store._conn.execute("INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES('synthetic','INBOX','7',?,'history','captured',?)",(n,episode.id))
        store.close()
    ClaimStore(folder/'knowledge.sqlite3').close()
    (folder/'einstellungen.json').write_text('{"schedule":{"enabled":false},"synthetic":true}')
    (folder/'schluessel.icarus').write_bytes(b'synthetic-opaque-placeholder-not-a-key')
    assert version(folder)==19
    return folder


def run(data, **kw):
    return preflight.run(data,service_stopped=True,unpublished=True,**kw)


def test_actual_migration_preserves_originals_rows_and_auxiliary_files(data):
    originals=rows(data,'SELECT id,digest,body,document FROM episodes ORDER BY id')
    categories=rows(data,'SELECT * FROM memory_category_sources ORDER BY episode_id')
    intake=rows(data,'SELECT * FROM mail_intake_items ORDER BY uid')
    settings=(data/'einstellungen.json').read_bytes()
    result=run(data)
    assert result['status']=='migrated',result
    assert result['publish_allowed'] is True and version(data)==20
    assert rows(data,'SELECT id,digest,body,document FROM episodes ORDER BY id')==originals
    assert rows(data,'SELECT * FROM memory_category_sources ORDER BY episode_id')==[row+(None,) for row in categories]
    assert rows(data,'SELECT * FROM mail_intake_items ORDER BY uid')==intake
    assert (data/'einstellungen.json').read_bytes()==settings
    assert not pending(data) and outdated(data)==[]
    snapshot=data/'sicherungen'/result['snapshot_name']
    assert version(snapshot)==19
    assert {entry['name'] for entry in verify_snapshot_set(snapshot)}=={'episodes.sqlite3','knowledge.sqlite3','einstellungen.json','schluessel.icarus'}
    # Public report contains aggregate fingerprints, never original content/keys.
    assert BODY_A not in json.dumps(result) and BODY_B not in json.dumps(result)


@pytest.mark.parametrize('stopped,unpublished',[(False,True),(True,False),(False,False)])
def test_refuses_without_stopped_and_unpublished_attestation(data,stopped,unpublished):
    before=(data/'episodes.sqlite3').read_bytes()
    result=preflight.run(data,service_stopped=stopped,unpublished=unpublished)
    assert result['status']=='preflight_failed' and result['publish_allowed'] is False
    assert (data/'episodes.sqlite3').read_bytes()==before
    assert not (data/'sicherungen').exists()


def test_refuses_a_second_run_or_existing_inspection_state(data):
    result=run(data);assert result['status']=='migrated'
    files=sorted(p.name for p in (data/'sicherungen').iterdir())
    result=run(data)
    assert result['status']=='preflight_failed' and version(data)==20
    assert sorted(p.name for p in (data/'sicherungen').iterdir())==files


def test_corrupted_backup_aborts_before_migration(data,monkeypatch):
    original=preflight.backup.snapshot_all
    def corrupt(*args,**kwargs):
        folder=original(*args,**kwargs)
        with (folder/'episodes.sqlite3').open('r+b') as stream:stream.write(b'bad snapshot')
        return folder
    monkeypatch.setattr(preflight.backup,'snapshot_all',corrupt)
    result=run(data)
    assert result['status']=='preflight_failed',result
    assert not result['rollback']['attempted'] and version(data)==19 and not pending(data)
    assert set(value[0] for value in rows(data,'SELECT body FROM episodes'))=={BODY_A,BODY_B}


def test_postcheck_failure_restores_schema19_and_inspection_boundary(data,monkeypatch):
    original=rows(data,'SELECT * FROM episodes ORDER BY id')
    def fail(*args,**kwargs):raise RuntimeError('synthetic postcheck failure with private-like content')
    monkeypatch.setattr(preflight,'_postcheck',fail)
    result=run(data)
    assert result['status']=='restored_inspection',result
    assert not result['publish_allowed'] and result['rollback']['verified']
    assert version(data)==19 and rows(data,'SELECT * FROM episodes ORDER BY id')==original
    marker=json.loads((data/'restore-state.json').read_text())
    assert marker['mode']=='inspection' and marker['operational'] is False
    assert outdated(data)==['episodes.sqlite3']
    assert 'private-like' not in json.dumps(result)
    assert list(data.glob('episodes.vor-wiederherstellung-*.sqlite3'))


def test_real_body_change_is_detected_and_restored(data,monkeypatch):
    original=preflight.episodes.EpisodeStore
    def changed(path):
        store=original(path)
        with store.transaction():store._conn.execute("UPDATE episodes SET body='synthetic corruption'")
        return store
    monkeypatch.setattr(preflight.episodes,'EpisodeStore',changed)
    result=run(data)
    assert result['status']=='restored_inspection',result
    assert version(data)==19 and pending(data)
    assert set(value[0] for value in rows(data,'SELECT body FROM episodes'))=={BODY_A,BODY_B}


def test_corrupt_backup_at_recovery_is_never_restored(data,monkeypatch):
    def fail(directory,*args,**kwargs):
        saved=next((directory/'sicherungen').glob('vor-update-*'))
        with (saved/'episodes.sqlite3').open('r+b') as stream:stream.write(b'corrupt after migration')
        raise RuntimeError('synthetic failed check')
    monkeypatch.setattr(preflight,'_postcheck',fail)
    result=run(data)
    assert result['status']=='recovery_failed',result
    assert result['publish_allowed'] is False and not result['rollback']['verified']
    assert version(data)==20 and pending(data)
    assert not list(data.glob('episodes.vor-wiederherstellung-*.sqlite3'))


def test_corrupt_other_database_aborts_before_any_backup_or_migration(data):
    (data/'knowledge.sqlite3').write_bytes(b'not sqlite')
    result=run(data)
    assert result['status']=='preflight_failed' and version(data)==19
    assert not (data/'sicherungen').exists()


def test_collision_does_not_overwrite_or_prune_an_old_snapshot(data,monkeypatch):
    at=datetime(2026,10,9,12,0,0,tzinfo=timezone.utc)
    old=snapshot_all(data,data/'sicherungen',prefix=UPDATE_SET_PREFIX,at=at)
    oldhash=hashlib.sha256((old/'episodes.sqlite3').read_bytes()).hexdigest()
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr(preflight,'datetime',FrozenDateTime)
    result=run(data)
    assert result['status']=='migrated',result
    assert result['snapshot_name']=='vor-update-20261009T120001Z'
    assert hashlib.sha256((old/'episodes.sqlite3').read_bytes()).hexdigest()==oldhash
    assert len(list((data/'sicherungen').glob('vor-update-*')))==2


@pytest.mark.parametrize('kind',['wal','unknown_db','symlink','inspection'])
def test_unsafe_or_uncovered_offline_layout_is_refused(data,tmp_path,kind):
    if kind=='wal':(data/'episodes.sqlite3-wal').write_bytes(b'not quiescent')
    if kind=='unknown_db':(data/'uncovered.sqlite3').write_bytes(b'not backed up')
    if kind=='symlink':
        outside=tmp_path/'outside';outside.write_bytes((data/'knowledge.sqlite3').read_bytes())
        (data/'knowledge.sqlite3').unlink();(data/'knowledge.sqlite3').symlink_to(outside)
    if kind=='inspection':(data/'restore-state.json').write_text('{}')
    result=run(data)
    assert result['status']=='preflight_failed' and result['publish_allowed'] is False
    assert not (data/'sicherungen').exists()


@pytest.mark.parametrize('failed_check',[False,True])
def test_operational_recovery_state_stays_outside_snapshot_and_is_preserved(data,monkeypatch,failed_check):
    path=data/'recovery-status.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE recovery_status(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)')
        connection.execute('INSERT INTO recovery_status VALUES(1,?)',('{"job":null,"synthetic":true}',))
    before=path.read_bytes()
    if failed_check:
        def fail(*args,**kwargs):raise RuntimeError('synthetic failure')
        monkeypatch.setattr(preflight,'_postcheck',fail)
    result=run(data)
    assert result['status']==('restored_inspection' if failed_check else 'migrated'),result
    assert path.read_bytes()==before
    assert result['operational_not_in_snapshot']==['recovery-status.sqlite3']
    manifest=verify_snapshot_set(data/'sicherungen'/result['snapshot_name'])
    assert 'recovery-status.sqlite3' not in {item['name'] for item in manifest}


def test_incomplete_but_checksummed_snapshot_is_rejected(data,monkeypatch):
    original=preflight.backup.snapshot_all
    def incomplete(*args,**kwargs):
        folder=original(*args,**kwargs);path=folder/'manifest.json';manifest=json.loads(path.read_text())
        manifest['files']=[entry for entry in manifest['files'] if entry['name']!='knowledge.sqlite3']
        path.write_text(json.dumps(manifest));return folder
    monkeypatch.setattr(preflight.backup,'snapshot_all',incomplete)
    result=run(data)
    assert result['status']=='preflight_failed' and result['error']=='snapshot_incomplete'
    assert version(data)==19 and not pending(data)


def test_product_dependency_logging_never_exposes_raw_exception_context(data,monkeypatch,caplog):
    import logging
    original=preflight.episodes.EpisodeStore
    def noisy(path):
        store=original(path)
        logging.getLogger('icarus_memory.synthetic_fault').error('SYNTHETIC_PRIVATE_ORIGINAL_VALUE')
        return store
    monkeypatch.setattr(preflight.episodes,'EpisodeStore',noisy)
    result=run(data)
    assert result['status']=='migrated'
    assert 'SYNTHETIC_PRIVATE_ORIGINAL_VALUE' not in caplog.text
    assert 'SYNTHETIC_PRIVATE_ORIGINAL_VALUE' not in json.dumps(result)


def test_exactly_one_episode_open_and_no_network_or_threads(data,monkeypatch):
    import socket,threading
    original=preflight.episodes.EpisodeStore;opens=[]
    def observed(path):opens.append(path);return original(path)
    def forbidden(*args,**kwargs):pytest.fail('Offline preflight started a network/background operation')
    monkeypatch.setattr(preflight.episodes,'EpisodeStore',observed)
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr(threading.Thread,'start',forbidden)
    result=run(data)
    assert result['status']=='migrated',result
    assert opens==[data/'episodes.sqlite3']


def test_preexisting_body_corruption_is_rejected_before_snapshot(data):
    with sqlite3.connect(data/'episodes.sqlite3') as connection:
        connection.execute("UPDATE episodes SET body='synthetic stale-digest body'")
    result=run(data)
    assert result['status']=='preflight_failed',result
    assert result['error']=='original_digest_mismatch'
    assert version(data)==19 and not (data/'sicherungen').exists()


def test_invalid_argument_returns_closed_result_and_restores_logging():
    import logging
    previous=logging.root.manager.disable
    result=preflight.run(None,service_stopped=True,unpublished=True)
    assert result['status']=='preflight_failed' and result['error']=='TypeError'
    assert logging.root.manager.disable==previous
