"""Verify persisted reply hints remain scoped to their synthetic mail account."""
from pathlib import Path
import sys,json
from dataclasses import replace
from datetime import timedelta
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source'
sys.path[:0]=[str(SOURCE/'sidecar'),str(SOURCE/'scripts'),str(SOURCE)]
from memory_acceptance_intake import load_frozen_sources,source_only_instance,offline_boundary,_source_mail
from messlatte.postfach import Postfach,postfach_installieren,rohmail
from icarus_memory.connectors.mail import MailConfig,MailConnector
from icarus_memory.mail_ingestion import remember
from icarus_memory.mail_timeline import SELF,REPLY,ReplyIndex
from icarus_memory.episodes import EpisodeStore

corpus=load_frozen_sources()
parent=replace(_source_mail(corpus.mail[0]),id='reply-persist-parent',betreff='Kuenstliche Rueckfrage',text='Bitte bestaetige den Eingang.',antwort_auf=None)
reply=replace(parent,id='reply-persist-child',zeit=parent.zeit+timedelta(hours=1),betreff='Re: Kuenstliche Rueckfrage',text='Der Eingang ist bestaetigt.',antwort_auf=parent.id)
mailbox=Postfach()
parent_uid=mailbox.ablegen('INBOX',parent.id,rohmail(parent))
reply_uid=mailbox.ablegen('INBOX',reply.id,rohmail(reply))
reader=MailConnector(MailConfig(imap_host='imap.reply.example',username=corpus.owner_address,password='synthetic-unused'))
ids={}
def assert_relation(store,account,expected):
    original=store.get(ids[(account,'parent')])
    own=[t for t in original.tags if t.startswith(SELF)]
    assert len(own)==1
    ref=REPLY+own[0][len(SELF):]
    assert ReplyIndex(store,wanted=[ref]).get(ref,original.id)==expected
    rows=store._conn.execute('SELECT value FROM episode_mail_headers WHERE episode_id=?',(original.id,)).fetchall()
    assert own[0] in {row[0] for row in rows}
    return ref

with offline_boundary(),source_only_instance(corpus,directory=ROOT/'reply-instance') as instance:
    with postfach_installieren(mailbox):
        for account,role,uid in [('account-a','parent',parent_uid),('account-a','reply',reply_uid),('account-b','parent',parent_uid)]:
            m=reader.message_mit_anhaengen('INBOX',f'1.{uid}')
            ids[(account,role)]=remember(instance.episodes,replace(m,account_id=account,uid=f'{account}:{m.uid}'),claims=instance.claims)['episode']['id']
        a=assert_relation(instance.episodes,'account-a',ids[('account-a','reply')])
        b=assert_relation(instance.episodes,'account-b',None)
        assert a!=b
        m=reader.message_mit_anhaengen('INBOX',f'1.{reply_uid}')
        ids[('account-b','reply')]=remember(instance.episodes,replace(m,account_id='account-b',uid=f'account-b:{m.uid}'),claims=instance.claims)['episode']['id']
        assert_relation(instance.episodes,'account-b',ids[('account-b','reply')])
        assert_relation(instance.episodes,'account-a',ids[('account-a','reply')])
    assert len(list(instance.episodes.each_episode()))==4
    database=instance.verzeichnis/'daten'/'episodes.sqlite3'

with offline_boundary():
    reopened=EpisodeStore(database)
    try:
        assert_relation(reopened,'account-a',ids[('account-a','reply')])
        assert_relation(reopened,'account-b',ids[('account-b','reply')])
    finally:reopened.close()
report={'code_commit':(ROOT/'base.txt').read_text().strip(),'status':'PASS',
        'synthetic_pair':[parent.id,reply.id],'account_count':2,'episode_count':4,
        'cross_account_false_relation':False,'persisted_relation_after_restart':True,
        'actual_full_mime_reads':mailbox.abrufe,'model_calls':0,'network_calls':0,
        'semantic_relationship_or_task_quality':'NOT EVALUATED'}
(ROOT/'reply-result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
