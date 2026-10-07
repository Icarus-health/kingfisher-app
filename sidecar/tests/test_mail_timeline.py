"""Import time must not manufacture present-day obligations."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind, ProposalStore
from icarus_memory.task_detection import for_briefing
from icarus_memory.mail_ingestion import remember
from icarus_memory.connectors.mail import Message

NOW = datetime(2026, 10, 7, 10, tzinfo=timezone.utc)

@pytest.fixture
def stores(tmp_path):
    episodes, proposals = EpisodeStore(tmp_path / 'episodes.sqlite3'), ProposalStore(tmp_path / 'proposals.sqlite3')
    try: yield episodes, proposals
    finally:
        episodes.close()
        proposals.close()

def candidate(stores, date, *, key='one', source=SourceType.EMAIL):
    episodes, proposals = stores
    e, _ = episodes.record(EpisodeKind.MESSAGE, 'Bitte', 'Bitte prüfe den Entwurf.',
        Provenance(source_type=source), occurred_at=date, at=NOW, source_key=key)
    proposals.record_task_analysis(e.id, e.digest,
        [{'title': 'Entwurf prüfen', 'quote': e.body}], proposed_by='test/local/task-review-v1')
    return e

@pytest.mark.parametrize('date', [datetime(2015, 1, 22, tzinfo=timezone.utc), None, NOW + timedelta(days=1)])
def test_import_today_does_not_promote_old_unknown_or_future_mail(stores, date):
    candidate(stores, date)
    result = for_briefing(*reversed(stores), now=NOW)
    assert result['items'] == [] and result['pending'] == 0
    assert len(stores[1].pending(ProposalKind.TASK)) == 1  # retained for explicit review
    assert result['review_pending'] == 1


def test_initial_inventory_is_not_live_mail_even_when_its_date_is_recent(stores):
    e = candidate(stores, NOW - timedelta(hours=1))
    with stores[0].transaction():
        stores[0]._conn.execute("INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES('work','INBOX','1',1,'history','captured',?)", (e.id,))
    result = for_briefing(*reversed(stores), now=NOW)
    assert result['items'] == [] and result['review_pending'] == 1


def test_recent_mail_is_offered_as_a_dated_suggestion(stores):
    e = candidate(stores, NOW - timedelta(hours=1))
    result = for_briefing(*reversed(stores), now=NOW)
    assert result['pending'] == 1 and result['review_pending'] == 0
    [item] = result['items']
    assert item['received_at'] == '2026-10-07T09:00:00+00:00'
    assert item['recorded_at'] == '2026-10-07T10:00:00+00:00'
    assert item['temporal_status'] == 'recent' and item['episode_id'] == e.id


def test_historical_candidates_cannot_hide_new_mail_behind_old_200_row_limit(stores):
    for i in range(205):candidate(stores, datetime(2015, 1, 22, tzinfo=timezone.utc), key=str(i))
    fresh = candidate(stores, NOW, key='fresh')
    result = for_briefing(*reversed(stores), now=NOW)
    assert [x['episode_id'] for x in result['items']] == [fresh.id]
    assert result['review_pending'] == 205


def mail(uid, date, *, account='work', message_id='', reply='', text='Bitte prüfe den Entwurf.'):
    m = Message(uid=uid, subject='Entwurf', sender='Anna <anna@example.test>', date=date,
                preview='', unread=True, body=text, account_id=account, message_id=message_id)
    # Source-level metadata; deliberately no subject-based relationship inference.
    m.in_reply_to = reply
    m.references = ()
    return m


def test_later_related_reply_blocks_earlier_request_without_erasing_it(stores):
    episodes, proposals = stores
    first = remember(episodes, mail('work:1', NOW-timedelta(hours=2), message_id='<request@example.test>'))
    e = episodes.get(first['episode']['id'])
    proposals.record_task_analysis(e.id, e.digest, [{'title':'Entwurf prüfen','quote':e.body}], proposed_by='test/local/task-review-v1')
    remember(episodes, mail('work:2', NOW-timedelta(hours=1), reply='<request@example.test>', text='Hat sich erledigt. Bitte nichts mehr schicken.'))
    result = for_briefing(proposals, episodes, now=NOW)
    assert result['items'] == [] and result['review_pending'] == 1
    assert len(proposals.pending(ProposalKind.TASK)) == 1


def test_reply_in_another_account_does_not_suppress_this_account(stores):
    episodes, proposals = stores
    first = remember(episodes, mail('work:1', NOW-timedelta(hours=2), message_id='<request@example.test>'))
    e = episodes.get(first['episode']['id'])
    proposals.record_task_analysis(e.id, e.digest, [{'title':'Entwurf prüfen','quote':e.body}], proposed_by='test/local/task-review-v1')
    remember(episodes, mail('other:2', NOW-timedelta(hours=1), account='other', reply='<request@example.test>', text='Erledigt.'))
    assert for_briefing(proposals, episodes, now=NOW)['pending'] == 1


def test_followup_link_uses_source_time_not_import_order(stores):
    from icarus_memory.mail_timeline import timings
    episodes, _ = stores
    first = remember(episodes, mail('work:1', NOW-timedelta(hours=3), message_id='<request@example.test>'))
    remember(episodes, mail('work:4', NOW-timedelta(hours=2, minutes=30), reply='<request@example.test>', text='Angekommen.'))
    newest = remember(episodes, mail('work:3', NOW-timedelta(hours=1), reply='<request@example.test>', text='Hat sich erledigt.'))
    remember(episodes, mail('work:2', NOW-timedelta(hours=2), reply='<request@example.test>', text='Danke, ich schaue gleich.'))
    e = episodes.get(first['episode']['id'])
    assert timings(episodes, [e], now=NOW)[e.id]['followup_episode_id'] == newest['episode']['id']


def test_api_preserves_historical_suggestion_with_two_times_and_explicit_acceptance(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app()
    e = candidate((app.state.episodes, app.state.proposals), datetime(2015,1,22,tzinfo=timezone.utc))
    with TestClient(app) as client:
        morning = client.get('/api/v1/morning-briefing?post=false').json()
        assert not any(x['source']=='zusage' for x in morning['needs_you'])
        assert morning['historical_task_reviews'] == 1
        [item] = client.get('/api/v1/task-candidates').json()
        assert item['received_at'] == '2015-01-22T00:00:00+00:00'
        assert item['temporal_status'] == 'old'
        assert item['recorded_at'] != item['received_at']
        assert client.post('/api/v1/task-candidates/'+item['id']+'/accept', json={'title':'Heute ausdrücklich prüfen','due':'2026-01-01T00:00:00+00:00'}).status_code == 200
        assert any(x['source']=='aufgabe' for x in client.get('/api/v1/morning-briefing?post=false').json()['needs_you'])
        assert app.state.episodes.get(e.id).body == 'Bitte prüfe den Entwurf.'


def test_legacy_parent_without_header_tags_is_protected_from_later_reply(stores):
    episodes, proposals = stores
    e, _ = episodes.record(EpisodeKind.MESSAGE, 'Entwurf', 'Bitte prüfe den Entwurf.',
        Provenance(source_type=SourceType.EMAIL, source_ref='work:<legacy@example.test>'),
        occurred_at=NOW-timedelta(hours=2))
    proposals.record_task_analysis(e.id,e.digest,[{'title':'Entwurf prüfen','quote':e.body}],proposed_by='test/local/task-review-v1')
    remember(episodes, mail('work:2', NOW-timedelta(hours=1), reply='<legacy@example.test>', text='Bitte nicht mehr prüfen.'))
    assert for_briefing(proposals,episodes,now=NOW)['items'] == []
    assert episodes.get(e.id).tags == []  # no backfill rewrites


def test_excluded_reply_does_not_hide_a_current_source(stores):
    episodes, proposals = stores
    first=remember(episodes, mail('work:1',NOW-timedelta(hours=2),message_id='<first@example.test>'))
    e=episodes.get(first['episode']['id'])
    proposals.record_task_analysis(e.id,e.digest,[{'title':'Entwurf prüfen','quote':e.body}],proposed_by='test/local/task-review-v1')
    later=remember(episodes,mail('work:2',NOW-timedelta(hours=1),reply='<first@example.test>',text='Erledigt.'))
    episodes.ignore(later['episode']['id'])
    assert for_briefing(proposals,episodes,now=NOW)['pending'] == 1


@pytest.mark.parametrize('ignored',[False,True])
def test_header_enrichment_preserves_legacy_source_identity_history_and_exclusion(stores,monkeypatch,ignored):
    import icarus_memory.mail_timeline as timeline
    episodes,proposals=stores
    m=mail('work:1',NOW-timedelta(hours=1),message_id='<legacy@example.test>')
    actual=timeline.thread_tags
    monkeypatch.setattr(timeline,'thread_tags',lambda _:[])
    first=remember(episodes,m)['episode']
    monkeypatch.setattr(timeline,'thread_tags',actual)
    with episodes.transaction():
        episodes._conn.execute("INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) VALUES('work','INBOX','1',1,'history','captured',?)",(first['id'],))
    if ignored:episodes.ignore(first['id'])
    again=remember(episodes,m)
    assert again['episode']['id']==first['id'] and again['new'] is False
    assert again['episode']['recorded_at']==first['recorded_at']
    assert len(episodes.all_episodes())==1
    e=episodes.get(first['id'])
    if ignored:
        assert e.state.value=='ignored'
    else:
        proposals.record_task_analysis(e.id,e.digest,[{'title':'Entwurf prüfen','quote':e.body}],proposed_by='test/local/task-review-v1')
        assert for_briefing(proposals,episodes,now=NOW)['review_pending']==1


def test_legacy_participants_still_gain_sender_roles(stores):
    from icarus_memory.mail_ingestion import source_key_for_message
    from icarus_memory.source_versions import track_source
    episodes,_=stores
    m=mail('work:1',NOW,message_id='<legacy@example.test>')
    e,_=episodes.record(EpisodeKind.MESSAGE,m.subject,m.body,Provenance(source_type=SourceType.EMAIL),
        occurred_at=m.date,participants=[m.sender],source_key=source_key_for_message(m))
    track_source(episodes,None,source_key_for_message(m),e)
    again=remember(episodes,m)['episode']
    assert again['id']==e.id
    assert any(c['rolle']=='von' for c in again['contacts'])


def test_reply_scan_is_shared_across_more_than_one_candidate_batch(stores):
    episodes,proposals=stores
    for i in range(205):
        captured=remember(episodes,mail(f'work:{i+1}',NOW,message_id=f'<mail{i}@example.test>'))
        e=episodes.get(captured['episode']['id'])
        proposals.record_task_analysis(e.id,e.digest,[{'title':'Entwurf prüfen','quote':e.body}],proposed_by='test/local/task-review-v1')
    statements=[]
    episodes._conn.set_trace_callback(statements.append)
    try:
        assert for_briefing(proposals,episodes,now=NOW)['pending']==205
    finally:episodes._conn.set_trace_callback(None)
    assert sum('SELECT e.id,j.value,' in query for query in statements)==1
