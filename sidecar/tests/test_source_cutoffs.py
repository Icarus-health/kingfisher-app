"""An explicit cutoff in uncertain/history text remains source evidence only."""
from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType, akten as akten_module
from icarus_memory.episodes import EpisodeState
from icarus_memory.fristlage import aus_akte
from icarus_memory.lage import eingabe_aus_akte
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_akten import akten, einordnen, neu_rechnen  # noqa: F401
from tests.test_akten_person_scope import _categorize
from tests.test_akten_routes import api  # noqa: F401
from tests.test_bezuege import stelle, welt  # noqa: F401
from tests.test_context_identity import core  # noqa: F401
from tests.test_date_roles import NOW, PERSON, SENDER, source
from tests.test_mappe import _quelle

OLD = datetime(2022, 2, 10, 9, tzinfo=timezone.utc)


@pytest.mark.parametrize('kind', ['uncertain', 'fact', 'historical', 'status'])
@pytest.mark.parametrize('archived', [False, True])
def test_original_cutoff_is_findable_without_becoming_an_action_deadline(welt, akten, kind, archived):
    text = 'Der Stand ist noch offen. 19.9. ist Redaktionsschluss.'
    episodes = welt[0]
    episode = source(episodes, text, kind=kind, reference=OLD)
    if archived:
        episode.state = EpisodeState.ARCHIVED
        episodes._put(episode)
    original = deepcopy(episodes.get(episode.id).to_dict())
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    evidence = profile['fristen']['quellenangaben']
    assert evidence['gesamt'] == 1
    cutoff = evidence['eintraege'][0]
    assert (cutoff['datum'], cutoff['ausdruck'], cutoff['episode_id']) == ('2022-09-19', '19.9.', episode.id)
    assert cutoff['text'] == text
    assert cutoff['einordnung'] == kind
    assert cutoff['zeitbezug'] == 'vergangen'
    assert cutoff['zustaendigkeit'] == 'ungeklaert'
    assert cutoff['nur_quellenangabe'] is True
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['offen']['gesamt'] == 0
    assert profile['aufgaben']['gesamt'] == 0
    assert profile['quellen']['archiviert'] == int(archived)
    assert episodes.get(episode.id).to_dict() == original


@pytest.mark.parametrize('text', [
    '09. April 2030 ist Redaktionsschluss. Das Datum steht unter Vorbehalt.',
    'Der Redaktionsschluss am 09. April 2030 wurde abgesagt.',
])
def test_tentative_or_cancelled_source_dates_never_enter_own_deadlines_or_model_state(welt, akten, text):
    episode = source(welt[0], text, kind='uncertain')
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    cutoff = profile['fristen']['quellenangaben']['eintraege'][0]
    assert cutoff['text'] == text
    assert cutoff['episode_id'] == episode.id
    assert cutoff['zeitbezug'] == 'kommend'
    assert cutoff['einordnung'] == 'uncertain'
    assert cutoff['nur_quellenangabe'] is True
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['offen']['gesamt'] == 0
    assert profile['stand_der_dinge']['aktuell'] is None
    assert profile['verlauf']['eintraege'][0]['text'] is None
    assert aus_akte(profile, heute=date(2030, 4, 8)) == []
    assert not any(beleg.rolle == 'Frist' for beleg in eingabe_aus_akte(profile).belege)


@pytest.mark.parametrize('kind', ['uncertain', 'fact'])
def test_source_cutoff_keeps_a_cancellation_beyond_the_normal_quote_limit(welt, akten, kind):
    ending = 'Der zuvor genannte Termin wurde abgesagt und ist ausdrücklich nicht verbindlich.'
    text = ('19.9. ist Redaktionsschluss. '
            + 'Die redaktionellen Einzelheiten werden noch abgestimmt. ' * 14 + ending)
    assert text.index(ending) > 598
    source(welt[0], text, kind=kind, reference=OLD)
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    cutoff = profile['fristen']['quellenangaben']['eintraege'][0]
    assert cutoff['text'] == text
    assert cutoff['text'].endswith(ending)
    assert cutoff['gekuerzt'] is False
    assert cutoff['nur_quellenangabe'] is True
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    if kind == 'fact':
        timeline = profile['verlauf']['eintraege'][0]
        assert timeline['gekuerzt'] is True
        assert ending not in timeline['text']


@pytest.mark.parametrize('text', [
    'Die Tagung ist am 09. April 2030.',
    'Die Ausstellung geht bis zum 09. April 2030.',
    'Ich bin bis zum 09. April 2030 im Urlaub.',
    'Bitte kommen Sie am Montag zur Tagung.',
    'Der Redaktionsschluss ist nicht der 09. April 2030.',
])
def test_event_absence_and_negated_dates_do_not_become_source_cutoffs(welt, akten, text):
    source(welt[0], text, kind='uncertain')
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert profile['fristen']['quellenangaben'] == {'eintraege': [], 'gesamt': 0}
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}


@pytest.mark.parametrize('archived', [False, True])
def test_source_withdrawal_removes_cached_cutoff_evidence(welt, akten, archived):
    episodes = welt[0]
    episode = source(episodes, '19.9. ist Redaktionsschluss.', kind='uncertain', reference=OLD)
    if archived:
        episode.state = EpisodeState.ARCHIVED
        episodes._put(episode)
    first = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert first['fristen']['quellenangaben']['gesamt'] == 1
    assert akten.akte(PERSON, jetzt=NOW)['aus_zwischenspeicher']
    episodes.ignore(episode.id)
    assert akten.akte(PERSON, jetzt=NOW) is None


def test_new_classification_discards_stale_uncertain_cutoff_evidence(welt, akten):
    episodes = welt[0]
    first = 'Die Unterlagen liegen vor.'
    text = first + ' 19.9. ist Redaktionsschluss.'
    episode = source(episodes, text, kind='uncertain', reference=OLD)
    old = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert old['fristen']['quellenangaben']['gesamt'] == 1
    with episodes.transaction():
        episodes._conn.execute('DELETE FROM working_memory_sources WHERE episode_id=?', (episode.id,))
    einordnen(episodes, episode, [(first, 'fact')])
    current = akten.akte(PERSON, jetzt=NOW)
    assert not current['aus_zwischenspeicher']
    assert current['eingabestand'] != old['eingabestand']
    assert current['fristen']['quellenangaben']['gesamt'] == 0


@pytest.mark.parametrize('archived', [False, True])
def test_revised_source_removes_cutoff_without_rewriting_the_original(welt, akten, archived):
    episodes = welt[0]
    provenance = Provenance(SourceType.EMAIL, source_ref='test:source-cutoff-revision')
    old_text = '19.9. ist Redaktionsschluss.'
    old, _ = episodes.record(EpisodeKind.MESSAGE, 'Planungsnotiz', old_text, provenance,
                             participants=[SENDER], occurred_at=OLD, source_key='test:source-cutoff-revision')
    episodes.advance_source_head('test:source-cutoff-revision', None, old.id)
    einordnen(episodes, old, [(old_text, 'uncertain')])
    if archived:
        old.state = EpisodeState.ARCHIVED
        episodes._put(old)
    before = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert before['fristen']['quellenangaben']['gesamt'] == 1
    new_text = 'Der Redaktionsschluss steht noch nicht fest.'
    new, _ = episodes.record(EpisodeKind.MESSAGE, 'Planungsnotiz', new_text, provenance,
                             participants=[SENDER], occurred_at=OLD, source_key='test:source-cutoff-revision')
    episodes.advance_source_head('test:source-cutoff-revision', old.id, new.id)
    einordnen(episodes, new, [(new_text, 'uncertain')])
    refs = WorkingMemoryStore(episodes).items_all([old.id, new.id], ['uncertain'], include_archived=True)['refs']
    assert [ref['episode_id'] for ref in refs] == [new.id]
    after = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert not after['aus_zwischenspeicher']
    assert after['eingabestand'] != before['eingabestand']
    assert after['fristen']['quellenangaben']['gesamt'] == 0
    assert episodes.get(old.id).body == old_text


def test_old_cache_is_recomputed_without_storing_source_quotes(welt, akten, monkeypatch):
    episodes = welt[0]
    text = 'Unverwechselbare Zeitschrift. 19.9. ist Redaktionsschluss.'
    source(episodes, text, kind='uncertain', reference=OLD)
    akten.bezuege.aktualisieren()
    sources = akten.bezuege.quellen_von(PERSON)
    with monkeypatch.context() as old:
        old.setattr(akten_module, 'AKTEN_VERSION', 7)
        raw = akten.roh(PERSON, sources)
        raw.pop('quellenfristen', None)
        akten._speichern(PERSON, akten._eingabe(PERSON, sources), raw)
    current = akten.akte(PERSON, jetzt=NOW)
    assert not current['aus_zwischenspeicher']
    assert current['fristen']['quellenangaben']['gesamt'] == 1
    cached = episodes._conn.execute('SELECT daten FROM akten_cache WHERE sache=?', (PERSON,)).fetchone()[0]
    assert 'Unverwechselbare Zeitschrift' not in cached


def test_signature_mention_does_not_receive_another_persons_source_cutoff(welt, akten):
    episodes = welt[0]
    cutoff = '19.9. ist Redaktionsschluss.'
    signature = 'Geschäftsführung: Tim Faber.'
    body = cutoff + '\n\n' + signature
    episode = source(episodes, body, kind=None, reference=OLD)
    einordnen(episodes, episode, [(cutoff, 'uncertain'), (signature, 'fact')])
    _categorize(episodes, episode, [stelle(body, 'Tim Faber')])
    own = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    mention = akten.akte('person:n:tim faber', jetzt=NOW)
    assert own['fristen']['quellenangaben']['gesamt'] == 1
    assert mention['fristen']['quellenangaben']['gesamt'] == 0
    assert mention['offen']['gesamt'] == 0
    assert mention['quellen']['gesamt'] == 1


def test_cutoff_evidence_is_available_through_the_profile_http_api(api):
    app, client = api
    text = 'Der Stand ist noch offen. 19.9. ist Redaktionsschluss.'
    episode = _quelle(app, 'Historischer Redaktionstermin', [(text, 'uncertain')], occurred_at=OLD)
    result = client.get('/api/v1/akten/akte', params={'sache': 'person:a:anna@agentur.example', 'warten': True})
    assert result.status_code == 200
    profile = result.json()
    cutoff = profile['fristen']['quellenangaben']['eintraege'][0]
    assert cutoff['datum'] == '2022-09-19'
    assert cutoff['episode_id'] == episode.id
    assert cutoff['art'] == 'Unklare Einordnung'
    assert cutoff['text'] == text
    assert cutoff['einordnung'] == 'uncertain'
    assert cutoff['zustaendigkeit'] == 'ungeklaert'
    assert profile['offen']['gesamt'] == 0
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}


def test_archived_read_is_explicit_and_does_not_reintroduce_archived_tasks(welt, akten):
    episodes = welt[0]
    request = 'Bitte schicken Sie den Entwurf bis zum 12. Oktober 2022.'
    cutoff = '19.9. ist Redaktionsschluss.'
    body = request + '\n\n' + cutoff
    episode = source(episodes, body, kind=None, reference=OLD)
    einordnen(episodes, episode, [(request, 'request'), (cutoff, 'uncertain')])
    episode.state = EpisodeState.ARCHIVED
    episodes._put(episode)
    memory = WorkingMemoryStore(episodes)
    assert memory.source_state(episode.id) == 'complete'
    assert memory.items_all([episode.id], ['request', 'uncertain'])['refs'] == []
    refs = memory.items_all([episode.id], ['uncertain'], include_archived=True)['refs']
    assert len(refs) == 1
    assert memory.resolve(refs[0]).episode.body == body
    profile = neu_rechnen(akten).akte(PERSON, jetzt=NOW)
    assert profile['fristen']['quellenangaben']['eintraege'][0]['datum'] == '2022-09-19'
    assert profile['offen']['gesamt'] == 0
    assert profile['fristen']['gesamt'] == {'kommend': 0, 'verstrichen': 0, 'ersetzt': 0}
    assert profile['verlauf']['eintraege'][0]['text'] is None
    assert profile['aufgaben']['gesamt'] == 0
    assert aus_akte(profile, heute=date(2022, 9, 18)) == []
    episodes.ignore(episode.id)
    assert memory.items_all([episode.id], ['uncertain'], include_archived=True)['refs'] == []


def test_empty_archive_cache_from_version_eight_is_recomputed(welt, akten, monkeypatch):
    episodes = welt[0]
    episode = source(episodes, '19.9. ist Redaktionsschluss.', kind='uncertain', reference=OLD)
    episode.state = EpisodeState.ARCHIVED
    episodes._put(episode)
    akten.bezuege.aktualisieren()
    sources = akten.bezuege.quellen_von(PERSON)
    with monkeypatch.context() as old:
        old.setattr(akten_module, 'AKTEN_VERSION', 8)
        old.setattr(akten_module, '_quellenfristen', lambda _: [])
        raw = akten.roh(PERSON, sources)
        assert raw['quellenfristen'] == []
        akten._speichern(PERSON, akten._eingabe(PERSON, sources), raw)
    profile = akten.akte(PERSON, jetzt=NOW)
    assert not profile['aus_zwischenspeicher']
    assert profile['fristen']['quellenangaben']['eintraege'][0]['datum'] == '2022-09-19'
