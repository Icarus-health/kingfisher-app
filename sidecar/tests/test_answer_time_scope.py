"""Ein Zeitraum in der Frage ordnet um, schließt aber nichts aus."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from icarus_memory import working_memory_answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.providers import Reply
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
