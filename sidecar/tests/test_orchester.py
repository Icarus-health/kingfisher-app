"""Speicherbedarf des Orchesters: Tag, Nacht, Festplatte; Ausweichwahl; Alltagssätze."""
import pytest

from icarus_memory.model_recommendation import (
    KATALOG, ROLLEN, Geraet, eintrag_fuer, empfehle, empfehle_alle, festplatte_reicht, orchester_bedarf,
    orchester_hinweise,
)

TITEL = {"frage": "Fragen verstehen", "antwort": "Antworten formulieren", "pruefung": "Sätze gegenprüfen",
         "hintergrund": "Im Hintergrund ordnen", "einbettung": "Bedeutungen finden"}


def mac(gb, frei=None):
    return Geraet(plattform="macos", chip="Apple M2 Max", arbeitsspeicher_gb=float(gb), festplatte_frei_gb=frei)


def wahl(**modelle):
    return {rolle: eintrag_fuer(rolle, name) for rolle, name in modelle.items()}


def test_tag_ist_antwort_frage_einbettung_nacht_ist_hintergrund_und_einbettung():
    auswahl = wahl(frage="qwen3.5:4b", antwort="gemma4:12b", hintergrund="qwen3.5:27b", einbettung="bge-m3")
    b = orchester_bedarf(auswahl, mac(32, 100))
    assert b["tag_gb"] == 6 + 10 + 2 and b["nacht_gb"] == 20 + 2
    assert b["festplatte_gb"] == pytest.approx(3.4 + 8.0 + 17.0 + 1.2)
    assert b["passt_tag"] is True and b["passt_nacht"] is True and b["passt_festplatte"] is True
    assert b["nutzbar_gb"] == pytest.approx(32 * 0.85)


def test_dasselbe_modell_in_zwei_rollen_wird_einmal_gezaehlt():
    auswahl = wahl(frage="qwen3.5:4b", antwort="qwen3.5:4b", hintergrund="qwen3.5:4b", einbettung="bge-m3")
    b = orchester_bedarf(auswahl, mac(8, 50))
    assert b["tag_gb"] == 6 + 2 and b["nacht_gb"] == 6 + 2
    assert b["festplatte_gb"] == pytest.approx(3.4 + 1.2)


def test_passt_nicht_wenn_die_summe_die_grenze_ueberschreitet_obwohl_jedes_einzeln_passt():
    auswahl = wahl(frage="qwen3.5:9b", antwort="qwen3.6:35b", hintergrund="qwen3.6:35b", einbettung="bge-m3")
    b = orchester_bedarf(auswahl, mac(32, 500))
    assert all(e.speicher_gb <= 32 * 0.85 for e in auswahl.values())  # einzeln passen alle
    assert b["tag_gb"] == 39 and b["passt_tag"] is False
    assert b["nacht_gb"] == 29 and b["passt_nacht"] is False


def test_festplatte_mit_reserve_und_nur_was_noch_fehlt():
    auswahl = wahl(frage="qwen3.5:4b", antwort="gemma4:12b", hintergrund="gemma4:12b", einbettung="bge-m3")
    gesamt = 3.4 + 8.0 + 1.2
    knapp = orchester_bedarf(auswahl, mac(32, gesamt + 1))  # 1 GB Luft ist weniger als die Reserve
    assert knapp["passt_festplatte"] is False
    genug = orchester_bedarf(auswahl, mac(32, gesamt + 2.5))
    assert genug["passt_festplatte"] is True
    schon_da = orchester_bedarf(auswahl, mac(32, 3), vorhanden=["gemma4:12b", "bge-m3:latest"])
    assert schon_da["festplatte_gb"] == pytest.approx(gesamt) and schon_da["festplatte_noch_gb"] == pytest.approx(3.4)
    assert schon_da["passt_festplatte"] is False  # 3,4 GB plus Reserve in 3 GB freiem Platz


def test_unbekanntes_ist_none_nie_geraten():
    auswahl = wahl(frage="qwen3.5:4b", antwort="gemma4:12b", hintergrund="gemma4:12b", einbettung="bge-m3")
    b = orchester_bedarf(auswahl, Geraet())
    assert b["passt_tag"] is None and b["passt_nacht"] is None and b["passt_festplatte"] is None
    assert b["tag_gb"] == 18 and b["festplatte_frei_gb"] is None and b["nutzbar_gb"] is None
    assert orchester_bedarf(auswahl, mac(32))["passt_festplatte"] is None  # Arbeitsspeicher bekannt, Platte nicht
    assert festplatte_reicht(5.0, mac(32)) is None


def test_modell_ausserhalb_des_katalogs_ist_unbekannt_und_macht_ein_ja_zu_none():
    auswahl = {"antwort": "eigenes-modell:7b", "frage": eintrag_fuer("frage", "qwen3.5:4b")}
    b = orchester_bedarf(auswahl, mac(32, 100))
    assert b["unbekannte_modelle"] == ["eigenes-modell:7b"]
    assert b["tag_gb"] == 6 and b["passt_tag"] is None  # Summe der bekannten passt, der Rest ist ungewiss
    zu_gross = orchester_bedarf({**auswahl, "hintergrund": eintrag_fuer("hintergrund", "qwen3.5:122b")}, mac(32, 100))
    assert zu_gross["passt_nacht"] is False  # schon das Bekannte sprengt die Grenze


def test_bedarf_nimmt_empfehlungen_wahlen_und_namen():
    from icarus_memory.model_roles import RollenWahl
    g = mac(32, 100)
    assert orchester_bedarf(empfehle_alle(g), g)["tag_gb"] > 0
    assert orchester_bedarf({"antwort": RollenWahl(modell="gemma4:12b"), "frage": RollenWahl()}, g)["tag_gb"] == 10
    assert orchester_bedarf({"antwort": "gemma4:12b"}, g)["tag_gb"] == 10


@pytest.mark.parametrize("gb", [16, 24, 32, 64, 128])
def test_empfehlung_passt_tagsueber_auf_jeder_stufe(gb):
    g = mac(gb, 1000)
    alle = empfehle_alle(g)
    b = orchester_bedarf(alle, g)
    assert b["passt_tag"] is True, (gb, b)
    assert set(alle) == set(ROLLEN)


@pytest.mark.parametrize("gb", [16, 24, 32, 64, 128])
def test_empfehlung_passt_auch_nachts_auf_jeder_stufe(gb):
    g = mac(gb, 1000)
    assert orchester_bedarf(empfehle_alle(g), g)["passt_nacht"] is True


def test_auf_8_gb_passt_es_tagsueber_nicht_und_es_gibt_nichts_kleineres():
    """Ehrlich statt schöngerechnet: Die kleinsten Modelle sind schon gewählt, der Hinweis sagt es."""
    g = mac(8, 1000)
    alle = empfehle_alle(g)
    assert orchester_bedarf(alle, g)["passt_tag"] is False
    assert {r: e.orchester_hinweis for r, e in alle.items()} == {r: "" for r in ROLLEN}
    satz = " ".join(orchester_hinweise(alle, g, TITEL))
    assert "Tagsüber" in satz and "nichts Kleineres" in satz


def test_32_gb_nimmt_fuer_die_antwort_die_kleinere_alternative_mit_begruendung():
    g = mac(32, 500)
    assert empfehle(g, "antwort").modell.name == "qwen3.6:35b"  # die einzelne Rolle bleibt, wie sie war
    alle = empfehle_alle(g)
    assert alle["antwort"].modell.name == "gemma4:12b"
    satz = alle["antwort"].orchester_hinweis
    assert "qwen3.6:35b" in satz and "tagsüber" in satz and "gemma4:12b" in satz
    assert alle["antwort"].passt_vermutlich is True
    assert "qwen3.6:35b" in {a.name for a in alle["antwort"].alternativen}  # die große Wahl bleibt wählbar
    # Das Hintergrundmodell bleibt auf 32 GB bei der gemessenen 9B-Familie.
    assert alle["hintergrund"].modell.name == "qwen3.5:9b"
    assert alle["hintergrund"].orchester_hinweis == ""
    # Rollen, die nicht getauscht werden mussten, tragen keinen Hinweis.
    assert alle["einbettung"].orchester_hinweis == "" and alle["frage"].orchester_hinweis == ""


def test_die_pruefung_laeuft_tagsueber_mit_und_zaehlt_zum_bedarf():
    auswahl = wahl(frage="qwen3.5:4b", antwort="gemma4:12b", pruefung="bespoke-minicheck:7b", einbettung="bge-m3")
    b = orchester_bedarf(auswahl, mac(32, 100))
    assert b["tag_gb"] == 6 + 10 + 6 + 2 and b["nacht_gb"] == 2


def test_die_pruefung_gibt_zuerst_speicher_her_wenn_das_allein_reicht():
    """24 GB: Mit dem kleinsten Prüfmodell passt es, also bleibt das Antwortmodell, wie es war."""
    alle = empfehle_alle(mac(24, 500))
    assert alle["antwort"].modell.name == empfehle(mac(24, 500), "antwort").modell.name
    assert alle["antwort"].orchester_hinweis == ""
    assert alle["pruefung"].modell.name == "tev1:0.8b" and "bespoke-minicheck:7b" in alle["pruefung"].orchester_hinweis
    assert orchester_bedarf(alle, mac(24, 500))["passt_tag"] is True


def test_reicht_die_pruefung_allein_nicht_wird_zuerst_die_antwort_kleiner():
    """32 GB: Das große Antwortmodell passt auch mit dem kleinsten Prüfmodell nicht; die Prüfung wird danach nur so
    klein wie nötig (nicht bis ganz unten)."""
    alle = empfehle_alle(mac(32, 500))
    assert alle["antwort"].modell.name == "gemma4:12b"
    assert alle["pruefung"].modell.name == "tev1:4b"
    assert orchester_bedarf(alle, mac(32, 500))["tag_gb"] == pytest.approx(26.7)


def test_64_gb_braucht_keinen_tausch():
    g = mac(64, 500)
    alle = empfehle_alle(g)
    assert {r: e.orchester_hinweis for r, e in alle.items()} == {r: "" for r in ROLLEN}
    assert alle["antwort"].modell.name == empfehle(g, "antwort").modell.name


def test_unbekanntes_geraet_bleibt_bei_der_kleinsten_stufe():
    alle = empfehle_alle(Geraet())
    assert {e.orchester_hinweis for e in alle.values()} == {""}
    assert alle["antwort"].modell.name == "qwen3.5:4b"


def test_hinweise_nennen_was_nicht_passt_und_was_stattdessen():
    g = mac(32, 500)
    auswahl = wahl(frage="qwen3.5:9b", antwort="qwen3.6:35b", hintergrund="qwen3.6:35b", einbettung="bge-m3")
    saetze = orchester_hinweise(auswahl, g, TITEL)
    text = " ".join(saetze)
    assert any("Tagsüber" in s and "39" in s for s in saetze)
    assert "Antworten formulieren" in text and "gemma4:12b" in text and "statt qwen3.6:35b" in text
    assert any("nachts" in s.lower() for s in saetze)
    assert orchester_hinweise(wahl(frage="qwen3.5:4b", antwort="gemma4:12b", hintergrund="gemma4:12b",
                                   einbettung="bge-m3"), mac(32, 500), TITEL) == []


def test_hinweis_zur_festplatte_nennt_frei_und_einen_kleineren_vorschlag():
    auswahl = wahl(frage="qwen3.5:9b", antwort="qwen3.6:35b", hintergrund="qwen3.6:35b", einbettung="bge-m3")
    saetze = orchester_hinweise(auswahl, mac(128, 20), TITEL)
    assert len(saetze) == 1 and "Festplatte" in saetze[0] and "frei sind etwa 20 GB" in saetze[0]
    assert "statt qwen3.6:35b" in saetze[0]
    # Mehrere Tauschschritte derselben Rolle werden ein Satz: von der ersten Wahl zur letzten.
    assert saetze[0].count("für „Im Hintergrund ordnen“") == 1 and saetze[0].count("für „Antworten formulieren“") == 1
    assert "Kleiner: qwen3.5:9b statt qwen3.6:35b für „Im Hintergrund ordnen“." in saetze[0]  # über mehrere Stufen hinweg


def test_hinweise_ehrlich_wenn_nichts_kleineres_hilft():
    auswahl = wahl(frage="qwen3.5:2b", antwort="qwen3.5:4b", hintergrund="qwen3.5:4b", einbettung="bge-m3")
    saetze = orchester_hinweise(auswahl, mac(8, 500), {**TITEL})
    assert saetze == [] or all("kleineres" in s.lower() or "kleiner" in s.lower() for s in saetze)


def test_katalog_hat_fuer_jede_rolle_und_stufe_eine_kleinere_ausweichmoeglichkeit_oder_ist_die_kleinste():
    """Der Tausch darf nie ein Modell wählen, das größer ist als das ersetzte."""
    for gb in (8, 16, 24, 32, 64, 128):
        g = mac(gb, 1000)
        for rolle, basis in ((r, empfehle(g, r)) for r in ROLLEN):
            gewaehlt = empfehle_alle(g)[rolle].modell
            assert gewaehlt.speicher_gb <= basis.modell.speicher_gb
    assert KATALOG  # der Katalog wird hier nicht verändert
