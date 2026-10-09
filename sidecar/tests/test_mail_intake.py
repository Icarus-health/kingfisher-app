from datetime import datetime, timezone
import pytest
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake
from icarus_memory.connectors.mail import Message

class Reader:
    generation = '7'
    count = 6
    fail = set()
    def inventory_page(self, folder, after_uid=0, before_uid=None, limit=100, uidvalidity=None):
        if uidvalidity and uidvalidity != self.generation:
            raise ValueError('generation changed')
        upper = self.count if before_uid is None else min(before_uid, self.count)
        end = min(upper, after_uid + limit)
        return dict(folder=folder, uidvalidity=self.generation, upper_uid=upper,
                    uids=list(range(after_uid+1,end+1)), next_uid=end, done=end>=upper)
    def message_in_folder(self, folder, uid):
        if int(uid.split('.')[1]) in self.fail:
            raise OSError('private server response')
        return Message(uid, uid, 'Alice <alice@example.org>', datetime(2026,1,1,tzinfo=timezone.utc), uid, False, body=uid)


def test_restart_progress_and_actual_counts(tmp_path):
    path=tmp_path/'episodes.sqlite3'
    ep=EpisodeStore(path); intake=Intake(ep); reader=Reader()
    intake.start('a',['INBOX'])
    intake.step('a',reader,batch=2)
    assert intake.status('a')['folders'][0]['total']==6
    ep.close(); ep=EpisodeStore(path); intake=Intake(ep)
    for _ in range(5): intake.step('a',reader,batch=2)
    state=intake.status('a')['folders'][0]
    assert state['captured']==6 and state['pending']==0 and state['inventory_complete']
    assert sum(ep.counts().values())==6
    ep.close()


def test_verlauf_von_neu_nach_alt(tmp_path):
    # Fürs Briefing zählt das Jüngste: Der Verlauf eines Postfachs kommt mit der höchsten UID zuerst (docs/46).
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep); r=Reader(); r.count=10
    intake.start('a',['INBOX'])
    intake.step('a',r,batch=3)
    with ep._lock:
        erste=[u for (u,) in ep._conn.execute("SELECT uid FROM mail_intake_items WHERE status='captured' ORDER BY uid")]
    assert erste==[8,9,10]
    ep.close()


def test_failures_do_not_block_later_messages_or_leak(tmp_path):
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep); r=Reader(); r.fail={1}
    intake.start('a',['INBOX'])
    for _ in range(3): intake.step('a',r,batch=3)
    state=intake.status('a'); assert state['folders'][0]['failed']==1
    assert state['folders'][0]['captured']==5
    assert 'private' not in str(state)


def test_new_mail_not_starved_and_pause_prevents_contact(tmp_path):
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep); r=Reader();r.count=50
    intake.start('a',['INBOX']); intake.step('a',r,batch=2)
    r.count=51; intake.step('a',r,batch=2)
    with ep._lock:
        assert ep._conn.execute("SELECT status FROM mail_intake_items WHERE uid=51").fetchone()[0]=='captured'
    intake.pause('a',True)
    class Forbidden:
        def inventory_page(self,*a,**k):pytest.fail('paused network')
    intake.step('a',Forbidden())
    assert intake.status('a')['paused']


def test_atomic_capture_checkpoint(tmp_path,monkeypatch):
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep); intake.start('a',['INBOX'])
    original=intake._captured
    def fail(*a,**k):raise RuntimeError('simulated crash')
    monkeypatch.setattr(intake,'_captured',fail)
    intake.step('a',Reader(),batch=1)
    assert sum(ep.counts().values())==0
    monkeypatch.setattr(intake,'_captured',original)
    intake.retry('a')
    intake.step('a',Reader(),batch=1)
    assert sum(ep.counts().values())==1


def test_revocation_during_fetch_prevents_capture(tmp_path):
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep);intake.start('a',['INBOX']);allowed=[True]
    class Revoked(Reader):
        def message_in_folder(self,*args):
            result=super().message_in_folder(*args);allowed[0]=False;return result
    intake.step('a',Revoked(),permitted=lambda:allowed[0])
    assert sum(ep.counts().values())==0


def test_gmail_labels_deduplicate_account_scoped_provider_id(tmp_path):
    from dataclasses import replace
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep)
    class Gmail(Reader):
        count=1
        def message_in_folder(self,*a):return replace(super().message_in_folder(*a),provider_id='123')
    intake.start('a',['INBOX','All']); intake.step('a',Gmail())
    assert sum(ep.counts().values())==1
    assert sum(f['duplicates'] for f in intake.status('a')['folders'])==1
    intake.start('b',['All']);intake.step('b',Gmail())
    assert sum(ep.counts().values())==2


def test_generation_reset_preserves_originals_and_restarts_inventory(tmp_path):
    from icarus_memory.connectors.mail import MailboxGenerationChanged
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep);intake.start('a',['INBOX'])
    class Reset(Reader):
        count=1
        def inventory_page(self,*a,**kw):
            if kw.get('uidvalidity') and kw['uidvalidity']!=self.generation:raise MailboxGenerationChanged('reset')
            return super().inventory_page(*a,**kw)
    r=Reset();intake.step('a',r);r.generation='8';intake.step('a',r)
    assert sum(ep.counts().values())==1
    intake.step('a',r)
    assert sum(ep.counts().values())==2
    assert intake.status('a')['folders'][0]['captured']==1


def test_analysis_progress_is_invalidated_on_withdrawal(tmp_path):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep);intake.start('a',['INBOX'])
    ids=intake.step('a',Reader(),batch=1); work=WorkingMemoryStore(ep)
    snap=work.pending(episode_ids=ids)[0]
    work.commit(snap,[{'start':0,'end':len(snap.episode.body),'kind':'fact'}],model='test')
    assert intake.status('a')['folders'][0]['analyzed']==1
    ep.ignore(ids[0])
    assert intake.status('a')['folders'][0]['analyzed']==0
    assert intake.status('a')['folders'][0]['excluded']==1


def test_legacy_inbox_source_is_reused_without_provider_id(tmp_path):
    from dataclasses import replace
    from icarus_memory.mail_ingestion import remember
    ep=EpisodeStore(tmp_path/'episodes.sqlite3'); intake=Intake(ep);r=Reader();r.count=1
    remember(ep,replace(r.message_in_folder('INBOX','7.1'),account_id='a',uid='a:7.1'))
    intake.start('a',['INBOX']);intake.step('a',r)
    assert sum(ep.counts().values())==1
    assert intake.status('a')['folders'][0]['duplicates']==1


def test_large_inventory_is_bounded_and_live_survives_analysis_backpressure(tmp_path):
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep);r=Reader();r.count=10000
    intake.start('a',['INBOX'])
    for _ in range(50):intake.step('a',r,batch=8)
    state=intake.status('a')['folders'][0]
    assert state['total']==10000 and state['inventory_complete']
    assert state['captured']<=208 and state['pending']>9000
    r.count=10001;intake.step('a',r,batch=8)
    assert ep._conn.execute('SELECT status FROM mail_intake_items WHERE uid=10001').fetchone()[0]=='captured'


def test_backup_roundtrip_preserves_progress_and_manual_categories(tmp_path):
    from icarus_memory.backup import snapshot_all,verify_snapshot_set
    from icarus_memory.memory_categories import Categories
    path=tmp_path/'episodes.sqlite3';ep=EpisodeStore(path);intake=Intake(ep);intake.start('a',['INBOX'])
    ids=intake.step('a',Reader(),batch=2)
    Categories(ep).correct(ids[0],['work'])
    before=intake.status('a')
    saved=snapshot_all(tmp_path,tmp_path/'backups')
    assert any(entry['name']=='episodes.sqlite3' for entry in verify_snapshot_set(saved))
    restored=EpisodeStore(saved/'episodes.sqlite3')
    assert Intake(restored).status('a')==before
    assert Categories(restored).list_for(ids[0])['categories'][0]['origin']=='user'
    restored.close();ep.close()


def test_retry_also_releases_failed_interpretation_cooldowns(tmp_path):
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from icarus_memory.memory_categories import Categories
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep);intake.start('a',['INBOX'])
    source=intake.step('a',Reader(),batch=1)[0]
    store=WorkingMemoryStore(ep);snapshot=store.pending(episode_ids=[source])[0];store.fail(snapshot)
    with ep.transaction():Categories(ep)._set_status(source,'test',1,'failed',retry_after=9999999999)
    intake.retry('a')
    assert store.pending(episode_ids=[source])
    assert ep._conn.execute('SELECT retry_after FROM memory_category_sources WHERE episode_id=?',(source,)).fetchone()[0]==0


def test_status_exposes_bounded_current_category_failure_reasons(tmp_path):
    from icarus_memory.memory_categories import Categories
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep);intake.start('a',['INBOX'])
    source=intake.step('a',Reader(),batch=1)[0]
    categories=Categories(ep)
    _current_category_failure(categories, source)
    folder=intake.status('a')['folders'][0]
    assert folder['categories_failed']==1
    assert folder['categories_failed_by']=={'provider_error':1}
    with ep.transaction():
        ep._conn.execute('UPDATE episodes SET support_generation=support_generation+1 WHERE id=?',(source,))
    refreshed=intake.status('a')['folders'][0]
    assert refreshed['categories_failed']==0
    assert refreshed['categories_failed_by']=={}
    ep.close()


def _current_category_failure(categories, source):
    from icarus_memory.memory_categories import source_fingerprint
    snapshot = categories.memory._snapshot(source)
    version = categories._required_version(source)
    with categories.episodes.transaction():
        categories._set_status(source, source_fingerprint(snapshot), version, 'failed',
                               failure_code='provider_error')


@pytest.mark.parametrize('transition', ['targeted_taxonomy', 'dismiss', 'replacement'])
def test_status_category_failure_reasons_follow_current_source_projection(tmp_path, transition):
    from icarus_memory.memory_categories import Categories
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from icarus_memory.episodes import EpisodeKind, Provenance, SourceType
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep);intake.start('a',['INBOX'])
    source=intake.step('a',Reader(),batch=1)[0]
    categories=Categories(ep);_current_category_failure(categories, source)
    assert categories.list_for(source)['status']=='failed'
    before=intake.status('a')['folders'][0]
    assert before['categories_failed']==1 and before['categories_failed_by']=={'provider_error':1}

    if transition == 'targeted_taxonomy':
        categories.add_category('new_topic', 'New topic', episode_ids=[source])
        expected='pending'
    elif transition == 'dismiss':
        assert WorkingMemoryStore(ep).dismiss(source)
        expected='excluded'
    else:
        old=ep._conn.execute('SELECT source_key FROM episodes WHERE id=?',(source,)).fetchone()[0]
        replacement,created=ep.record(EpisodeKind.MESSAGE,'Replacement','New version',
            Provenance(SourceType.EMAIL,source_ref='replacement'),source_key=old)
        assert created
        ep.advance_source_head(old,source,replacement.id)
        expected='excluded'

    assert categories.list_for(source)['status']==expected
    after=intake.status('a')['folders'][0]
    assert after['categories_failed']==0
    assert after['categories_failed_by']=={}
    assert after['categories_pending']==(1 if expected=='pending' else 0)
    ep.close()


def test_status_never_exposes_unrecognized_persisted_category_failure_code(tmp_path):
    from icarus_memory.memory_categories import Categories
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep);intake.start('a',['INBOX'])
    source=intake.step('a',Reader(),batch=1)[0]
    categories=Categories(ep);_current_category_failure(categories, source)
    with ep.transaction():
        ep._conn.execute('PRAGMA ignore_check_constraints=ON')
        ep._conn.execute("UPDATE memory_category_sources SET failure_code='private raw failure' WHERE episode_id=?",(source,))
        ep._conn.execute('PRAGMA ignore_check_constraints=OFF')
    folder=intake.status('a')['folders'][0]
    assert folder['categories_failed']==1
    assert folder['categories_failed_by']=={'unknown':1}
    assert 'private raw failure' not in str(folder)
    ep.close()


def test_status_bounds_failed_category_projection_across_windows_and_folders(tmp_path, monkeypatch):
    from icarus_memory import mail_intake as mail_intake_module
    from icarus_memory.memory_categories import Categories, source_fingerprint
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep);reader=Reader();reader.count=8
    intake.start('a',['INBOX']);intake.step('a',reader,batch=50)
    with ep._lock:
        sources=[row[0] for row in ep._conn.execute(
            "SELECT episode_id FROM mail_intake_items WHERE folder='INBOX' ORDER BY uid")]
    assert len(sources)==8 and len(set(sources))==8
    categories=Categories(ep)
    with ep.transaction():
        for source in sources:
            snapshot=categories.memory._snapshot(source)
            categories._set_status(source,source_fingerprint(snapshot),categories._required_version(source),
                                   'failed',failure_code='provider_error')
        intake.start('a',['Archive'])
        ep._conn.execute("UPDATE mail_intake_folders SET generation='7',upper_uid=8,scan_uid=8,live_uid=8,inventory_complete=1 WHERE account='a' AND folder='Archive'")
        ep._conn.executemany("INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES('a','Archive','7',?,'history','duplicate',?)",
                             [(index+1,source) for index,source in enumerate(sources)])

    calls=[]
    original=Categories.list_for
    def counted(self, source):
        calls.append(source)
        return original(self,source)
    monkeypatch.setattr(Categories,'list_for',counted)
    monkeypatch.setattr(mail_intake_module,'CATEGORY_DIAGNOSTIC_BUDGET',3,raising=False)
    monkeypatch.setattr(mail_intake_module,'STATUS_WINDOW',2)
    state=intake.status('a')

    assert len(calls)==3
    assert len(set(calls))==3
    assert state['folders'][0]['folder']=='Archive'
    assert state['folders'][0]['categories_failed']==3
    assert state['folders'][0]['categories_unverified']==5
    assert state['folders'][0]['categories_failed_by']=={'provider_error':3}
    assert state['folders'][1]['categories_failed']==3
    assert state['folders'][1]['categories_unverified']==5
    assert state['folders'][1]['categories_failed_by']=={'provider_error':3}
    ep.close()


def test_explicit_retry_reaches_current_failures_beyond_stale_diagnostic_prefix(tmp_path, monkeypatch):
    from icarus_memory.memory_categories import Categories, source_fingerprint
    from icarus_memory.working_memory_store import WorkingMemoryStore
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep);reader=Reader();reader.count=19
    intake.start('a',['INBOX']);intake.step('a',reader,batch=50)
    with ep._lock:
        sources=[row[0] for row in ep._conn.execute(
            "SELECT episode_id FROM mail_intake_items WHERE folder='INBOX' ORDER BY uid")]
    assert len(sources)==19
    categories=Categories(ep);future=9999999999
    with ep.transaction():
        for source in sources:
            snapshot=categories.memory._snapshot(source)
            categories._set_status(source,source_fingerprint(snapshot),categories._required_version(source),
                                   'failed',retry_after=future,failure_code='provider_error')

    projected_ids=[]
    original=Categories.list_for
    def record_projection(self, source):
        projected_ids.append(source)
        return original(self,source)
    monkeypatch.setattr(Categories,'list_for',record_projection)
    monkeypatch.setattr('icarus_memory.mail_intake.CATEGORY_DIAGNOSTIC_BUDGET',16)
    first=intake.status('a')['folders'][0]
    assert first['categories_failed']==16 and first['categories_unverified']==3
    stale_prefix=projected_ids[:]
    assert len(stale_prefix)==16 and len(set(stale_prefix))==16

    store=WorkingMemoryStore(ep)
    for source in stale_prefix:
        assert store.dismiss(source)
    projected_ids.clear()
    after_dismiss=intake.status('a')['folders'][0]
    assert after_dismiss['categories_failed']==0 and after_dismiss['categories_unverified']==3
    assert projected_ids==stale_prefix

    # This is the same persistence operation used by the explicit retry route.
    # The category worker's bounded page must skip the dismissed prefix and see
    # the still-current failures after it, without calling a provider/model.
    intake.retry('a')
    retry_candidates=categories._pending(limit=20)
    assert {snapshot.episode.id for snapshot, _version, _taxonomy in retry_candidates}==set(sources)-set(stale_prefix)
    ep.close()


@pytest.mark.parametrize('manual_first',[True,False])
def test_provider_identity_shared_by_manual_and_automatic_intake(tmp_path,manual_first):
    from dataclasses import replace
    from icarus_memory.mail_ingestion import remember
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep)
    class Gmail(Reader):
        count=1
        def message_in_folder(self,*a):return replace(super().message_in_folder(*a),provider_id='123')
    reader=Gmail();message=replace(reader.message_in_folder('INBOX','7.1'),account_id='a',uid='a:7.1')
    if manual_first:remember(ep,message)
    intake.start('a',['INBOX']);intake.step('a',reader)
    remember(ep,message)
    assert sum(ep.counts().values())==1
