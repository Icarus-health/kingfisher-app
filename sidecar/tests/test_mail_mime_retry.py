"""Expliziter bestehender Retry repariert alte MIME-Präfixe, ohne Originale zu überschreiben."""
from dataclasses import replace

import pytest

from icarus_memory.claims import ClaimStore
from icarus_memory.connectors import mail
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake
from tests.test_mail_bounded_mime import multipart_pdf, reader as wire_reader


def inventory(folder, after_uid=0, before_uid=None, limit=200, uidvalidity=None, **kwargs):
    return dict(folder=folder, uidvalidity='7', upper_uid=103, uids=[103] if after_uid < 103 else [],
                next_uid=103, next_before_uid=0, done=True)


@pytest.fixture
def partial(tmp_path, monkeypatch, request):
    raw, pdf = multipart_pdf()
    connector, server = wire_reader(monkeypatch, raw)
    monkeypatch.setattr(connector, 'inventory_page', inventory)
    if getattr(request, 'param', None)=='gmail':
        server.capabilities=(b'X-GM-EXT-1',)
        server.change=lambda server, number, result: ('OK', [(result[1][0][0].replace(b'FLAGS',b'X-GM-MSGID 123 FLAGS'),result[1][0][1]),b')'])
    monkeypatch.setattr('icarus_memory.document_text.pdf_seiten',
                        lambda data, **kwargs: {'seiten': ['Erfundene vollständige Unterlage.'], 'gesamt': 1, 'leer': []})
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    intake = Intake(episodes); intake.start('qa', ['INBOX'])
    with monkeypatch.context() as old_limit:
        old_limit.setattr(mail, 'MAX_MESSAGE_MIME_BYTES', 2 * 1024 * 1024)
        parent = intake.step('qa', connector, batch=1, claims=claims)[0]
    original = episodes.get(parent).to_dict()
    assert 'source:truncated' in original['tags'] and len(server.requests) == 1
    yield path, episodes, claims, connector, server, parent, original
    episodes.close(); claims.close()


def test_existing_retry_after_restart_refetches_complete_bounded_mime_and_retains_original(partial):
    path, episodes, claims, connector, server, parent, original = partial
    episodes.close(); reopened = EpisodeStore(path)
    try:
        intake = Intake(reopened)
        intake.retry('qa')
        repaired = intake.step('qa', connector, batch=1, claims=claims)
        assert len(server.requests) == 3, 'Retry muss die vollständige MIME über den vorhandenen Connector neu holen'
        assert repaired and repaired[0] != parent
        current = reopened.get(repaired[0])
        assert 'source:truncated' not in current.tags
        assert reopened.get(parent).body == original['body']
        assert reopened.get(parent).digest == original['digest']
        assert reopened.get(parent).state.value == 'ignored'
        assert reopened.support_snapshot(current.id).head_id == current.id
        children = reopened.mail_attachment_children(current.id)
        assert len(children) == 1 and 'Erfundene vollständige Unterlage.' in reopened.get(children[0]).body
        assert intake.status('qa')['mime_refreshable'] == 0
    finally:
        reopened.close()


def test_partial_capture_is_visible_to_existing_retry_status(partial):
    _, ep, _, _, server, _, _ = partial
    assert Intake(ep).status('qa')['mime_refreshable'] == 1
    assert len(server.requests) == 1, 'Status darf nicht nachladen'


@pytest.mark.parametrize('blocked', ['mailbox_pause', 'permission', 'light_mode'])
def test_queued_refresh_respects_pause_permission_and_light_mode(partial, blocked):
    _, ep, claims, connector, server, _, _ = partial
    intake=Intake(ep); intake.retry('qa')
    # Früher neue Post darf durch den leichten Takt nicht als Altbestand nachgeladen werden.
    ep._conn.execute("UPDATE mail_intake_items SET lane='live'")
    ep._conn.commit()
    if blocked == 'mailbox_pause': intake.pause('qa', True)
    intake.step('qa', connector, claims=claims, nur_neu=blocked=='light_mode',
                permitted=lambda: blocked!='permission')
    assert len(server.requests) == 1
    assert ep._conn.execute('SELECT status FROM mail_intake_items').fetchone()[0] == 'pending'


@pytest.mark.parametrize('change', ['ignored', 'completed', 'metadata', 'revoked', 'provider_changed'])
def test_refresh_during_fetch_cannot_replace_changed_or_unpermitted_sources(partial, change):
    _, ep, claims, connector, server, parent, original = partial
    from icarus_memory.mail_ingestion import remember
    intake=Intake(ep); intake.retry('qa'); allowed=[True]
    fetch=connector.message_mit_anhaengen
    completed=[]
    def changed(folder, uid):
        message=fetch(folder,uid)
        if change=='ignored': ep.ignore(parent)
        if change=='completed':
            result=remember(ep,replace(message, account_id='qa',uid='qa:'+uid),claims=claims)
            completed.append(result['episode']['id'])
        if change=='metadata': ep.add_contacts(parent,[{'adresse':'other@example.invalid','rolle':'cc'}], ['Other'])
        if change=='revoked': allowed[0]=False
        return replace(message,provider_id='different') if change=='provider_changed' else message
    connector.message_mit_anhaengen=changed
    result=intake.step('qa',connector,claims=claims,permitted=lambda:allowed[0])
    assert not result
    assert ep.get(parent).body == original['body']
    heads=[row[0] for row in ep._conn.execute('SELECT episode_id FROM source_heads WHERE source_key NOT LIKE "%:attachment:%"')]
    assert (completed[0] in heads) if completed else parent in heads
    assert not any('different' in (ep.get(row[0]).provenance.source_ref or '') for row in ep._conn.execute('SELECT id FROM episodes'))


def test_still_partial_is_terminal_across_ticks_explicit_retries_and_restart(partial, monkeypatch):
    path, ep, claims, connector, server, parent, original = partial
    intake=Intake(ep); intake.retry('qa')
    with monkeypatch.context() as capped:
        capped.setattr(mail,'MAX_MESSAGE_MIME_BYTES',2*1024*1024)
        assert intake.step('qa',connector,claims=claims)==[]
    assert len(server.requests)==2 and ep.get(parent).to_dict()==original
    ep.close(); reopened=EpisodeStore(path)
    try:
        intake=Intake(reopened); intake.retry('qa')
        for _ in range(3): intake.step('qa',connector,claims=claims)
        assert len(server.requests)==2 and intake.status('qa')['mime_refreshable']==0
    finally: reopened.close()


@pytest.mark.parametrize('partial', ['gmail'], indirect=True)
def test_same_source_gmail_label_rows_consume_one_refresh_capability(partial):
    _, ep, claims, connector, server, parent, _ = partial
    ep._conn.execute("INSERT INTO mail_intake_folders SELECT account,'All Mail',generation,upper_uid,scan_uid,live_uid,inventory_complete,paused,error,updated FROM mail_intake_folders")
    ep._conn.execute("""INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id)
        SELECT account,'All Mail',generation,uid,'history','duplicate',episode_id FROM mail_intake_items""")
    ep._conn.commit()
    intake=Intake(ep); intake.retry('qa')
    assert ep._conn.execute("SELECT COUNT(*) FROM mail_intake_items WHERE status='pending'").fetchone()[0]==1
    assert ep._conn.execute('SELECT MIN(mime_refresh_version) FROM mail_intake_items').fetchone()[0]>0
    intake.step('qa',connector,claims=claims)
    intake.retry('qa'); intake.step('qa',connector,claims=claims)
    assert len(server.requests)==3


@pytest.mark.parametrize('extension', ['docx', 'png'])
def test_legacy_unsupported_complete_mime_is_read_once_without_reanalyzing_unchanged_logos(tmp_path,monkeypatch,extension):
    from email.message import EmailMessage
    from email.policy import SMTP
    from icarus_memory import anhaenge
    from tests.test_mail_docx_attachments import word
    message=EmailMessage();message['Subject']='Erfundene Anlage';message.set_content('Anbei.')
    data=word(text='Erfundener Word-Haupttext.') if extension=='docx' else b'invented-logo'
    mime='vnd.openxmlformats-officedocument.wordprocessingml.document' if extension=='docx' else 'octet-stream'
    message.add_attachment(data,maintype='application',subtype=mime,filename='Unterlage.'+extension)
    connector,server=wire_reader(monkeypatch,message.as_bytes(policy=SMTP))
    monkeypatch.setattr(connector,'inventory_page',inventory)
    ep=EpisodeStore(tmp_path/'episodes.sqlite3');claims=ClaimStore(tmp_path/'claims.sqlite3');intake=Intake(ep)
    try:
        intake.start('qa',['INBOX'])
        with monkeypatch.context() as legacy:
            legacy.setattr(anhaenge,'_ist_docx',lambda *args:False)
            parent=intake.step('qa',connector,claims=claims)[0]
        snapshot=ep.support_snapshot(parent).support_fingerprint()
        assert 'source:truncated' not in ep.get(parent).tags
        assert intake.status('qa')['mime_refreshable']==1
        intake.retry('qa');intake.step('qa',connector,claims=claims)
        children=ep.mail_attachment_children(parent)
        assert len(children)==(1 if extension=='docx' else 0)
        if children: assert 'Erfundener Word-Haupttext.' in ep.get(children[0]).body
        else: assert ep.support_snapshot(parent).support_fingerprint()==snapshot
        intake.retry('qa');intake.step('qa',connector,claims=claims)
        ep.close();ep=EpisodeStore(tmp_path/'episodes.sqlite3');intake=Intake(ep)
        intake.retry('qa');intake.step('qa',connector,claims=claims)
        assert len(server.requests)==2
        assert intake.status('qa')['mime_incomplete']==0
    finally: ep.close();claims.close()


@pytest.mark.parametrize('current', ['ignored', 'complete'])
def test_only_current_incomplete_heads_are_queued(partial,current):
    _, ep, claims, connector, server, parent, _ = partial
    if current=='ignored': ep.ignore(parent)
    else:
        from icarus_memory.mail_ingestion import remember
        message=connector.message_mit_anhaengen('INBOX','7.103')
        remember(ep,replace(message,uid='qa:7.103',account_id='qa'),claims=claims)
    requests=len(server.requests)
    intake=Intake(ep);assert intake.status('qa')['mime_refreshable']==0
    intake.retry('qa');intake.step('qa',connector,claims=claims)
    assert len(server.requests)==requests


def test_refresh_shares_normal_batch_and_never_calls_screening_model(partial):
    _, ep, claims, connector, server, _, _ = partial
    ep._conn.execute("INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status) VALUES('qa','INBOX','7',104,'history','pending')")
    ep._conn.commit()
    intake=Intake(ep);intake.retry('qa')
    # Reparatur hat einen gezählten früheren Versuch, neue Post kommt zuerst.
    fetch=connector.message_mit_anhaengen
    fetched=[]
    def one(folder,uid):
        fetched.append(uid)
        if uid=='7.104': return mail.Message(uid,'Neu','synthetic@example.invalid',None,'Neu',False,body='Neu')
        return fetch(folder,uid)
    connector.message_mit_anhaengen=one
    intake.step('qa',connector,batch=1,claims=claims)
    assert fetched==['7.104'] and len(server.requests)==1
    intake.step('qa',connector,batch=1,claims=claims,
                screen=lambda _:pytest.fail('Vorhandene freigegebene Quelle braucht keine neue Modellfreigabe'))
    assert fetched==['7.104','7.103'] and len(server.requests)==3


def test_migration26_keeps_old_original_and_capture_checkpoint(partial):
    import sqlite3
    path, ep, _, _, _, parent, original=partial
    ep.close()
    with sqlite3.connect(path) as connection:
        connection.execute('ALTER TABLE mail_intake_items DROP COLUMN mime_refresh_version')
        connection.execute('PRAGMA user_version=25')
    upgraded=EpisodeStore(path)
    try:
        assert upgraded.get(parent).to_dict()==original
        item=upgraded._conn.execute('SELECT status,episode_id,mime_refresh_version FROM mail_intake_items').fetchone()
        assert tuple(item)==('captured',parent,0)
        assert upgraded._conn.execute('PRAGMA user_version').fetchone()[0]==26
        assert Intake(upgraded).status('qa')['mime_refreshable']==1
    finally: upgraded.close()


def test_missing_mime_has_priority_over_one_time_legacy_unknown_formats(partial):
    _, ep, claims, connector, _, _, _=partial
    from icarus_memory.mail_ingestion import remember
    report={'geprueft':True,'abruf_vollstaendig':True,'zuordnung_vollstaendig':True,'nicht_unterstuetzt':1}
    logo=mail.Message('qa:7.104','Logo','synthetic@example.invalid',None,'Logo',False,
                      body='Logo',account_id='qa',anhang_bericht=report)
    result=remember(ep,logo,claims=claims)
    ep._conn.execute("""INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id,attempts)
        VALUES('qa','INBOX','7',104,'history','captured',?,1)""",(result['episode']['id'],));ep._conn.commit()
    intake=Intake(ep);intake.retry('qa');fetch=connector.message_mit_anhaengen;fetched=[]
    def one(folder,uid):
        fetched.append(uid)
        return replace(logo,uid=uid,account_id='') if uid=='7.104' else fetch(folder,uid)
    connector.message_mit_anhaengen=one
    intake.step('qa',connector,batch=1,claims=claims)
    assert fetched==['7.103']


def test_inconsistent_saved_snapshot_is_skipped_without_fetch_or_source_mutation(partial):
    _, ep, claims, connector, server, parent, original=partial
    ep._conn.execute("UPDATE episodes SET metadata_digest='inconsistent' WHERE id=?",(parent,));ep._conn.commit()
    intake=Intake(ep);intake.retry('qa')
    assert intake.step('qa',connector,claims=claims)==[]
    assert len(server.requests)==1 and ep.get(parent).to_dict()==original
    assert intake.status('qa')['mime_refreshable']==0


def test_changed_folder_generation_cannot_fetch_an_old_queued_uid(partial):
    _, ep, claims, connector, server, parent, original=partial
    intake=Intake(ep);intake.retry('qa')
    ep._conn.execute("UPDATE mail_intake_folders SET generation='8'");ep._conn.commit()
    connector.inventory_page=lambda folder,**kwargs:dict(inventory(folder,**kwargs),uidvalidity='8',uids=[])
    assert intake.step('qa',connector,claims=claims)==[]
    assert len(server.requests)==1 and ep.get(parent).to_dict()==original


@pytest.mark.parametrize('rotate', [False, True])
def test_attempted_mime_gap_remains_visible_after_restart_without_more_io(tmp_path,rotate):
    from tests.test_mail_intake import NeueKennung
    class Partial(NeueKennung):
        complete=False
        def __init__(self):
            super().__init__();self.fetches=[]
        def message_mit_anhaengen(self,folder,uid):
            self.fetches.append(uid)
            return replace(super().message_in_folder(folder,uid),truncated=not self.complete,
                anhang_bericht={'geprueft':True,'abruf_vollstaendig':self.complete,
                               'zuordnung_vollstaendig':self.complete,'nicht_unterstuetzt':0})
    path=tmp_path/'episodes.sqlite3';ep=EpisodeStore(path);claims=ClaimStore(tmp_path/'claims.sqlite3')
    reader=Partial();intake=Intake(ep);intake.start('a',['INBOX'])
    try:
        parent=intake.step('a',reader,claims=claims)[0]
        if rotate:
            reader.generation='8'
            intake.step('a',reader,claims=claims);intake.step('a',reader,claims=claims)
            assert [row[0] for row in ep._conn.execute('SELECT episode_id FROM mail_intake_items')]==[parent,parent]
            reader.complete=True  # Der exakte alte Quellenkey bleibt absichtlich nicht verifizierbar.
        original=ep.get(parent).to_dict()
        intake.retry('a');assert intake.step('a',reader,claims=claims)==[]
        fetches=len(reader.fetches)
        ep.close();ep=EpisodeStore(path);intake=Intake(ep)
        for _ in range(2):
            intake.retry('a');assert intake.step('a',reader,claims=claims)==[]
        state=intake.status('a')
        assert state['mime_refreshable']==0 and state['mime_incomplete']==1
        assert len(reader.fetches)==fetches and ep.get(parent).to_dict()==original
    finally:ep.close();claims.close()


def test_pure_text_limit_with_complete_mime_never_reports_a_remaining_mime_gap(partial):
    _,ep,claims,connector,server,parent,_=partial
    ep.set_mail_attachment_report(parent,{'geprueft':True,'abruf_vollstaendig':True,
        'zuordnung_vollstaendig':True,'nicht_unterstuetzt':0})
    intake=Intake(ep);state=intake.status('qa')
    assert state['mime_refreshable']==state['mime_incomplete']==0
    intake.retry('qa');intake.step('qa',connector,claims=claims)
    assert len(server.requests)==1 and 'source:truncated' in ep.get(parent).tags
