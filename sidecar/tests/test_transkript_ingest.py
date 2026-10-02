"""Der Ordneradapter „transkripte“ (Container und Zeitplan): dieselbe Aufnahme wie am Mac (F3)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.calendar_memory import KalenderGedaechtnis, fenster
from icarus_memory.claims import ClaimStore
from icarus_memory.connectors.calendar import Event
from icarus_memory.episodes import EpisodeState, EpisodeStore
from icarus_memory.ingest import ingest_directory
from icarus_memory.security import SecurityError
from icarus_memory.source_versions import exclude_missing_documents, track_document
from icarus_memory.transkript_zuordnung import Zuordner, Zuordnungen

JETZT = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)
TAG = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)
ANNA = 'Anna Berg <anna.berg@winter.example>'
MEETING = 'Anna Berg: Guten Tag.\nBert Kraus: Hallo.\nAnna Berg: Das Budget steht.\nBert Kraus: Gut.\n'


@pytest.fixture
def welt(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    ablage = Zuordnungen(tmp_path / 'gespraeche.sqlite3')
    von, bis = fenster(JETZT)
    KalenderGedaechtnis(episodes, claims).abgleichen(
        'k', 'Arbeit', [Event(uid='a', summary='Jour fixe Winter', start=TAG, end=TAG + timedelta(hours=1), attendees=[ANNA])],
        von, bis, at=JETZT)
    zuordner = Zuordner(episodes, ablage)
    ordner = tmp_path / 'Transkripte'
    ordner.mkdir()

    def lauf(pfad=None, roots=None):
        return ingest_directory(
            episodes, pfad or ordner, 'transkripte', roots=roots or [tmp_path],
            on_source=lambda root, ref, episode: track_document(episodes, claims, root, ref, episode),
            on_complete=lambda root, adapter, observed: exclude_missing_documents(episodes, claims, root, adapter, observed),
            on_transcript=lambda episode, hinweise: zuordner.vormerken(episode, hinweise))

    yield type('Welt', (), {'episodes': episodes, 'zuordner': zuordner, 'ordner': ordner, 'lauf': staticmethod(lauf),
                            'tmp': tmp_path})
    episodes.close()
    claims.close()
    ablage.close()


def test_ordner_wird_aufgenommen_zugeordnet_und_ist_wiederholbar(welt):
    (welt.ordner / '2026-09-28 14.30 Jour fixe Winter.txt').write_text(MEETING, encoding='utf-8')
    (welt.ordner / 'Notizen.md').write_text('Nur eine Notiz ohne Sprecher.', encoding='utf-8')
    (welt.ordner / 'bild.png').write_bytes(b'\x89PNG')
    bericht = welt.lauf()
    assert bericht.recorded == 2 and bericht.skipped == 1 and not bericht.errors
    eintraege, stand = welt.zuordner.eintraege()
    assert stand['aufgenommen'] == 2 and stand['zugeordnet'] == 1
    # Zweiter Lauf: nichts neu, kein Fehler, obwohl die Zuordnung Metadaten der Quelle ergänzt hat.
    zweiter = welt.lauf()
    assert zweiter.recorded == 0 and zweiter.duplicates == 2 and not zweiter.errors
    assert len(welt.episodes.tagged('transkript')) == 2


def test_nur_freigegebene_ordner_werden_gelesen(welt):
    draussen = welt.tmp / 'Privat'
    draussen.mkdir()
    (draussen / 'geheim.txt').write_text(MEETING, encoding='utf-8')
    with pytest.raises(SecurityError):
        welt.lauf(draussen, roots=[welt.ordner])
    assert welt.episodes.tagged('transkript') == []


def test_entfernte_datei_wird_entzogen(welt):
    datei = welt.ordner / '2026-09-28 14.30 Jour fixe Winter.txt'
    datei.write_text(MEETING, encoding='utf-8')
    welt.lauf()
    (episode,) = welt.episodes.tagged('transkript')
    datei.unlink()
    (welt.ordner / 'anderes.txt').write_text('Eine andere Datei.\nMit Text.', encoding='utf-8')
    bericht = welt.lauf()
    assert bericht.removed == 1
    assert welt.episodes.get(episode.id).state is EpisodeState.IGNORED
    assert welt.zuordner.eintraege()[1]['aufgenommen'] == 1


def test_unlesbare_datei_zaehlt_als_uebersprungen_nie_als_entfernt(welt):
    (welt.ordner / 'kaputt.docx').write_bytes(b'kein zip')
    (welt.ordner / 'gut.txt').write_text(MEETING, encoding='utf-8')
    bericht = welt.lauf()
    assert bericht.recorded == 1 and bericht.skipped == 1
    assert any('kaputt.docx' in grund for grund in bericht.skipped_reasons)
    assert os.path.exists(welt.ordner / 'kaputt.docx')      # die Originaldatei bleibt unberührt
