"""Suchen in Stufen: erst klären, was gemeint ist, dann gezielt in die Tiefe.

„Was ist mit Mainz los?“ kann das Projekt Mainz oder die Uniklinik meinen.
Kingfisher fragt dann mit einem Klick nach, statt zu raten, und sucht nach
dem Klick nur in den Quellen der gewählten Bedeutung.
"""
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api, _ask, _conversation
from tests.test_working_memory_choices import _choose, _selector

PROJEKT = 'Die Druckfreigabe für die Broschüre kommt Donnerstag.'
KLINIK = 'Die Studienunterlagen der Kardiologie folgen nächste Woche.'
FRAGE = 'Was ist mit Mainz los?'


def _quelle(app, titel, text, absender, project=None, einordnen=True):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, text,
        Provenance(SourceType.EMAIL, source_ref=f'work:<{titel}-{len(text)}@example.invalid>'),
        participants=[absender], project_id=project)
    if einordnen:
        store = WorkingMemoryStore(app.state.episodes)
        pending = store.pending(episode_ids=[episode.id])[0]
        assert store.commit(pending, [{'start': 0, 'end': len(text), 'kind': 'fact'}], model='local-test')
    return episode


def _mainz(app):
    projekt = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
    # Die Projektquelle nennt Mainz nicht: Sie gehört trotzdem dazu.
    eigen = _quelle(app, 'Druckfreigabe', PROJEKT, 'Anna <anna@agentur.example>', projekt.id)
    klinik = [_quelle(app, 'Studie', KLINIK, 'Dr. Kranz <kranz@unimedizin-mainz.example>'),
              _quelle(app, 'Rückfrage', 'Kurze Rückfrage zur Ethikkommission.',
                      'Dr. Kranz <kranz@unimedizin-mainz.example>')]
    return projekt, eigen, klinik


def test_open_question_asks_which_meaning_without_model(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        calls = _selector(provider, 'reports')
        conversation = _conversation(client)
        asked = _ask(client, conversation, FRAGE)
        context = asked['metadata']['context']
        assert context['answer_contract']['status'] == 'meaning_choice'
        labels = [option['label'] for option in context['clarification_choices']]
        assert labels == ['Projekt Mainz', 'Mails von unimedizin-mainz.example']
        assert 'Welchen meinst du?' in asked['content']
        assert 'Projekt Mainz — eine Quelle' in asked['content']
        # Die erste Stufe braucht kein Modell und schreibt nichts.
        assert calls == []
    finally:
        client.close()


def test_click_searches_only_the_chosen_meaning(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _, eigen, klinik = _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        asked = _ask(client, conversation, FRAGE)
        labels = [option['label'] for option in asked['metadata']['context']['clarification_choices']]
        revision = app.state.claims.revision

        response = _choose(client, conversation, labels.index('Mails von unimedizin-mainz.example'),
                           'Mails von unimedizin-mainz.example')
        assert response.status_code == 201, response.text
        answer = response.json()['messages'][-1]
        assert answer['metadata']['context']['answer_contract']['status'] == 'working_reports'
        assert 'Gemeint: Mails von unimedizin-mainz.example' in answer['content']
        assert KLINIK in answer['content'] and PROJEKT not in answer['content']
        assert 'Auch gefunden: Projekt Mainz' in answer['content']
        assert {link['episode_id'] for link in answer['metadata']['context']['source_links']} <= {
            episode.id for episode in klinik}
        assert app.state.claims.revision == revision

        # Das Projekt: sofort der Stand der Dinge aus der Mappe, ohne Modell,
        # auch mit der Quelle, in der „Mainz“ gar nicht steht.
        asked = _ask(client, conversation, FRAGE)
        response = _choose(client, conversation, 0, 'Projekt Mainz')
        answer = response.json()['messages'][-1]
        assert answer['metadata']['context']['answer_contract'] == {
            'version': 1, 'status': 'mappe', 'semantic_validation': False, 'model_called': False,
            'selected_assertion_ids': []}
        assert answer['content'].startswith('Projekt Mainz · Stand der Dinge')
        vorne = answer['content'].split('Auch gefunden:')[0]
        assert PROJEKT in vorne and KLINIK not in vorne
        assert [link['episode_id'] for link in answer['metadata']['context']['source_links']] == [eigen.id]
    finally:
        client.close()


def test_stale_or_forged_meaning_click_is_refused(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        assert _choose(client, conversation, 0, 'Projekt Orion').status_code == 409
        assert _choose(client, conversation, 4, 'Projekt Mainz').status_code == 409
    finally:
        client.close()


def test_one_clear_meaning_is_answered_right_away(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        projekt = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        for n in range(4):
            _quelle(app, f'Druck {n}', f'Freigabe Teil {n} kommt.', 'Anna <anna@agentur.example>', projekt.id)
        _quelle(app, 'Ausflug', 'Wir waren in Mainz am Dom.', 'Oma <oma@example.invalid>')
        _selector(provider, 'reports')
        conversation = _conversation(client)
        answer = _ask(client, conversation, FRAGE)
        assert answer['metadata']['context']['answer_contract']['status'] == 'mappe'
        assert answer['content'].startswith('Projekt Mainz · Stand der Dinge')
        assert 'am Dom' not in answer['content'].split('Auch gefunden')[0]
        assert 'Auch gefunden: Mails mit Oma' in answer['content']
    finally:
        client.close()


def test_chosen_meaning_without_classified_sources_says_so(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        projekt = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        _quelle(app, 'Druckfreigabe', PROJEKT, 'Anna <anna@agentur.example>', projekt.id, einordnen=False)
        for titel in ('Studie', 'Ethik', 'Termine'):
            _quelle(app, titel, f'{KLINIK} {titel}', 'Dr. Kranz <kranz@unimedizin-mainz.example>', einordnen=False)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        asked = _ask(client, conversation, FRAGE)
        # Auch ohne Einordnung kennt die erste Stufe die Bedeutungen.
        assert asked['metadata']['context']['answer_contract']['status'] == 'meaning_choice'
        answer = _choose(client, conversation, 0, 'Projekt Mainz').json()['messages'][-1]
        assert 'Eine Quelle wird noch eingeordnet' in answer['content']
    finally:
        client.close()


def test_clear_but_unclassified_meaning_does_not_ask_with_one_choice(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        projekt = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        _quelle(app, 'Druckfreigabe', PROJEKT, 'Anna <anna@agentur.example>', projekt.id, einordnen=False)
        _selector(provider, 'reports')
        answer = _ask(client, _conversation(client), FRAGE)
        context = answer['metadata'].get('context', {})
        assert context.get('answer_contract', {}).get('status') != 'meaning_choice'
        assert 'clarification_choices' not in context
    finally:
        client.close()


def test_precise_question_skips_the_first_stage(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        answer = _ask(client, conversation, 'Wann kommen die Studienunterlagen der Kardiologie?')
        assert answer['metadata']['context']['answer_contract']['status'] != 'meaning_choice'
        assert 'Gemeint:' not in answer['content']
    finally:
        client.close()


def test_calendar_meaning_is_shown_but_not_a_search_button(core, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        _selector(provider, 'reports')
        start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        app.state.agent._termine = lambda: [{'uid': 't1', 'summary': 'Workshop', 'start': start,
                                             'location': 'Mainz, Rheinufer'}]
        conversation = _conversation(client)
        asked = _ask(client, conversation, FRAGE)
        assert 'Termin „Workshop“' in asked['content'] and 'Mainz, Rheinufer' in asked['content']
        labels = [option['label'] for option in asked['metadata']['context']['clarification_choices']]
        assert not any('Workshop' in label for label in labels)
        answer = _choose(client, conversation, 0, 'Projekt Mainz').json()['messages'][-1]
        # Nach der Wahl des Projekts steht der Termin in dessen Mappe, nicht doppelt darunter.
        vorne, hinten = answer['content'].split('Auch gefunden:')
        assert '· Workshop am ' in vorne and 'Workshop' not in hinten
        # Ein kaputter Kalender kippt die Frage nicht.
        app.state.agent._termine = lambda: 1 / 0
        assert _ask(client, conversation, FRAGE)['metadata']['context']['answer_contract']['status'] \
            == 'meaning_choice'
    finally:
        client.close()


def test_questions_to_kingfisher_itself_are_not_a_search(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _quelle(app, 'Gruß', 'Ich schreibe dir morgen wegen Mainz.', 'Anna <anna@agentur.example>')
        _quelle(app, 'Gruß 2', 'Danke dir für alles.', 'Anna <anna@agentur.example>')
        _selector(provider, 'reports')
        conversation = _conversation(client)
        for frage in ('Was ist mit dir los?', 'Was weißt du über mich?'):
            context = _ask(client, conversation, frage)['metadata'].get('context', {})
            assert context.get('answer_contract', {}).get('status') not in {'meaning_choice', 'meaning_overview'}
    finally:
        client.close()


def test_own_chat_lines_are_no_meaning(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, 'Was gibt es Neues bei Rust?')
        _ask(client, conversation, 'Merk dir: Rust ist spannend.')
        assert app.state.episodes.mentions('Rust') == ([], False)
    finally:
        client.close()


def test_ignored_source_retires_the_question_and_its_labels(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _, _, klinik = _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        app.state.episodes.ignore(klinik[0].id)
        # Die gespeicherte Rückfrage nennt die Klinik nicht mehr wörtlich …
        shown = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert 'unimedizin' not in shown['content'] and 'nicht mehr aktuell' in shown['content']
        assert 'clarification_choices' not in shown['metadata']['context']
        # … und ein Klick darauf wird abgelehnt.
        assert _choose(client, conversation, 1, 'Mails von unimedizin-mainz.example').status_code == 409
    finally:
        client.close()


def test_also_found_disappears_with_its_sources(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _, _, klinik = _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        answer = _choose(client, conversation, 0, 'Projekt Mainz').json()['messages'][-1]
        assert 'Mails von unimedizin-mainz.example' in answer['content']
        for episode in klinik:
            app.state.episodes.ignore(episode.id)
        shown = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert PROJEKT in shown['content'] and 'unimedizin' not in shown['content']
    finally:
        client.close()


def test_follow_up_stays_within_the_chosen_meaning(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        _choose(client, conversation, 1, 'Mails von unimedizin-mainz.example')
        response = client.post(f'/api/v1/conversations/{conversation}/messages',
                               json={'message': 'Erklär mir das genauer', 'answer_mode': 'auto'})
        answer = response.json()['messages'][-1]
        assert PROJEKT not in answer['content']
        assert answer['metadata']['context']['working_answer']['meaning_scope']['art'] == 'absender'
    finally:
        client.close()


def test_one_mail_does_not_outweigh_many_mentions(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _quelle(app, 'Studie', KLINIK, 'Dr. Kranz <kranz@unimedizin-mainz.example>')
        for n in range(5):
            _quelle(app, f'Reise {n}', f'Wir fahren nach Mainz, Teil {n}.', f'P{n} <p{n}@firma{n}.example>')
        _selector(provider, 'reports')
        asked = _ask(client, _conversation(client), FRAGE)
        assert asked['metadata']['context']['answer_contract']['status'] == 'meaning_choice'
        labels = [c['label'] for c in asked['metadata']['context']['clarification_choices']]
        assert labels == ['Mails von unimedizin-mainz.example', 'Weitere Erwähnungen von „Mainz“']
    finally:
        client.close()


def test_only_plain_mentions_take_the_usual_way(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        # Einzelne Erwähnungen von verschiedenen Absendern sind keine Bedeutung: der gewohnte Weg.
        for n in range(2):
            _quelle(app, f'Notiz {n}', f'Python ist installiert, Teil {n}.', f'P{n} <p{n}@firma{n}.example>')
        _selector(provider, 'reports')
        answer = _ask(client, _conversation(client), 'Was weißt du über Python?')
        context = answer['metadata'].get('context', {})
        assert context.get('answer_contract', {}).get('status') not in {'meaning_choice', 'meaning_overview'}
        assert 'Gemeint:' not in answer['content']
    finally:
        client.close()


def test_appointment_and_mentions_do_not_ask_with_one_choice(core, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _quelle(app, 'Ausflug', 'Wir waren in Mainz am Dom.', 'Oma <oma@example.invalid>')
        _selector(provider, 'reports')
        start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        app.state.agent._termine = lambda: [{'uid': 't1', 'summary': 'Workshop Mainz', 'start': start}]
        answer = _ask(client, _conversation(client), FRAGE)
        assert 'clarification_choices' not in answer['metadata'].get('context', {})
        assert 'am Dom' in answer['content']
        assert 'Auch gefunden: Termin „Workshop Mainz“' in answer['content']
    finally:
        client.close()


def test_unrelated_confirmed_words_do_not_switch_the_stage_off(core, tmp_path, monkeypatch):
    agent, _, _, _, accept = core
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        accept('project:orion', 'Orion: Es gibt Neues zur Lieferung.')
        _mainz(app)
        _selector(provider, 'reports')
        asked = _ask(client, _conversation(client), 'Was gibt es Neues bei Mainz?')
        assert asked['metadata']['context']['answer_contract']['status'] == 'meaning_choice'
    finally:
        client.close()


def test_outdated_question_offers_to_ask_again(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _, _, klinik = _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        app.state.episodes.ignore(klinik[0].id)
        context = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]['metadata']['context']
        assert context['answer_contract']['status'] == 'meaning_outdated'
        assert context['original_question'] == FRAGE and context['refresh_available'] is True
    finally:
        client.close()


def test_project_answer_shows_new_sources_when_reopened(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        projekt = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        for n in range(3):
            _quelle(app, f'Druck {n}', f'Freigabe Mainz Teil {n} kommt.', 'Anna <anna@agentur.example>', projekt.id)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        answer = _ask(client, conversation, FRAGE)
        assert answer['content'].startswith('Projekt Mainz · Stand der Dinge')
        _quelle(app, 'Druck neu', 'Neue Freigabe Mainz ist da.', 'Anna <anna@agentur.example>', projekt.id)
        # Die Mappe ist eine Ansicht: Beim erneuten Öffnen steht die neue Quelle darin.
        shown = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert 'Neue Freigabe Mainz ist da.' in shown['content']
    finally:
        client.close()


def test_automatic_scope_becomes_stale_with_new_sources(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _quelle(app, 'Standort Mainz', 'Die Halle ist frei.', 'Makler <info@makler.example>')
        _quelle(app, 'AW: Standort Mainz', 'Danke für die Rückmeldung.', 'Makler <info@makler.example>')
        _selector(provider, 'reports')
        conversation = _conversation(client)
        answer = _ask(client, conversation, FRAGE)
        assert 'Gemeint: Mails mit Makler (makler.example)' in answer['content']
        _quelle(app, 'Notiz', 'Mainz meldet sich morgen.', 'Oma <oma@example.invalid>')
        shown = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert shown['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
    finally:
        client.close()


def test_folder_answer_drops_ignored_sources_when_reopened(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _, eigen, _ = _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        assert PROJEKT in _choose(client, conversation, 0, 'Projekt Mainz').json()['messages'][-1]['content']
        app.state.episodes.ignore(eigen.id)
        shown = client.get(f'/api/v1/conversations/{conversation}').json()['messages'][-1]
        assert PROJEKT not in shown['content'] and shown['metadata']['context']['source_links'] == []
    finally:
        client.close()


def test_follow_up_after_folder_answer_stays_in_the_project(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        _choose(client, conversation, 0, 'Projekt Mainz')
        response = client.post(f'/api/v1/conversations/{conversation}/messages',
                               json={'message': 'Erklär mir das genauer', 'answer_mode': 'auto'})
        answer = response.json()['messages'][-1]
        scope = answer['metadata']['context']['working_answer']['meaning_scope']
        assert scope['art'] == 'projekt' and PROJEKT in answer['content'] and KLINIK not in answer['content']
    finally:
        client.close()


def test_folder_answer_is_stored_without_quotes(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        _selector(provider, 'reports')
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        _choose(client, conversation, 0, 'Projekt Mainz')
        stored = app.state.conversations.messages(conversation)[-1]
        assert PROJEKT not in stored.content and 'source_links' not in stored.metadata['context']
    finally:
        client.close()


def test_folder_works_without_local_model(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    try:
        _mainz(app)
        provider.is_local = False
        conversation = _conversation(client)
        _ask(client, conversation, FRAGE)
        answer = _choose(client, conversation, 0, 'Projekt Mainz').json()['messages'][-1]
        assert answer['content'].startswith('Projekt Mainz · Stand der Dinge') and PROJEKT in answer['content']
    finally:
        client.close()
