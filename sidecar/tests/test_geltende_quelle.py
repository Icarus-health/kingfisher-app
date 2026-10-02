"""Es gibt genau eine Definition der „geltenden“ Quelle (`episodes.py`).

Zwei Sperren:

1. Statisch: Kein anderes Modul darf die Listen (Arten, Zustände, Prüfung der
   aktuellen Fassung) als Kopie in SQL oder Python hart kodieren.
2. Dynamisch: Ändert man die Definition an der einen Stelle, folgen alle
   Nutzer, ohne dass eine zweite Stelle angefasst wird. Eine neue Art oder ein
   neuer Zustand braucht also genau eine Änderung.
"""
import re
import sys
from pathlib import Path

import pytest

from icarus_memory import episodes as episodes_modul
from icarus_memory import source_search
from icarus_memory.episodes import (
    AUSGEBLENDETE_ZUSTAENDE, IGNORIERTE_ZUSTAENDE, QUELLEN_ARTEN, EpisodeKind, EpisodeState,
    EpisodeStore, sql_geltend, sql_nicht_ausgeblendet, sql_sichtbar,
)
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore

PAKET = Path(episodes_modul.__file__).parent

# Muster, die außerhalb von episodes.py nichts zu suchen haben. Jedes steht für
# eine Kopie der Definition. `OLD.state`/`NEW.state` in Triggern (DDL) sind
# keine Abfrage und ausgenommen.
VERBOTEN = {
    'harte Artenliste in SQL': re.compile(r"kind\s+IN\s*\(\s*'message'", re.I),
    'harte Artenliste mit Platzhaltern': re.compile(r"kind\s+IN\s*\(\?,\s*\?(,\s*\?)?\)", re.I),
    'Arten als Platzhalterliste aus der Definition': re.compile(r"for\s+_\s+in\s+(ROHQUELLEN|QUELLEN_ARTEN)"),
    'Art als Einzelvergleich mit Zustandsfilter im selben Text': re.compile(r"kind\s*=\s*'message'\s+AND\s+(e\.)?state", re.I),
    'harter Ignoriert-Filter': re.compile(r"(?<!OLD\.)(?<!NEW\.)\bstate\s*(!=|<>)\s*'ignored'", re.I),
    'harter Zustandsfilter': re.compile(r"state\s+NOT\s+IN\s*\(\s*'ignored'", re.I),
    'Zustandsmenge im Code': re.compile(r"\{\s*EpisodeState\.IGNORED\s*,\s*EpisodeState\.ARCHIVED\s*\}"),
    'Artenpaar im Code': re.compile(r"\(\s*EpisodeKind\.MESSAGE\s*,\s*EpisodeKind\.DOCUMENT\s*\)"),
    'eigene Prüfung der aktuellen Fassung': re.compile(r"FROM\s+source_heads\s+h\b", re.I),
    'eigene Prüfung der aktuellen Fassung (Kurzform)': re.compile(r"episode_id\s+FROM\s+source_heads", re.I),
}


def test_keine_kopie_der_definition_ausserhalb_von_episodes():
    funde = []
    for datei in sorted(PAKET.rglob('*.py')):
        if datei.name == 'episodes.py':
            continue
        text = datei.read_text(encoding='utf-8')
        for name, muster in VERBOTEN.items():
            for treffer in muster.finditer(text):
                zeile = text.count('\n', 0, treffer.start()) + 1
                funde.append(f'{datei.relative_to(PAKET)}:{zeile}: {name}')
    assert not funde, ('Die geltende Quelle wird nur in episodes.py definiert '
                       '(QUELLEN_ARTEN, sql_geltend, …):\n' + '\n'.join(funde))


@pytest.fixture
def store(tmp_path):
    speicher = EpisodeStore(tmp_path / 'episodes.sqlite3')
    yield speicher
    speicher.close()


def _neu(store, art, titel, *, key='', state=None, projekt=None):
    episode, _ = store.record(art, titel, f'{titel}: Mainzer Angebot', Provenance(SourceType.DOCUMENT),
                              project_id=projekt, source_key=key)
    if state is not None:
        episode.state = state
        store._put(episode)
    return episode


@pytest.fixture
def bestand(store):
    """Von jeder Sorte eine: geltend, ignoriert, archiviert, überholt, andere Art."""
    e = {}
    e['nachricht'] = _neu(store, EpisodeKind.MESSAGE, 'Nachricht', projekt='p1')
    e['dokument'] = _neu(store, EpisodeKind.DOCUMENT, 'Dokument', projekt='p1')
    e['ignoriert'] = _neu(store, EpisodeKind.MESSAGE, 'Ignoriert', projekt='p1', state=EpisodeState.IGNORED)
    e['archiviert'] = _neu(store, EpisodeKind.MESSAGE, 'Archiviert', projekt='p1', state=EpisodeState.ARCHIVED)
    e['alt'] = _neu(store, EpisodeKind.MESSAGE, 'Alt', key='quelle-a', projekt='p1')
    store.advance_source_head('quelle-a', None, e['alt'].id)
    e['neu'] = store.record(EpisodeKind.MESSAGE, 'Neu', 'Neu: Mainzer Angebot, geändert',
                            Provenance(SourceType.DOCUMENT), project_id='p1', source_key='quelle-a')[0]
    store.advance_source_head('quelle-a', e['alt'].id, e['neu'].id)
    # Ein Termin ist Rohquelle (wie Nachricht und Dokument); eine Beobachtung ist es nie.
    e['termin'] = _neu(store, EpisodeKind.EVENT, 'Termin', projekt='p1')
    e['ereignis'] = _neu(store, EpisodeKind.OBSERVATION, 'Beobachtung', projekt='p1')
    return e


def _ids(zeilen):
    return {z[0] for z in zeilen}


def _geltend_laut_sql(store):
    with store._lock:
        return _ids(store._conn.execute(f'SELECT id FROM episodes WHERE {sql_geltend()}').fetchall())


def test_definition_liefert_das_erwartete_bild(store, bestand):
    assert _geltend_laut_sql(store) == {bestand[n].id for n in ('nachricht', 'dokument', 'termin', 'archiviert', 'neu')}
    with store._lock:
        sichtbar = _ids(store._conn.execute(f'SELECT id FROM episodes WHERE {sql_sichtbar()}').fetchall())
    assert sichtbar == {bestand[n].id for n in ('nachricht', 'dokument', 'termin', 'alt', 'neu')}


def _nutzer(store):
    """Alle Nutzer der Definition, jeder liefert die Ids der Quellen, die er sieht."""
    memory = WorkingMemoryStore(store)
    rohquellen = {e.id for e in store.analysis_batch(limit=200)}
    return {
        'usable_ids': lambda ids: store.usable_ids(ids),
        'mentions': {m['id'] for m in store.mentions('Mainzer')[0]},
        'project_heads': {h['id'] for h in store.project_heads('p1')},
        'source_search': set(source_search.search(store, 'mainzer')['ids']),
        'analysis_batch': rohquellen,
        'working_memory_pending': {s.episode.id for s in memory.pending(limit=200)},
        'working_memory_progress': memory.progress()['total'],
    }


def test_alle_nutzer_folgen_der_einen_definition(store, bestand):
    n = _nutzer(store)
    geltend = {bestand[k].id for k in ('nachricht', 'dokument', 'termin', 'archiviert', 'neu')}
    alle = {e.id for e in bestand.values()}
    # Geltend: Rohquelle, nicht ignoriert, aktuelle Fassung.
    assert n['mentions'] == geltend
    assert n['project_heads'] == geltend
    assert n['source_search'] == geltend
    assert n['working_memory_progress'] == len(geltend)
    # Ohne Prüfung der aktuellen Fassung (Durchlauf über alle Fassungen), aber
    # mit denselben Arten und Zuständen.
    ohne_fassung = geltend | {bestand['alt'].id}
    assert n['analysis_batch'] == ohne_fassung
    assert n['working_memory_pending'] <= ohne_fassung
    # usable_ids: gleiche Zustands- und Fassungsprüfung, gleich welcher Art.
    assert n['usable_ids'](alle) == geltend | {bestand['ereignis'].id}


def _ersetze_ueberall(monkeypatch, name, neu):
    """Setzt eine Konstante in episodes.py und in jedem Modul, das sie importiert hat."""
    original = getattr(episodes_modul, name)
    for modul in list(sys.modules.values()):
        if getattr(modul, '__name__', '').startswith('icarus_memory') and getattr(modul, name, None) is original:
            monkeypatch.setattr(modul, name, neu)


def test_neue_art_an_einer_stelle_genuegt(monkeypatch, store, bestand):
    vorher = _nutzer(store)
    ereignis = bestand['ereignis'].id
    assert ereignis not in vorher['mentions']
    _ersetze_ueberall(monkeypatch, 'QUELLEN_ARTEN', (*QUELLEN_ARTEN, EpisodeKind.OBSERVATION))
    nachher = _nutzer(store)
    # Der Suchindex (`source_search`) ist ein gespeicherter, abgeleiteter Bestand: Er nimmt eine neue Art
    # erst nach Neuaufbau auf. Seine Artenliste (`source_index.ARTEN`, eine Kopie wegen des
    # Importzyklus) sperrt `test_suchindex_arten_gleich_definition`.
    for name in ('mentions', 'project_heads', 'analysis_batch'):
        assert ereignis in nachher[name], f'{name} folgt der Definition nicht'
    # Die Arbeitsliste des Arbeitsgedächtnisses schreitet mit einem Zeiger fort; darum gezielt fragen.
    assert [s.episode.id for s in WorkingMemoryStore(store).pending(limit=200, episode_ids=[ereignis])] == [ereignis], \
        'working_memory_pending folgt der Definition nicht'
    assert nachher['working_memory_progress'] == vorher['working_memory_progress'] + 1


def test_neuer_zustand_an_einer_stelle_genuegt(monkeypatch, store, bestand):
    vorher = _nutzer(store)
    archiviert = bestand['archiviert'].id
    assert archiviert in vorher['mentions']
    # Archiviertes würde zusätzlich ignoriert: alle Nutzer der Ignoriert-Definition folgen.
    _ersetze_ueberall(monkeypatch, 'IGNORIERTE_ZUSTAENDE', frozenset({*IGNORIERTE_ZUSTAENDE, EpisodeState.ARCHIVED}))
    nachher = _nutzer(store)
    for name in ('mentions', 'project_heads', 'source_search', 'analysis_batch'):
        assert archiviert not in nachher[name], f'{name} folgt der Definition nicht'
    assert nachher['working_memory_progress'] == vorher['working_memory_progress'] - 1


def test_ausgeblendet_umfasst_ignoriert_und_archiviert():
    assert IGNORIERTE_ZUSTAENDE <= AUSGEBLENDETE_ZUSTAENDE
    assert 'archived' in sql_nicht_ausgeblendet() and 'ignored' in sql_nicht_ausgeblendet()


def test_suchindex_arten_gleich_definition():
    """`source_index` kann `episodes` nicht importieren (Zyklus) und führt zwei Werte als benannte Kopie."""
    from icarus_memory import source_index
    assert set(source_index.ARTEN) == {art.value for art in QUELLEN_ARTEN}
    assert source_index.CHAT_LOOKUP_TAG == episodes_modul.CHAT_LOOKUP_TAG
    assert source_index._verwendbar() == sql_geltend('e')
