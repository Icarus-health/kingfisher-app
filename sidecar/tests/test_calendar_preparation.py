"""Terminvorbereitung liest nur aktuelle Quellen und expliziten Projektkontext."""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.connectors.calendar import Event
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence
from icarus_memory.server import create_app


class Calendar:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.items = [Event('meeting', 'Atlas besprechen', now, now + timedelta(hours=1))]
        self.fail = False

    def events(self, **kwargs):
        if self.fail:
            raise RuntimeError('Quelle nicht erreichbar')
        return self.items


def preparation_app():
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    source = Calendar()
    app.state.calendar = CalendarCollection([NamedCalendar('test', 'Testkalender', source)])
    return app, source


def test_preparation_scopes_live_context_and_corrections():
    app, source = preparation_app()
    client = TestClient(app)
    project = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()
    pid = project['id']
    task = client.post('/api/v1/tasks', json={'title': 'Angebot prüfen', 'project_id': pid}).json()
    client.post('/api/v1/tasks', json={'title': 'Fremde Aufgabe'})
    episode = app.state.episodes.record(EpisodeKind.MESSAGE, 'Test', 'Atlas hat Budget.', Provenance(source_type=SourceType.USER_STATED))[0]
    candidate = app.state.knowledge_service.propose(subject_ref=f'project:{pid}', predicate='budget', value='vorhanden', statement=episode.body, rationale='Test', evidence=[Evidence(episode.id, episode.body, episode.digest)])[0]
    claim = app.state.knowledge_service.accept(candidate.id, supersedes=[])
    decision = client.post('/api/v1/decisions', json={'statement': 'Angebot einholen', 'claim_ids': [claim.id], 'project_id': pid}).json()
    url = '/api/v1/calendar/preparation'
    bare = client.get(url, params={'uid': 'test:meeting'}).json()
    assert bare['project'] is None and bare['tasks'] == []  # Titel ist keine Zuordnung.
    params = {'uid': 'test:meeting', 'project_id': pid}
    prepared = client.get(url, params=params).json()
    assert [t['id'] for t in prepared['tasks']] == [task['id']]
    assert prepared['claims'][0]['evidence'][0]['episode_id'] == episode.id
    assert prepared['sources'][0]['id'] == episode.id
    assert prepared['sources'][0]['reason'] == 'Beleg einer aktuellen Aussage'
    assert not prepared['decisions'][0]['erschuettert']
    app.state.claims.retract(claim.id, reason='Korrigiert')
    assert client.post(f'/api/v1/tasks/{task["id"]}/done').status_code == 200
    changed = client.get(url, params=params).json()
    assert changed['claims'] == [] and changed['tasks'] == []
    assert changed['sources'] == []
    assert changed['decisions'][0]['erschuettert']
    client.post(f'/api/v1/decisions/{decision["id"]}/retract')
    assert client.get(url, params=params).json()['decisions'] == []
    source.items = []
    assert client.get(url, params=params).status_code == 404
    source.fail = True
    assert client.get(url, params=params).status_code == 503


def test_calendar_identity_is_stable_and_missing_context_rejected():
    app, source = preparation_app()
    client = TestClient(app)
    for _ in range(3):
        assert client.get('/api/v1/calendar').json()['items'][0]['uid'] == 'test:meeting'
    assert source.items[0].uid == 'meeting'
    assert client.get('/api/v1/calendar/preparation', params={'uid': 'test:meeting', 'project_id': 'missing'}).status_code == 404
    app.state.calendar = None
    assert client.get('/api/v1/calendar/preparation', params={'uid': 'test:meeting'}).status_code == 404


def test_preparation_sources_keep_provenance_and_do_not_infer_people():
    app, source = preparation_app()
    client = TestClient(app)
    pid = client.post('/api/v1/projects', json={'name': 'Atlas'}).json()['id']
    provenance = Provenance(source_type=SourceType.USER_STATED)
    included = app.state.episodes.record(EpisodeKind.MESSAGE, 'Projektmail', '<script>nicht ausführen</script>\nHallo Atlas', provenance, project_id=pid, participants=['Alex'])[0]
    excluded = app.state.episodes.record(EpisodeKind.MESSAGE, 'Atlas erwähnt', 'Nur gleicher Projektname', provenance, participants=['Robin'])[0]
    ignored = app.state.episodes.record(EpisodeKind.MESSAGE, 'Ignoriert', 'Nicht berücksichtigen', provenance, project_id=pid)[0]
    app.state.episodes.ignore(ignored.id)
    long = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Langes Dokument', 'x' * 20001, provenance, project_id=pid)[0]
    result = client.get('/api/v1/calendar/preparation', params={'uid': 'test:meeting', 'project_id': pid}).json()
    sources = {item['id']: item for item in result['sources']}
    assert included.id in sources and excluded.id not in sources and ignored.id not in sources
    assert sources[included.id]['body'] == included.body
    assert sources[included.id]['participants'] == ['Alex']
    assert sources[included.id]['reason'] == 'Dem Projekt zugeordnet'
    assert result['event']['attendees'] == []  # Quellenname wird nicht zum Teilnehmer.
    assert sources[long.id]['truncated'] and len(sources[long.id]['body']) == 20000


def test_explicit_person_context_keeps_same_names_separate_and_obeys_revocation():
    app, source = preparation_app()
    client = TestClient(app)
    first = app.state.claims.entities.create('person', 'Alex')
    second = app.state.claims.entities.create('person', 'Alex')
    source.items[0].attendees = ['Alex']
    provenance = Provenance(source_type=SourceType.USER_STATED)
    claims = []
    for person, statement in [(first, 'Alex prüft Verträge.'), (second, 'Alex leitet Schulungen.')]:
        episode = app.state.episodes.record(EpisodeKind.MESSAGE, 'Beleg', statement, provenance)[0]
        proposal = app.state.knowledge_service.propose(subject_ref=person['id'], predicate='role',
            value=statement, statement=statement, rationale='Ausdrücklicher Testbeleg',
            evidence=[Evidence(episode.id, episode.body, episode.digest)])[0]
        claims.append(app.state.knowledge_service.accept(proposal.id, supersedes=[]))
    url = '/api/v1/calendar/preparation'
    bare = client.get(url, params={'uid':'test:meeting'}).json()
    assert bare['person'] is None and bare['claims'] == []  # Ein Name ist keine Identität.
    params = {'uid':'test:meeting', 'person_id':first['id']}
    result = client.get(url, params=params).json()
    assert result['person']['id'] == first['id']
    assert [item['id'] for item in result['claims']] == [claims[0].id]
    assert result['tasks'] == [] and result['project'] is None
    assert [item['body'] for item in result['sources']] == ['Alex prüft Verträge.']
    eid = result['sources'][0]['id']
    assert client.post(f'/api/v1/episodes/{eid}/ignore').status_code == 200
    changed = client.get(url, params=params).json()
    assert changed['claims'] == [] and changed['sources'] == []
    assert source.items[0].attendees == ['Alex']
    assert len(app.state.claims.entities.list('person')) == 2
    assert client.get(url, params={'uid':'test:meeting','person_id':'missing'}).status_code == 404
    project_entity = app.state.claims.entities.create('project', 'Kein Mensch')
    assert client.get(url, params={'uid':'test:meeting','person_id':project_entity['id']}).status_code == 404


def test_briefing_and_preparation_follow_task_lifecycle_and_project_changes():
    app, source = preparation_app()
    client = TestClient(app)
    first = client.post('/api/v1/projects', json={'name':'Atlas'}).json()['id']
    second = client.post('/api/v1/projects', json={'name':'Boreas'}).json()['id']
    task = client.post('/api/v1/tasks', json={'title':'Gemeinsamer aktueller Stand',
        'project_id':first, 'due':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}).json()
    tid = task['id']
    def overview():
        return client.get('/api/v1/morning-briefing').json()['needs_you']
    def prepare(pid):
        return client.get('/api/v1/calendar/preparation', params={'uid':'test:meeting','project_id':pid}).json()['tasks']
    assert any(item['source_ref'] == tid and item['project_id'] == first for item in overview())
    assert [item['id'] for item in prepare(first)] == [tid]
    assert client.post(f'/api/v1/tasks/{tid}/done').status_code == 200
    assert all(item['source_ref'] != tid for item in overview()) and prepare(first) == []
    assert client.post(f'/api/v1/tasks/{tid}/reopen').status_code == 200
    assert any(item['source_ref'] == tid for item in overview())
    assert client.patch(f'/api/v1/tasks/{tid}/project', json={'project_id':second}).status_code == 200
    assert prepare(first) == [] and [item['id'] for item in prepare(second)] == [tid]
    assert any(item['source_ref'] == tid and item['project_id'] == second for item in overview())
    assert client.post(f'/api/v1/tasks/{tid}/warten', json={'name':'Alex'}).status_code == 200
    assert all(item['source_ref'] != tid for item in overview())
    assert prepare(second)[0]['wartet_auf'] == 'Alex'
    assert client.post(f'/api/v1/tasks/{tid}/zurueckholen').status_code == 200
    assert any(item['source_ref'] == tid for item in overview())


def test_many_waiting_tasks_do_not_hide_own_overdue_task_from_briefing():
    app, source = preparation_app()
    client = TestClient(app)
    old = (datetime.now(timezone.utc)-timedelta(days=10)).isoformat()
    for i in range(50):
        tid = client.post('/api/v1/tasks', json={'title':f'Warten {i}', 'due':old}).json()['id']
        client.post(f'/api/v1/tasks/{tid}/warten', json={'name':'Alex'})
    own = client.post('/api/v1/tasks', json={'title':'Meine überfällige Aufgabe',
        'due':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()}).json()['id']
    result = client.get('/api/v1/morning-briefing').json()
    assert any(item['source_ref'] == own for item in result['needs_you'])
    attention = next(item for item in result['needs_you'] if item['source_ref'] == own)
    assert attention['title'] == 'Meine überfällige Aufgabe'
    assert 'Seit dem' in attention['reason']


def test_excluded_task_source_does_not_return_through_open_task():
    app, source = preparation_app()
    client = TestClient(app)
    pid = client.post('/api/v1/projects', json={'name':'Atlas'}).json()['id']
    episode = app.state.episodes.record(EpisodeKind.MESSAGE, 'Alte Grundlage', 'Nicht weiter verwenden.',
        Provenance(source_type=SourceType.USER_STATED), project_id=pid)[0]
    task = app.state.tasks.add('Aufgabe bleibt bestehen',
        Provenance(source_type=SourceType.USER_STATED, source_ref=f'episode:{episode.id}'), project_id=pid)
    params = {'uid':'test:meeting', 'project_id':pid}
    before = client.get('/api/v1/calendar/preparation', params=params).json()
    assert [item['id'] for item in before['sources']] == [episode.id]
    assert client.post(f'/api/v1/episodes/{episode.id}/ignore').status_code == 200
    after = client.get('/api/v1/calendar/preparation', params=params).json()
    assert [item['id'] for item in after['tasks']] == [task.id]
    assert after['sources'] == []


def test_project_target_relationship_is_prepared_without_name_matching():
    app, source = preparation_app()
    client = TestClient(app)
    project = client.post('/api/v1/projects', json={'name':'Atlas'}).json()['id']
    other = client.post('/api/v1/projects', json={'name':'Atlas'}).json()['id']
    person = app.state.claims.entities.create('person','Alex')
    accepted=[]
    for pid in (project, other):
        episode=app.state.episodes.record(EpisodeKind.MESSAGE,'Projektbezug',f'Alex unterstützt Projekt {pid}.',
            Provenance(source_type=SourceType.USER_STATED))[0]
        proposal=app.state.knowledge_service.propose(subject_ref=person['id'],target_ref=f'project:{pid}',
            predicate='works_on',value='Unterstützung',statement=episode.body,rationale='Explizite Kennung',
            evidence=[Evidence(episode.id,episode.body,episode.digest)])[0]
        accepted.append(app.state.knowledge_service.accept(proposal.id,supersedes=[]))
    params={'uid':'test:meeting','project_id':project}
    result=client.get('/api/v1/calendar/preparation',params=params).json()
    assert [c['id'] for c in result['claims']]==[accepted[0].id]
    assert [s['id'] for s in result['sources']]==[accepted[0].evidence[0].episode_id]
    app.state.claims.retract(accepted[0].id,reason='Zuordnung korrigiert')
    changed=client.get('/api/v1/calendar/preparation',params=params).json()
    assert changed['claims']==[] and changed['sources']==[]


def test_preparation_and_profile_share_targeted_selection_beyond_global_window(monkeypatch):
    app, source = preparation_app()
    client=TestClient(app)
    project=client.post('/api/v1/projects',json={'name':'Atlas'}).json()['id']
    person=app.state.claims.entities.create('person','Alex')
    episode=app.state.episodes.record(EpisodeKind.MESSAGE,'Beleg','Alex arbeitet an Atlas.',Provenance(source_type=SourceType.USER_STATED))[0]
    proposal=app.state.knowledge_service.propose(subject_ref=person['id'],target_ref=f'project:{project}',predicate='works_on',value='Mitarbeit',statement=episode.body,rationale='Expliziter Beleg',evidence=[Evidence(episode.id,episode.body,episode.digest)])[0]
    claim=app.state.knowledge_service.accept(proposal.id,supersedes=[])
    # Simuliert ein globales Ergebnisfenster, in dem diese ältere Beziehung fehlt.
    monkeypatch.setattr(app.state.claims,'all_claims',lambda **kwargs: [])
    params={'uid':'test:meeting','project_id':project,'person_id':person['id']}
    prepared=client.get('/api/v1/calendar/preparation',params=params).json()
    profile=client.get('/api/v1/memory/registry/'+person['id']).json()
    assert [c['id'] for c in prepared['claims']]==[claim.id]
    assert prepared['claims']==profile['claims']
    assert [s['id'] for s in prepared['sources']]==[episode.id]
    app.state.claims.retract(claim.id,reason='Beziehung korrigiert')
    assert client.get('/api/v1/calendar/preparation',params=params).json()['claims']==[]
    assert client.get('/api/v1/memory/registry/'+person['id']).json()['claims']==[]


def test_changed_decision_basis_keeps_project_context_in_briefing_and_preparation():
    app, source = preparation_app()
    client = TestClient(app)
    project = client.post('/api/v1/projects', json={'name':'Atlas'}).json()['id']
    episode = app.state.episodes.record(EpisodeKind.MESSAGE, 'Budgetbeleg', 'Budget ist freigegeben.',
        Provenance(source_type=SourceType.USER_STATED))[0]
    proposal = app.state.knowledge_service.propose(subject_ref='project:'+project, predicate='budget',
        value='freigegeben', statement=episode.body, rationale='Nutzerangabe',
        evidence=[Evidence(episode.id, episode.body, episode.digest)])[0]
    claim = app.state.knowledge_service.accept(proposal.id, supersedes=[])
    decision = client.post('/api/v1/decisions', json={'statement':'Angebot beauftragen',
        'claim_ids':[claim.id], 'project_id':project}).json()
    def briefing():
        return [item for item in client.get('/api/v1/morning-briefing').json()['needs_you'] if item['source']=='entscheidung']
    def preparation():
        return client.get('/api/v1/calendar/preparation', params={'uid':'test:meeting','project_id':project}).json()
    assert briefing() == [] and not preparation()['decisions'][0]['erschuettert']
    app.state.claims.retract(claim.id, reason='Budget wurde zurückgezogen')
    attention = briefing()[0]
    assert attention['source_ref'] == decision['id']
    assert attention['project_id'] == project
    assert attention['title'] == 'Angebot beauftragen'
    assert attention['detail'] == 'Projekt: Atlas'
    assert 'Budget ist freigegeben' in attention['reason']
    assert preparation()['decisions'][0]['erschuettert'] and preparation()['claims'] == []
    client.post('/api/v1/decisions/'+decision['id']+'/retract')
    assert briefing() == [] and preparation()['decisions'] == []


def test_briefing_uses_browser_timezone_for_day_and_event_time(monkeypatch):
    from icarus_memory import server
    from zoneinfo import ZoneInfo
    for utc_now, expected in [('2026-09-07T23:10:00+00:00', '01:30'), ('2026-01-07T23:10:00+00:00', '00:30')]:
        instant = datetime.fromisoformat(utc_now)
        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
        monkeypatch.setattr(server, 'datetime', FixedDatetime)
        app, source = preparation_app()
        source.items = [Event('local-day', 'Lokaler Tag', instant+timedelta(minutes=20), instant+timedelta(hours=1))]
        result = TestClient(app).get('/api/v1/morning-briefing', params={'timezone':'Europe/Berlin'}).json()
        assert result['later_today'][0]['time'] == expected
        assert datetime.fromisoformat(result['generated_at']).date() == instant.astimezone(ZoneInfo('Europe/Berlin')).date()
        assert result['timezone'] == 'Europe/Berlin'
    assert TestClient(app).get('/api/v1/morning-briefing', params={'timezone':'not/a-zone'}).status_code == 422


def test_briefing_keeps_healthy_calendar_and_reports_partial_failure_until_retry():
    app, source = preparation_app()
    failed = Calendar()
    failed.fail = True
    app.state.calendar = CalendarCollection([
        NamedCalendar('test', 'Testkalender', source),
        NamedCalendar('other', 'Zweiter Kalender', failed),
    ])
    client = TestClient(app)
    result = client.get('/api/v1/morning-briefing').json()
    assert any(item['source_ref'] == 'test:meeting' for item in result['later_today'])
    assert any(item['section'] == 'calendar' for item in result['partial_failures'])
    assert client.get('/api/v1/calendar/preparation', params={'uid':'test:meeting'}).status_code == 200
    assert client.get('/api/v1/calendar/preparation', params={'uid':'other:meeting'}).status_code == 503
    failed.fail = False
    result = client.get('/api/v1/morning-briefing').json()
    assert not any(item['section'] == 'calendar' for item in result['partial_failures'])
    assert client.get('/api/v1/calendar/preparation', params={'uid':'other:meeting'}).status_code == 200


def test_memory_read_failure_keeps_calendar_visible_and_clears_after_retry(monkeypatch):
    app, source = preparation_app()
    client = TestClient(app)
    original = app.state.store.usable
    def unavailable(*args, **kwargs):
        raise RuntimeError('synthetic internal storage detail')
    monkeypatch.setattr(app.state.store, 'usable', unavailable)
    response = client.get('/api/v1/morning-briefing')
    assert response.status_code == 200
    result = response.json()
    assert result['later_today'][0]['source_ref'] == 'test:meeting'
    assert any(item['section'] == 'memory' for item in result['partial_failures'])
    assert 'synthetic internal storage detail' not in str(result)
    monkeypatch.setattr(app.state.store, 'usable', original)
    result = client.get('/api/v1/morning-briefing').json()
    assert not any(item['section'] == 'memory' for item in result['partial_failures'])
