"""Fortschritt erst nach Aufnahme; Wiederholung nach Fehler bleibt verlustfrei."""
import pytest
from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeStore, EpisodeError
from icarus_memory.mail_ingestion import sync_account


class Inbox:
    broken = True
    def pending_uids(self, after=None, limit=50):
        return [uid for uid in ['7.1', '7.2'] if after is None or uid > after][:limit]
    def message(self, uid):
        if uid == '7.2' and self.broken:
            raise OSError('offline')
        return Message(uid, uid, 'a@example.invalid', None, uid, True, body=uid)


def test_resume_after_failure_and_restart(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    inbox = Inbox()
    with pytest.raises(OSError):
        sync_account(episodes, 'work', inbox)
    assert episodes.mail_cursor('work') == '7.1'
    episodes.close()
    episodes = EpisodeStore(path)
    inbox.broken = False
    assert sync_account(episodes, 'work', inbox)['recorded'] == 1
    assert episodes.mail_cursor('work') == '7.2'
    assert sync_account(episodes, 'work', inbox)['recorded'] == 0
    assert episodes.mail_cursor('private') is None
    episodes.close()


def test_crash_before_checkpoint_retries_without_duplicate(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    advance = episodes.advance_mail_cursor
    def fail(*args):
        raise OSError('Disk full')
    monkeypatch.setattr(episodes, 'advance_mail_cursor', fail)
    with pytest.raises(OSError):
        sync_account(episodes, 'work', Inbox(), limit=1)
    assert episodes.mail_cursor('work') is None
    monkeypatch.setattr(episodes, 'advance_mail_cursor', advance)
    result = sync_account(episodes, 'work', Inbox(), limit=1)
    assert result == {'recorded': 0, 'duplicates': 1, 'cursor': '7.1'}
    with pytest.raises(EpisodeError):
        episodes.advance_mail_cursor('work', None, '7.2')
    assert episodes.mail_cursor('work') == '7.1'
    episodes.close()


def test_existing_v1_database_gets_checkpoint_table_without_changing_sources(tmp_path):
    import sqlite3
    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    sync_account(episodes, 'work', Inbox(), limit=1)
    episodes.close()
    with sqlite3.connect(path) as connection:
        from tests.working_memory_legacy import drop_intake_extensions
        drop_intake_extensions(connection)
        before = connection.execute('SELECT id, body FROM episodes').fetchall()
        for table in ('working_memory_terms', 'working_memory_items', 'working_memory_sources', 'working_memory_scan'):
            connection.execute('DROP TABLE ' + table)
        from icarus_memory.support_schema import EPISODE_TRIGGERS
        for trigger in EPISODE_TRIGGERS:
            connection.execute('DROP TRIGGER ' + trigger)
        connection.execute('DROP TABLE episode_produced_assertions')
        connection.execute('ALTER TABLE episodes DROP COLUMN support_generation')
        connection.execute('DROP TABLE mail_progress')
        connection.execute('DROP TABLE source_heads')
        connection.execute("DROP INDEX idx_episodes_digest")
        connection.execute("ALTER TABLE episodes DROP COLUMN source_key")
        connection.execute("ALTER TABLE episodes DROP COLUMN metadata_digest")
        connection.execute("CREATE UNIQUE INDEX idx_episodes_digest ON episodes(digest)")
        connection.execute('PRAGMA user_version = 1')
    episodes = EpisodeStore(path)
    assert episodes.mail_cursor('work') is None
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT id, body FROM episodes').fetchall() == before
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 19
    episodes.close()


def test_disabled_source_does_not_contact_mail_server(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    class Forbidden:
        def pending_uids(self, **kwargs):
            pytest.fail('Deaktivierte Quelle darf nicht abgerufen werden')
    result = sync_account(episodes, 'work', Forbidden(), permitted=lambda: False)
    assert result['cancelled']
    assert episodes.mail_cursor('work') is None
    episodes.close()


def test_revocation_during_network_fetch_prevents_capture(tmp_path):
    import threading
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    gate = threading.Lock()
    permission = [True]
    class RevokedInbox(Inbox):
        def message(self, uid):
            with gate:
                permission[0] = False
            return super().message(uid)
    result = sync_account(episodes, 'work', RevokedInbox(),
                          permitted=lambda: permission[0], permission_lock=gate)
    assert result == {'recorded': 0, 'duplicates': 0, 'cursor': None, 'cancelled': True}
    assert episodes.mail_cursor('work') is None
    from icarus_memory.episodes import digest_of
    assert episodes.by_digest(digest_of('7.1')) is None
    # Bei erneuter Freigabe beginnt die Aufnahme genau bei dieser Nachricht.
    assert sync_account(episodes, 'work', Inbox(), limit=1)['recorded'] == 1
    episodes.close()


def test_mail_identity_and_versions_keep_independent_evidence(tmp_path):
    from dataclasses import replace
    from icarus_memory.mail_ingestion import remember
    from icarus_memory.claims import ClaimStore, KnowledgeService
    from icarus_memory.proposals import ProposalStore, Evidence
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    first = Message('work:7.1', 'Budget', 'alex@example.invalid', None, 'Budget zugesagt', False,
                    body='Budget zugesagt', message_id='<same@example.invalid>', account_id='work')
    second = replace(first, uid='work:7.2')
    a = remember(episodes, first, claims=claims)['episode']
    b = remember(episodes, second, claims=claims)['episode']
    assert a['id'] != b['id'] and a['digest'] == b['digest']
    person = claims.entities.create('person', 'Alex')
    accepted = []
    for index, source in enumerate((a, b)):
        proposal, _ = service.propose(subject_ref=person['id'], predicate=f'budget_{index}', value='zugesagt',
            statement=source['body'], rationale='Beleg', evidence=[Evidence(source['id'], source['body'], source['digest'])])
        accepted.append(service.accept(proposal.id, supersedes=[]))
    duplicate = remember(episodes, replace(first, uid='7.1'), claims=claims)
    assert not duplicate['new'] and duplicate['episode']['id'] == a['id']
    changed = remember(episodes, replace(first, body='Budget zurückgezogen'), claims=claims)
    assert changed['new'] and changed['changed']
    assert not claims.is_usable(claims.get(accepted[0].id))
    assert claims.is_usable(claims.get(accepted[1].id))
    assert episodes.get(a['id']).body == 'Budget zugesagt'
    assert episodes.get(a['id']).state.value == 'ignored'
    private = remember(episodes, replace(first, account_id='private', uid='7.1'), claims=claims)
    assert private['episode']['id'] not in (a['id'], b['id'])
    episodes.close(); episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    assert not remember(episodes, replace(first, body='Budget zurückgezogen'), claims=claims)['new']
    assert not remember(episodes, first, claims=claims)['new']
    assert episodes.get(a['id']).state.value == 'ignored'
    assert not claims.is_usable(claims.get(accepted[0].id))
    episodes.close(); claims.close(); proposals.close()
