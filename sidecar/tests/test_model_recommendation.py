"""Modellempfehlung je Speicherstufe: reine Tabelle, keine Netzzugriffe."""
from datetime import date

import pytest

from icarus_memory.device_profile import save_device_profile
from icarus_memory.model_recommendation import (
    KATALOG, KATALOG_STAND, ROLLEN, STUFEN, Geraet, empfehle, empfehle_alle, eintrag_fuer,
    geraet_aus_profil, normalisiere, stufe_fuer,
)


def mac(gb):
    return Geraet("macos", "Apple M2 Max", float(gb))


def test_katalog_ist_datiert_und_vollstaendig():
    date.fromisoformat(KATALOG_STAND)
    for rolle in ROLLEN:
        for stufe in STUFEN:
            zeilen = [e for e in KATALOG if e.rolle == rolle and stufe in e.stufen and not e.alternative]
            assert len(zeilen) == 1, (rolle, stufe)  # genau eine Vorauswahl je Rolle und Stufe
    for e in KATALOG:
        assert e.begruendung.endswith(".") and e.name and e.groesse_gb > 0
        assert e.speicher_gb >= e.groesse_gb  # Betrieb braucht mehr als die Datei


@pytest.mark.parametrize("gb", STUFEN)
@pytest.mark.parametrize("rolle", ROLLEN)
def test_vorauswahl_meldet_den_tatsaechlichen_reservebedarf(gb, rolle):
    empfehlung = empfehle(mac(gb), rolle)
    assert empfehlung.stufe == gb
    assert empfehlung.passt_vermutlich == (empfehlung.modell.speicher_gb <= mac(gb).modellbudget_gb)
    assert empfehlung.modell.rolle == rolle


def test_32_gb_mac_bekommt_moe_allrounder_und_kleines_fragemodell():
    # Die Tabelle je Rolle; ob alle zusammen passen, prüft `empfehle_alle` (tests/test_orchester.py).
    alle = {rolle: empfehle(mac(32), rolle) for rolle in ROLLEN}
    assert alle["antwort"].modell.art == "moe" and alle["antwort"].modell.name.startswith("qwen3.6:35b")
    assert alle["hintergrund"].modell.name == "qwen3.5:9b"
    # Ausweichmöglichkeiten: dichtes ~27B und ein kleineres dichtes Modell, das tagsüber Speicher freilässt
    assert [a.art for a in alle["antwort"].alternativen] == ["dicht", "dicht"]
    assert any(a.name == "gemma4:12b" for a in alle["antwort"].alternativen)
    assert any(a.name == "qwen3.5:27b" for a in alle["hintergrund"].alternativen)
    assert alle["frage"].modell.art == "klein" and alle["frage"].modell.groesse_gb <= 8
    assert alle["einbettung"].modell.name == "bge-m3"


def test_32gb_mac_background_default_stays_within_the_qwen35_9b_family():
    for gb in (16, 24, 32):
        assert empfehle(mac(gb), "hintergrund").modell.name == "qwen3.5:9b"
    at_32 = empfehle(mac(32), "hintergrund")
    assert "qwen3.5:27b" in {a.name for a in at_32.alternativen}
    assert empfehle(mac(64), "hintergrund").modell.name == "qwen3.6:35b"


def test_measured_nemotron_and_tev1_sizes_are_reflected_conservatively():
    nemotron = eintrag_fuer("hintergrund", "nemotron-3.5-lightning:30b")
    tev1 = eintrag_fuer("pruefung", "tev1:4b")
    assert nemotron.groesse_gb >= 25.43 and nemotron.speicher_gb >= 26.7
    assert 32 not in nemotron.stufen and nemotron.alternative
    assert tev1.groesse_gb >= 4.48 and tev1.speicher_gb >= 4.686


def test_kleine_geraete_bekommen_keine_grossen_modelle():
    for gb in (8, 16):
        for rolle in ROLLEN:
            assert empfehle(mac(gb), rolle).modell.speicher_gb <= gb * 0.85
    assert empfehle(mac(8), "antwort").modell.groesse_gb < 5


def test_groessere_geraete_bekommen_nie_ein_kleineres_hintergrundmodell():
    groessen = [empfehle(mac(gb), "hintergrund").modell.groesse_gb for gb in STUFEN]
    assert groessen == sorted(groessen)


def test_stufen_rundung_und_unbekanntes_geraet():
    assert stufe_fuer(mac(31.9)) == 32
    assert stufe_fuer(mac(28)) == 24
    assert stufe_fuer(mac(4)) == 8
    unbekannt = Geraet()
    assert not unbekannt.bekannt and stufe_fuer(unbekannt) == 8  # im Zweifel die sichere Stufe
    assert empfehle(unbekannt, "antwort").modell.groesse_gb < 5


def test_getrennter_grafikspeicher_zaehlt_ausser_am_mac():
    assert stufe_fuer(Geraet("windows", None, 64.0, 8.0)) == 8
    assert stufe_fuer(Geraet("windows", None, 64.0, 24.0)) == 24
    assert stufe_fuer(Geraet("macos", None, 64.0, 8.0)) == 64  # einheitlicher Speicher


def test_profil_wird_plattformneutral_gelesen(tmp_path):
    from icarus_memory.device_profile import load_device_profile
    for plattform in ("macos", "windows", "linux"):
        profil = save_device_profile(tmp_path, {"platform": plattform, "chip": "Chip X", "memory_bytes": 32 * 1024**3})
        geraet = geraet_aus_profil(profil)
        assert (geraet.plattform, geraet.arbeitsspeicher_gb, stufe_fuer(geraet)) == (plattform, 32.0, 32)
        assert load_device_profile(tmp_path) == profil
    profil = save_device_profile(tmp_path, {"platform": "windows", "chip": "x", "memory_bytes": 64 * 1024**3,
                                            "gpu_memory_bytes": 12 * 1024**3})
    assert stufe_fuer(geraet_aus_profil(profil)) == 8
    with pytest.raises(ValueError):
        save_device_profile(tmp_path, {"platform": "plan9", "chip": "x", "memory_bytes": 32 * 1024**3})
    assert geraet_aus_profil(load_device_profile(tmp_path / "leer")).plattform == "unbekannt"


def test_namen_und_unbekannte_rolle():
    assert normalisiere("bge-m3:latest") == normalisiere("bge-m3") == "bge-m3"
    assert eintrag_fuer("einbettung", "bge-m3:latest").name == "bge-m3"
    assert eintrag_fuer("frage", "bge-m3") is None
    with pytest.raises(KeyError):
        empfehle(mac(32), "nachrichten")
