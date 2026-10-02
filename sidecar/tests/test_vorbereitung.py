"""Etappe 2: Termine von selbst vorbereiten, ohne Modell und ohne Namensraten."""
from datetime import datetime, timedelta, timezone

from icarus_memory import briefing
from icarus_memory.connectors.calendar import Event
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.vorbereitung import projekt_vorschlag
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api

JETZT = datetime.now(timezone.utc)


class Kalender:
    def __init__(self, events):
        self._events = events
        self.last_errors = {}

    def events(self, days=7, at=None):
        return list(self._events)


def _mail(app, titel, absender, project=None, tage=1):
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, f'Text zu {titel}.',
        Provenance(SourceType.EMAIL, source_ref=f'work:<{titel}-{absender}@example.invalid>'),
        participants=[absender], project_id=project, occurred_at=JETZT - timedelta(days=tage))
    return episode


def _tagesbeginn(stunden=3):
    """Mitternacht am Tag des Termins: Das Briefing nennt nur Termine von heute.

    Mit der echten Uhrzeit fiele ein Termin in drei Stunden ab 21 Uhr auf
    morgen, und der Test hinge von der Tageszeit ab.
    """
    return (JETZT + timedelta(hours=stunden)).astimezone().replace(hour=0, minute=0, second=0, microsecond=0)


def _termin(uid='t1', summary='Abstimmung', attendees=(), stunden=3, location=''):
    return Event(uid=uid, summary=summary, start=JETZT + timedelta(hours=stunden),
                 end=JETZT + timedelta(hours=stunden + 1), location=location, attendees=list(attendees))


def test_attendees_are_matched_by_address_and_self_is_left_out(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        for n in range(3):
            _mail(app, f'Druck {n}', 'Anna Keller <anna_keller@agentur.example>', tage=n + 1)
        _mail(app, 'Alt', 'A. Keller <ANNA_KELLER@agentur.example>', tage=40)
        app.state.settings.mail_accounts = [type('Konto', (), {'user': 'ich@example.invalid', 'sender': ''})()]
        app.state.calendar = Kalender([_termin(attendees=[
            'anna_keller@agentur.example', 'Ich <ich@example.invalid>', 'Anna Keller', 'Neu <neu@example.invalid>'])])
        data = client.get('/api/v1/calendar/zuordnung', params={'uid': 't1'}).json()
        namen = [(t['name'], t['person'], t['kontakte']) for t in data['teilnehmer']]
        # Genau über die Adresse erkannt, auch mit Unterstrich und anderer
        # Schreibweise; ohne Adresse und ganz neu bleibt unbekannt, und das
        # eigene Konto fällt weg.
        assert namen == [('Anna Keller', 'Anna Keller <anna_keller@agentur.example>', 4),
                         ('Anna Keller', None, 0), ('Neu', None, 0)]
    finally:
        client.close()


def _p(name, **quellen):
    return {'name': name, 'quellen': quellen}


def test_project_is_suggested_from_title_or_from_the_attendees_mail():
    projekte = [('p1', 'Mainz'), ('p2', 'Mainz Messe'), ('p3', 'Orion'), ('p4', 'IT')]
    assert projekt_vorschlag('Abstimmung Mainz Messe', [], projekte)['id'] == 'p2'
    assert projekt_vorschlag('Orion Review', [], projekte)['grund'] == 'Der Termin nennt „Orion“.'
    # Zwei verschiedene Projekte im Titel: offen, also kein Vorschlag.
    assert projekt_vorschlag('Mainz, dann Orion', [], projekte) is None
    # Kurze Namen nur in genau dieser Schreibweise: „it“ ist kein Projekt.
    assert projekt_vorschlag('Wie geht it weiter', [], projekte) is None
    assert projekt_vorschlag('IT Sprechstunde', [], projekte)['id'] == 'p4'
    person = _p('Anna Keller', e1='p1', e2='p1', e3='p1', e4='p1', e5='p1', e6='p3', e7='p3')
    vorschlag = projekt_vorschlag('Abstimmung', [person], projekte)
    assert vorschlag['id'] == 'p1'
    assert vorschlag['grund'] == '5 von 7 zugeordneten Quellen mit Anna Keller gehören zu „Mainz“.'
    # Nicht klar genug: kein Vorschlag statt eines geratenen.
    assert projekt_vorschlag('Abstimmung', [_p('A', e1='p1', e2='p1', e3='p3', e4='p3')], projekte) is None
    assert projekt_vorschlag('Abstimmung', [_p('A', e1='p1')], projekte) is None
    assert projekt_vorschlag('Abstimmung', [], projekte) is None


def test_shared_messages_count_once_and_closed_projects_count_in_the_denominator():
    projekte = [('p1', 'Mainz'), ('p2', 'Berlin')]
    geteilt = {'e1': 'p1', 'e2': 'p1'}
    personen = [_p('A', **geteilt), _p('B', **geteilt), _p('C', **geteilt), _p('D', e3='p2', e4='p2', e5='p2')]
    vorschlag = projekt_vorschlag('Abstimmung', personen, projekte)
    assert vorschlag['id'] == 'p2' and vorschlag['grund'].startswith('3 von 5 ')
    # 50 Quellen zu einem geschlossenen Projekt: Zwei zu Orion sind keine Mehrheit.
    viele = {f'x{n}': 'p-alt' for n in range(50)}
    assert projekt_vorschlag('Abstimmung', [_p('A', **viele, y1='p1', y2='p1')], projekte) is None


def test_title_does_not_win_against_clear_mail_evidence():
    projekte = [('p1', 'Mainz'), ('p2', 'Berlin')]
    person = _p('A', e1='p2', e2='p2', e3='p2')
    assert projekt_vorschlag('Termin in Mainz', [person], projekte) is None


def test_correction_holds_and_no_project_beats_a_suggestion(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        mainz = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        orion = app.state.workspace.add_project('Orion', Provenance(SourceType.USER_STATED))
        app.state.calendar = Kalender([_termin(summary='Abstimmung Mainz')])
        data = client.get('/api/v1/calendar/zuordnung', params={'uid': 't1'}).json()
        assert data['projekt'] == {'id': mainz.id, 'name': 'Mainz', 'grund': 'Der Termin nennt „Mainz“.',
                                   'herkunft': 'vorschlag'}
        data = client.put('/api/v1/calendar/zuordnung', json={'uid': 't1', 'project_id': orion.id}).json()
        assert data['projekt'] == {'id': orion.id, 'name': 'Orion', 'herkunft': 'gewaehlt'}
        data = client.put('/api/v1/calendar/zuordnung', json={'uid': 't1', 'project_id': None}).json()
        assert data['projekt'] is None and data['festgelegt'] is True and data['vorschlag']['id'] == mainz.id
        assert client.get('/api/v1/calendar/zuordnung', params={'uid': 't1'}).json()['projekt'] is None
        assert client.put('/api/v1/calendar/zuordnung', json={'uid': 't1', 'project_id': 'p-gibt-es-nicht'}
                          ).status_code == 404
        assert client.get('/api/v1/calendar/zuordnung', params={'uid': 'unbekannt'}).status_code == 404
    finally:
        client.close()


def test_briefing_names_who_comes_and_that_it_is_prepared(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        mainz = app.state.workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
        for n in range(3):
            _mail(app, f'Druck {n}', 'Anna Keller <anna@agentur.example>', mainz.id, n + 1)
        app.state.calendar = Kalender([_termin(attendees=['Anna Keller <anna@agentur.example>'])])
        dashboard = client.get('/dashboard').json()
        [termin] = dashboard['calendar']['items']
        assert termin['vorbereitung'] == {'bekannte': ['Anna Keller'], 'teilnehmer': 1, 'projekt': 'Mainz',
                                          'vorschlag': True}
        texte = [p['text'] for p in briefing.erstelle(dashboard, jetzt=_tagesbeginn()).to_dict()['punkte']]
        # Ein Vorschlag ist eine Vermutung und heißt auch so.
        assert any('mit Anna Keller. Vorbereitet, vermutlich Projekt Mainz.' in text for text in texte)
        client.put('/api/v1/calendar/zuordnung', json={'uid': 't1', 'project_id': mainz.id})
        texte = [p['text'] for p in briefing.erstelle(client.get('/dashboard').json(),
                                                      jetzt=_tagesbeginn()).to_dict()['punkte']]
        assert any('mit Anna Keller. Vorbereitet, Projekt Mainz.' in text for text in texte)
    finally:
        client.close()


def test_unknown_attendees_are_not_called_prepared():
    daten = {'calendar': {'items': [{'uid': 'x', 'summary': 'Zahnarzt',
                                     'start': (JETZT + timedelta(hours=2)).isoformat(),
                                     'vorbereitung': {'bekannte': [], 'projekt': None}}]}}
    text = str(briefing.erstelle(daten, jetzt=_tagesbeginn(2)).to_dict())
    assert '„Zahnarzt“' in text and 'Vorbereitet' not in text


def test_similar_address_is_not_the_same_person(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        _mail(app, 'Hanna', 'Hanna Berg <hanna@agentur.example>')
        _mail(app, 'Anna', 'Anna Keller <anna@agentur.example>')
        treffer = app.state.episodes.participants_for_address('anna@agentur.example')
        assert [(t['name'], t['anzahl']) for t in treffer] == [('Anna Keller <anna@agentur.example>', 1)]
    finally:
        client.close()


def test_briefing_converts_utc_appointments_to_local_time():
    from datetime import timezone as tz
    berlin = tz(timedelta(hours=2))
    jetzt = datetime(2026, 9, 28, 9, 30, tzinfo=berlin)
    daten = {'calendar': {'items': [
        {'uid': 'a', 'summary': 'Früh', 'start': '2026-09-28T09:00:00+00:00'},
        {'uid': 'b', 'summary': 'Spät', 'start': '2026-09-28T12:00:00+00:00'}]}}
    text = str(briefing.erstelle(daten, jetzt=jetzt).to_dict())
    # 09:00Z ist 11:00 in Berlin und liegt noch vor uns; es darf nicht fehlen.
    assert 'Um 11:00 Uhr ist „Früh“' in text


def test_briefing_counts_the_other_attendees():
    daten = {'calendar': {'items': [{'uid': 'x', 'summary': 'Runde', 'start': (JETZT + timedelta(hours=2)).isoformat(),
                                     'vorbereitung': {'bekannte': ['Anna Keller'], 'teilnehmer': 10,
                                                      'projekt': None, 'vorschlag': False}}]}}
    text = str(briefing.erstelle(daten, jetzt=_tagesbeginn(2)).to_dict())
    assert 'mit Anna Keller und 9 weiteren.' in text and 'Vorbereitet' not in text


def test_last_name_first_and_mailto_formats_are_the_same_person(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        _mail(app, 'Druck', 'Keller, Anna <anna@agentur.example>')
        app.state.calendar = Kalender([_termin(attendees=['Keller, Anna <anna@agentur.example>',
                                                          'mailto:ANNA@agentur.example'])])
        [person] = client.get('/api/v1/calendar/zuordnung', params={'uid': 't1'}).json()['teilnehmer']
        assert person['person'] == 'Keller, Anna <anna@agentur.example>' and person['kontakte'] == 1
        assert person['name'] == 'Keller, Anna'
    finally:
        client.close()
