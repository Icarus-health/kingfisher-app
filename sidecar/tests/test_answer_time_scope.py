"""Ein Zeitraum in der Frage ordnet um, schließt aber nichts aus."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from icarus_memory import working_memory_answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
from icarus_memory.frage import Anfrage
from icarus_memory.time_scope import mentioned_period
from icarus_memory.working_memory_answers import _fresh, prepare, render
from icarus_memory.working_memory_store import WorkingMemoryStore

NOW = datetime(2026, 9, 26, 10, tzinfo=timezone.utc)


class Selector:
    is_local = True

    def __init__(self):
        self.rows = None

    def complete_json(self, messages, **kwargs):
        self.rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in self.rows]}))


@pytest.mark.parametrize('question,expected', [
    ('Was hat Anna letzte Woche geschrieben?', ('2026-09-14', '2026-09-21', 'der letzten Woche')),
    ('Was kam gestern?', ('2026-09-25', '2026-09-26', 'von gestern')),
    ('Neues in den letzten 3 Tagen?', ('2026-09-24', '2026-09-27', 'der letzten 3 Tage')),
    ('Was ist seit zwei Wochen passiert?', ('2026-09-13', '2026-09-27', 'der letzten 14 Tage')),
    ('diesen Monat', ('2026-09-01', '2026-10-01', 'dieses Monats')),
    ('Was ist nächste Woche?', None),
    ('Wann ist die Abnahme im Oktober?', None),
    ('Was war vorletzte Woche?', None),
    ('Welche Orion-Mail meine ich, nicht heute?', None),
    ('Welche Orion-Mail meine ich, nicht von heute?', None),
    ('Was kam nicht heute, sondern gestern zu Orion?', ('2026-09-25', '2026-09-26', 'von gestern')),
    ('Was kam nicht gestern, sondern heute zu Orion?', ('2026-09-26', '2026-09-27', 'von heute')),
    ('Was kam nicht nur heute zu Orion?', None),
    ('Was kam nicht nur heute, sondern auch gestern zu Orion?', None),
    ('Was kam nicht in der letzten Woche zu Orion?', None),
    ('Was kam heute zur noch nicht bezahlten Orion-Rechnung?', ('2026-09-26', '2026-09-27', 'von heute')),
])
def test_only_unambiguous_past_periods_are_recognized(question, expected):
    found = mentioned_period(question, NOW)
    assert (None if found is None else (str(found[0].date()), str(found[1].date()), found[2])) == expected


@pytest.fixture
def mailbox(tmp_path, monkeypatch):
    episodes = EpisodeStore(tmp_path / 'e.sqlite3')
    claims = ClaimStore(tmp_path / 'k.sqlite3')
    ids = {}
    # Mehr neuere Mails (diese Woche) zum selben Stichwort, als es Kandidaten gibt, und eine von letzter Woche:
    # Ohne Zeitraum fiele die neue an der Grenze der Kandidaten (`MAX_REFS`) heraus.
    for n in range(working_memory_answers.MAX_REFS + 4):
        body = f'Rechnung Orion Teil {n}: bitte prüfen, Rechnung Orion ergänzen.'
        ids[f'alt{n}'] = _mail(episodes, body, NOW - timedelta(hours=1 + n))
    ids['neu'] = _mail(episodes, 'Die Orion-Rechnung ist bezahlt.', NOW - timedelta(days=8))
    monkeypatch.setattr('icarus_memory.time_scope.datetime',
                        type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: NOW)}))
    yield episodes, claims, ids
    claims.close()
    episodes.close()


def _mail(episodes, body, when):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, 'Orion', body, Provenance(SourceType.EMAIL),
                                 participants=['Anna <anna@example.test>'], occurred_at=when)
    assert WorkingMemoryStore(episodes).commit(
        episodes.support_snapshot(episode.id), [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='t')
    return episode.id


def test_period_brings_matching_sources_first_without_excluding(mailbox):
    episodes, claims, ids = mailbox
    plain = prepare('Was ist mit der Rechnung Orion?', episodes, claims, Selector())
    assert ids['neu'] not in {ref['episode_id'] for ref in plain['basis']}

    selector = Selector()
    answer = prepare('Was kam letzte Woche zur Rechnung Orion?', episodes, claims, selector)
    basis = [ref['episode_id'] for ref in answer['basis']]
    assert basis[0] == ids['neu'] and len(basis) == working_memory_answers.MAX_REFS
    assert answer['time_label'] == 'der letzten Woche'
    text, _, _ = render(answer, episodes, claims)
    assert 'Zuerst berücksichtigt: Quellen der letzten Woche.' in text


def test_stored_period_keeps_answer_fresh_next_day(mailbox, monkeypatch):
    episodes, claims, _ = mailbox
    answer = prepare('Was kam letzte Woche zur Rechnung Orion?', episodes, claims, Selector())
    later = NOW + timedelta(days=9)
    monkeypatch.setattr('icarus_memory.time_scope.datetime',
                        type('Later', (datetime,), {'now': classmethod(lambda cls, tz=None: later)}))
    assert _fresh(answer, episodes, claims)
    broken = dict(answer, time_scope=['gestern', 'heute'])
    assert not _fresh(broken, episodes, claims)


@pytest.fixture
def mixed_source_dates(tmp_path):
    episodes = EpisodeStore(tmp_path / 'period.sqlite3')
    try:
        undated, _ = episodes.record(EpisodeKind.DOCUMENT, 'Undated import', 'Orion undated.',
                                    Provenance(SourceType.DOCUMENT), at=NOW - timedelta(days=8))
        dated = _mail(episodes, 'Orion dated.', NOW - timedelta(days=8))
        period = (datetime(2026, 9, 14, tzinfo=timezone.utc), datetime(2026, 9, 21, tzinfo=timezone.utc))
        yield episodes, undated.id, dated, period
    finally:
        episodes.close()


def test_period_prioritizes_dated_source_over_undated_import(mixed_source_dates):
    episodes, undated, dated, period = mixed_source_dates
    refs = [{'episode_id': undated}, {'episode_id': dated}]
    assert [ref['episode_id'] for ref in working_memory_answers._period_first(refs, episodes, period)] == [dated, undated]


def test_person_period_does_not_use_import_date_as_source_date(mixed_source_dates):
    episodes, undated, dated, period = mixed_source_dates
    assert working_memory_answers._within([undated, dated], episodes, period) == [dated]


def test_unknown_source_time_does_not_render_import_as_an_outside_source_date(tmp_path, monkeypatch):
    episodes, claims = EpisodeStore(tmp_path / 'e.sqlite3'), ClaimStore(tmp_path / 'k.sqlite3')
    try:
        episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Undated original', 'Orion: Die Freigabe ist offen.',
                                     Provenance(SourceType.DOCUMENT), at=NOW)
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),
            [{'start': 0, 'end': len(episode.body), 'kind': 'fact'}], model='t')
        monkeypatch.setattr('icarus_memory.time_scope.datetime',
                            type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: NOW)}))
        selector = Selector()
        answer = prepare('Was kam letzte Woche zur Freigabe Orion?', episodes, claims, selector)
        text, _, _ = render(answer, episodes, claims)
        assert episode.body in text
        assert 'Quellenzeit: unbekannt' in text and 'Erfasst:' in text
        assert 'Außerhalb des gefragten Zeitraums' not in text
        assert 'ausserhalb_zeitraum' not in selector.rows[0]
    finally:
        claims.close()
        episodes.close()


@pytest.mark.parametrize('question,period', [
    ('Was kam nicht von heute zur Orion-Freigabe?', None),
    ('Was kam nicht nur heute zur Orion-Freigabe?', None),
    ('Was kam nicht nur heute, sondern auch gestern zur Orion-Freigabe?', None),
    ('Was kam nicht heute, sondern gestern zur Orion-Freigabe?', 'von gestern'),
])
def test_negated_period_cannot_return_through_question_understanding(tmp_path, monkeypatch, question, period):
    episodes, claims = EpisodeStore(tmp_path / 'negated-e.sqlite3'), ClaimStore(tmp_path / 'negated-k.sqlite3')
    try:
        _mail(episodes, 'Die Orion-Freigabe ist offen.', NOW - timedelta(days=1))
        monkeypatch.setattr('icarus_memory.time_scope.datetime',
                            type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: NOW)}))
        # Exercise preparation and reopening with a valid structured question as in the Agent path.
        anfrage = Anfrage(('Orion',), 'gestern' if period else None, 'rueckblick',
                          suchworte=('Orion',), herkunft='modell')
        selector = Selector()
        answer = prepare(question, episodes, claims, selector, anfrage=anfrage)
        assert answer.get('time_label') == period
        text, _, _ = render(answer, episodes, claims)
        assert 'Zuerst berücksichtigt: Quellen von heute.' not in text
        assert all('ausserhalb_zeitraum' not in row for row in selector.rows)
        assert 'Orion-Freigabe ist offen' in text
    finally:
        claims.close()
        episodes.close()


def test_invalid_structured_today_cannot_restore_negated_time_label(tmp_path):
    episodes, claims = EpisodeStore(tmp_path / 'invalid-e.sqlite3'), ClaimStore(tmp_path / 'invalid-k.sqlite3')
    try:
        _mail(episodes, 'Die Orion-Freigabe ist offen.', NOW - timedelta(days=1))
        selector = Selector()
        answer = prepare('Was kam nicht von heute zur Orion-Freigabe?', episodes, claims, selector,
                         anfrage=Anfrage(('Orion',), 'heute', 'rueckblick', herkunft='modell'))
        assert 'time_label' not in answer
        # A structured question inconsistent with the original cannot certify a saved answer.
        assert answer['status'] == 'unavailable'
        assert selector.rows is None
    finally:
        claims.close()
        episodes.close()


@pytest.mark.parametrize('question', [
    'Was kam nicht von heute zur Orion-Freigabe?',
    'Was kam nicht nur heute zur Orion-Freigabe?',
    'Was kam nicht heute, sondern gestern zur Orion-Freigabe?',
])
def test_saved_legacy_negated_today_without_structured_question_is_unavailable(tmp_path, monkeypatch, question):
    from icarus_memory import time_scope
    episodes, claims = EpisodeStore(tmp_path / 'legacy-e.sqlite3'), ClaimStore(tmp_path / 'legacy-k.sqlite3')
    try:
        _mail(episodes, 'Die Orion-Freigabe ist offen.', NOW - timedelta(days=1))
        today = mentioned_period('heute', NOW)
        # Reproduce the original interpretation and real stored fields/signatures, without an Anfrage.
        with monkeypatch.context() as legacy:
            legacy.setattr(time_scope, 'has_negated_period', lambda question: False)
            legacy.setattr(time_scope, 'mentioned_period', lambda question, now=None: today)
            saved = prepare(question, episodes, claims, Selector(), semantic_search=None)
        assert saved['status'] == 'reports' and 'anfrage' not in saved
        assert saved['time_label'] == 'von heute'
        assert saved['time_scope'] == [today[0].isoformat(), today[1].isoformat()]
        assert not _fresh(saved, episodes, claims)
        text, links, status = render(saved, episodes, claims)
        assert status == 'working_unavailable' and not links
        assert 'Zuerst berücksichtigt: Quellen von heute' not in text
        reopened = working_memory_answers.project_message({'role': 'assistant', 'content': 'old display',
            'metadata': {'context': {'working_answer': saved}}}, episodes, claims)
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert not reopened['metadata']['context']['source_links']
    finally:
        claims.close()
        episodes.close()


def test_valid_negation_with_positive_yesterday_keeps_frozen_period_after_reopen(tmp_path, monkeypatch):
    episodes, claims = EpisodeStore(tmp_path / 'frozen-e.sqlite3'), ClaimStore(tmp_path / 'frozen-k.sqlite3')
    try:
        _mail(episodes, 'Die Orion-Freigabe ist offen.', NOW - timedelta(days=1))
        monkeypatch.setattr('icarus_memory.time_scope.datetime',
                            type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: NOW)}))
        saved = prepare('Was kam nicht heute, sondern gestern zur Orion-Freigabe?',
                        episodes, claims, Selector(), semantic_search=None)
        assert saved['time_label'] == 'von gestern'
        frozen = list(saved['time_scope'])
        later = NOW + timedelta(days=10)
        monkeypatch.setattr('icarus_memory.time_scope.datetime',
                            type('Later', (datetime,), {'now': classmethod(lambda cls, tz=None: later)}))
        assert _fresh(saved, episodes, claims)
        text, _, status = render(saved, episodes, claims)
        assert status == 'working_reports' and 'Orion-Freigabe ist offen' in text
        assert saved['time_scope'] == frozen
    finally:
        claims.close()
        episodes.close()


def test_period_keeps_undated_person_context_behind_dated_match(tmp_path, monkeypatch):
    episodes, claims = EpisodeStore(tmp_path / 'e.sqlite3'), ClaimStore(tmp_path / 'k.sqlite3')
    try:
        dated = _mail(episodes, 'Die Gussprobe ist angekommen.', NOW - timedelta(days=8))
        undated = _mail(episodes, 'Die Ersatzteile werden separat geprüft.', None)
        monkeypatch.setattr('icarus_memory.time_scope.datetime',
                            type('Fixed', (datetime,), {'now': classmethod(lambda cls, tz=None: NOW)}))
        selector = Selector()
        answer = prepare('Was wollte sie letzte Woche?', episodes, claims, selector,
                         person_ids=[undated, dated])
        # No lexical query anchor occurs in these bodies: the person relationship must retain both.
        assert [ref['episode_id'] for ref in answer['basis']] == [dated, undated]
        assert selector.rows[1]['occurred_at'] is None
        assert 'ausserhalb_zeitraum' not in selector.rows[1]
    finally:
        claims.close()
        episodes.close()


@pytest.mark.parametrize('question', [
    'Auf welches Datum bezog sich heute um 14:00 in der Originalnotiz zum Einkauf-Gespräch?',
    'Was bedeutete gestern in der alten Mail zur Orion-Freigabe?',
    'Welches Datum war mit nächsten Freitag in der Originalmail zur Orion-Freigabe gemeint?',
])
def test_original_relative_word_question_does_not_set_current_source_period(tmp_path, question):
    episodes, claims = EpisodeStore(tmp_path / 'relative-e.sqlite3'), ClaimStore(tmp_path / 'relative-k.sqlite3')
    try:
        body = 'Orion-Freigabe: Heute um 14:00 Gespräch im Einkauf. Die Originalnotiz stammt vom 02.09.2026.'
        source = _mail(episodes, body, datetime(2026, 9, 2, 9, tzinfo=timezone.utc))
        selector = Selector()
        answer = prepare(question, episodes, claims, selector, semantic_search=None)
        assert answer['status'] == 'reports'
        assert 'time_scope' not in answer and 'time_label' not in answer
        assert all('ausserhalb_zeitraum' not in row for row in selector.rows)
        text, links, status = render(answer, episodes, claims)
        assert status == 'working_reports' and body in text
        assert 'Zuerst berücksichtigt:' not in text and 'Außerhalb des gefragten Zeitraums' not in text
        assert [link['episode_id'] for link in links] == [source]
    finally:
        claims.close()
        episodes.close()


@pytest.mark.parametrize('question', [
    'Was kam heute als Originalmail zur Orion-Freigabe?',
    'Was wurde heute in der Originalnotiz zur Orion-Freigabe geschrieben?',
    'Auf welches Datum bezog sich die Orion-Freigabe in der Originalnotiz von heute?',
])
def test_original_source_mention_alone_keeps_explicit_source_period(question):
    found = mentioned_period(question, NOW)
    assert found is not None and found[2] == 'von heute'


def test_original_time_reference_does_not_allow_a_structured_current_period(tmp_path):
    episodes, claims = EpisodeStore(tmp_path / 'original-model-e.sqlite3'), ClaimStore(tmp_path / 'original-model-k.sqlite3')
    try:
        _mail(episodes, 'Heute um 14:00 Gespräch im Einkauf. Originalnotiz vom 02.09.2026.',
              datetime(2026, 9, 2, 9, tzinfo=timezone.utc))
        selector = Selector()
        answer = prepare('Auf welches Datum bezog sich heute um 14:00 in der Originalnotiz zum Einkauf-Gespräch?',
                         episodes, claims, selector, semantic_search=None,
                         anfrage=Anfrage(('Einkauf',), 'heute', 'fakt', herkunft='modell'))
        assert answer['status'] == 'unavailable'
        assert 'time_scope' not in answer and 'time_label' not in answer
        assert selector.rows is None
    finally:
        claims.close()
        episodes.close()


def test_original_time_reference_cannot_be_restored_by_a_simplified_lookup(tmp_path, monkeypatch):
    episodes, claims = EpisodeStore(tmp_path / 'original-lookup-e.sqlite3'), ClaimStore(tmp_path / 'original-lookup-k.sqlite3')
    try:
        _mail(episodes, 'Heute um 14:00 Gespräch im Einkauf. Originalnotiz vom 02.09.2026.',
              datetime(2026, 9, 2, 9, tzinfo=timezone.utc))
        # A search representation is not authority to reinterpret the original question's time intent.
        monkeypatch.setattr(Anfrage, 'suchanfrage', lambda self, question: 'Einkauf heute')
        selector = Selector()
        answer = prepare('Auf welches Datum bezog sich heute um 14:00 in der Originalnotiz zum Einkauf-Gespräch?',
                         episodes, claims, selector, semantic_search=None,
                         anfrage=Anfrage(('Einkauf',), None, 'fakt', herkunft='modell'))
        assert answer['status'] == 'reports'
        assert 'time_scope' not in answer and 'time_label' not in answer
        assert all('ausserhalb_zeitraum' not in row for row in selector.rows)
        assert 'Zuerst berücksichtigt:' not in render(answer, episodes, claims)[0]
    finally:
        claims.close()
        episodes.close()


def test_saved_legacy_original_time_reference_with_today_scope_is_unavailable(tmp_path, monkeypatch):
    from icarus_memory import time_scope
    episodes, claims = EpisodeStore(tmp_path / 'original-legacy-e.sqlite3'), ClaimStore(tmp_path / 'original-legacy-k.sqlite3')
    question = 'Auf welches Datum bezog sich heute um 14:00 in der Originalnotiz zum Einkauf-Gespräch?'
    try:
        _mail(episodes, 'Heute um 14:00 Gespräch im Einkauf. Originalnotiz vom 02.09.2026.',
              datetime(2026, 9, 2, 9, tzinfo=timezone.utc))
        today = mentioned_period('heute', NOW)
        with monkeypatch.context() as legacy:
            legacy.setattr(time_scope, 'mentioned_period', lambda question, now=None: today)
            if hasattr(time_scope, 'original_time_reference'):
                legacy.setattr(time_scope, 'original_time_reference', lambda question: False)
            saved = prepare(question, episodes, claims, Selector(), semantic_search=None)
        assert saved['status'] == 'reports' and saved['time_label'] == 'von heute'
        assert not _fresh(saved, episodes, claims)
        text, links, status = render(saved, episodes, claims)
        assert status == 'working_unavailable' and links == []
        reopened = working_memory_answers.project_message({'role': 'assistant', 'content': 'old today display',
            'metadata': {'context': {'working_answer': saved}}}, episodes, claims)
        assert reopened['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert 'Zuerst berücksichtigt:' not in reopened['content']
    finally:
        claims.close()
        episodes.close()
