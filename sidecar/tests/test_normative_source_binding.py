"""Frozen independent wrong-action/role/condition controls; no model required."""
import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from icarus_memory import satzantwort as sa
from icarus_memory.satzpruefung import Beleg, Satz, satz_pruefen
from tests.test_original_sentence_selection import Selector, evidence

CATALOG = json.loads((Path(__file__).parent / 'fixtures/normative_source_holdouts.json').read_text())
SOURCES = {s['id']: s['text'] for s in CATALOG['sources']}
CASES = [c for c in CATALOG['known_controls'] + CATALOG['new_controls'] if c['required_for_increment']]
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_independent_original_binding_controls(case):
    belege = {str(n): Beleg(str(n), SOURCES[s]) for n, s in enumerate(case['source_ids'], 1)}
    result = satz_pruefen(Satz(case['candidate'], tuple(belege)), belege)
    assert result.bestanden is case['expected_binding'], result.gruende


@pytest.mark.parametrize('case_id', ['N02', 'N06', 'N09', 'N11', 'N13', 'N14', 'N20', 'N22'])
def test_legacy_wrong_candidate_cannot_escape_through_formulation(case_id):
    case = next(c for c in CASES if c['id'] == case_id)
    provider = Selector({'status': 'antwort', 'saetze': [{'text': case['candidate'], 'belege': [1]}]})
    result = sa.formulieren('Was gilt?', [evidence(SOURCES[case['source_ids'][0]])], provider, jetzt=NOW)
    assert result.status == 'zitate'
    assert result.verworfen


@pytest.mark.parametrize('case_id', ['P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07', 'P08'])
def test_model_selects_complete_original_instead_of_reconstructing_rule(case_id):
    case = next(c for c in CASES if c['id'] == case_id)
    source = SOURCES[case['source_ids'][0]]
    provider = Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]})
    result = sa.formulieren('Was gilt?', [evidence(source)], provider, jetzt=NOW)
    assert result.status == 'saetze'
    assert result.saetze[0].text == (case['candidate'] if case_id == 'P01' else source)


def test_hidden_original_cannot_be_reintroduced_by_legacy_text():
    hidden = 'Die Klappe darf nach der Kontrolle geöffnet werden.'
    visible = 'Der Bericht liegt im Tresor.'
    provider = Selector({'status': 'antwort', 'saetze': [{'text': hidden, 'belege': [1]}]})
    result = sa.formulieren('Was gilt?', [evidence(visible, pruef_text=hidden + ' ' + visible, gekuerzt=True)],
                            provider, jetzt=NOW)
    assert result.status == 'zitate'


def test_visibility_and_unquoted_context_must_belong_to_the_same_cited_source():
    from dataclasses import replace
    permission = 'Die Klappe darf nach der Kontrolle geöffnet werden.'
    visible = 'Der Bericht liegt im Tresor.'
    hidden = evidence(visible, pruef_text=permission + ' ' + visible, gekuerzt=True)
    quoted = replace(evidence('Alte Anweisung: „Zunächst wird das Datum notiert. ' + permission
                              + ' Diese Anweisung wurde verworfen.“'), nummer=2, episode_id='source-2')
    for cited in [[1], [2], [1, 2]]:
        result = sa.formulieren('Was gilt?', [hidden, quoted], Selector({'status': 'antwort', 'saetze': [
            {'text': permission, 'belege': cited}]}), jetzt=NOW)
        assert result.status == 'zitate', cited


@pytest.mark.parametrize('source', [
    'Die Messsonde darf z. B. nach der Kalibrierung eingeschaltet werden.',
    'Der Techniker muss die Schraube Nr. 7 vor dem Start prüfen.',
    'Die Anlage darf nach Freigabe durch Dr. Weber gestartet werden.',
    'Die Anlage darf am 9. Oktober nach der Prüfung gestartet werden.',
])
def test_abbreviations_and_ordinals_do_not_issue_permission_fragments(source):
    provider = Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]})
    result = sa.formulieren('Was gilt?', [evidence(source)], provider, jetzt=NOW)
    offered = json.loads(provider.messages[0][0][-1]['content'])['belege'][0]['originalsaetze']
    assert offered == [{'nr': 1, 'text': source}]
    assert result.status == 'saetze'


def test_uncited_source_cannot_support_a_changed_condition():
    belege = {'1': Beleg('1', 'Die Klappe darf nach der Kontrolle geöffnet werden.'),
              '2': Beleg('2', 'Die Klappe darf nach der Wartung geöffnet werden.')}
    assert not satz_pruefen(Satz(belege['2'].text, ('1',)), belege).bestanden


@pytest.mark.parametrize('case_id', ['N02', 'N06'])
def test_incorrect_yes_from_second_model_cannot_override_original_binding(case_id):
    from icarus_memory import satzpruefung_modell as spm
    from tests.test_satzpruefung_modell import Pruefer
    case = next(c for c in CASES if c['id'] == case_id)
    judge = Pruefer(standard='{"urteil":"ja"}')
    provider = Selector({'status': 'antwort', 'saetze': [{'text': case['candidate'], 'belege': [1]}]})
    result = sa.formulieren('Was gilt?', [evidence(SOURCES[case['source_ids'][0]])], provider,
                            jetzt=NOW, pruefung=spm.tor('an', judge))
    assert result.status == 'zitate'
    assert not judge.anfragen, 'The central guard rejects before a fallible second model'


@pytest.mark.parametrize('verdict', ['ja', 'nein', 'unklar'])
def test_selected_original_still_requires_second_gate(verdict):
    from icarus_memory import satzpruefung_modell as spm
    from tests.test_satzpruefung_modell import Pruefer
    source = SOURCES['N02-S1']
    judge = Pruefer(standard=json.dumps({'urteil': verdict}))
    result = sa.formulieren('Was gilt?', [evidence(source)],
        Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}),
        jetzt=NOW, pruefung=spm.tor('an', judge))
    assert len(judge.anfragen) == 1
    assert result.status == ('saetze' if verdict == 'ja' else 'zitate')


def test_relative_normative_date_conservatively_falls_back_without_rewriting_source():
    from dataclasses import replace
    source = 'Die Probe muss morgen abgegeben werden.'
    result = sa.formulieren('Wann?', [replace(evidence(source), zeit=NOW)],
        Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}), jetzt=NOW)
    assert result.status == 'zitate'


def test_rejected_rule_cannot_be_hidden_by_a_true_fact_from_same_source():
    source = SOURCES['N02-S1'] + ' Der Bericht liegt im Tresor.'
    bad = next(c['candidate'] for c in CASES if c['id'] == 'N02')
    result = sa.formulieren('Was gilt?', [evidence(source)], Selector({'status': 'antwort', 'saetze': [
        {'text': bad, 'belege': [1]}, {'text': 'Der Bericht liegt im Tresor.', 'belege': [1]}]}), jetzt=NOW)
    assert result.status == 'zitate'
    assert result.verworfen


@pytest.mark.parametrize('case_id', ['N02', 'N06', 'N11', 'N13', 'N14', 'N22', 'P02', 'P03'])
def test_old_answers_are_rechecked_after_real_stores_reopen(tmp_path, case_id):
    from icarus_memory import EpisodeStore, EpisodeKind, Provenance, SourceType, working_memory_answers
    from icarus_memory.claims import ClaimStore
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from tests.test_satzantwort import Skript

    case = next(c for c in CASES if c['id'] == case_id)
    body = SOURCES[case['source_ids'][0]]
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        # Obtain a real saved answer envelope, then reproduce an old unchecked
        # candidate inside it. Product validation is never replaced with a mock.
        plain, _ = episodes.record(EpisodeKind.DOCUMENT, 'Bericht', 'Der Bericht liegt im Tresor.',
                                   Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(plain.id),
            [{'start': 0, 'end': len(plain.body), 'kind': 'fact'}], model='synthetic')
        provider = Skript({'status': 'antwort', 'saetze': [{'text': 'Der Bericht liegt im Tresor.', 'belege': [1]}]})
        answer = working_memory_answers.prepare('Wo liegt der Bericht?', episodes, claims, provider, saetze=True)
        saved = answer['satzantwort']
        assert saved['status'] == 'saetze'
        source, _ = episodes.record(EpisodeKind.DOCUMENT, 'Regel', body, Provenance(SourceType.DOCUMENT))
        assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(source.id),
            [{'start': 0, 'end': len(body), 'kind': 'conditional'}], model='synthetic')
        # Preserve the exact current-source reference shape used by production.
        ref = WorkingMemoryStore(episodes).source_refs(episode_ids=[source.id])['refs'][0]
        saved['belege'][0]['ref'] = ref
        saved['saetze'][0].update(roh=case['candidate'], text=case['candidate'])
        saved.pop('suche', None)
    finally:
        claims.close()
        episodes.close()
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    try:
        restored = sa.wiederherstellen(saved, episodes, claims)
        assert (restored is not None) is case['expected_binding']
        if restored is not None:
            episodes.ignore(source.id)
            assert sa.wiederherstellen(saved, episodes, claims) is None
            assert episodes.get(source.id).body == body
    finally:
        claims.close()
        episodes.close()
