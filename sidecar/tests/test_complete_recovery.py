"""Vollständiges Paket mit echten Einträgen in jedem gesicherten Datenbereich."""
import json
import sqlite3
from pathlib import Path

from icarus_memory import EpisodeKind, EpisodeStore, Kind, Provenance, SelfModelStore, SourceType, SqliteBackend, TaskStore, WorkspaceStore
from icarus_memory.audit import AuditLog
from icarus_memory.backup import BACKUP_DATA_FILES, SQLITE_DATA_FILES
from icarus_memory.claim_index import register as register_claim_normalizer
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.conversations import ConversationStore
from icarus_memory.logbuch import Logbuch
from icarus_memory.mac_calendar import MacCalendar
from icarus_memory.proposals import ProposalStore, Evidence
from icarus_memory.recovery_bundle import export_bundle, restore_bundle
from icarus_memory.regeln import RegelStore
from icarus_memory.rueckmeldung import Rueckmeldungen
from icarus_memory.transkript_zuordnung import Zuordnungen
from icarus_memory.secrets import Keychain


def database_contents(path):
    with sqlite3.connect(path) as connection:
        # iterdump reads the derived external-content view as well as tables.
        register_claim_normalizer(connection)
        assert connection.execute('PRAGMA integrity_check').fetchone()==('ok',)
        return (connection.execute('PRAGMA user_version').fetchone()[0], tuple(connection.iterdump()))


def test_every_backup_store_and_encrypted_key_survives_separate_restore(tmp_path, monkeypatch):
    data=tmp_path/'data'
    provenance=Provenance(source_type=SourceType.USER_STATED, source_ref='test:recovery')
    backend=SqliteBackend(data/'self-model.sqlite3')
    SelfModelStore(backend, subject_id='test').record('Bestätigte Grundlage', Kind.STATE, provenance)
    backend.close()
    workspace=WorkspaceStore(data/'workspace.sqlite3')
    project=workspace.add_project('Wiederherstellungsprojekt', provenance)
    workspace.add_note('Notiz', 'Gesicherter Inhalt', provenance, project_id=project.id)
    workspace.close()
    tasks=TaskStore(data/'tasks.sqlite3')
    task=tasks.add('Gesicherte Aufgabe', provenance, project_id=project.id)
    tasks.close()
    episodes=EpisodeStore(data/'episodes.sqlite3')
    episode,_=episodes.record(EpisodeKind.DOCUMENT,'Originalquelle','Alex arbeitet am Wiederherstellungsprojekt.',provenance,project_id=project.id)
    episodes.advance_source_head('synthetic-source',None,episode.id)
    proposals=ProposalStore(data/'proposals.sqlite3')
    claims=ClaimStore(data/'knowledge.sqlite3')
    person=claims.entities.create('person','Alex')
    service=KnowledgeService(proposals=proposals,claims=claims,episodes=episodes)
    proposal,_=service.propose(subject_ref=person['id'],target_ref='project:'+project.id,predicate='works_on',value='Mitarbeit',statement=episode.body,rationale='Expliziter Testbeleg',evidence=[Evidence(episode.id,episode.body,episode.digest)])
    claim=service.accept(proposal.id,supersedes=[])
    service.propose(subject_ref=person['id'],predicate='role',value='Projektkontakt',statement=episode.body,rationale='Noch nicht bestätigt',evidence=[Evidence(episode.id,episode.body,episode.digest)])
    episodes.close(); proposals.close(); claims.close()
    conversations=ConversationStore(data/'conversations.sqlite3')
    conversation=conversations.create('Gesichertes Gespräch')
    conversations.add_message(conversation.id,'user','Meine Frage')
    conversations.add_message(conversation.id,'assistant','Meine Antwort')
    conversations.close()
    audit=AuditLog(data/'audit.sqlite3')
    audit.record('test','read','auto','executed',{'source':episode.id})
    audit.close()
    rules=RegelStore(data/'regeln.sqlite3')
    rules.anlegen('Gesicherte Regel','zeit','notify',{'zone':'UTC'})
    rules.close()
    MacCalendar(data/'mac-calendar.sqlite3').enable()
    zuordnungen=Zuordnungen(data/'gespraeche.sqlite3')   # Entscheidungen des Nutzers zu Mitschriften
    zuordnungen.schreiben(episode.id,status='zugeordnet',termin='k|t1',von='nutzer',hinweise={'titel':'Jour fixe'},kandidaten=[],gruende=['Von dir gewählt.'],abgelehnt=['k|t2'])
    zuordnungen.close()
    meldungen=Rueckmeldungen(data/'rueckmeldungen.sqlite3')   # Meldungen „Stimmt nicht?“ samt Erledigt
    meldung=meldungen.melden(frage='Bis wann?',antwort='Bis zum 31. Oktober.',art='veraltet',nachricht_id='m1',richtig='15. November')
    meldungen.erledigt(meldung['id'])
    meldungen.close()
    buch=Logbuch(data/'logbuch.sqlite3')   # die Chronik: Zähler, Titel, Kennungen
    buch.vermerke('quellen',sorte='mail',anzahl=41)
    buch.vermerke('akte_neu',sache='person:a:anna@example.org',name='Anna Keller')
    buch.close()
    from icarus_memory.lint import Befund, Befunde, Beleg
    befunde=Befunde(data/'lint.sqlite3')   # Befunde des Lint samt „Ignorieren“ des Nutzers
    befund=Befund('waise',('person:a:alt@example.invalid',),(Beleg(episode.id),),'Ruht seit einem Jahr.','hinweis','ruhend')
    befunde.abgleichen([befund])
    befunde.status_setzen(befund.schluessel,'abgewiesen')
    befunde.close()
    (data/'einstellungen.json').write_text(json.dumps({'provider':'ollama','model':'synthetic-local-model'}))
    monkeypatch.setenv('ICARUS_SECRETS_PASSPHRASE','synthetic-key-passphrase')
    monkeypatch.setattr(Keychain,'_detect',lambda self:'file')
    Keychain(data_dir=data).set('ICARUS_MAIL_PASSWORD','synthetic-mail-password')
    config=tmp_path/'settings.env'
    config.write_text('ICARUS_SECRETS_PASSPHRASE=synthetic-key-passphrase\nICARUS_SIDECAR_TOKEN=synthetic-token\n')
    from icarus_memory.calendar_actions import CalendarActions
    CalendarActions(data/'calendar-actions.sqlite3', lambda: None, None)
    with sqlite3.connect(data/'calendar-actions.sqlite3') as db:
        db.execute('INSERT INTO actions VALUES (?, ?, ?)', ('completed-draft', 'done', json.dumps({'id':'completed-draft','status':'done','provider_event_id':'confirmed-event'})))
    assert all((data/name).is_file() for name in BACKUP_DATA_FILES)
    before={name:database_contents(data/name) for name in SQLITE_DATA_FILES}
    assert all(any(line.startswith('INSERT INTO') for line in content[1]) for content in before.values())
    bundle=export_bundle(data,config,tmp_path/'all.recovery','synthetic-backup-password',image_id='sha256:'+'b'*64)
    tasks=TaskStore(data/'tasks.sqlite3')
    tasks.add('Neuere Arbeit bleibt erhalten',provenance)
    tasks.close()
    newer=database_contents(data/'tasks.sqlite3')
    result=restore_bundle(bundle,tmp_path/'restored','synthetic-backup-password')
    assert {name:database_contents(result/'data'/name) for name in SQLITE_DATA_FILES}==before
    assert database_contents(data/'tasks.sqlite3')==newer
    for name in ('einstellungen.json','schluessel.icarus'):
        assert (result/'data'/name).read_bytes()==(data/name).read_bytes()
    assert (result/'settings.env').read_bytes()==config.read_bytes()
    assert Keychain(data_dir=result/'data').get('ICARUS_MAIL_PASSWORD')=='synthetic-mail-password'
    restored_episodes=EpisodeStore(result/'data/episodes.sqlite3')
    assert restored_episodes.source_head('synthetic-source')==episode.id
    restored_episodes.close()
    restored=ClaimStore(result/'data/knowledge.sqlite3')
    assert restored.get(claim.id).target_ref=='project:'+project.id
    assert restored.get(claim.id).evidence[0].episode_id==episode.id
    restored.close()
    restored_tasks=TaskStore(result/'data/tasks.sqlite3')
    assert restored_tasks.get(task.id).project_id==project.id
    restored_tasks.close()
    restored_zuordnungen=Zuordnungen(result/'data/gespraeche.sqlite3')
    assert restored_zuordnungen.zeile(episode.id)['abgelehnt']==['k|t2']
    restored_zuordnungen.close()
    restored_meldungen=Rueckmeldungen(result/'data/rueckmeldungen.sqlite3')
    assert [(m['richtig'],m['status']) for m in restored_meldungen.liste()]==[('15. November','erledigt')]
    restored_meldungen.close()
    restored_buch=Logbuch(result/'data/logbuch.sqlite3')
    assert [(e.art,e.daten.get('anzahl') or e.daten.get('name')) for e in restored_buch.ereignisse(0)]==[('quellen',41),('akte_neu','Anna Keller')]
    restored_buch.close()
    restored_befunde=Befunde(result/'data/lint.sqlite3')
    assert [(b['id'],b['status']) for b in restored_befunde.liste()]==[(befund.schluessel,'abgewiesen')]
    restored_befunde.close()

    journal = CalendarActions(result/'data/calendar-actions.sqlite3', lambda: None, None)
    assert journal.get('completed-draft')['status'] == 'done'
    assert journal.get('completed-draft')['provider_event_id'] == 'confirmed-event'
