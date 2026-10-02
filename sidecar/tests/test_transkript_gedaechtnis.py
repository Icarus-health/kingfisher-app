"""Mitschriften fließen in Suche, Einordnung, Bezüge und Akten wie jede andere Quelle (F3, Punkt 4)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from icarus_memory import source_index
from icarus_memory.calendar_memory import KalenderGedaechtnis, fenster
from icarus_memory.claims import ClaimStore
from icarus_memory.connectors.calendar import Event
from icarus_memory.episodes import EpisodeKind, EpisodeState
from icarus_memory.model import Provenance, SourceType
from icarus_memory.source_versions import track_source
from icarus_memory.transkript_eingang import aufnehmen, lesen
from icarus_memory.transkript_zuordnung import Zuordner, Zuordnungen
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_bezuege import welt  # noqa: F401 - Fixture (Episoden, Arbeitsbereich, Bezüge)

JETZT = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)
TAG = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)
ANNA = 'Anna Berg <anna.berg@winter-catering.example>'
MEETING = ('Anna Berg: Guten Tag zusammen.\nLea Hartmann: Wir sprechen über das Budget für den Sommerempfang.\n'
           'Anna Berg: Das Budget beträgt 40.000 Euro.\nLea Hartmann: Einverstanden.\n')
SACHE = 'person:a:anna.berg@winter-catering.example'


def _aufnehmen(episodes, tmp_path, name, text=MEETING, mit_termin=True):
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    if mit_termin:
        von, bis = fenster(JETZT)
        KalenderGedaechtnis(episodes, claims).abgleichen(
            'k', 'Arbeit', [Event(uid='a', summary='Jour fixe Winter', start=TAG, end=TAG + timedelta(hours=1),
                                  attendees=[ANNA])], von, bis, at=JETZT)
    zuordner = Zuordner(episodes, Zuordnungen(tmp_path / 'gespraeche.sqlite3'))
    gelesen = lesen(name, text.encode())
    episode, _ = aufnehmen(episodes, gelesen, Provenance(source_type=SourceType.DOCUMENT, source_ref=f'transkript:{name}'),
                           f'transkript:{name}')
    track_source(episodes, claims, f'transkript:{name}', episode)
    zuordner.vormerken(episode, gelesen.hinweise())
    return episode, claims


def test_suche_findet_die_mitschrift(welt, tmp_path):
    episodes, _, _ = welt
    episode, _ = _aufnehmen(episodes, tmp_path, '2026-09-28 14.30 Jour fixe Winter.txt')
    assert episode.kind is EpisodeKind.DOCUMENT and 'transkript' in episode.tags
    gefunden = source_index.suchen(episodes._conn, 'Budget Sommerempfang')
    assert episode.id in list(gefunden.episoden)


def test_einordnung_sieht_die_mitschrift_wie_jede_quelle(welt, tmp_path):
    episodes, _, _ = welt
    episode, _ = _aufnehmen(episodes, tmp_path, '2026-09-28 14.30 Jour fixe Winter.txt')
    offen = [snapshot.episode.id for snapshot in WorkingMemoryStore(episodes).pending(limit=50)]
    assert episode.id in offen
    assert episode.id in [e.id for e in episodes.analysis_batch()]


def test_zugeordneter_sprecher_ist_ein_ankerbezug_zur_person(welt, tmp_path):
    episodes, _, bezuege = welt
    episode, _ = _aufnehmen(episodes, tmp_path, '2026-09-28 14.30 Jour fixe Winter.txt')
    bezuege.aktualisieren()
    belegt = {b['sache']: b['grundlagen'] for b in bezuege.bezuege_der_quelle(episode.id)['bezuege']}
    assert belegt.get(SACHE) == ['anker']
    assert episode.id in [q['episode_id'] for q in bezuege.quellen_von(SACHE)]


def test_mitschrift_ohne_termin_bleibt_eine_gewoehnliche_quelle_ohne_erfundene_person(welt, tmp_path):
    episodes, _, bezuege = welt
    episode, _ = _aufnehmen(episodes, tmp_path, 'Aufnahme.txt', mit_termin=False)
    bezuege.aktualisieren()
    daten = bezuege.bezuege_der_quelle(episode.id)
    assert not any(b['sache'].startswith('person:a:') for b in daten['bezuege'])   # kein Anker ohne Adresse
    assert episode.id in [e.id for e in episodes.tagged('transkript')]


def test_entzogene_mitschrift_verschwindet_aus_bezuegen_und_suche(welt, tmp_path):
    episodes, _, bezuege = welt
    episode, _ = _aufnehmen(episodes, tmp_path, '2026-09-28 14.30 Jour fixe Winter.txt')
    bezuege.aktualisieren()
    assert bezuege.bezuege_der_quelle(episode.id) is not None
    episodes.ignore(episode.id, grund='ordner')
    bezuege.aktualisieren()
    assert bezuege.bezuege_der_quelle(episode.id) is None
    assert episode.id not in [q['episode_id'] for q in bezuege.quellen_von(SACHE)]
    assert episode.id not in list(source_index.suchen(episodes._conn, 'Budget Sommerempfang').episoden)
    assert episodes.get(episode.id).state is EpisodeState.IGNORED      # die Episode bleibt als Nachweis
