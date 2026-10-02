"""Saved, indexed and failed must be distinguishable at the source boundary."""
import pytest
from tests.test_context_identity import core
from tests.test_source_answers_http import _api, _upload
from tests.test_conversation_retraction import _close_app
from icarus_memory.working_memory_store import WorkingMemoryStore


def test_source_status_tracks_actual_index_lifecycle(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        eid = _upload(client, 'Die Dachprüfung ist am 5. November 2026.')
        def state():
            return client.get(f'/api/v1/episodes/{eid}').json().get('memory_status', {}).get('state')
        assert state() == 'paused'
        store = WorkingMemoryStore(app.state.episodes)
        snap = app.state.episodes.support_snapshot(eid)
        store.fail(snap)
        # Automatik aus: Der Satz verspricht keinen Versuch, der nicht kommt (Fremdprobe 3, Befund 9).
        assert state() == 'failed_paused'
        assert 'sobald das automatische Sortieren läuft' in client.get(f'/api/v1/episodes/{eid}').json()['memory_status']['label']
        assert store.commit(snap, [{'start':0,'end':len(snap.episode.body),'kind':'fact'}], model='synthetic')
        assert state() == 'complete'
        items = client.get('/api/v1/sources/documents').json()['items']
        assert next(i for i in items if i['id']==eid)['memory_status']['state'] == 'complete'
        store.dismiss(eid)
        assert state() == 'dismissed'
        app.state.episodes.ignore(eid)
        assert state() == 'excluded'
    finally:
        client.close(); _close_app(app)


@pytest.mark.parametrize('mode, expected', [('empty','empty'),('deferred','deferred')])
def test_no_findings_or_unsupported_source_is_not_reported_as_search_ready(core,tmp_path,monkeypatch,mode,expected):
    app,client,_ = _api(core,tmp_path,monkeypatch)
    try:
        eid=_upload(client,'Ein kurzer Text ohne weitere Angaben.')
        store=WorkingMemoryStore(app.state.episodes); snap=app.state.episodes.support_snapshot(eid)
        if mode=='empty': store.commit(snap,[],model='synthetic')
        else: store.defer(snap)
        assert client.get(f'/api/v1/episodes/{eid}').json().get('memory_status',{}).get('state') == expected
    finally:
        client.close();_close_app(app)
