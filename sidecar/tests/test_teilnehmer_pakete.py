"""Beteiligte zu sehr vielen Adressen: in Paketen abgefragt, jede Quelle zählt einmal.

Mit 10.000 Quellen fragte das Logbuch die Namen aller Akten auf einmal ab; die eine OR-Kette über
tausende Adressen ließ SQLite mit „Expression tree is too large“ abbrechen (Fund aus der Messlatte, M4).
"""
from datetime import datetime, timezone

from icarus_memory import episodes as episodes_modul
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType


def _mail(store, titel, beteiligte):
    episode, _ = store.record(
        EpisodeKind.MESSAGE, titel, 'Kurzer Text.',
        Provenance(SourceType.EMAIL, source_ref=f'work:<{titel}@example.invalid>'),
        participants=beteiligte, occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    return episode


def test_tausende_adressen_brechen_nicht_ab(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    _mail(store, 'Gruss', ['Anna Keller <anna@agentur.example>'])
    adressen = [f'person{i}@rauschen.example' for i in range(3000)] + ['anna@agentur.example']
    ergebnis = store.participants_for_addresses(adressen)
    assert len(ergebnis) == 3001
    assert ergebnis['anna@agentur.example']['namen'] == {'Anna Keller <anna@agentur.example>': 1}


def test_eine_quelle_ueber_mehrere_pakete_zaehlt_einmal(tmp_path, monkeypatch):
    monkeypatch.setattr(episodes_modul, 'ADRESSEN_JE_ABFRAGE', 1)
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    _mail(store, 'Runde', ['Anna Keller <anna@agentur.example>', 'Ben Roth <ben@druck.example>'])
    ergebnis = store.participants_for_addresses(['anna@agentur.example', 'ben@druck.example'])
    assert ergebnis['anna@agentur.example']['namen'] == {'Anna Keller <anna@agentur.example>': 1}
    assert ergebnis['ben@druck.example']['namen'] == {'Ben Roth <ben@druck.example>': 1}
    assert len(ergebnis['anna@agentur.example']['quellen']) == 1
