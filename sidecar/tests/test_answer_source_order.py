"""Mehrere Quellen: neueste zuerst, gekennzeichnet; Gleichzeitiges bleibt ungekennzeichnet."""
from datetime import datetime, timezone

from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_answers import prepare, render
from icarus_memory.working_memory_store import WorkingMemoryStore
import json

from icarus_memory.providers import Reply


class Reversed:
    """Nennt die Quellen in umgekehrter Suchreihenfolge, also älteste zuerst."""
    is_local = True

    def complete_json(self, messages, **kwargs):
        rows = json.loads(messages[-1]['content'])['sources']
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in reversed(rows)]}))


def _mail(episodes, title, body, day):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, title, body, Provenance(SourceType.EMAIL),
                                 participants=['Anna <anna@example.test>'],
                                 occurred_at=datetime(2026, 9, day, 9, tzinfo=timezone.utc) if day else None)
    assert WorkingMemoryStore(episodes).commit(
        episodes.support_snapshot(episode.id), [{'start': 0, 'end': len(body), 'kind': 'fact'}], model='t')
    return episode


def _render(tmp_path, days):
    episodes = EpisodeStore(tmp_path / 'e.sqlite3')
    claims = ClaimStore(tmp_path / 'k.sqlite3')
    try:
        for n, day in enumerate(days):
            _mail(episodes, f'Stand {n}', f'Die Freigabe für Orion kommt am {20 + n}. Oktober.', day)
        answer = prepare('Wann kommt die Freigabe für Orion?', episodes, claims, Reversed())
        text, links, _ = render(answer, episodes, claims)
        return text, links, answer
    finally:
        claims.close()
        episodes.close()


def test_newest_source_comes_first_and_is_marked(tmp_path):
    text, links, answer = _render(tmp_path, [3, 18, 9])
    assert text.index('Stand 1') < text.index('Stand 2') < text.index('Stand 0')
    assert 'Stand 1 · neueste Quelle' in text and text.count('neueste Quelle') == 1
    assert [link['label'] for link in links] == ['Quelle 1 öffnen', 'Quelle 2 öffnen', 'Quelle 3 öffnen']


def test_same_time_sources_are_not_marked(tmp_path):
    text, _, _ = _render(tmp_path, [5, 5])
    assert 'neueste Quelle' not in text


def test_single_source_is_not_marked(tmp_path):
    text, _, _ = _render(tmp_path, [5])
    assert 'neueste Quelle' not in text


def test_unknown_source_time_is_never_called_newest(tmp_path):
    text, _, _ = _render(tmp_path, [5, None])
    assert 'neueste Quelle' not in text
