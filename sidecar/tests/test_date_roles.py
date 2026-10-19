"""A paragraph's request kind must not turn every source date into a deadline."""
from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory import akten as akten_module
from icarus_memory.fristen import fristen_in
from tests.test_akten import akten, einordnen, neu_rechnen  # noqa: F401
from tests.test_bezuege import welt  # noqa: F401

SENDER = 'Nora Becker <nora@tagung.example>'
PERSON = 'person:a:nora@tagung.example'
REFERENCE = datetime(2030, 3, 1, 9, tzinfo=timezone.utc)
NOW = datetime(2030, 3, 2, 9, tzinfo=timezone.utc)


def source(episodes, text, *, kind='request', title='Tagungsanfrage', reference=REFERENCE):
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, title, text,
        Provenance(SourceType.EMAIL, source_ref=f'test:date-role:{title}'),
        participants=[SENDER], occurred_at=reference)
    if kind:
        einordnen(episodes, episode, [(text, kind)])
    return episode


@pytest.mark.parametrize('text,source_dates', [
    ('Die Frühjahrstagung findet am 16. April statt. Über Ihre Anmeldung bis zum 07. April würde ich mich freuen.',
     [date(2030, 4, 16), date(2030, 4, 7)]),
    ('Bitte melden Sie sich bis zum 07. April zur Frühjahrstagung am 16. April an.',
     [date(2030, 4, 7), date(2030, 4, 16)]),
    ('Für die Frühjahrstagung am 16. April erbitten wir Ihre Anmeldung bis zum 07. April.',
     [date(2030, 4, 16), date(2030, 4, 7)]),
    ('Für die Frühjahrstagung am 16. April ist der Anmeldeschluss der 07. April.',
     [date(2030, 4, 16), date(2030, 4, 7)]),
    ('Anmeldeschluss ist der 07. April; die Frühjahrstagung ist am 16. April.',
     [date(2030, 4, 7), date(2030, 4, 16)]),
])
def test_person_profile_only_promotes_the_deadline_bound_date(welt, akten, text, source_dates):
    episodes = welt[0]
    episode = source(episodes, text)
    original = deepcopy(episodes.get(episode.id).to_dict())
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)

    assert [item['datum'] for item in profile['fristen']['kommend']] == ['2030-04-07']
    assert profile['fristen']['kommend'][0]['ausdruck'] in ('07. April', '07. April.')
    assert profile['fristen']['gesamt'] == {'kommend': 1, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['termine']['gesamt'] == {'kommend': 0, 'vergangen': 0}
    assert [item['text'] for item in profile['offen']['eintraege']] == [text]
    assert profile['offen']['eintraege'][0]['art'] == 'Bitte'
    assert profile['offen']['eintraege'][0]['vermutlich']
    # Event date remains available in the original and broad date API.
    assert [item.datum for item in fristen_in(text, REFERENCE).fristen] == source_dates
    assert profile['verlauf']['eintraege'][0]['text'] == text
    assert episodes.get(episode.id).to_dict() == original


@pytest.mark.parametrize('text', [
    'Bitte prüfen Sie das Programm zur Tagung am 16. April 2030.',
    'Bitte prüfen Sie die Daten 07. April 2030 und 16. April 2030.',
    'Die Tagung läuft vom 07. April 2030 bis zum 16. April 2030; bitte prüfen Sie das Programm.',
    'Die Abschlussveranstaltung ist am 16. April 2030; bitte prüfen Sie das Programm.',
    'Der Tagungsabschluss ist am 16. April 2030; bitte prüfen Sie das Programm.',
    'Der Vertragsabschluss ist am 16. April 2030; bitte prüfen Sie die Angaben.',
    'Das Abgabeformular ist am 16. April 2030 verfügbar; bitte prüfen Sie die Angaben.',
])
def test_unbound_event_or_ambiguous_dates_are_not_profile_deadlines(welt, akten, text):
    source(welt[0], text)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['offen']['eintraege'][0]['text'] == text
    assert fristen_in(text, REFERENCE).fristen


@pytest.mark.parametrize('text,expected_deadlines,source_dates', [
    ('Der Workshop dauert bis zum 16. April. Bitte prüfen Sie das Programm.',
     [], [date(2030, 4, 16)]),
    ('Der Workshop dauert bis Montag. Bitte prüfen Sie das Programm.',
     [], [date(2030, 3, 4)]),
    ('Der Workshop läuft bis zum 16. April. Bitte prüfen Sie das Programm.',
     [], [date(2030, 4, 16)]),
    ('Die Tagung läuft vom 7. bis zum 16. April 2030; bitte prüfen Sie das Programm.',
     [], [date(2030, 4, 16)]),
    ('Die Tagung läuft vom 7. bis 16. April 2030; bitte prüfen Sie das Programm.',
     [], [date(2030, 4, 16)]),
    ('Die Ausstellung geht bis zum 16. April 2030; bitte prüfen Sie das Programm.',
     [], [date(2030, 4, 16)]),
    ('Die Tagung findet bis zum 16. April 2030 statt; bitte prüfen Sie das Programm.',
     [], [date(2030, 4, 16)]),
    ('Die Anmeldefrist ist vorbei und der Workshop dauert bis zum 16. April 2030.',
     [], [date(2030, 4, 16)]),
    ('Ich bin bis zum 16. April im Urlaub. Bitte stimmen Sie sich mit Nora ab.',
     [], [date(2030, 4, 16)]),
    ('Ich bin bis Montag abwesend. Bitte stimmen Sie sich mit Nora ab.',
     [], [date(2030, 3, 4)]),
    ('Bitte melden Sie sich bis zum 07. April an; der Workshop dauert bis zum 16. April.',
     ['2030-04-07'], [date(2030, 4, 7), date(2030, 4, 16)]),
    ('Der Workshop dauert bis zum 16. April. Bitte melden Sie sich bis zum 07. April an.',
     ['2030-04-07'], [date(2030, 4, 16), date(2030, 4, 7)]),
    ('Ich bin bis zum 16. April im Urlaub, bitte antworten Sie bis zum 07. April.',
     ['2030-04-07'], [date(2030, 4, 16), date(2030, 4, 7)]),
    ('Bitte melden Sie sich bis zum 07. April an; die Ausstellung geht bis zum 16. April.',
     ['2030-04-07'], [date(2030, 4, 7), date(2030, 4, 16)]),
])
def test_explicit_duration_endpoints_do_not_become_deadlines(welt, akten, text, expected_deadlines, source_dates):
    episodes = welt[0]
    episode = source(episodes, text)
    original = deepcopy(episodes.get(episode.id).to_dict())
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert [item['datum'] for item in profile['fristen']['kommend']] == expected_deadlines
    assert profile['fristen']['verstrichen'] == []
    assert profile['fristen']['ersetzt'] == []
    assert profile['verlauf']['eintraege'][0]['text'] == text
    assert [item.datum for item in fristen_in(text, REFERENCE).fristen] == source_dates
    assert episodes.get(episode.id).to_dict() == original


@pytest.mark.parametrize('text', [
    'Die Tagung ist Ende Oktober. Bitte prüfen Sie das Programm.',
    'Die Tagung ist nächste Woche. Bitte prüfen Sie das Programm.',
    'Bitte Tagung nächste Woche. Das Programm muss geprüft werden.',
    'Ich bin bis Ende Oktober im Urlaub. Bitte stimmen Sie sich mit Nora ab.',
    'Die Tagung läuft vom 28. Februar bis zum 16. April 2030; bitte prüfen Sie das Programm.',
])
def test_unresolved_event_dates_and_ranges_are_not_deadlines(welt, akten, text):
    source(welt[0], text)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['fristen']['ohne_datum']['gesamt'] == 0
    broad = fristen_in(text, REFERENCE)
    assert broad.ohne_datum
    assert profile['verlauf']['eintraege'][0]['text'] == text


@pytest.mark.parametrize('text', [
    'Bitte kommen Sie am Montag zur Tagung.',
    'Bitte nehmen Sie am Montag teil.',
    'Bitte erscheinen Sie am Montag zur Tagung.',
    'Bitte kommen Sie nächste Woche zur Tagung.',
    'Bitte nehmen Sie nächste Woche teil.',
    'Bitte erscheinen Sie nächste Woche zur Tagung.',
])
def test_invitations_with_a_time_are_not_cutoff_instructions(welt, akten, text):
    episodes = welt[0]
    episode = source(episodes, text)
    original = deepcopy(episodes.get(episode.id).to_dict())
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['fristen']['ohne_datum']['gesamt'] == 0
    broad = fristen_in(text, REFERENCE)
    assert broad.fristen or broad.ohne_datum
    assert profile['verlauf']['eintraege'][0]['text'] == text
    assert episodes.get(episode.id).to_dict() == original


@pytest.mark.parametrize('text', [
    'Die Tagung ist Ende Oktober. Bitte Manuskriptabgabe Ende Oktober.',
    'Die Tagung ist Ende Oktober und die Manuskriptabgabe ist bis Ende Oktober.',
])
def test_repeated_vague_date_keeps_the_deadline_occurrence_not_the_event_occurrence(welt, akten, text):
    source(welt[0], text)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert profile['fristen']['ohne_datum']['gesamt'] == 1
    raw = akten.roh(PERSON, akten.bezuege.quellen_von(PERSON))
    assert raw['ohne_datum'][0]['start'] == text.rindex('Ende Oktober')
    assert [item['ausdruck'] for item in profile['fristen']['ohne_datum']['eintraege']] == ['Ende Oktober.']
    assert len(fristen_in(text, REFERENCE).ohne_datum) == 2


def test_conditional_participation_does_not_create_a_confirmation_or_calendar_event(welt, akten):
    text = ('Wenn Sie an der Tagung am 16. April teilnehmen möchten, '
            'melden Sie sich bitte bis zum 07. April an.')
    source(welt[0], text, kind='conditional')
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert [item['datum'] for item in profile['fristen']['kommend']] == ['2030-04-07']
    assert profile['offen']['gesamt'] == 0
    assert profile['termine']['gesamt'] == {'kommend': 0, 'vergangen': 0}
    assert profile['verlauf']['eintraege'][0]['text'] == text
    assert profile['verlauf']['eintraege'][0]['art'] == 'Bedingte Aussage'


def test_imprecise_deadline_stays_verbatim_while_event_date_is_not_a_deadline(welt, akten):
    text = 'Die Tagung ist am 16. November 2030. Bitte melden Sie sich bis Ende Oktober.'
    source(welt[0], text)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert [item['ausdruck'] for item in profile['fristen']['ohne_datum']['eintraege']] == ['Ende Oktober.']


@pytest.mark.parametrize('kind,text,expected', [
    ('request', 'Bitte antworten Sie spätestens am 09. April 2030.', '2030-04-09'),
    ('commitment', 'Ich sende Ihnen die Unterlagen bis zum 09. April 2030.', '2030-04-09'),
    ('request', 'Der 09. April 2030 ist Anmeldeschluss.', '2030-04-09'),
    ('request', 'Die Unterlagen sind am 09. April 2030 fällig.', '2030-04-09'),
    ('change', 'Die Einreichfrist wurde auf den 09. April 2030 verschoben.', '2030-04-09'),
    ('request', 'Bitte antworten Sie bis Montag.', '2030-03-04'),
    ('request', 'Die Rückmeldefrist endet in zwei Wochen.', '2030-03-15'),
    ('request', 'Die Einreichfrist läuft bis zum 09. April 2030.', '2030-04-09'),
    ('request', 'Redaktionsschluss ist am 09. April 2030.', '2030-04-09'),
    ('request', 'Einsendeschluss ist am 09. April 2030.', '2030-04-09'),
    ('request', 'Bewerbungsschluss ist am 09. April 2030.', '2030-04-09'),
    ('request', 'Die Manuskriptabgabe ist am 09. April 2030.', '2030-04-09'),
    ('request', 'Der Abgabetermin ist am 09. April 2030.', '2030-04-09'),
    ('request', 'Das Fristende ist am 09. April 2030.', '2030-04-09'),
    ('request', 'Die Fälligkeit ist am 09. April 2030.', '2030-04-09'),
    ('request', 'Bitte antworten Sie am Montag.', '2030-03-04'),
    ('request', 'Bitte senden Sie am Montag die Unterlagen.', '2030-03-04'),
])
def test_explicit_request_commitment_and_changed_deadlines_remain_available(welt, akten, kind, text, expected):
    source(welt[0], text, kind=kind)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert [item['datum'] for item in profile['fristen']['kommend']] == [expected]
    assert profile['fristen']['kommend'][0]['text'] == text


def test_historical_quoted_deadlines_do_not_become_current_requests(welt, akten):
    current = 'Die Tagung ist am 16. April. Bitte melden Sie sich bis zum 07. April an.'
    quote = '> Bitte melden Sie sich bis zum 03. April 2029 an.'
    text = current + '\n\n' + quote
    episodes = welt[0]
    episode = source(episodes, text, kind=None)
    einordnen(episodes, episode, [(current, 'request'), (quote, 'historical')])
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert [item['datum'] for item in profile['fristen']['kommend']] == ['2030-04-07']
    assert profile['fristen']['verstrichen'] == []
    assert profile['offen']['gesamt'] == 1
    assert episodes.get(episode.id).body == text


def test_profile_recomputes_a_legacy_cache_that_promoted_the_event_date(welt, akten, monkeypatch):
    text = 'Die Tagung ist am 16. April. Bitte melden Sie sich bis zum 07. April an.'
    source(welt[0], text)
    akten.bezuege.aktualisieren()
    sources = akten.bezuege.quellen_von(PERSON)
    with monkeypatch.context() as old:
        old.setattr(akten_module, 'AKTEN_VERSION', 6)
        raw = akten.roh(PERSON, sources)
        ref = raw['offen'][0]['ref']
        raw['fristen'].append({'ref': ref, 'start': 18, 'ende': 27,
                               'datum': '2030-04-16', 'art': 'datum', 'ersetzt_durch': None})
        akten._speichern(PERSON, akten._eingabe(PERSON, sources), raw)
    profile = akten.akte(PERSON, jetzt=NOW)
    assert [item['datum'] for item in profile['fristen']['kommend']] == ['2030-04-07']
    assert not profile['aus_zwischenspeicher']


@pytest.mark.parametrize('old_text,change,expected,old_replaced', [
    ('Bitte schicken Sie mir den Belegungsplan bis zum 07. April 2030.',
     'Der Belegungsplan verschiebt sich deshalb auf den 09. April 2030; Nora bekommt ihn dann direkt von uns.',
     ['2030-04-09'], True),
    ('Bitte senden Sie den Belegungsplan für die Frühjahrstagung bis zum 07. April 2030.',
     'Die Frühjahrstagung verschiebt sich auf den 09. April 2030.',
     ['2030-04-07'], False),
    ('Für die Frühjahrstagung am 16. April 2030 erbitten wir die Anmeldung bis zum 07. April 2030.',
     'Die Frühjahrstagung verschiebt sich auf den 18. April 2030.',
     ['2030-04-07'], False),
    (None, 'Die Frühjahrstagung verschiebt sich auf den 09. April 2030.', [], False),
])
def test_explicit_shift_inherits_only_a_previously_bound_task_deadline(
        welt, akten, old_text, change, expected, old_replaced):
    episodes = welt[0]
    if old_text:
        source(episodes, old_text, title='Vorherige Frist')
    source(episodes, change, kind='change', title='Verschiebung', reference=NOW)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert [item['datum'] for item in profile['fristen']['kommend']] == expected
    assert [item['datum'] for item in profile['fristen']['ersetzt']] == (['2030-04-07'] if old_replaced else [])
    assert [item.datum for item in fristen_in(change, NOW).fristen]
