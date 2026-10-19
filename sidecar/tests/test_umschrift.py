"""Umlaut-Umschrift: „Mueller“ findet „Müller“ und umgekehrt, in jeder Suche und bei Personen in der Frage.

Nur zur Fragezeit; gespeicherte Wörter, Index und Originale bleiben unverändert.
"""
from datetime import datetime, timezone

import pytest

from icarus_memory import personenfrage, source_index
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.word_forms import umschrift_gleich, umschriften
from tests.test_source_index import classify, put

AT = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def episodes(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    yield store
    store.close()


def test_umschriften_in_beide_richtungen_und_begrenzt():
    assert umschriften('Mueller') == {'müller'} and umschriften('Müller') == {'mueller'}
    assert umschriften('Koenigsfeld') == {'königsfeld'} and umschriften('Rechnung') == frozenset()
    assert umschriften('Fuehrungskraefte') == {'führungskraefte', 'fuehrungskräfte', 'führungskräfte'}
    assert len(umschriften('aeoeueaeoeue')) == 7   # höchstens drei Stellen
    assert umschrift_gleich('Müller') == umschrift_gleich('MUELLER') == 'mueller'


@pytest.mark.parametrize('gespeichert,gefragt', [('Müller', 'Mueller'), ('Mueller', 'Müller'),
                                                 ('Ärztekammer', 'Aerztekammer'), ('Aerztekammer', 'Ärztekammer')])
def test_volltextsuche_findet_die_andere_schreibweise(episodes, gespeichert, gefragt):
    ziel = put(episodes, 'Angebot', f'Das Angebot von {gespeichert} liegt bei.')
    put(episodes, 'Anderes', 'Hier steht nichts davon.', days=1)
    treffer = source_index.suchen(episodes._conn, f'Was schrieb {gefragt}?')
    assert list(treffer.episoden) == [ziel.id]
    assert treffer.ohne_treffer == ('schrieb',)   # der Name gilt als gefunden, nur „schrieb“ steht nirgends


@pytest.mark.parametrize('gespeichert,gefragt', [('Müller', 'Mueller'), ('Mueller', 'Müller')])
def test_wortsuche_findet_die_andere_schreibweise(episodes, gespeichert, gefragt):
    ziel = put(episodes, 'Angebot', f'Das Angebot von {gespeichert} liegt bei.')
    put(episodes, 'Anderes', 'Hier steht nichts davon.', days=1)
    memory = classify(episodes)
    gefunden = memory.search(f'Angebot {gefragt}', limit=5)
    assert [ref['episode_id'] for ref in gefunden['refs']][:1] == [ziel.id]
    nur_name = memory.search(gefragt, limit=5)
    assert [ref['episode_id'] for ref in nur_name['refs']] == [ziel.id]


@pytest.mark.parametrize('gespeichert,gefragt', [('Sabine Müller', 'Frau Mueller'), ('Sabine Mueller', 'Frau Müller'),
                                                 ('Sabine Müller', 'Sabine Mueller')])
def test_person_in_der_frage_mit_anderer_schreibweise(episodes, gespeichert, gefragt):
    e, _ = episodes.record(EpisodeKind.MESSAGE, 'Rechnung', 'Anbei die Rechnung.',
                           Provenance(SourceType.EMAIL, 'ref:1', AT), occurred_at=AT,
                           participants=[f'{gespeichert} <s.mueller@praxis.example>'])
    erwaehnt = personenfrage.erwaehnte(f'Was hat {gefragt} zur Rechnung geschrieben?', episodes)
    assert [k.adresse for k in erwaehnt[0].kandidaten] == ['s.mueller@praxis.example']
    assert e.id in erwaehnt[0].kandidaten[0].quellen


def test_umlautlos_getippte_funktionswoerter_sind_keine_suchwoerter():
    from icarus_memory.working_memory_store import WorkingMemoryStore
    worte, varianten, _ = WorkingMemoryStore._query_terms('Was koennen wir der Akademie liefern?')
    assert 'koennen' not in worte and 'können' not in worte and 'akademie' in worte
    assert source_index.woerter('Was koennen und muessen wir der Akademie liefern?')[0] == ['akademie', 'liefern']
