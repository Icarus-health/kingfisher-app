"""Read explicit ICS cancellation evidence through the calendar memory job."""
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import httpx
import pytest

from icarus_memory.calendar_memory import KalenderGedaechtnis, kalender_job, quelle_schluessel
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.connectors.calendar import CalendarConfig, CalendarConnector
from icarus_memory.connectors.collections import ICalendarSubscription, NamedCalendar
from icarus_memory.episodes import EpisodeKind, EpisodeState, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalStore

AT = datetime(2026, 9, 1, tzinfo=timezone.utc)
START = 'DTSTART:20260908T100000Z'
END = 'DTEND:20260908T110000Z'
ACTIVE = ('UID:inspection', 'SUMMARY:Site inspection', START, END, 'DESCRIPTION:Bring sample A')
CANCEL = ('UID:inspection', 'SUMMARY:Site inspection', 'STATUS:CANCELLED', 'DESCRIPTION:Road closed')
NEIGHBOR = ('UID:neighbor', 'SUMMARY:Site inspection', START, END)
SERIES = ('UID:series', 'SUMMARY:Site inspection', START, END, 'RRULE:FREQ=DAILY;COUNT=2')


def feed(*items, method=''):
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0']
    if method:
        lines.append(f'METHOD:{method}')
    for event in items:
        lines.extend(('BEGIN:VEVENT', *event, 'END:VEVENT'))
    return '\r\n'.join((*lines, 'END:VCALENDAR', '')).encode()


@pytest.fixture
def memory(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    yield KalenderGedaechtnis(episodes, claims), proposals
    proposals.close()
    claims.close()
    episodes.close()


class Subscription:
    def __init__(self, memory, source='site'):
        self.memory = memory
        self.source = source
        self.body = b''
        self.status = 200
        self.reader = ICalendarSubscription('https://calendar.example.test/read', transport=httpx.MockTransport(
            lambda request: httpx.Response(self.status, content=self.body)))

    def sync(self, body):
        self.body = body
        return kalender_job(self.memory, [NamedCalendar(self.source, 'Site calendar', self.reader)], at=AT)[self.source]

    def head(self, uid='inspection'):
        episodes = self.memory.episodes
        episode_id = episodes.source_head(quelle_schluessel(self.source, uid))
        return episodes.get(episode_id) if episode_id else None


def test_sole_cancellation_replaces_searchable_support_and_preserves_independent_deadline(memory):
    kg, proposals = memory
    subscription = Subscription(kg)
    assert subscription.sync(feed((*ACTIVE, 'SEQUENCE:0'))).neu == 1
    original = subscription.head()
    deadline, _ = kg.episodes.record(
        EpisodeKind.DOCUMENT, 'License renewal', 'License renewal deadline: 18 September.',
        Provenance(source_type=SourceType.DOCUMENT, source_ref='synthetic:license.pdf'),
        source_key='attachment:license')
    kg.episodes.advance_source_head('attachment:license', None, deadline.id)
    other = Subscription(kg, 'other-calendar')
    assert other.sync(feed(ACTIVE)).neu == 1
    other_original = other.head()

    service = KnowledgeService(proposals=proposals, claims=kg.claims, episodes=kg.episodes)
    site = kg.claims.entities.create('project', 'Site work')
    proposal, _ = service.propose(
        subject_ref=site['id'], predicate='sample', value='sample A',
        statement='Bring sample A', rationale='Calendar note',
        evidence=[Evidence(original.id, 'Bring sample A', original.digest)])
    claim = service.accept(proposal.id, supersedes=[])

    cancellation = feed((*CANCEL, 'SEQUENCE:1', 'DTSTAMP:20260902T120000Z'), method='CANCEL')
    change = subscription.sync(cancellation)
    cancelled = subscription.head()
    assert change.geaendert == 1
    assert cancelled.id != original.id
    assert cancelled.occurred_at is None
    assert cancelled.provenance.captured_at == datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    assert cancelled.provenance.source_ref == 'calendar:site:inspection'
    assert 'abgesagt' in cancelled.body.casefold() and 'Road closed' in cancelled.body
    assert kg.episodes.belegbarer_snapshot(cancelled.id) is not None
    assert kg.episodes.belegbarer_snapshot(original.id) is None
    assert kg.episodes.get(original.id).body == original.body
    assert not kg.claims.is_usable(kg.claims.get(claim.id))
    assert kg.episodes.belegbarer_snapshot(deadline.id) is not None
    assert other.head().id == other_original.id
    assert subscription.reader.events(at=AT, days=30) == []

    assert subscription.sync(cancellation).unveraendert == 1
    assert subscription.head().id == cancelled.id
    assert kg.episodes.counts() == {'new': 3, 'ignored': 1}
    subscription.sync(feed(NEIGHBOR))
    assert subscription.head().id == cancelled.id
    assert kg.episodes.belegbarer_snapshot(cancelled.id) is not None


def test_stale_or_conflicting_explicit_revision_cannot_resurrect_cancelled_event(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:3')))
    original = subscription.head()
    subscription.sync(feed((*CANCEL, START, END, 'SEQUENCE:2')))
    assert subscription.head().id == original.id

    subscription.sync(feed((*CANCEL, START, END, 'SEQUENCE:4')))
    cancelled = subscription.head()
    assert cancelled.id != original.id
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:3')))
    assert subscription.head().id == cancelled.id
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:4')))
    assert subscription.head().id == cancelled.id

    subscription.sync(feed((*ACTIVE, 'SEQUENCE:5')))
    restored = subscription.head()
    assert restored.id != cancelled.id
    assert 'Bring sample A' in restored.body
    assert memory[0].episodes.get(cancelled.id).state is EpisodeState.IGNORED


@pytest.mark.parametrize('cancel_first', [False, True])
def test_ambiguous_same_snapshot_does_not_overwrite_head_or_withdraw_neighbor(memory, cancel_first):
    subscription = Subscription(memory[0])
    subscription.sync(feed(ACTIVE, NEIGHBOR))
    original, neighbor = subscription.head(), subscription.head('neighbor')
    rows = ((*CANCEL, START, END, 'SEQUENCE:2'), (*ACTIVE, 'SEQUENCE:2'))
    subscription.sync(feed(*(rows if cancel_first else reversed(rows))))
    assert subscription.head().id == original.id
    assert subscription.head('neighbor').id == neighbor.id
    assert subscription.head('neighbor').state is EpisodeState.NEW


def test_unversioned_restoration_reuses_original_without_undoing_user_withdrawal(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed(ACTIVE))
    original = subscription.head()
    subscription.sync(feed(CANCEL))
    assert subscription.head().id != original.id
    assert subscription.sync(feed(ACTIVE)).wiederhergestellt == 1
    assert subscription.head().id == original.id
    memory[0].episodes.ignore(original.id)
    subscription.sync(feed(CANCEL))
    subscription.sync(feed((*ACTIVE, 'DESCRIPTION:Updated logistics')))
    assert subscription.head().id == original.id
    assert subscription.head().state is EpisodeState.IGNORED


@pytest.mark.parametrize('response', ['sole', 'delta', 'truncated', 'empty', 'http_error'])
def test_partial_or_failed_read_never_withdraws_a_neighbor(memory, response):
    subscription = Subscription(memory[0])
    subscription.sync(feed(ACTIVE, NEIGHBOR))
    original, neighbor = subscription.head(), subscription.head('neighbor')
    if response == 'sole':
        payload = feed((*CANCEL, START, END))
    elif response == 'delta':
        payload = feed((*CANCEL, START, END), ('UID:other', START, END), method='CANCEL')
    elif response == 'truncated':
        payload = feed((*CANCEL, START, END), ('UID:other', START, END)).removesuffix(b'END:VCALENDAR\r\n')
    elif response == 'empty':
        payload = feed()
    else:
        subscription.status, payload = 503, feed(NEIGHBOR)
    subscription.sync(payload)
    assert subscription.head('neighbor').id == neighbor.id
    assert subscription.head('neighbor').state is EpisodeState.NEW
    if response in {'sole', 'delta', 'truncated'}:
        assert subscription.head().id != original.id
    else:
        assert subscription.head().id == original.id


def test_cancelled_exception_uses_original_recurrence_identity_without_fabricating_start(memory):
    subscription = Subscription(memory[0])
    moved = ('UID:series', 'RECURRENCE-ID:20260909T100000Z', 'DTSTART:20260911T120000Z',
             'DTEND:20260911T130000Z', 'SUMMARY:Moved inspection')
    subscription.sync(feed(SERIES, moved))
    first = subscription.head('series#20260908T100000Z')
    moved_original = subscription.head('series#20260909T100000Z')
    cancellation = ('UID:series', 'RECURRENCE-ID:20260909T100000Z',
                    'STATUS:CANCELLED', 'DESCRIPTION:No vehicle')
    subscription.sync(feed(SERIES, cancellation))
    assert subscription.head('series#20260908T100000Z').id == first.id
    changed = subscription.head('series#20260909T100000Z')
    assert changed.id != moved_original.id
    assert changed.occurred_at is None
    assert 'No vehicle' in changed.body
    assert [e.uid for e in subscription.reader.events(at=AT, days=30)] == ['series#20260908T100000Z']


def test_series_cancellation_does_not_cancel_a_similarly_named_distinct_uid(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed(SERIES, NEIGHBOR))
    first = subscription.head('series#20260908T100000Z')
    second = subscription.head('series#20260909T100000Z')
    subscription.sync(feed((*SERIES, 'STATUS:CANCELLED')))
    for original, uid in ((first, 'series#20260908T100000Z'), (second, 'series#20260909T100000Z')):
        assert memory[0].episodes.get(original.id).state is EpisodeState.IGNORED
        assert 'abgesagt' in subscription.head(uid).body.casefold()
    assert subscription.head('neighbor').state is EpisodeState.NEW
    assert subscription.reader.events(at=AT, days=30) == []


def test_caldav_partial_multistatus_records_explicit_cancellation_without_implied_deletions(memory, monkeypatch):
    kg, _ = memory
    lookup = Subscription(kg)
    lookup.sync(feed(ACTIVE, NEIGHBOR))
    original = lookup.head()
    data = escape(feed((*CANCEL, START, END), ('UID:other', START, END)).decode())
    success = f'<D:response><D:propstat><D:prop><C:calendar-data>{data}</C:calendar-data></D:prop>' \
              '<D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>'
    failure = '<D:response><D:status>HTTP/1.1 507 Insufficient Storage</D:status></D:response>'
    transport = httpx.MockTransport(lambda request: httpx.Response(
        207, text='<D:multistatus xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">'
                  + success + failure + '</D:multistatus>'))
    monkeypatch.setattr(CalendarConnector, '_client', lambda self: httpx.Client(transport=transport))
    reader = CalendarConnector(CalendarConfig('https://calendar.example.test/read', 'test', 'test'))
    kalender_job(kg, [NamedCalendar('site', 'Site calendar', reader)], at=AT)
    assert lookup.head().id != original.id
    assert 'Road closed' in lookup.head().body
    assert lookup.head('neighbor').state is EpisodeState.NEW
    assert [e.uid for e in reader.events(at=AT, days=30)] == ['other']


def test_method_cancel_applies_only_to_its_calendar_envelope(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed(ACTIVE, NEIGHBOR))
    original, neighbor = subscription.head(), subscription.head('neighbor')
    method_only = ('UID:inspection', 'SUMMARY:Site inspection', START, END, 'DESCRIPTION:Road closed')
    new_event = ('UID:new-event', 'SUMMARY:Work briefing', START, END)
    subscription.sync(feed(method_only, method='CANCEL') + feed(new_event))
    assert subscription.head().id != original.id
    assert 'abgesagt' in subscription.head().body.casefold()
    assert subscription.head('neighbor').id == neighbor.id
    assert subscription.head('neighbor').state is EpisodeState.NEW
    assert 'abgesagt' not in subscription.head('new-event').body.casefold()
    assert [e.uid for e in subscription.reader.events(at=AT, days=30)] == ['new-event']


def test_series_cancel_does_not_copy_the_master_start_to_a_detached_exception(memory):
    subscription = Subscription(memory[0])
    moved = ('UID:series', 'RECURRENCE-ID:20260909T100000Z', 'DTSTART:20260911T120000Z',
             'DTEND:20260911T130000Z', 'SUMMARY:Moved inspection')
    subscription.sync(feed(SERIES, moved))
    subscription.sync(feed((*SERIES, 'STATUS:CANCELLED'), moved))
    cancelled = subscription.head('series#20260909T100000Z')
    assert 'abgesagt' in cancelled.body.casefold()
    assert cancelled.occurred_at is None


def test_legacy_ambiguous_recurrence_key_is_not_overwritten_as_a_literal_uid(memory):
    from icarus_memory.connectors.calendar import parse_events

    kg, _ = memory
    subscription = Subscription(kg)
    # This pre-repair head does not carry the raw UID. It could also be an actual series occurrence.
    literal_uid = 'series#20260909T100000Z'
    original_ics = feed((f'UID:{literal_uid}', 'SUMMARY:Independent event', START, END))
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    kg.abgleichen('site', 'Site calendar', parse_events(original_ics, start, end), start, end, at=AT)
    original = subscription.head(literal_uid)
    cancellation = ('UID:series', 'RECURRENCE-ID:20260909T100000Z', 'STATUS:CANCELLED')
    result = subscription.sync(feed(cancellation, method='CANCEL'))
    assert subscription.head(literal_uid).id == original.id
    assert subscription.head(literal_uid).state is EpisodeState.NEW
    assert result.fehler


def test_newer_cancelled_revision_keeps_stale_active_copy_out_of_live_events(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:2'), (*CANCEL, START, END, 'SEQUENCE:3')))
    assert 'abgesagt' in subscription.head().body.casefold()
    assert subscription.reader.events(at=AT, days=30) == []


def test_unordered_active_replay_cannot_discard_known_revision(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:4')))
    original = subscription.head()
    subscription.sync(feed(ACTIVE))
    assert subscription.head().id == original.id
    subscription.sync(feed((*CANCEL, START, END, 'SEQUENCE:3')))
    assert subscription.head().id == original.id


@pytest.mark.parametrize('user_excludes_after_failure', [False, True])
def test_failed_calendar_head_advance_can_retry_without_overriding_a_user_exclusion(
        memory, monkeypatch, user_excludes_after_failure):
    from icarus_memory.episodes import EpisodeError

    kg, proposals = memory
    subscription = Subscription(kg)
    subscription.sync(feed(ACTIVE))
    original = subscription.head()
    service = KnowledgeService(proposals=proposals, claims=kg.claims, episodes=kg.episodes)
    site = kg.claims.entities.create('project', 'Site work')
    proposal, _ = service.propose(
        subject_ref=site['id'], predicate='sample', value='sample A',
        statement='Bring sample A', rationale='Calendar note',
        evidence=[Evidence(original.id, 'Bring sample A', original.digest)])
    claim = service.accept(proposal.id, supersedes=[])
    cancellation = feed(CANCEL)
    advance = kg.episodes.advance_source_head

    def fail_once(*args):
        raise EpisodeError('Synthetic interrupted write')

    with monkeypatch.context() as patches:
        patches.setattr(kg.episodes, 'advance_source_head', fail_once)
        result = subscription.sync(cancellation)
    assert result.fehler == ['EpisodeError']
    assert subscription.head().id == original.id
    assert subscription.head().state is EpisodeState.NEW
    assert not kg.claims.is_usable(kg.claims.get(claim.id))
    assert kg.episodes.counts() == {'new': 1}

    if user_excludes_after_failure:
        kg.episodes.ignore(original.id)
        assert subscription.sync(cancellation).ausgeschlossen == 1
        assert subscription.head().id == original.id
        assert subscription.head().state is EpisodeState.IGNORED
    else:
        assert subscription.sync(cancellation).geaendert == 1
        assert subscription.head().id != original.id
        assert 'Road closed' in subscription.head().body
    assert kg.episodes.advance_source_head == advance
    assert not kg.claims.is_usable(kg.claims.get(claim.id))


def test_malformed_detached_occurrence_cannot_withdraw_its_saved_head(memory):
    subscription = Subscription(memory[0])
    detached = ('UID:series', 'RECURRENCE-ID:20260909T100000Z', START, END, 'SUMMARY:Inspection moved')
    subscription.sync(feed(detached, NEIGHBOR))
    uid = 'series#20260909T100000Z'
    original = subscription.head(uid)
    damaged = tuple('DTSTART:invalid' if line == START else line for line in detached)
    result = subscription.sync(feed(damaged, (*NEIGHBOR, 'DESCRIPTION:Updated neighbors')))
    assert result.entzogen == 0
    assert subscription.head(uid).id == original.id
    assert subscription.head(uid).state is EpisodeState.NEW
    assert 'Updated neighbors' in subscription.head('neighbor').body


def test_publish_message_updates_its_event_without_withdrawing_unlisted_neighbors(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed(ACTIVE, NEIGHBOR))
    neighbor = subscription.head('neighbor')
    result = subscription.sync(feed((*ACTIVE, 'LOCATION:New venue'), method='PUBLISH'))
    assert result.geaendert == 1
    assert 'New venue' in subscription.head().body
    assert subscription.head('neighbor').id == neighbor.id
    assert subscription.head('neighbor').state is EpisodeState.NEW


def test_unchanged_legacy_upgrade_keeps_accepted_claim_and_learns_revision(memory, tmp_path):
    from icarus_memory.connectors.calendar import parse_events

    kg, proposals = memory
    subscription = Subscription(kg)
    original_ics = feed((*ACTIVE, 'SEQUENCE:4'))
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    kg.abgleichen('site', 'Site calendar', parse_events(original_ics, AT, end), AT, end, at=AT)
    original = subscription.head()
    snapshot = kg.episodes.belegbarer_snapshot(original.id)
    service = KnowledgeService(proposals=proposals, claims=kg.claims, episodes=kg.episodes)
    site = kg.claims.entities.create('project', 'Site work')
    proposal, _ = service.propose(
        subject_ref=site['id'], predicate='sample', value='sample A',
        statement='Bring sample A', rationale='Calendar note',
        evidence=[Evidence(original.id, 'Bring sample A', original.digest)])
    claim = service.accept(proposal.id, supersedes=[])

    assert subscription.sync(original_ics).unveraendert == 1
    assert subscription.head().id == original.id
    current = kg.episodes.belegbarer_snapshot(original.id)
    assert current.support_fingerprint() == snapshot.support_fingerprint()
    assert current.fingerprint() == snapshot.fingerprint()
    assert kg.claims.is_usable(kg.claims.get(claim.id))

    # An ordinary episode write and then a fresh store instance must both preserve advisory order.
    kg.episodes.mark_consolidated(original.id)
    reopened = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        replay = Subscription(KalenderGedaechtnis(reopened, kg.claims))
        replay.sync(feed((*CANCEL, START, END, 'SEQUENCE:3')))
        assert replay.head().id == original.id
        assert replay.head().state is EpisodeState.CONSOLIDATED
        assert replay.sync(feed((*ACTIVE, 'SEQUENCE:5', 'LOCATION:New venue'))).geaendert == 1
        assert reopened.belegbarer_snapshot(original.id) is None
        assert not kg.claims.is_usable(kg.claims.get(claim.id))
    finally:
        reopened.close()


def test_detached_explicit_cancellation_keeps_its_own_source_fields(memory):
    subscription = Subscription(memory[0])
    original = ('UID:series', 'RECURRENCE-ID:20260909T100000Z', 'DTSTART:20260911T120000Z',
                'DTEND:20260911T130000Z', 'SUMMARY:Moved inspection')
    subscription.sync(feed(SERIES, original))
    master = (*SERIES, 'STATUS:CANCELLED', 'DESCRIPTION:Master closure')
    detached = (*original, 'STATUS:CANCELLED', 'DESCRIPTION:Specific road closure', 'DTSTAMP:20260902T120000Z')
    subscription.sync(feed(master, detached))
    cancelled = subscription.head('series#20260909T100000Z')
    assert 'Specific road closure' in cancelled.body
    assert 'Master closure' not in cancelled.body
    assert cancelled.provenance.captured_at == datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    assert cancelled.occurred_at == datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize('method', ['CANCEL', ''])
def test_sparse_master_updates_only_proven_occurrences_with_older_revisions(memory, method):
    from icarus_memory.connectors.calendar import parse_events

    kg, _ = memory
    subscription = Subscription(kg)
    detached = ('UID:series', 'RECURRENCE-ID:20260909T100000Z', 'DTSTART:20260911T120000Z',
                'DTEND:20260911T130000Z', 'SEQUENCE:7', 'SUMMARY:Newer revision')
    literal = ('UID:series#20260910T100000Z', 'SUMMARY:Independent event', START, END)
    subscription.sync(feed((*SERIES, 'SEQUENCE:2'), detached, literal, NEIGHBOR))
    legacy_id = 'series#20260912T100000Z'
    legacy = feed(('UID:series', 'RECURRENCE-ID:20260912T100000Z', START, END, 'SUMMARY:Legacy occurrence'))
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    kg.abgleichen('site', 'Site calendar', parse_events(legacy, AT, end), AT, end, at=AT, vollstaendig=False)
    older = subscription.head('series#20260908T100000Z')
    newer = subscription.head('series#20260909T100000Z')
    independent = subscription.head('series#20260910T100000Z')
    legacy_original = subscription.head(legacy_id)
    neighbor = subscription.head('neighbor')

    sparse = ('UID:series', 'SEQUENCE:3', 'DESCRIPTION:Site closed', 'DTSTAMP:20260902T120000Z')
    if not method:
        sparse = (*sparse, 'STATUS:CANCELLED')
    result = subscription.sync(feed(sparse, method=method) + feed(('UID:updated', START, END)))
    cancelled = subscription.head('series#20260908T100000Z')
    assert result.geaendert == 1
    assert cancelled.id != older.id and 'Site closed' in cancelled.body
    assert cancelled.occurred_at is None
    assert cancelled.provenance.source_ref == 'calendar:site:series#20260908T100000Z'
    assert subscription.head('series#20260909T100000Z').id == newer.id
    assert subscription.head('series#20260910T100000Z').id == independent.id
    assert subscription.head('series#20260910T100000Z').state is EpisodeState.NEW
    assert subscription.head(legacy_id).id == legacy_original.id
    assert subscription.head(legacy_id).state is EpisodeState.NEW
    assert subscription.head('neighbor').id == neighbor.id
    assert subscription.head('neighbor').state is EpisodeState.NEW
    assert subscription.head('series#20260911T100000Z') is None


@pytest.mark.parametrize('method', ['CANCEL', ''])
def test_timed_sparse_master_keeps_its_time_on_the_master_only(memory, method):
    subscription = Subscription(memory[0])
    subscription.sync(feed((*SERIES, 'SEQUENCE:1'), NEIGHBOR))
    first_uid = 'series#20260908T100000Z'
    second_uid = 'series#20260909T100000Z'
    first, second = subscription.head(first_uid), subscription.head(second_uid)
    neighbor = subscription.head('neighbor')

    master = ('UID:series', 'SEQUENCE:2', START, END, 'DESCRIPTION:Site closed', 'STATUS:CANCELLED')
    result = subscription.sync(feed(master, method=method) + feed(('UID:updated', START, END)))

    assert result.geaendert == 2
    assert subscription.head('series').occurred_at == datetime(2026, 9, 8, 10, tzinfo=timezone.utc)
    assert 'Wann:' in subscription.head('series').body
    for original, uid in ((first, first_uid), (second, second_uid)):
        cancelled = subscription.head(uid)
        assert cancelled.id != original.id and 'Site closed' in cancelled.body
        assert cancelled.occurred_at is None and 'Wann:' not in cancelled.body
    assert subscription.head('neighbor').id == neighbor.id
    assert subscription.head('neighbor').state is EpisodeState.NEW
    assert subscription.head('series#20260910T100000Z') is None


def test_sparse_status_cancellation_without_verified_fanout_cannot_withdraw_legacy_or_neighbor(memory):
    from icarus_memory.connectors.calendar import parse_events

    kg, _ = memory
    subscription = Subscription(kg)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    legacy = feed(SERIES, NEIGHBOR)
    kg.abgleichen('site', 'Site calendar', parse_events(legacy, AT, end), AT, end, at=AT)
    existing = {uid: subscription.head(uid) for uid in (
        'series#20260908T100000Z', 'series#20260909T100000Z', 'neighbor',
    )}

    master = ('UID:series', 'SEQUENCE:2', START, END, 'DESCRIPTION:Site closed', 'STATUS:CANCELLED')
    result = subscription.sync(feed(master, ('UID:updated', START, END)))

    assert (result.neu, result.geaendert, result.entzogen) == (2, 0, 0)
    assert 'Site closed' in subscription.head('series').body
    for uid, original in existing.items():
        assert subscription.head(uid).id == original.id
        assert subscription.head(uid).state is EpisodeState.NEW
    assert subscription.head('series#20260910T100000Z') is None


@pytest.mark.parametrize(
    ('replay', 'stale_copies'),
    [
        pytest.param(
            ('SEQUENCE:4',),
            (('SEQUENCE:4', 'LAST-MODIFIED:20260903T100000Z'),),
            id='omitted-secondary',
        ),
        pytest.param(
            ('LAST-MODIFIED:20260904T100000Z',),
            (('SEQUENCE:3', 'LAST-MODIFIED:20260905T100000Z'),),
            id='omitted-primary-equal-secondary',
        ),
        pytest.param(
            ('LAST-MODIFIED:20260906T100000Z',),
            (
                ('SEQUENCE:3', 'LAST-MODIFIED:20260907T100000Z'),
                ('SEQUENCE:4', 'LAST-MODIFIED:20260905T100000Z'),
            ),
            id='omitted-primary-newer-secondary',
        ),
        pytest.param(
            (),
            (
                ('SEQUENCE:3', 'LAST-MODIFIED:20260905T100000Z'),
                ('SEQUENCE:4', 'LAST-MODIFIED:20260903T100000Z'),
            ),
            id='both-omitted',
        ),
        pytest.param(
            ('SEQUENCE:3', 'LAST-MODIFIED:20260905T100000Z'),
            (('SEQUENCE:4', 'LAST-MODIFIED:20260903T100000Z'),),
            id='lower-primary-later-secondary',
        ),
    ],
)
def test_unchanged_partial_revision_replay_cannot_erase_known_ordering(memory, replay, stale_copies):
    kg, _ = memory
    subscription = Subscription(kg)
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:4', 'LAST-MODIFIED:20260904T100000Z')))
    original = subscription.head()
    snapshot = kg.episodes.belegbarer_snapshot(original.id)

    assert subscription.sync(feed((*ACTIVE, *replay))).unveraendert == 1
    for stale in stale_copies:
        assert subscription.sync(feed((*ACTIVE, *stale, 'LOCATION:Stale venue'))).geaendert == 0
    assert subscription.head().to_dict() == original.to_dict()
    assert kg.episodes.belegbarer_snapshot(original.id).support_fingerprint() == snapshot.support_fingerprint()


def test_higher_sequence_can_start_a_new_order_without_inheriting_the_old_timestamp(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:4', 'LAST-MODIFIED:20260904T100000Z')))
    original = subscription.head()
    assert subscription.sync(feed((*ACTIVE, 'SEQUENCE:5'))).unveraendert == 1
    assert subscription.head().id == original.id

    # The old revision's timestamp cannot order the new sequence's later edit.
    newer = (*ACTIVE, 'SEQUENCE:5', 'LAST-MODIFIED:20260903T100000Z', 'LOCATION:New venue')
    assert subscription.sync(feed(newer)).geaendert == 1
    assert 'New venue' in subscription.head().body


def test_same_sequence_change_without_secondary_keeps_previously_known_order(memory):
    subscription = Subscription(memory[0])
    subscription.sync(feed((*ACTIVE, 'SEQUENCE:4', 'LAST-MODIFIED:20260904T100000Z')))
    assert subscription.sync(feed((*ACTIVE, 'SEQUENCE:4', 'LOCATION:Current venue'))).geaendert == 1
    current = subscription.head()

    stale = (*ACTIVE, 'SEQUENCE:4', 'LAST-MODIFIED:20260903T100000Z', 'LOCATION:Stale venue')
    assert subscription.sync(feed(stale)).geaendert == 0
    assert subscription.head().to_dict() == current.to_dict()
