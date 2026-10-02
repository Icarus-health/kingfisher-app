"""Die vier Leseweisen für Zeitangaben und die Monatsnamen (datumstext.py)."""
from datetime import datetime, timezone

import pytest

from icarus_memory import briefing, datumstext, personen
from icarus_memory.datumstext import (
    MONATE, iso_lesen, iso_lesen_streng, iso_versuchen, iso_versuchen_utc, tag_und_monat,
)

UTC = timezone.utc


def test_iso_lesen_versteht_z_und_leer():
    assert iso_lesen('2026-09-29T07:30:00Z') == datetime(2026, 9, 29, 7, 30, tzinfo=UTC)
    assert iso_lesen(None) is None and iso_lesen('') is None
    with pytest.raises(ValueError):
        iso_lesen('gestern')


def test_streng_wirft_auch_bei_leer():
    assert iso_lesen_streng('2026-09-29T07:30:00+00:00').hour == 7
    with pytest.raises(ValueError):
        iso_lesen_streng('')


def test_versuchen_wirft_nie_und_laesst_zeitpunkte_unveraendert():
    naiv = datetime(2026, 9, 29, 7, 30)
    assert iso_versuchen(naiv) is naiv
    assert iso_versuchen('unsinn') is None and iso_versuchen(None) is None and iso_versuchen('') is None
    assert iso_versuchen('2026-09-29T07:30:00Z') == datetime(2026, 9, 29, 7, 30, tzinfo=UTC)


def test_versuchen_utc_gibt_zeitpunkten_ohne_zone_utc():
    assert iso_versuchen_utc(datetime(2026, 9, 29, 7, 30)).tzinfo is UTC
    assert iso_versuchen_utc('2026-09-29T07:30:00').tzinfo is UTC
    assert iso_versuchen_utc(5) is None and iso_versuchen_utc('') is None and iso_versuchen_utc('x') is None


def test_monatsnamen_gibt_es_nur_einmal():
    assert len(MONATE) == 12 and MONATE[2] == 'März'
    assert briefing.MONATE is datumstext.MONATE and personen.MONATE is datumstext.MONATE
    assert tag_und_monat(datetime(2026, 8, 7)) == '7. August'


def test_alle_module_teilen_die_monatsnamen_und_monatsnummern():
    from icarus_memory import bedeutungen, calendar_memory, fristen
    assert calendar_memory.MONATE is datumstext.MONATE
    assert bedeutungen._MONATE is datumstext.MONAT_NUMMER
    # Fristen lesen zusätzlich Kürzel, aber jeder Monatsname kommt aus der einen Tabelle.
    assert all(fristen._MONATE[name] == nummer for name, nummer in datumstext.MONAT_NUMMER.items())
    assert fristen._MONATE['okt'] == 10 and 'okt' not in datumstext.MONAT_NUMMER
    for nummer, name in enumerate(datumstext.MONATE, 1):
        assert datumstext.MONAT_NUMMER[name.casefold()] == nummer


def test_lage_und_meldungen_lesen_zeiten_wie_datumstext():
    from icarus_memory import lage, welt_meldungen
    assert lage._zeit is iso_versuchen_utc
    jetzt = datetime(2026, 9, 29, tzinfo=UTC)
    assert welt_meldungen._jung('2026-09-01T00:00:00Z', jetzt) is True
    assert welt_meldungen._jung('2026-01-01T00:00:00', jetzt) is False  # ohne Zone: UTC, älter als 90 Tage
    assert welt_meldungen._jung('unsinn', jetzt) is False
    assert welt_meldungen._am('2026-08-07T10:00:00Z') == ' vom 7. August'
    assert welt_meldungen._am(None) == '' and welt_meldungen._am('unsinn') == ''


# Diese Leser bleiben eigene, weil ihre Semantik abweicht (Grund je Datei). Jeder weitere
# „ISO mit Z lesen“-Aufruf gehört in datumstext.py.
BEWUSST_EIGEN = {
    'folder_sync.py': 'Frische: TypeError/AttributeError zählen als unfrisch',
    'google_calendar.py': 'Terminfelder des Anbieters mit eigener Ganztagsbehandlung',
    'ingest.py': 'Metadaten aus Dateien: strip, erste lesbare Angabe, sonst Dateiname',
    'relations.py': 'wirft eigene Meldungen je Feldname',
    'transkript_zuordnung.py': 'naive Zeiten gelten in der Zeitzone des Nutzers, nicht UTC',
    'welt_feeds.py': 'RFC-822 zuerst, ISO als Rückfall',
    'world_monitor.py': 'Frische in UTC; naive und unlesbare Zeiten gelten als veraltet',
}


def test_kein_weiterer_z_leser_ausser_den_benannten():
    import re
    from pathlib import Path
    muster = re.compile(r"""\.replace\(\s*['"]Z['"]\s*,\s*['"]\+00:00['"]\s*\)""")
    funde = []
    for datei in sorted(Path(datumstext.__file__).parent.glob('*.py')):
        if datei.name == 'datumstext.py' or datei.name in BEWUSST_EIGEN:
            continue
        if muster.search(datei.read_text(encoding='utf-8')):
            funde.append(datei.name)
    assert not funde, f'ISO mit Z wird nur in datumstext.py gelesen (sonst in BEWUSST_EIGEN mit Grund): {funde}'


def test_keine_zweite_monatsliste():
    import re
    from pathlib import Path
    muster = re.compile(r"""['"]Januar['"]\s*,\s*['"]Februar['"]""")
    funde = [d.name for d in sorted(Path(datumstext.__file__).parent.glob('*.py'))
             if d.name != 'datumstext.py' and muster.search(d.read_text(encoding='utf-8'))]
    assert not funde, f'Die Monatsnamen stehen nur in datumstext.MONATE: {funde}'
