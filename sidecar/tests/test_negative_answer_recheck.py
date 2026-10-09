"""A rejected relevant original gets one recheck, never an invented status.

Removing the recheck must lose the explicit negative status despite an available
second selection. Removing its bound must make the persistent-unknown case call
again. Removing the ordinary safety gates must accept the wrong IDs or verdict.
"""
import json
from datetime import datetime, timezone

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType, satzantwort as sa
from icarus_memory import satzpruefung_modell as gate, working_memory_answers as answers
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.providers import ProviderError, Reply
from icarus_memory.working_memory_store import WorkingMemoryStore

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
BODY = ('Bei Z-204 darf die Lieferung erst nach schriftlicher Zustimmung versandt werden. '
        'Die Zustimmung liegt noch nicht vor.')
QUESTION = 'Ist die Zustimmung für die Lieferung Z-204 schon eingegangen?'
EMPTY = {'status': 'nichts_vorliegend', 'originalstellen': []}
FULL = {'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}


class SequenceProvider:
    """Only the slow external JSON boundary is scripted; all evidence gates run."""
    is_local = True
    name = model = 'synthetic-sequence'

    def __init__(self, *outputs):
        self.outputs = iter(outputs)
        self.answer_payloads = []

    def complete_json(self, messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        if 'sources' in payload:
            return Reply(text=json.dumps({'status': 'source_reports',
                                          'ids': [source['id'] for source in payload['sources']]}))
        self.answer_payloads.append(payload)
        value = next(self.outputs)  # An unbounded third call is not a valid script.
        if isinstance(value, Exception):
            raise value
        return Reply(text=json.dumps(value))


def evidence(body=BODY):
    return sa.AntwortBeleg(1, {}, 'status', 'source-1', 'Lieferung Z-204', '', body, None)


def test_rechecked_negative_status_keeps_the_whole_original_paragraph():
    provider = SequenceProvider(EMPTY, FULL)
    result = sa.formulieren(QUESTION, [evidence()], provider, jetzt=NOW)
    assert result.status == 'saetze'
    assert [sentence.text for sentence in result.saetze] == [BODY]
    assert result.saetze[0].belege == (1,)
    assert len(provider.answer_payloads) == 2
    assert provider.answer_payloads[0] == provider.answer_payloads[1]
    assert provider.answer_payloads[1]['belege'][0]['originalsaetze'] == [{'nr': 1, 'text': BODY}]


def test_rechecked_negative_status_survives_restart_and_withdrawal(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Lieferung Z-204', BODY,
                                    Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),
            [{'start': 0, 'end': len(BODY), 'kind': 'status'}], model='synthetic')
        saved = answers.prepare(QUESTION, episodes, claims, SequenceProvider(EMPTY, FULL), saetze=True)
        assert saved['satzantwort']['status'] == 'saetze'
    finally:
        claims.close()
        episodes.close()
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        text, links, status = answers.render(saved, episodes, claims)
        assert status == 'working_reports'
        assert BODY in text and 'keine Information' not in text
        assert [link['episode_id'] for link in links] == [episode.id]
        episodes.ignore(episode.id)
        text, links, status = answers.render(saved, episodes, claims)
        assert status == 'working_unavailable' and links == []
        assert BODY not in text
        assert episodes.get(episode.id).body == BODY
    finally:
        claims.close()
        episodes.close()


def test_a_rule_alone_still_does_not_establish_its_condition():
    provider = SequenceProvider(EMPTY, EMPTY)
    result = sa.formulieren(QUESTION, [evidence(BODY.split(' Die Zustimmung')[0])], provider, jetzt=NOW)
    assert result.status == 'nichts' and result.saetze == []
    assert len(provider.answer_payloads) == 2


@pytest.mark.parametrize('last', [
    {'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 2}]},
    {'status': 'antwort', 'originalstellen': [{'beleg': 2, 'satz': 1}]},
    {'status': 'nichts_vorliegend', 'originalstellen': [{'beleg': 1, 'satz': 1}]},
    ProviderError('bounded synthetic failure'),
])
def test_recheck_cannot_bypass_original_identity_or_consistency(last):
    provider = SequenceProvider(EMPTY, last)
    result = sa.formulieren(QUESTION, [evidence()], provider, jetzt=NOW)
    assert result.status == 'zitate' and result.saetze == []
    assert len(provider.answer_payloads) == 2


def test_recheck_keeps_the_second_verification_gate():
    verifier = SequenceProvider({'urteil': 'nein'})
    result = sa.formulieren(QUESTION, [evidence()], SequenceProvider(EMPTY, FULL), jetzt=NOW,
                            pruefung=gate.Tor(gate.AN, verifier))
    assert result.status == 'zitate' and result.saetze == []
    assert result.verworfen[0].pruefmodell == gate.NEIN


def test_ordinary_unknown_does_not_add_an_original_recheck():
    provider = SequenceProvider({'status': 'nichts_vorliegend', 'saetze': []})
    result = sa.formulieren('Welche Diagnose hat die Person?',
                            [evidence('Die Person wünscht sich einen Bildschirmhalter.')], provider, jetzt=NOW)
    assert result.status == 'nichts' and result.saetze == []
    assert len(provider.answer_payloads) == 1
