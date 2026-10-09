"""Synthetic limits: normative sentence binding must retain its same-paragraph context."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from icarus_memory import satzantwort as sa
from icarus_memory.providers import Reply
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
CATALOG = json.loads((Path(__file__).parent / 'fixtures/normative_source_holdouts.json').read_text())
SOURCES = {source['id']: source['text'] for source in CATALOG['sources']}


class Selector:
    is_local = True
    name = model = 'synthetic-selector'

    def __init__(self, output):
        self.output = output
        self.messages = []

    def complete_json(self, messages, **kwargs):
        self.messages.append((messages, kwargs))
        data = json.loads(messages[-1]['content'])
        output = self.output(data) if callable(self.output) else self.output
        return Reply(text=json.dumps(output))


def evidence(text, **kwargs):
    return sa.AntwortBeleg(1, {}, 'conditional', 'source-1', 'Regel', '', text, None, **kwargs)


@pytest.mark.parametrize('case_id', ['L01', 'L02'])
def test_isolated_normative_sentence_loses_same_paragraph_context(case_id):
    case = next(case for case in CATALOG['known_controls'] + CATALOG['new_controls'] if case['id'] == case_id)
    source = SOURCES[case['source_ids'][0]]
    direct = satz_pruefen(Satz(case['candidate'], ('1',)), {'1': Beleg('1', source)})
    assert direct.bestanden  # The individual rule is literal; completeness is an answer-level contract.

    result = sa.formulieren('Was gilt?', [evidence(source)], Selector({'status': 'antwort', 'saetze': [
        {'text': case['candidate'], 'belege': [1]}]}), jetzt=NOW)
    # The individual sentence gate allows a literal sentence. The answer-level
    # check blocks it because its context sentence was omitted.
    assert result.status == 'zitate'
    assert result.verworfen


@pytest.mark.parametrize('case_id', ['L01', 'L02'])
def test_complete_visible_paragraph_is_an_available_verbatim_answer(case_id):
    source = SOURCES[case_id + '-S1']
    provider = Selector(lambda data: {'status': 'antwort', 'originalstellen': [
        {'beleg': data['belege'][0]['nr'], 'satz': sentence['nr']}
        for sentence in data['belege'][0]['originalsaetze']]})
    result = sa.formulieren('Was gilt?', [evidence(source)], provider, jetzt=NOW)
    assert result.status == 'saetze'
    assert [sentence.text for sentence in result.saetze] == [source]
    offered = json.loads(provider.messages[0][0][-1]['content'])['belege'][0]['originalsaetze']
    assert offered[0] == {'nr': 1, 'text': source}


def test_single_sentence_rule_remains_short_and_selectable():
    source = SOURCES['N20-S1']
    result = sa.formulieren('Was gilt?', [evidence(source)],
        Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}), jetzt=NOW)
    assert result.status == 'saetze'
    assert [sentence.text for sentence in result.saetze] == [source]


def test_ordinary_multisentence_facts_keep_the_existing_paraphrase_path():
    source = 'Der Bericht liegt im Tresor. Der Schlüssel steckt in der Tasche.'
    candidate = 'Der Bericht liegt im Tresor.'
    result = sa.formulieren('Wo liegt der Bericht?', [evidence(source)], Selector({'status': 'antwort', 'saetze': [
        {'text': candidate, 'belege': [1]}]}), jetzt=NOW)
    assert result.status == 'saetze'
    assert [sentence.text for sentence in result.saetze] == [candidate]


def test_context_binding_is_limited_to_the_matching_paragraph():
    unrelated = 'Der Schalter darf nach der Prüfung umgelegt werden.'
    source = SOURCES['L01-S1'] + '\n\n' + unrelated
    result = sa.formulieren('Was gilt für den Schalter?', [evidence(source)], Selector({'status': 'antwort', 'saetze': [
        {'text': unrelated, 'belege': [1]}]}), jetzt=NOW)
    assert result.status == 'saetze'
    assert [sentence.text for sentence in result.saetze] == [unrelated]


def test_truncated_paragraph_cannot_be_used_as_an_isolated_original():
    source = SOURCES['L01-S1']
    isolated = 'Die Klappe darf geöffnet werden.'
    excerpt = isolated + ' […]'
    result = sa.formulieren('Was gilt?', [evidence(excerpt, pruef_text=source, gekuerzt=True)],
        Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}), jetzt=NOW)
    assert result.status == 'zitate'


def test_second_gate_cannot_remove_context_after_approving_the_rule():
    from icarus_memory import satzpruefung_modell as spm
    from tests.test_satzpruefung_modell import Pruefer as Judge

    source = SOURCES['L01-S1']
    provider = Selector({'status': 'antwort', 'saetze': [{'text': source.split('. ')[0] + '.', 'belege': [1]}]})
    judge = Judge()
    result = sa.formulieren('Was gilt?', [evidence(source)], provider, jetzt=NOW,
                            pruefung=spm.tor('an', judge))
    assert result.status == 'zitate'
    assert len(judge.anfragen) == 1


def test_saved_old_sentence_is_rejected_after_reopen_and_withdrawal(tmp_path):
    from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType, working_memory_answers
    from icarus_memory.claims import ClaimStore
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from tests.test_satzantwort import Skript

    body = SOURCES['L01-S1']
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        plain, _ = episodes.record(EpisodeKind.DOCUMENT, 'Bericht', 'Der Bericht liegt im Tresor.',
                                   Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(plain.id),
            [{'start': 0, 'end': len(plain.body), 'kind': 'fact'}], model='synthetic')
        answer = working_memory_answers.prepare('Wo liegt der Bericht?', episodes, claims,
            Skript({'status': 'antwort', 'saetze': [{'text': 'Der Bericht liegt im Tresor.', 'belege': [1]}]}),
            saetze=True)
        saved = answer['satzantwort']
        source, _ = episodes.record(EpisodeKind.DOCUMENT, 'Regel', body, Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(source.id),
            [{'start': 0, 'end': len(body), 'kind': 'conditional'}], model='synthetic')
        ref = WorkingMemoryStore(episodes).source_refs(episode_ids=[source.id])['refs'][0]
        saved['belege'][0]['ref'] = ref
        saved['saetze'][0].update(roh='Die Klappe darf geöffnet werden.', text='Die Klappe darf geöffnet werden.')
        saved.pop('suche', None)
    finally:
        claims.close()
        episodes.close()

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        assert sa.wiederherstellen(saved, episodes, claims) is None
        episodes.ignore(source.id)
        assert sa.wiederherstellen(saved, episodes, claims) is None
        assert episodes.get(source.id).body == body
    finally:
        claims.close()
        episodes.close()


@pytest.mark.parametrize('source', [
    'Entwurf\n\nDie Klappe darf geöffnet werden. Dies gilt nur während der Prüfung.',
    'Die Klappe darf geöffnet werden. Dies darf ausschließlich nach schriftlicher Freigabe erfolgen.',
    'Die Klappe darf geöffnet werden. Dies muss ausschließlich nach schriftlicher Freigabe erfolgen.',
    'Die Klappe darf geöffnet werden. Dies soll ausschließlich nach schriftlicher Freigabe erfolgen.',
])
@pytest.mark.parametrize('all_yes', [False, True])
def test_header_and_all_normative_companions_are_atomic(source, all_yes):
    from icarus_memory import satzpruefung_modell as spm
    from tests.test_satzpruefung_modell import Pruefer as Judge

    candidate = sa.satzpruefung.originalabschnitte(source)[0]
    provider = Selector({'status': 'antwort', 'saetze': [{'text': candidate, 'belege': [1]}]})
    judge = Judge({'': '{"urteil":"ja"}'})
    result = sa.formulieren('Was gilt?', [evidence(source)], provider, jetzt=NOW,
                            pruefung=spm.tor('an', judge) if all_yes else spm.OHNE)
    assert result.status == 'zitate'
    offered = json.loads(provider.messages[0][0][-1]['content'])['belege'][0]['originalsaetze']
    assert any(item['text'] == source for item in offered)
    assert not any(sa.satzpruefung.originaltext(candidate) == sa.satzpruefung.originaltext(item['text'])
                   for item in offered)
    if all_yes:
        assert judge.anfragen


@pytest.mark.parametrize('source', [
    'Entwurf\n\nDie Klappe darf geöffnet werden. Dies gilt nur während der Prüfung.',
    'Die Klappe darf geöffnet werden. Dies darf ausschließlich nach schriftlicher Freigabe erfolgen.',
])
def test_incomplete_context_is_rejected_after_real_store_reopen(tmp_path, source):
    from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType, working_memory_answers
    from icarus_memory.claims import ClaimStore
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from tests.test_satzantwort import Skript

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        plain, _ = episodes.record(EpisodeKind.DOCUMENT, 'Fakt', 'Der Bericht liegt im Tresor.',
                                   Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(plain.id),
            [{'start': 0, 'end': len(plain.body), 'kind': 'fact'}], model='synthetic')
        saved_answer = working_memory_answers.prepare('Wo liegt der Bericht?', episodes, claims,
            Skript({'status': 'antwort', 'saetze': [{'text': 'Der Bericht liegt im Tresor.', 'belege': [1]}]}),
            saetze=True)
        saved = saved_answer['satzantwort']
        episode, _ = episodes.record(EpisodeKind.DOCUMENT, 'Regel', source, Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(episode.id),
            [{'start': 0, 'end': len(source), 'kind': 'conditional'}], model='synthetic')
        ref = WorkingMemoryStore(episodes).source_refs(episode_ids=[episode.id])['refs'][0]
        candidate = sa.satzpruefung.originalabschnitte(source)[0]
        saved['belege'][0]['ref'] = ref
        saved['saetze'][0].update(roh=candidate, text=candidate)
        saved.pop('suche', None)
    finally:
        claims.close()
        episodes.close()

    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        assert sa.wiederherstellen(saved, episodes, claims) is None
        source_id = saved['belege'][0]['ref']['episode_id']
        episodes.ignore(source_id)
        assert sa.wiederherstellen(saved, episodes, claims) is None
        assert episodes.get(source_id).body == source
    finally:
        claims.close()
        episodes.close()


def test_context_sentences_cannot_be_reversed_or_interleaved():
    source = 'Die Klappe darf geöffnet werden. Dies gilt ausschließlich nach schriftlicher Freigabe.'
    other = 'Der Schalter darf umgelegt werden.'
    rule, qualifier = sa.satzpruefung.originalabschnitte(source)
    for sentences, belege in [
        ([qualifier, rule], ('1',)),
        ([rule, other, qualifier], ('1', '2')),
    ]:
        evidence_list = [evidence(source)] + ([evidence(other)] if len(belege) == 2 else [])
        parsed = [Satz(text, (str(index),)) for text in sentences
                  for index in ([2] if text == other else [1])]
        result = sa._urteilen('antwort', parsed, evidence_list, NOW, (), 'synthetic')
        assert result.status == 'zitate'

    ordered = sa._urteilen('antwort', [Satz(rule, ('1',)), Satz(qualifier, ('1',))],
                           [evidence(source)], NOW, (), 'synthetic')
    assert ordered.status == 'saetze'


def test_formulieren_rejects_reversed_and_interleaved_context_output():
    from dataclasses import replace

    source = 'Die Klappe darf geöffnet werden. Dies gilt ausschließlich nach schriftlicher Freigabe.'
    other = 'Der Schalter darf umgelegt werden.'
    rule, qualifier = sa.satzpruefung.originalabschnitte(source)
    other_evidence = replace(evidence(other), nummer=2, episode_id='source-2')
    outputs = [
        [{'text': qualifier, 'belege': [1]}, {'text': rule, 'belege': [1]}],
        [{'text': rule, 'belege': [1]}, {'text': other, 'belege': [2]},
         {'text': qualifier, 'belege': [1]}],
    ]
    for sentences in outputs:
        result = sa.formulieren('Was gilt?', [evidence(source), other_evidence],
            Selector({'status': 'antwort', 'saetze': sentences}), jetzt=NOW)
        assert result.status == 'zitate'
