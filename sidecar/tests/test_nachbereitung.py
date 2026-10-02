"""Etappe 2: Nach dem Termin fragt Kingfisher, was herausgekommen ist."""
from datetime import datetime, timedelta, timezone

from icarus_memory import briefing
from icarus_memory.connectors.calendar import Event
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.nachbereitung import text_aus_mitschrift
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api


class Kalender:
    """Wie ein echter Kalender: nur Termine, die ins Fenster ab `at` fallen."""

    def __init__(self, events):
        self._events = events
        self.last_errors = {}

    def events(self, days=7, at=None):
        beginn = at or datetime.now(timezone.utc)
        ende = beginn + timedelta(days=days)
        return [e for e in self._events if (e.end or e.start) > beginn and e.start < ende]

JETZT = datetime.now(timezone.utc).replace(microsecond=0)


def _vorbei(uid='t1', summary='Abstimmung Druck', attendees=('Anna Keller <anna@agentur.example>',),
            stunden=3, dauer=1, all_day=False):
    """Ein Termin, der vor `stunden` Stunden begann."""
    start = JETZT - timedelta(hours=stunden)
    return Event(uid=uid, summary=summary, start=start, end=start + timedelta(hours=dauer),
                 attendees=list(attendees), all_day=all_day)


def _offen(client):
    return client.get('/dashboard').json()['calendar']['nachzubereiten']


def _saetze(client):
    return [p['text'] for p in briefing.erstelle(client.get('/dashboard').json(),
                                                 jetzt=JETZT.astimezone()).to_dict()['punkte']]


def test_same_title_time_notes_keep_distinct_occurrences_and_context(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        first = app.state.workspace.add_project('Erstes Projekt', Provenance(SourceType.USER_STATED))
        second = app.state.workspace.add_project('Zweites Projekt', Provenance(SourceType.USER_STATED))
        a = _vorbei(uid='eins', attendees=('Anna <anna@example.org>',))
        b = _vorbei(uid='zwei', attendees=('Ben <ben@example.org>',))
        app.state.calendar = Kalender([a, b])
        ids = []
        for event, project in ((a, first), (b, second)):
            payload = {'uid': event.uid, 'start': event.start.isoformat(),
                       'text': 'Nichts Neues.', 'project_id': project.id}
            response = client.post('/api/v1/calendar/nachbereitung', json=payload)
            assert response.status_code == 200, response.text
            ids.append(response.json()['id'])
            assert client.post('/api/v1/calendar/nachbereitung', json=payload).json()['id'] == ids[-1]
            addition = client.post('/api/v1/calendar/nachbereitung',
                                   json={**payload, 'text': 'Ein weiterer Beschluss.'})
            assert addition.status_code == 200, addition.text
            assert addition.json()['id'] not in ids
        assert ids[0] != ids[1]
        assert app.state.episodes.get(ids[0]).project_id == first.id
        assert app.state.episodes.get(ids[1]).project_id == second.id
        assert app.state.episodes.get(ids[0]).participants != app.state.episodes.get(ids[1]).participants
    finally:
        client.close()


def test_followup_retry_remains_idempotent_when_display_timezone_changes(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        event = _vorbei(uid='zone')
        app.state.calendar = Kalender([event])
        body = {'uid': event.uid, 'start': event.start.isoformat(), 'text': 'Wir warten auf die Freigabe.'}
        first = client.post('/api/v1/calendar/nachbereitung', json=body).json()
        original = Event.to_dict
        def offset_display(self):
            result = original(self)
            shifted = timezone(timedelta(hours=-7))
            result['start'] = self.start.astimezone(shifted).isoformat()
            result['end'] = self.end.astimezone(shifted).isoformat()
            return result
        monkeypatch.setattr(Event, 'to_dict', offset_display)
        again = client.post('/api/v1/calendar/nachbereitung', json=body)
        assert again.status_code == 200, again.text
        assert again.json()['id'] == first['id']
        assert again.json()['created'] is False
    finally:
        client.close()


def test_same_note_with_new_project_keeps_source_and_explicit_choice(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        first = app.state.workspace.add_project('Erstes Projekt', Provenance(SourceType.USER_STATED))
        second = app.state.workspace.add_project('Zweites Projekt', Provenance(SourceType.USER_STATED))
        event = _vorbei(uid='wahl')
        app.state.calendar = Kalender([event])
        body = {'uid': event.uid, 'start': event.start.isoformat(), 'text': 'Wir warten auf die Freigabe.'}
        saved = client.post('/api/v1/calendar/nachbereitung', json={**body, 'project_id': first.id}).json()
        moved = client.post('/api/v1/calendar/nachbereitung', json={**body, 'project_id': second.id})
        assert moved.status_code == 200, moved.text
        assert moved.json()['id'] == saved['id']
        assert moved.json()['project_id'] == second.id
        assert app.state.episodes.get(saved['id']).project_id == second.id
    finally:
        client.close()


def test_ended_meeting_with_others_asks_what_came_out(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.settings.mail_accounts = [type('Konto', (), {'user': 'ich@example.invalid', 'sender': ''})()]
        app.state.calendar = Kalender([
            _vorbei(),
            _vorbei(uid='zahn', summary='Zahnarzt', attendees=()),
            _vorbei(uid='allein', summary='Fokuszeit', attendees=('Ich <ich@example.invalid>',)),
            _vorbei(uid='alt', summary='Alte Runde', stunden=60),
            _vorbei(uid='tag', summary='Messe', all_day=True),
            _vorbei(uid='laeuft', summary='Läuft noch', stunden=0, dauer=2),
        ])
        dashboard = client.get('/dashboard').json()
        assert [t['uid'] for t in dashboard['calendar']['nachzubereiten']] == ['t1']
        # Vorbei ist nicht mehr „kommend“; was noch läuft, schon.
        assert [t['uid'] for t in dashboard['calendar']['items']] == ['laeuft']
        # Mit bekanntem Gesprächspartner fragt das Briefing nach dem Gespräch.
        [satz] = [s for s in _saetze(client) if 'Gespräch' in s]
        assert satz.startswith('Wie war das Gespräch mit Anna Keller? („Abstimmung Druck“ von ')
        punkt = next(p for p in briefing.erstelle(dashboard, jetzt=JETZT.astimezone()).to_dict()['punkte']
                     if p['quelle'] == 'nachbereitung')
        assert punkt['aktion'] == 'Nachbereiten' and punkt['ref'].startswith('t1|')
    finally:
        client.close()


def test_a_chosen_project_alone_does_not_make_a_meeting_worth_asking(core, tmp_path, monkeypatch):
    # Entscheidung F3: gefragt wird nur nach Terminen mit Externen; ein Projekt allein genügt nicht.
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        mainz = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        app.state.calendar = Kalender([_vorbei(uid='solo', summary='Konzept schreiben', attendees=())])
        client.put('/api/v1/calendar/zuordnung', json={'uid': 'solo', 'project_id': mainz.id})
        assert _offen(client) == []
    finally:
        client.close()


def test_recording_stores_a_source_with_attendees_project_and_end_time(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        mainz = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        start = termin.start.isoformat()
        vorher = app.state.store.alles()
        stand = client.get('/api/v1/calendar/nachbereitung', params={'uid': 't1', 'start': start}).json()
        assert stand['stand'] == 'offen' and stand['teilnehmer'] == ['Anna Keller <anna@agentur.example>']
        antwort = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': start, 'text': '  Anna schickt bis Freitag das Angebot.  ',
            'project_id': mainz.id})
        assert antwort.status_code == 200, antwort.text
        daten = antwort.json()
        assert daten['nachbereitung']['stand'] == 'festgehalten' and daten['einordnung'] == 'aus'
        episode = app.state.episodes.get(daten['id'])
        assert episode.kind is EpisodeKind.MESSAGE
        assert episode.body.startswith('Nachbereitung des Termins „Abstimmung Druck“ vom ')
        assert episode.body.endswith(':\n\nAnna schickt bis Freitag das Angebot.')
        assert episode.title == 'Nachbereitung: Abstimmung Druck'
        assert episode.participants == ['Anna Keller <anna@agentur.example>']
        assert episode.project_id == mainz.id
        assert episode.occurred_at == termin.end
        assert episode.provenance.source_type is SourceType.USER_STATED
        assert episode.provenance.source_ref.startswith('termin:t1|')
        # Die Quelle geht wie jede Mail durch Einordnung und Aufgabenerkennung.
        assert daten['id'] in [e.id for e in app.state.episodes.analysis_batch()]
        # Ein Fakt ist daraus nicht geworden: Der Bestand ist unverändert.
        assert app.state.store.alles() == vorher
        # Die Projektwahl gilt für den Termin, und das Briefing fragt nicht mehr.
        assert app.state.workspace.event_project('t1') == (True, mainz.id)
        assert _offen(client) == []
        # Anna ist jetzt über diese Quelle bekannt.
        assert app.state.episodes.participants_for_address('anna@agentur.example')[0]['anzahl'] == 1
    finally:
        client.close()


def test_transcript_becomes_readable_text_without_timecodes(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        srt = ('1\n00:00:01,000 --> 00:00:04,000\n<v Anna>Ich schicke das Angebot.</v>\n\n'
               '2\n00:00:04,000 --> 00:00:06,000\n<v Anna>Bis Freitag.</v>\n\n'
               '3\n00:00:06,000 --> 00:00:08,000\n<v Ben>Gut.</v>\n')
        daten = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': termin.start.isoformat(), 'text': srt, 'format': 'srt'}).json()
        episode = app.state.episodes.get(daten['id'])
        assert '-->' not in episode.body and '00:00' not in episode.body
        assert episode.provenance.source_type is SourceType.DOCUMENT
        assert client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': termin.start.isoformat(), 'text': 'kein srt', 'format': 'vtt'}).status_code == 422
    finally:
        client.close()


def test_mitschrift_joins_one_speaker_and_keeps_who_spoke():
    vtt = ('WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Anna>Ich schicke es.\n\n'
           '00:00:02.000 --> 00:00:03.000\n<v Anna>Bis Freitag.\n\n'
           '00:00:03.000 --> 00:00:04.000\n<v Ben>Gut.\n')
    assert text_aus_mitschrift(vtt, 'vtt') == 'Anna: Ich schicke es. Bis Freitag.\nBen: Gut.'


def test_a_series_is_followed_up_per_occurrence(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        heute = _vorbei(uid='serie', summary='Jour fixe', stunden=3)
        gestern = _vorbei(uid='serie', summary='Jour fixe', stunden=27)
        app.state.calendar = Kalender([gestern, heute])
        assert len(_offen(client)) == 2
        assert any('Ein weiterer Termin wartet darauf.' in s for s in _saetze(client))
        client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 'serie', 'start': gestern.start.isoformat(), 'text': 'Gestern: Budget steht.'})
        [offen] = _offen(client)
        assert offen['start'] == heute.start.astimezone().isoformat()
    finally:
        client.close()


def test_nothing_to_record_stops_asking_and_can_be_taken_back(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        start = termin.start.isoformat()
        stand = client.put('/api/v1/calendar/nachbereitung/stand',
                           json={'uid': 't1', 'start': start, 'nichts': True}).json()
        assert stand['stand'] == 'nichts' and _offen(client) == []
        assert not any('vorbei' in s for s in _saetze(client))
        stand = client.put('/api/v1/calendar/nachbereitung/stand',
                           json={'uid': 't1', 'start': start, 'nichts': False}).json()
        assert stand['stand'] == 'offen' and len(_offen(client)) == 1
        # Festgehaltenes bleibt festgehalten, auch wenn jemand „doch“ klickt.
        client.post('/api/v1/calendar/nachbereitung', json={'uid': 't1', 'start': start, 'text': 'Angebot kommt.'})
        for nichts in (True, False):
            stand = client.put('/api/v1/calendar/nachbereitung/stand',
                               json={'uid': 't1', 'start': start, 'nichts': nichts}).json()
            assert stand['stand'] == 'festgehalten' and stand['episode_id']
    finally:
        client.close()


def test_refusals_say_why(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        kommt = Event(uid='bald', summary='Bald', start=JETZT + timedelta(hours=2), end=JETZT + timedelta(hours=3),
                      attendees=['anna@agentur.example'])
        app.state.calendar = Kalender([termin, kommt])
        start = termin.start.isoformat()
        assert client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 'bald', 'start': kommt.start.isoformat(), 'text': 'x'}).status_code == 409
        assert client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': start, 'text': 'x', 'project_id': 'p-gibt-es-nicht'}).status_code == 404
        assert client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': start, 'text': '   '}).status_code == 422
        # Anderer Beginn: ein anderer Termin, den es nicht gibt.
        assert client.get('/api/v1/calendar/nachbereitung', params={
            'uid': 't1', 'start': (termin.start + timedelta(days=7)).isoformat()}).status_code == 404
        # Nichts davon hat etwas gespeichert.
        assert app.state.workspace.event_followup(f"t1|{termin.start.astimezone(timezone.utc).isoformat()}") == (False, None)
        assert _offen(client)[0]['uid'] == 't1'
    finally:
        client.close()


def test_classification_is_requested_when_it_runs_automatically(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        angefragt = []
        app.state.scheduler = type('Plan', (), {'request_working_memory': lambda self, eid: angefragt.append(eid)})()
        app.state.agent = type('Agent', (), {'provider': type('P', (), {'is_local': True})()})()
        monkeypatch.setattr(app.state.settings.schedule, 'enabled', True)
        monkeypatch.setattr(app.state.settings.schedule, 'with_model', True)
        daten = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': termin.start.isoformat(), 'text': 'Ben prüft den Vertrag.'}).json()
        assert daten['einordnung'] == 'laeuft' and angefragt == [daten['id']]
    finally:
        client.close()


def test_workspace_never_reopens_a_recorded_followup(tmp_path):
    from icarus_memory.workspace import WorkspaceStore
    store = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    try:
        store.set_event_followup('a|x', 'e-1')
        store.set_event_followup('b|x', None)
        assert store.reopen_event_followup('a|x') is False and store.event_followup('a|x') == (True, 'e-1')
        assert store.reopen_event_followup('b|x') is True and store.event_followup('b|x') == (False, None)
        assert store.event_followups(['a|x', 'b|x', 'c|x']) == {'a|x': 'e-1'}
    finally:
        store.close()


def test_followup_ranks_after_the_next_meeting_and_before_suggestions():
    daten = {
        'calendar': {
            'items': [{'uid': 'bald', 'summary': 'Bald', 'start': (JETZT + timedelta(hours=1)).isoformat()}],
            'nachzubereiten': [{'uid': 't1', 'summary': 'Runde', 'start': (JETZT - timedelta(hours=3)).isoformat(),
                                'end': (JETZT - timedelta(hours=2)).isoformat()}]},
        'task_candidates': {'pending': 1, 'items': [{'id': 'v1', 'statement': 'Angebot schicken'}]},
    }
    vorschlaege = [{'kind': 'confirmation', 'id': 'c1', 'statement': 'Alt'}]
    punkte = briefing.erstelle(daten, jetzt=JETZT.astimezone(), vorschlaege=vorschlaege).to_dict()['punkte']
    assert [p['quelle'] for p in punkte] == ['termin', 'nachbereitung', 'zusage']


def test_morning_card_asks_short_enough_to_be_read(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.calendar = Kalender([_vorbei()])
        morgen = client.get('/api/v1/morning-briefing', params={'timezone': 'UTC'}).json()
        [punkt] = [p for p in morgen['needs_you'] if p['source'] == 'nachbereitung']
        assert punkt['title'] == 'Wie war das Gespräch mit Anna Keller?'
        assert punkt['source_ref'].startswith('t1|')
    finally:
        client.close()


def test_same_words_after_two_meetings_are_two_sources(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        a = _vorbei(uid='a', summary='Runde A', stunden=5)
        b = _vorbei(uid='b', summary='Runde B', stunden=3, attendees=('Ben <ben@example.invalid>',))
        app.state.calendar = Kalender([a, b])
        erste = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 'a', 'start': a.start.isoformat(), 'text': 'Nichts Neues.'}).json()
        zweite = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 'b', 'start': b.start.isoformat(), 'text': 'Nichts Neues.'}).json()
        assert erste['id'] != zweite['id'] and zweite['created'] is True
        assert app.state.episodes.get(zweite['id']).participants == ['Ben <ben@example.invalid>']
        # Beim selben Termin legt erneutes Senden nichts doppelt an und sagt das.
        nochmal = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 'b', 'start': b.start.isoformat(), 'text': 'Nichts Neues.'}).json()
        assert nochmal['id'] == zweite['id'] and nochmal['einordnung'] == 'schon_festgehalten'
    finally:
        client.close()


def test_no_project_while_recording_keeps_the_meetings_assignment(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        mainz = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        client.put('/api/v1/calendar/zuordnung', json={'uid': 't1', 'project_id': mainz.id})
        client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': termin.start.isoformat(), 'text': 'Kurz.', 'project_id': None})
        assert app.state.workspace.event_project('t1') == (True, mainz.id)
    finally:
        client.close()


def test_a_running_meeting_without_end_stays_upcoming(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        ohne = Event(uid='offen', summary='Ohne Ende', start=JETZT - timedelta(minutes=10), end=None,
                     attendees=['anna@agentur.example'])
        app.state.calendar = Kalender([ohne])
        kalender = client.get('/dashboard').json()['calendar']
        assert [t['uid'] for t in kalender['items']] == ['offen'] and kalender['nachzubereiten'] == []
    finally:
        client.close()


def test_notes_are_kept_next_to_a_transcript(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        vtt = 'WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Anna>Ich schicke das Angebot.\n'
        daten = client.post('/api/v1/calendar/nachbereitung', json={
            'uid': 't1', 'start': termin.start.isoformat(), 'text': vtt, 'format': 'vtt',
            'notiz': 'Preis noch offen.'}).json()
        body = app.state.episodes.get(daten['id']).body
        assert 'Preis noch offen.' in body and 'Anna: Ich schicke das Angebot.' in body
    finally:
        client.close()


def test_nothing_from_a_second_window_does_not_overwrite_a_record(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei()
        app.state.calendar = Kalender([termin])
        start = termin.start.isoformat()
        daten = client.post('/api/v1/calendar/nachbereitung', json={'uid': 't1', 'start': start, 'text': 'A.'}).json()
        key = f"t1|{termin.start.astimezone(timezone.utc).isoformat()}"
        assert app.state.workspace.mark_event_nothing(key) is False
        assert app.state.workspace.event_followup(key) == (True, daten['id'])
    finally:
        client.close()


def test_an_occurrence_from_last_year_is_found_in_the_last_week(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        termin = _vorbei(stunden=30)
        app.state.calendar = Kalender([termin])
        # Der Jahresabruf beginnt am 1. Januar; ein Termin vom 31. Dezember
        # fehlt dort. Hier fehlt er, weil der Jahresabruf leer bleibt.
        original = Kalender.events
        def ohne_jahr(self, days=7, at=None):
            # Der Jahresabruf scheitert; die letzte Woche antwortet.
            if days > 31:
                raise RuntimeError('Jahresabruf zu langsam')
            return original(self, days, at)
        monkeypatch.setattr(Kalender, 'events', ohne_jahr)
        stand = client.get('/api/v1/calendar/nachbereitung', params={'uid': 't1', 'start': termin.start.isoformat()})
        assert stand.status_code == 200 and stand.json()['stand'] == 'offen'
        # Wirklich weg: 404, nicht „gerade nicht erreichbar“.
        assert client.get('/api/v1/calendar/nachbereitung', params={
            'uid': 'weg', 'start': termin.start.isoformat()}).status_code == 404
    finally:
        client.close()
