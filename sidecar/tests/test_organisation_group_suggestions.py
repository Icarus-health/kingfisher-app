"""Synthetische Organisationsansichten: Regelgrenzen, aktueller Stand und CAS."""
import pytest
from fastapi.testclient import TestClient
from icarus_memory import MemoryBackend, SelfModelStore, EpisodeKind, Provenance, SourceType
from icarus_memory.server import create_app


def entry(identifier, name, fp='r1'):
    return {'id': identifier, 'name': name, 'sources': [['source-' + identifier, fp]]}


def test_local_rule_offers_amazon_variants_but_not_amazonas_or_general_prefixes():
    from icarus_memory.organisation_group_suggestions import candidates
    entries = [entry('organisation:de', 'Amazon.de'), entry('organisation:com', 'Amazon.com'),
               entry('organisation:digital', 'Amazon Digital Germany'), entry('organisation:river', 'Amazonas'),
               entry('organisation:river2', 'Amazonas Reisen'), entry('organisation:clinic', 'Digital Klinik'),
               entry('organisation:factory', 'Digital Fabrik'), entry('organisation:other', 'Amazon Apotheke')]
    found = candidates(entries)
    assert len(found) == 1
    assert found[0]['members'] == ['organisation:com', 'organisation:de', 'organisation:digital']
    assert 'ähnliche Namen' in found[0]['reason']
    assert len(found[0]['id']) == 64
    assert candidates(list(reversed(entries))) == found


def test_unconnected_specific_names_and_common_domain_roots_are_not_grouped():
    from icarus_memory.organisation_group_suggestions import candidates
    assert candidates([entry('a', 'Acme Dental'), entry('b', 'Acme Logistics')]) == []
    assert candidates([entry('a', 'Service.de'), entry('b', 'Service.com')]) == []
    assert candidates([entry('a', 'Amazonas.de'), entry('b', 'Amazon.com')]) == []


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    from icarus_memory.organisation_group_suggestions import register
    if not any(getattr(route, 'path', '') == '/api/v1/organisation-group-suggestions' for route in app.routes):
        mounts = [route for route in app.router.routes if getattr(route, 'path', None) == '']
        app.router.routes[:] = [route for route in app.router.routes if route not in mounts]
        register(app, [])
        app.router.routes.extend(mounts)
    from icarus_memory.akten_routes import bausteine
    bezuege = bausteine(app)[0]
    episodes = []
    for identifier, name in [('de', 'Amazon.de'), ('com', 'Amazon.com'), ('digital', 'Amazon Digital Germany')]:
        episode, _ = app.state.episodes.record(EpisodeKind.DOCUMENT, name, name,
                Provenance(SourceType.USER_STATED, source_ref='synthetic:' + identifier))
        bezuege.nutzer_setzen(episode.id, 'organisation:' + identifier, 'zu')
        episodes.append(episode)
    # Die Schreibweise wird aus synthetischen Original-Textstellen gelesen.
    bezuege.aktualisieren()
    with app.state.episodes._lock, app.state.episodes._conn:
        for episode, identifier in zip(episodes, ['de', 'com', 'digital']):
            fp = bezuege.quellen_von('organisation:' + identifier)[0]['fp']
            app.state.episodes._conn.execute('INSERT INTO sach_bezuege VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (episode.id, fp, 'organisation:' + identifier, 'organisation', 'nutzer', 0, len(episode.body), '', '', 0))
    return TestClient(app), app, episodes


def preview(client):
    result = client.get('/api/v1/organisation-group-suggestions')
    assert result.status_code == 200, result.text
    return result.json()


def body(snapshot, **changes):
    candidate = snapshot['suggestions'][0]
    return {'candidate_id': candidate['id'], 'name': candidate['name'], 'members': candidate['members'],
            'source_revision': snapshot['source_revision'], 'groups_revision': snapshot['groups_revision'],
            'group_revision': 0, **changes}


def test_complete_basis_confirm_edit_double_click_and_normal_undo(world):
    client, app, episodes = world
    state = preview(client)
    assert state['complete'] is True and state['total'] == 3
    assert {x['name'] for x in state['entries']} == {'Amazon.de', 'Amazon.com', 'Amazon Digital Germany'}
    request = body(state, name='Einkäufe', members=['organisation:de', 'organisation:com'])
    saved = client.post('/api/v1/organisation-group-suggestions/confirm', json=request)
    assert saved.status_code == 200, saved.text
    again = client.post('/api/v1/organisation-group-suggestions/confirm', json=request)
    assert again.status_code == 200 and again.json() == saved.json()
    assert app.state.workspace_views.count('organisation_group') == 1
    assert app.state.episodes.get(episodes[0].id).body == 'Amazon.de'
    assert preview(client)['suggestions'] == []
    result = client.post('/api/v1/workspace-view/organisation_group/' + saved.json()['id'] + '/undo',
                         json={'revision': saved.json()['revision']})
    assert result.status_code == 200
    assert len(preview(client)['suggestions']) == 1


def test_source_withdrawal_member_change_and_group_change_reject_stale_confirmation(world):
    client, app, episodes = world
    old = preview(client)
    app.state.episodes.ignore(episodes[0].id)
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=body(old)).status_code == 409
    assert app.state.workspace_views.count('organisation_group') == 0


def test_changed_members_and_existing_groups_take_priority(world):
    client, app, _ = world
    old = preview(client)
    app.state.workspace_views.put('organisation_group', 'manual', {'name': 'Meine Wahl', 'members': ['organisation:de', 'organisation:other']}, 0)
    assert preview(client)['suggestions'] == []
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=body(old)).status_code == 409


def test_dismissal_persists_and_can_be_undone_without_merging(world):
    client, app, _ = world
    state = preview(client)
    identifier = state['suggestions'][0]['id']
    response = client.post('/api/v1/organisation-group-suggestions/' + identifier + '/dismiss',
                    json={'source_revision': state['source_revision'], 'groups_revision': state['groups_revision']})
    assert response.status_code == 200, response.text
    assert preview(client)['suggestions'] == []
    assert preview(client)['dismissals'][0]['name'] == 'Amazon'
    duplicate = client.post('/api/v1/organisation-group-suggestions/' + identifier + '/dismiss',
                    json={'source_revision': state['source_revision'], 'groups_revision': state['groups_revision']})
    assert duplicate.status_code == 200 and duplicate.json()['revision'] == 1
    assert app.state.workspace_views.count('organisation_group') == 0
    assert client.post('/api/v1/organisation-group-suggestions/' + identifier + '/undo-dismissal', json={'revision': 1}).status_code == 200
    assert len(preview(client)['suggestions']) == 1


def test_manual_selection_also_rechecks_members_and_does_not_overwrite_group(world):
    client, app, _ = world
    state = preview(client)
    manual = body(state, candidate_id=None, members=['organisation:de', 'organisation:missing'])
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=manual).status_code == 409
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=body(state, members=['organisation:de', 'organisation:de'])).status_code == 422


def test_current_name_or_added_member_requires_new_preview(world):
    client, app, episodes = world
    state = preview(client)
    changed = app.state.episodes.get(episodes[0].id)
    changed.body = 'Amazon Prime'
    with app.state.episodes.transaction():
        app.state.episodes._put(changed)
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=body(state)).status_code == 409
    assert app.state.workspace_views.count('organisation_group') == 0


def test_complete_current_basis_exceeds_graph_and_metadata_page_limits(world):
    client, app, episodes = world
    from icarus_memory.akten_routes import bausteine
    bezuege = bausteine(app)[0]
    # 2101 Nutzerbezüge derselben synthetischen Quelle; kein Graph-/UI-Paging.
    fp = bezuege.quellen_von('organisation:de')[0]['fp']
    with app.state.episodes._lock, app.state.episodes._conn:
        app.state.episodes._conn.executemany('INSERT INTO sach_nutzer VALUES (?,?,?,?,?,?)',
            [(episodes[0].id, 'organisation:fixture' + str(i), 'organisation', 'zu', fp, 'synthetic') for i in range(2101)])
    state = preview(client)
    assert state['total'] == 2104
    assert len(state['entries']) == 2104
    assert state['complete'] is True
    assert 'organisation:fixture2100' in {row['id'] for row in state['entries']}


def test_recreate_after_undo_uses_tombstone_cas_and_group_edit_is_guarded(world):
    client, _, _ = world
    first = client.post('/api/v1/organisation-group-suggestions/confirm', json=body(preview(client))).json()
    assert client.post('/api/v1/workspace-view/organisation_group/' + first['id'] + '/undo', json={'revision': 1}).status_code == 200
    snapshot = preview(client)
    recreated = client.post('/api/v1/organisation-group-suggestions/confirm', json=body(snapshot))
    assert recreated.status_code == 200 and recreated.json()['revision'] == 3
    current = preview(client)
    edit = {'candidate_id': None, 'group_id': first['id'], 'group_revision': 3, 'name': 'Neue Ansicht',
            'members': ['organisation:de', 'organisation:com'], 'source_revision': current['source_revision'], 'groups_revision': current['groups_revision']}
    edited = client.post('/api/v1/organisation-group-suggestions/confirm', json=edit)
    assert edited.status_code == 200 and edited.json()['revision'] == 4
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=edit).json() == edited.json()
    conflicting = {**edit, 'name': 'Überschreiben'}
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=conflicting).status_code == 409


def test_new_member_and_user_withdrawn_relation_invalidates_original_preview(world):
    client, app, episodes = world
    from icarus_memory.akten_routes import bausteine
    old = preview(client)
    bezuege = bausteine(app)[0]
    bezuege.nutzer_setzen(episodes[0].id, 'organisation:other', 'zu')
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=body(old)).status_code == 409
    latest = preview(client)
    bezuege.nutzer_setzen(episodes[1].id, 'organisation:com', 'nicht')
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=body(latest)).status_code == 409


def test_write_error_has_no_partial_group_and_revision_stays_reviewable(world, monkeypatch):
    client, app, _ = world
    state = preview(client)
    from icarus_memory.workspace_views import ViewChanged
    def fail(*args):
        raise ViewChanged('Synthetischer Schreibkonflikt')
    monkeypatch.setattr(app.state.workspace_views, 'put', fail)
    response = client.post('/api/v1/organisation-group-suggestions/confirm', json=body(state))
    assert response.status_code == 409
    assert app.state.workspace_views.count('organisation_group') == 0
    assert preview(client)['groups_revision'] == state['groups_revision']


def test_new_manual_group_cannot_rename_existing_group_implicitly(world):
    client, _, _ = world
    first = client.post('/api/v1/organisation-group-suggestions/confirm', json=body(preview(client))).json()
    latest = preview(client)
    request = {'candidate_id': None, 'name': 'Unbeabsichtigte Umbenennung', 'members': first['data']['members'],
               'group_revision': 0, 'source_revision': latest['source_revision'], 'groups_revision': latest['groups_revision']}
    assert client.post('/api/v1/organisation-group-suggestions/confirm', json=request).status_code == 409
    assert client.get('/api/v1/workspace-view/organisation_group/' + first['id']).json()['data']['name'] == 'Amazon'


def edited_group(client):
    first_response = client.post('/api/v1/organisation-group-suggestions/confirm', json=body(preview(client), members=['organisation:de', 'organisation:com']))
    assert first_response.status_code == 200
    first = first_response.json()
    current = preview(client)
    response = client.post('/api/v1/organisation-group-suggestions/confirm', json={
        'name': 'Geänderte Ansicht', 'members': ['organisation:com', 'organisation:digital'],
        'group_id': first['id'], 'group_revision': first['revision'],
        'source_revision': current['source_revision'], 'groups_revision': current['groups_revision']})
    assert response.status_code == 200
    return first, response.json()


def test_group_undo_rejects_restore_without_current_permitted_source_and_preserves_history(world):
    from fastapi import HTTPException
    from icarus_memory.organisation_group_suggestions import undo_group
    client, app, episodes = world
    first, updated = edited_group(client)
    app.state.episodes.ignore(episodes[0].id)
    assert 'organisation:de' not in {row['id'] for row in preview(client)['entries']}
    before_events = app.state.workspace_views._conn.execute('SELECT count(*) FROM view_events').fetchone()[0]
    with pytest.raises(HTTPException) as exc:
        undo_group(app, first['id'], updated['revision'])
    assert exc.value.status_code == 409
    routed = client.post('/api/v1/workspace-view/organisation_group/' + first['id'] + '/undo', json={'revision': updated['revision']})
    assert routed.status_code == 409, routed.text
    assert app.state.workspace_views.get('organisation_group', first['id']) == updated
    assert app.state.workspace_views._conn.execute('SELECT count(*) FROM view_events').fetchone()[0] == before_events


def test_group_undo_can_remove_group_after_all_member_sources_are_withdrawn(world):
    from fastapi import HTTPException
    from icarus_memory.organisation_group_suggestions import undo_group
    client, app, episodes = world
    saved = client.post('/api/v1/organisation-group-suggestions/confirm', json=body(preview(client))).json()
    for episode in episodes:
        app.state.episodes.ignore(episode.id)
    removed = undo_group(app, saved['id'], saved['revision'])
    assert removed['data'] is None and removed['revision'] == saved['revision'] + 1
    # Ein doppeltes Undo darf die eben entfernte Gruppe nicht wiederherstellen.
    with pytest.raises(HTTPException) as exc:
        undo_group(app, saved['id'], saved['revision'])
    assert exc.value.status_code == 409
    assert app.state.workspace_views.get('organisation_group', saved['id']) == removed
    # Undo der Entfernung wäre eine Wiederherstellung und ist mangels Quellen gesperrt.
    with pytest.raises(HTTPException) as exc:
        undo_group(app, saved['id'], removed['revision'])
    assert exc.value.status_code == 409
    assert app.state.workspace_views.get('organisation_group', saved['id']) == removed


def test_group_undo_uses_current_revision_and_preserves_current_cross_group_overlap_guard(world):
    from fastapi import HTTPException
    from icarus_memory.organisation_group_suggestions import undo_group
    client, app, _ = world
    first, updated = edited_group(client)
    with pytest.raises(HTTPException) as exc:
        undo_group(app, first['id'], first['revision'])
    assert exc.value.status_code == 409
    # Die frühere DE-Mitgliedschaft liegt inzwischen in einer anderen Gruppe.
    app.state.workspace_views.put('organisation_group', 'other-group', {'name': 'Andere', 'members': ['organisation:de']}, 0)
    with pytest.raises(HTTPException) as exc:
        undo_group(app, first['id'], updated['revision'])
    assert exc.value.status_code == 409
    assert app.state.workspace_views.get('organisation_group', first['id']) == updated


def test_group_undo_holds_current_source_and_group_locks_until_real_write(world, monkeypatch):
    import threading
    from icarus_memory.organisation_group_suggestions import undo_group
    client, app, _ = world
    first, updated = edited_group(client)
    store = app.state.workspace_views
    original_undo = store.undo
    results = []
    def checked_undo(*args):
        # Ein anderer Thread kann weder Quelle noch Gruppe zwischen Prüfung
        # und tatsächlichem Undo ändern; der echte Store schreibt anschließend.
        def contender():
            source_acquired = app.state.episodes._lock.acquire(blocking=False)
            if source_acquired:
                app.state.episodes._lock.release()
            view_acquired = store._lock.acquire(blocking=False)
            if view_acquired:
                store._lock.release()
            results.append((source_acquired, view_acquired))
        worker = threading.Thread(target=contender)
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive()
        return original_undo(*args)
    monkeypatch.setattr(store, 'undo', checked_undo)
    restored = undo_group(app, first['id'], updated['revision'])
    assert results == [(False, False)]
    assert restored['data'] == first['data'] and restored['revision'] == updated['revision'] + 1


@pytest.mark.parametrize('revision', [True, 0, -1, '1'])
def test_group_undo_rejects_invalid_revision_without_writing(world, revision):
    from fastapi import HTTPException
    from icarus_memory.organisation_group_suggestions import undo_group
    client, app, _ = world
    saved = client.post('/api/v1/organisation-group-suggestions/confirm', json=body(preview(client))).json()
    with pytest.raises(HTTPException) as exc:
        undo_group(app, saved['id'], revision)
    assert exc.value.status_code == 422
    assert app.state.workspace_views.get('organisation_group', saved['id']) == saved


def test_group_undo_checks_restored_members_not_withdrawn_current_members(world):
    from icarus_memory.organisation_group_suggestions import undo_group
    client, app, episodes = world
    first, updated = edited_group(client)
    app.state.episodes.ignore(episodes[2].id)  # Digital gehört nur zur derzeitigen Fassung.
    restored = undo_group(app, first['id'], updated['revision'])
    assert restored['data'] == first['data']
    assert restored['data']['members'] == ['organisation:com', 'organisation:de']
