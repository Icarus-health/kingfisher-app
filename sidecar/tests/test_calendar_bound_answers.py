"""Calendar bounds must survive answer rewriting, including stored reopening."""
from datetime import datetime, timezone

import pytest

from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen


@pytest.mark.parametrize('source,answer', [
    ('Die Zusage gilt nur bis 30.09.2026.', 'Die Zusage gilt ab 30.09.2026.'),
    ('Das Archiv ist erst ab 12.10.2026 zugänglich.', 'Das Archiv ist bis 12.10.2026 zugänglich.'),
    ('Die Anmeldung ist vor dem 12. Oktober 2026 möglich.', 'Die Anmeldung ist nach dem 12.10.2026 möglich.'),
    ('Die Zusage gilt nach 12.10.2026.', 'Die Zusage gilt ab 12.10.2026.'),
    ('Die Zusage gilt nicht vor 12.10.2026.', 'Die Zusage gilt vor 12.10.2026.'),
    ('Die Lizenz ist bis zum 2026-10-12 gültig.', 'Die Lizenz ist am 12.10.2026 gültig.'),
    ('Die Zusage gilt nur bis 30.09.2026.', 'Die Zusage gilt.'),
    ('Die Zusage gilt nur bis 30.09.2026.', 'Die Zusage gilt aktuell.'),
    ('Die Lizenz ist ab dem 12.10.2026 gültig.', 'Die Lizenz ist gültig.'),
])
def test_calendar_condition_is_not_reversed_or_dropped(source, answer):
    result = satz_pruefen(Satz(answer, ('1',)), {'1': Beleg('1', source)})
    assert not result.bestanden, (source, answer, result)
    assert any('Datumsgrenze' in reason for reason in result.gruende)


@pytest.mark.parametrize('source,answer', [
    ('Die Zusage gilt nur bis 30.09.2026.', 'Die Zusage gilt nur bis 30. September 2026.'),
    ('Die Zusage gilt nur bis 30.09.2026.', 'Die Zusage gilt bis 30. September 2026.'),
    ('Die Lizenz ist erst ab dem 2026-10-12 gültig.', 'Die Lizenz ist ab 12.10.2026 gültig.'),
    ('Die Lizenz ist ab dem 2026-10-12 gültig.', 'Die Lizenz ist ab 12.10.2026 gültig.'),
    ('Die Zusage gilt erst nach 12.10.2026.', 'Die Zusage gilt nach dem 12. Oktober 2026.'),
    ('Die Zusage gilt nicht vor 12.10.2026.', 'Die Zusage gilt nicht vor dem 12. Oktober 2026.'),
    ('Die Anmeldung ist bis 12.10. möglich.', 'Die Anmeldung ist bis 12.10.2026 möglich.'),
    ('Die Zusage gilt bis 30.09.2026. Die Lizenz ist gültig.', 'Die Lizenz ist gültig.'),
    ('Die Zusage gilt bis 30.09.2026. Die Rechnung liegt vor.', 'Die Rechnung liegt vor.'),
    ('Die Zusage liegt vor.', 'Die Zusage liegt vor.'),
    ('Die Lizenz gilt bis 30.09.2026 für den Test. Die Lizenz gilt für den Betrieb unbefristet.',
     'Die Lizenz gilt für den Betrieb unbefristet.'),
    ('Die Zusage gilt bis 30.09.2026. Die Zusage gilt ab 01.10.2026.',
     'Die Zusage gilt ab 01.10.2026.'),
    ('Die Zusage galt nur bis 30.09.2026.', 'Die Zusage galt.'),
    ('Bitte schicken Sie die Druckdaten bis Freitag.', 'Bitte die Druckdaten schicken.'),
    ('Bitte schicken Sie die Druckdaten bis Freitag.', 'Die Druckdaten werden bis 25.09.2026 erwartet.'),
    ('Die Einreichfrist ist der 12. Oktober 2026.', 'Die Einreichfrist ist der 12.10.2026.'),
])
def test_date_formats_and_unrelated_facts_remain_usable(source, answer):
    result = satz_pruefen(Satz(answer, ('1',)), {'1': Beleg('1', source, datetime(2026, 9, 21, tzinfo=timezone.utc))})
    assert result.bestanden, result.gruende


@pytest.fixture
def memory(tmp_path, monkeypatch):
    from icarus_memory.episodes import EpisodeKind, EpisodeStore
    from icarus_memory.claims import ClaimStore
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from icarus_memory import working_memory_answers as answers
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    source, _ = episodes.record(EpisodeKind.MESSAGE, 'Zusage', 'Die Zusage gilt nur bis 30.09.2026.',
                               Provenance(SourceType.EMAIL), occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(source.id),
        [{'start': 0, 'end': len(source.body), 'kind': 'fact'}], model='synthetic')
    monkeypatch.setattr(answers, 'now', lambda: datetime(2026, 10, 8, tzinfo=timezone.utc))
    yield episodes, claims, source
    claims.close()
    episodes.close()


@pytest.mark.parametrize('sentence', ['Die Zusage gilt aktuell.', 'Die Zusage gilt ab 30.09.2026.'])
def test_real_answer_falls_back_to_original_when_date_bound_is_lost(memory, sentence):
    from icarus_memory import working_memory_answers as answers
    from tests.test_satzantwort import Skript
    episodes, claims, source = memory
    provider = Skript({'status': 'antwort', 'saetze': [{'text': sentence, 'belege': [1]}]})
    answer = answers.prepare('Wie lange gilt die Zusage?', episodes, claims, provider, saetze=True,
                             semantic_search=None)
    assert answer['satzantwort']['status'] == 'zitate'
    assert any('Datumsgrenze' in reason for reason in answer['satzantwort']['gruende'])
    text, links, _ = answers.render(answer, episodes, claims)
    assert source.body in text and sentence not in text
    assert {link['episode_id'] for link in links} == {source.id}


def test_saved_old_unbounded_answer_is_rejected_without_models(memory):
    from copy import deepcopy
    from icarus_memory import satzantwort, working_memory_answers as answers
    from tests.test_satzantwort import Skript
    episodes, claims, source = memory
    valid = 'Die Zusage gilt nur bis 30.09.2026.'
    provider = Skript({'status': 'antwort', 'saetze': [{'text': valid, 'belege': [1]}]})
    answer = answers.prepare('Wie lange gilt die Zusage?', episodes, claims, provider, saetze=True,
                             semantic_search=None)
    assert answer['satzantwort']['status'] == 'saetze'
    assert satzantwort.wiederherstellen(answer['satzantwort'], episodes, claims) is not None
    old = deepcopy(answer)
    old['satzantwort']['saetze'][0].update(roh='Die Zusage gilt aktuell.', text='Die Zusage gilt aktuell.')
    assert satzantwort.wiederherstellen(old['satzantwort'], episodes, claims) is None
    text, _, _ = answers.render(old, episodes, claims)
    assert source.body in text and 'Die Zusage gilt aktuell.' not in text
