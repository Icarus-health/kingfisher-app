"""Öffentliche Zugriffe des Episodenspeichers statt Griffen in `_conn`/`_lock` aus fremden Modulen."""
import pytest

from icarus_memory import source_index
from icarus_memory.episodes import CHAT_LOOKUP_TAG, EpisodeKind, EpisodeState, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalStore
from tests.test_context_identity import core  # noqa: F401
from tests.test_source_correction_flow import preview, setup_correction, submit  # noqa: F401


@pytest.fixture
def store(tmp_path):
    speicher = EpisodeStore(tmp_path / 'episodes.sqlite3')
    yield speicher
    speicher.close()


def _neu(store, art, titel, text=None, *, ref='doc:x', tags=None, **kw):
    return store.record(art, titel, text or f'{titel}: Inhalt', Provenance(SourceType.DOCUMENT, source_ref=ref),
                        tags=tags, **kw)[0]


def test_belegbarer_snapshot_nur_fuer_geltende_rohquellen(store):
    gut = _neu(store, EpisodeKind.DOCUMENT, 'Gut')
    ignoriert = _neu(store, EpisodeKind.DOCUMENT, 'Weg', ref='doc:y')
    store.ignore(ignoriert.id)
    frage = _neu(store, EpisodeKind.DOCUMENT, 'Frage', ref='doc:z', tags=[CHAT_LOOKUP_TAG])
    beobachtung = _neu(store, EpisodeKind.OBSERVATION, 'Beobachtung', ref='doc:o')
    assert store.belegbarer_snapshot(gut.id).episode.id == gut.id
    for nicht in (ignoriert, frage, beobachtung):
        assert store.belegbarer_snapshot(nicht.id) is None
    assert store.belegbarer_snapshot('gibt-es-nicht') is None
    assert store.belegbarer_snapshot(gut.id, max_bytes=10) is None  # zu groß


def test_quellen_kopf_zaehlt_alle_rohquellen_und_zeigt_kopfdaten(store):
    a = _neu(store, EpisodeKind.MESSAGE, 'A')
    b = _neu(store, EpisodeKind.DOCUMENT, 'B', ref='doc:b')
    _neu(store, EpisodeKind.OBSERVATION, 'Kein Beleg', ref='doc:c')
    store.ignore(b.id)
    gesamt, kopf = store.quellen_kopf(1)
    assert gesamt == 2 and len(kopf) == 1
    _, kopf = store.quellen_kopf()
    assert {z['id']: z['state'] for z in kopf} == {a.id: 'new', b.id: 'ignored'}
    assert set(kopf[0]) == {'id', 'digest', 'state', 'source_truncated'}


def test_nachrichten_mit_text_und_termine_nach_herkunft(store):
    eigene = _neu(store, EpisodeKind.MESSAGE, 'Eine', 'Von anna@firma.example', ref='mail:1')
    andere = _neu(store, EpisodeKind.MESSAGE, 'Andere', 'Auch ANNA@firma.example', ref='mail:2')
    _neu(store, EpisodeKind.DOCUMENT, 'Dokument', 'anna@firma.example', ref='doc:3')
    treffer = store.nachrichten_mit_text('anna@firma.example', ausser=eigene.id, limit=10)
    assert [e.id for e in treffer] == [andere.id]
    termin = _neu(store, EpisodeKind.EVENT, 'Termin', ref='calendar:mac:UID_1')
    assert store.termine_nach_herkunft('%UID\\_1') == [(termin.id, 'Termin: Inhalt', 'calendar:mac:UID_1')]
    assert store.termine_nach_herkunft('%UIDx1') == []
    store.ignore(termin.id)
    assert store.termine_nach_herkunft('%UID\\_1') == []


def test_aussagen_ab(store, tmp_path):
    assert store.quellen_mit_aussagen_ab('', 5) == []
    vorschlaege = ProposalStore(tmp_path / 'proposals.sqlite3')
    try:
        assert vorschlaege.angenommene_aussagen_ab('', 5) == []
        vorschlaege.commit()
    finally:
        vorschlaege.close()


def test_berichtigung_ist_sofort_im_suchindex(setup_correction):  # noqa: F811
    app, client, _provider, source = setup_correction
    zustand = preview(client, source)
    antwort = submit(client, source, zustand)
    assert antwort.status_code == 201, antwort.text
    berichtigung = antwort.json()['episode_id']
    with app.state.episodes._lock:
        gefunden = source_index.suchen(app.state.episodes._conn, 'Freigabe fehlt noch')
    assert berichtigung in gefunden.episoden
