"""Mappe, Ebene 2: offene Punkte zu Projekt und Person, ohne Modell."""
from datetime import datetime, timedelta, timezone

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api
from tests.test_source_answers_http import _ask, _conversation

BITTE = 'Kannst du mir bis Freitag die Druckdaten schicken?'
ZUSAGE = 'Ich liefere die Prüfmuster am 12. Oktober.'
AENDERUNG = 'Der Termin mit der Druckerei verschiebt sich auf November.'
FAKT = 'Das Papier ist 120 g schwer.'


def test_project_question_works_without_model_and_free_chat_has_honest_fallback(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id)
        app.state.agent._provider = None
        assert client.get('/api/v1/status').json()['chat'] is False
        project = _ask(client, _conversation(client), 'Erzähl mir was zu Mainz')
        assert 'Druckdaten' in project['content']
        assert project['metadata']['context']['answer_contract']['status'] == 'mappe'
        free = _ask(client, _conversation(client), 'Erzähl mir einen Witz.')
        assert 'noch kein Modell dafür eingerichtet' in free['content']
    finally:
        client.close()


def _quelle(app, titel, abschnitte, absender='Anna Keller <anna@agentur.example>', project=None, tage=1):
    text = ' '.join(t for t, _ in abschnitte)
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, text,
        Provenance(SourceType.EMAIL, source_ref=f'work:<{titel}@example.invalid>'),
        participants=[absender], project_id=project,
        occurred_at=datetime.now(timezone.utc) - timedelta(days=tage))
    store = WorkingMemoryStore(app.state.episodes)
    pending = store.pending(episode_ids=[episode.id])[0]
    items, pos = [], 0
    for teil, art in abschnitte:
        start = text.index(teil, pos)
        items.append({'start': start, 'end': start + len(teil), 'kind': art})
        pos = start + len(teil)
    assert store.commit(pending, items, model='local-test')
    return episode


def _projekt(app, name='Mainz'):
    return app.state.workspace.add_project(name, Provenance(SourceType.USER_STATED))


def test_project_details_quote_requests_commitments_and_changes(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        bitte = _quelle(app, 'Druckdaten', [(BITTE, 'request'), (FAKT, 'fact')], project=projekt.id, tage=1)
        _quelle(app, 'Muster', [(ZUSAGE, 'commitment')], 'Ben <ben@druck.example>', projekt.id, tage=3)
        _quelle(app, 'Verschiebung', [(AENDERUNG, 'change')], project=projekt.id, tage=2)
        _quelle(app, 'Fremd', [('Bitte ruf mich an.', 'request')], tage=1)
        data = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()
        offen = data['bitten_und_zusagen']
        assert [e['text'] for e in offen['eintraege']] == [BITTE, ZUSAGE]
        assert [e['art'] for e in offen['eintraege']] == ['Bitte', 'Zusage']
        assert offen['gesamt'] == 2 and offen['eintraege'][0]['episode_id'] == bitte.id
        assert [e['text'] for e in data['entwicklungen']['eintraege']] == [AENDERUNG]
        # Eine bloße Angabe ist kein offener Punkt, steht aber unter den neuesten
        # Angaben; eine fremde Bitte gehört nicht dazu.
        assert FAKT not in str(offen) and [e['text'] for e in data['angaben']['eintraege']] == [FAKT]
        assert 'ruf mich an' not in str(data)
        assert data['einordnung'] == {'eingeordnet': 3, 'offen': 0, 'ausgeschlossen': 0}
    finally:
        client.close()


def test_lists_name_their_total_instead_of_cutting_silently(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        for n in range(11):
            _quelle(app, f'Bitte {n}', [(f'Bitte schick mir Teil {n}.', 'request')], project=projekt.id, tage=n + 1)
        offen = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()['bitten_und_zusagen']
        assert len(offen['eintraege']) == 5 and offen['gesamt'] == 11
        # Neueste zuerst.
        assert offen['eintraege'][0]['text'] == 'Bitte schick mir Teil 0.'
    finally:
        client.close()


def test_ignored_and_claimed_sources_stay_out(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        weg = _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id)
        app.state.episodes.ignore(weg.id)
        data = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()
        assert data['bitten_und_zusagen'] == {'eintraege': [], 'gesamt': 0, 'ungefaehr': False, 'archiviert': 0}
    finally:
        client.close()


def test_long_sections_are_shortened_visibly(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        lang = 'Bitte prüfe ' + 'sehr ' * 120 + 'genau.'
        _quelle(app, 'Lang', [(lang, 'request')], project=projekt.id)
        [eintrag] = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()[
            'bitten_und_zusagen']['eintraege']
        assert eintrag['gekuerzt'] is True and eintrag['text'].endswith(' …')
        assert lang.startswith(eintrag['text'][:-2])
    finally:
        client.close()


def test_open_tasks_and_matching_appointments(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        jetzt = datetime.now(timezone.utc)
        spaeter = app.state.tasks.add('Druckdaten prüfen', Provenance(SourceType.USER_STATED),
                                      due=jetzt + timedelta(days=5), project_id=projekt.id)
        frueher = app.state.tasks.add('Angebot freigeben', Provenance(SourceType.USER_STATED),
                                      due=jetzt - timedelta(days=1), project_id=projekt.id)
        erledigt = app.state.tasks.add('Alt', Provenance(SourceType.USER_STATED), project_id=projekt.id)
        app.state.tasks.complete(erledigt.id)
        app.state.agent._termine = lambda: [
            {'uid': 't1', 'summary': 'Abstimmung Mainz', 'start': (jetzt + timedelta(days=2)).isoformat()},
            {'uid': 't2', 'summary': 'Zahnarzt', 'start': (jetzt + timedelta(days=1)).isoformat()},
            {'uid': 't3', 'summary': 'Mainz Rückblick', 'start': (jetzt - timedelta(days=3)).isoformat()}]
        data = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()
        assert [t['id'] for t in data['aufgaben']['eintraege']] == [frueher.id, spaeter.id]
        assert data['aufgaben']['eintraege'][0]['overdue'] is True and data['aufgaben']['gesamt'] == 2
        assert [t['uid'] for t in data['termine']['eintraege']] == ['t1']
        # Ein Kalender, der nicht antwortet, wird genannt, nicht verschwiegen.
        app.state.agent._termine = lambda: None
        data = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()
        assert data['termine']['kalender'] == 'nicht_erreichbar'
    finally:
        client.close()


def test_person_details_cover_their_sources_and_waiting_tasks(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        _quelle(app, 'Druckdaten', [(BITTE, 'request')], 'Anna Keller')
        _quelle(app, 'Muster', [(ZUSAGE, 'commitment')], 'Ben Roth')
        task = app.state.tasks.add('Rückmeldung zum Entwurf', Provenance(SourceType.USER_STATED))
        app.state.tasks.warten_auf(task.id, 'Anna Keller')
        response = client.get('/api/v1/memory/people/Anna%20Keller/einzelheiten')
        assert response.status_code == 200, response.text
        data = response.json()
        assert [e['text'] for e in data['bitten_und_zusagen']['eintraege']] == [BITTE]
        assert [t['id'] for t in data['aufgaben']['eintraege']] == [task.id]
        assert client.get('/api/v1/memory/people/Niemand/einzelheiten').status_code == 404
    finally:
        client.close()


def test_details_write_nothing(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id)
        revision = app.state.claims.revision
        client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten')
        assert app.state.claims.revision == revision and provider.calls == []
    finally:
        client.close()


def test_source_with_confirmed_claim_is_not_quoted_raw(core, tmp_path, monkeypatch):
    accept = core[4]
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        _, episode = accept('project:mainz', BITTE)
        app.state.episodes.link_project(episode.id, projekt.id)
        store = WorkingMemoryStore(app.state.episodes)
        pending = store.pending(episode_ids=[episode.id])[0]
        assert store.commit(pending, [{'start': 0, 'end': len(BITTE), 'kind': 'request'}], model='local-test')
        data = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()
        # Die bestätigte Aussage steht im Wissensstand; die Rohquelle kehrt
        # nicht als unbestätigter Punkt zurück, auch nicht in der Zahl.
        assert data['bitten_und_zusagen']['eintraege'] == []
        assert data['bitten_und_zusagen']['gesamt'] == 0
    finally:
        client.close()


def test_valid_older_entries_are_not_hidden_behind_filtered_newer_ones(core, tmp_path, monkeypatch):
    accept = core[4]
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        _quelle(app, 'Alt', [(ZUSAGE, 'commitment')], project=projekt.id, tage=40)
        store = WorkingMemoryStore(app.state.episodes)
        for n in range(20):
            text = f'Bitte schick mir Teil {n}.'
            _, episode = accept(f'project:p{n}', text)
            app.state.episodes.link_project(episode.id, projekt.id)
            pending = store.pending(episode_ids=[episode.id])[0]
            assert store.commit(pending, [{'start': 0, 'end': len(text), 'kind': 'request'}], model='local-test')
        offen = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()['bitten_und_zusagen']
        assert [e['text'] for e in offen['eintraege']] == [ZUSAGE]
        assert offen['gesamt'] == 1 and offen['ungefaehr'] is False
    finally:
        client.close()


def test_all_entries_can_be_opened_in_place(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        for n in range(11):
            _quelle(app, f'Bitte {n}', [(f'Bitte schick mir Teil {n}.', 'request')], project=projekt.id, tage=n + 1)
        offen = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten?alle=1').json()['bitten_und_zusagen']
        assert len(offen['eintraege']) == 11 and offen['gesamt'] == 11
    finally:
        client.close()


def test_all_day_appointments_and_names_versus_addresses(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        _quelle(app, 'Druckdaten', [(BITTE, 'request')], 'Anna Keller <anna@agentur.example>')
        jetzt = datetime.now(timezone.utc)
        heute = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
        app.state.agent._termine = lambda: [
            {'uid': 't1', 'summary': 'Messe Mainz', 'start': heute.isoformat(), 'all_day': True},
            {'uid': 't2', 'summary': 'Telefonat', 'start': (jetzt + timedelta(days=1)).isoformat(),
             'attendees': ['mainz@example.org']},
            {'uid': 't3', 'summary': 'Abstimmung', 'start': (jetzt + timedelta(days=2)).isoformat(),
             'attendees': ['Anna Keller <anna@agentur.example>']},
            {'uid': 't4', 'summary': 'Essen mit Anna Keller', 'start': (jetzt + timedelta(days=3)).isoformat()}]
        projekt_termine = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()['termine']
        # Der heutige Ganztagstermin zählt, eine Adresse mit „mainz“ nicht.
        assert [t['uid'] for t in projekt_termine['eintraege']] == ['t1']
        assert projekt_termine['eintraege'][0]['ganztags'] is True
        person = client.get('/api/v1/memory/people/Anna%20Keller%20%3Canna%40agentur.example%3E/einzelheiten').json()
        assert [t['uid'] for t in person['termine']['eintraege']] == ['t3', 't4']
        assert [e['text'] for e in person['bitten_und_zusagen']['eintraege']] == [BITTE]
    finally:
        client.close()


def test_waiting_task_with_passed_date_is_overdue(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        _quelle(app, 'Druckdaten', [(BITTE, 'request')], 'Anna Keller')
        task = app.state.tasks.add('Rückmeldung', Provenance(SourceType.USER_STATED),
                                   due=datetime.now(timezone.utc) - timedelta(days=2))
        app.state.tasks.warten_auf(task.id, 'Anna Keller')
        [eintrag] = client.get('/api/v1/memory/people/Anna%20Keller/einzelheiten').json()['aufgaben']['eintraege']
        assert eintrag['overdue'] is True
    finally:
        client.close()


def test_classification_state_counts_the_same_sources_as_the_folder(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        projekt = _projekt(app)
        _quelle(app, 'Fertig', [(BITTE, 'request')], project=projekt.id)
        roh, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Neu', 'Noch nicht eingeordnet.',
                                           Provenance(SourceType.EMAIL, source_ref='work:<neu@example.invalid>'),
                                           project_id=projekt.id)
        weg, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Weg', 'Ausgenommen.',
                                           Provenance(SourceType.EMAIL, source_ref='work:<weg@example.invalid>'),
                                           project_id=projekt.id)
        WorkingMemoryStore(app.state.episodes).dismiss(weg.id)
        ignoriert, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Ignoriert', 'Egal.',
                                                 Provenance(SourceType.EMAIL, source_ref='work:<ig@example.invalid>'),
                                                 project_id=projekt.id)
        app.state.episodes.ignore(ignoriert.id)
        data = client.get(f'/api/v1/memory/projects/{projekt.id}/einzelheiten').json()
        assert data['einordnung'] == {'eingeordnet': 1, 'offen': 1, 'ausgeschlossen': 1}
    finally:
        client.close()
