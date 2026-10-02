"""Fremdprobe 3, Befunde 8 und 13: Sätze über den Hintergrund und wie oft er läuft. Nur synthetische Daten."""
from __future__ import annotations

from datetime import timedelta

from icarus_memory import config, hintergrund
from icarus_memory.scheduler import backup_job


def test_wartesatz_sagt_dass_man_nichts_tun_muss():
    """Befund 8: „Wartet, solange du arbeitest.“ las sich, als solle man aufhören zu arbeiten."""
    for grund in ('nutzer', 'antwort'):
        satz = hintergrund.GRUND_TEXT[grund]
        assert satz.startswith('Kingfisher lernt weiter, sobald') and satz.endswith('du musst nichts tun.')
    assert 'Wartet' not in ' '.join(hintergrund.GRUND_TEXT.values())


def test_vorgabe_haelt_das_briefing_am_selben_vormittag_aktuell():
    """Befund 13: ohne eigene Wahl alle 30 Minuten statt alle vier Stunden."""
    assert config.ScheduleSettings().interval_minutes == 30
    assert config.Settings.from_dict({}).schedule.interval_minutes == 30


def test_alte_vorgabe_ohne_eigene_wahl_wird_zur_neuen():
    # Jedes Speichern schrieb den ganzen Zeitplan; 240 ohne Vermerk war die frühere Vorgabe, keine Wahl.
    plan = config.Settings.from_dict({'schedule': {'enabled': True, 'interval_minutes': 240}}).schedule
    assert plan.interval_minutes == 30 and not plan.interval_gewaehlt


def test_ausdruecklich_gewaehlter_abstand_bleibt():
    gewaehlt = config.Settings.from_dict({'schedule': {'interval_minutes': 240, 'interval_gewaehlt': True}}).schedule
    assert gewaehlt.interval_minutes == 240 and gewaehlt.interval_gewaehlt
    # Ein anderer Wert als die frühere Vorgabe war immer eine Wahl.
    assert config.Settings.from_dict({'schedule': {'interval_minutes': 1440}}).schedule.interval_minutes == 1440


def test_gespeichert_und_wieder_geladen_bleibt_die_wahl(tmp_path):
    einstellungen = config.Settings()
    einstellungen.schedule.interval_minutes = 240
    einstellungen.schedule.interval_gewaehlt = True
    config.save(tmp_path, einstellungen)
    assert config.load(tmp_path).schedule.interval_minutes == 240


def test_wahl_ueber_die_oberflaeche_wird_vermerkt(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    with TestClient(create_app(SelfModelStore(MemoryBackend(), subject_id='test'))) as client:
        # Einschalten schickt den Abstand mit, ändert ihn aber nicht: keine Wahl.
        client.put('/api/v1/schedule', json={'enabled': False, 'interval_minutes': 30})
        assert config.load(tmp_path).schedule.interval_gewaehlt is False
        client.put('/api/v1/schedule', json={'interval_minutes': 240})
        geladen = config.load(tmp_path).schedule
        assert geladen.interval_minutes == 240 and geladen.interval_gewaehlt is True


def test_sicherung_hoechstens_alle_vier_stunden(tmp_path, monkeypatch):
    """Läuft der Zeitplan alle 30 Minuten, darf die Sicherung nicht mitlaufen: 14 Sicherungen wären sonst sieben Stunden."""
    import sqlite3
    from icarus_memory import scheduler
    sqlite3.connect(tmp_path / 'episodes.sqlite3').close()
    sichern = backup_job(tmp_path)
    assert sichern().detail.startswith('kingfisher-')
    assert sichern().detail == 'letzte Sicherung ist jünger als vier Stunden'
    spaeter = scheduler.now() + timedelta(hours=4, minutes=1)
    monkeypatch.setattr(scheduler, 'now', lambda: spaeter)
    assert sichern().detail.startswith('kingfisher-')
