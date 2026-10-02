"""Today and explicit meeting context share current automatic source reports."""
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_calendar_preparation import Calendar
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api


def indexed(app, *, project_id=None, text='Nora liefert den Entwurf nur nach Freigabe.'):
    episode, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, 'Projektbrief', text,
        Provenance(SourceType.DOCUMENT, source_ref='synthetic:project-brief'), project_id=project_id)
    store = WorkingMemoryStore(app.state.episodes)
    assert store.commit(app.state.episodes.support_snapshot(episode.id),
        [{'start':0, 'end':len(text), 'kind':'conditional'}], model='synthetic')
    return episode


def test_today_uses_current_reports_and_withdrawal_without_creating_tasks(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        episode = indexed(app)
        briefing = client.get('/api/v1/morning-briefing').json()
        rows = [row for row in briefing['happening_now'] if row['source'] == 'working_memory']
        assert [row['source_ref'] for row in rows] == [episode.id]
        assert rows[0]['detail'] == 'Quelle berichtet · Bedingte Aussage'
        assert not any(row.get('source_ref') == episode.id for row in briefing['needs_you'])
        assert app.state.tasks.open_tasks(limit=None) == [] and app.state.claims.revision == 0
        assert provider.calls == []
        client.post(f'/api/v1/episodes/{episode.id}/ignore').raise_for_status()
        after = client.get('/api/v1/morning-briefing').json()
        assert not any(row.get('source_ref') == episode.id for row in after['happening_now'])
        assert not any(episode.title in str(row) for row in after['happening_now'])
    finally:
        client.close()
        _close_app(app)


def test_meeting_only_labels_explicit_project_sources_and_refreshes_after_dismissal(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        app.state.calendar = CalendarCollection([NamedCalendar('test', 'Testkalender', Calendar())])
        pid = client.post('/api/v1/projects', json={'name':'Atlas'}).json()['id']
        selected = indexed(app, project_id=pid)
        outside = indexed(app, text='Atlas ist im Text erwähnt, aber nicht zugeordnet.')
        url = '/api/v1/calendar/preparation'
        assert client.get(url, params={'uid':'test:meeting'}).json()['sources'] == []
        params = {'uid':'test:meeting', 'project_id':pid}
        before = client.get(url, params=params).json()
        assert [row['id'] for row in before['sources']] == [selected.id]
        assert before['sources'][0]['working_kinds'] == ['conditional']
        assert before['sources'][0]['body'] == selected.body
        assert outside.id not in str(before)
        assert provider.calls == []
        client.post(f'/api/v1/memory/working/{selected.id}/dismiss').raise_for_status()
        after = client.get(url, params=params).json()
        assert after['sources'][0]['body'] == selected.body
        assert after['sources'][0]['working_kinds'] == []
        assert after['working_memory_more']
        client.post(f'/api/v1/episodes/{selected.id}/ignore').raise_for_status()
        assert client.get(url, params=params).json()['sources'] == []
    finally:
        client.close()
        _close_app(app)
