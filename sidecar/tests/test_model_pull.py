"""Laden eines Modells über die lokale Ollama-Schnittstelle: Fortschritt und erklärte Fehler."""
import httpx
import pytest

from icarus_memory.model_pull import (
    Fehlergrund, Fehlschlag, PullBelegt, PullManager, bestaetigungssatz, dauer_minuten, deute_fehler,
)
from tests.ollama_fake import FakeOllama, Verbindungsfehler


class Beobachter(PullManager):
    """Merkt sich jeden Fortschrittswert, damit der Verlauf prüfbar ist."""

    verlauf: list

    def _setze(self, job_id, **felder):
        if "fortschritt" in felder:
            self.verlauf.append(felder["fortschritt"])
        super()._setze(job_id, **felder)


def manager(fake, nachher=lambda modell, rolle: {"modell": modell}):
    m = Beobachter(lambda: "http://ollama.test", nachher,
                   client=lambda: httpx.Client(transport=fake.transport, trust_env=False))
    m.verlauf = []
    return m


def lauf(m, modell="qwen3.5:4b"):
    stand = m.starte(modell, "antwort")
    m.warte()
    return m.stand(stand.id)


def test_fortschritt_wird_ueber_alle_teile_summiert_und_endet_bei_eins():
    fake = FakeOllama()
    m = manager(fake)
    stand = lauf(m)
    assert stand.phase == "fertig" and stand.fortschritt == 1.0 and stand.ergebnis == {"modell": "qwen3.5:4b"}
    zwischen = [v for v in m.verlauf if v is not None and 0 < v < 1]
    assert 0.25 in zwischen  # 250 von 1000 im ersten Teil
    bekannt = [v for v in m.verlauf if v is not None]
    assert bekannt == sorted(bekannt)  # nie zurück
    assert 0.99 in bekannt  # der Balken bleibt unter 100 %, bis Ollama „success“ meldet
    assert ("POST", "/api/pull", {"model": "qwen3.5:4b", "stream": True}) in fake.anfragen


def test_schon_installiertes_modell_wird_nicht_erneut_geladen():
    fake = FakeOllama(installiert=["qwen3.5:4b"])
    stand = lauf(manager(fake))
    assert stand.phase == "fertig"
    assert not any(pfad == "/api/pull" for _, pfad, _ in fake.anfragen)


@pytest.mark.parametrize("modus,teil", [
    ("fehler_platz", "Speicherplatz"), ("fehler_netz", "Internet"), ("unbekannt", "kennt dieses Modell"),
    ("abbruch", "Internet"), ("http500", "nicht geladen"),
])
def test_fehler_kommen_mit_grund_und_naechstem_schritt(modus, teil):
    stand = lauf(manager(FakeOllama(modus=modus)))
    assert stand.phase == "fehler" and stand.fortschritt != 1.0
    assert teil in stand.fehler["grund"]
    assert stand.fehler["naechster_schritt"].strip()
    assert "Traceback" not in stand.text and "/root/" not in stand.text and "/root/" not in str(stand.fehler)


def test_kein_ollama_erreichbar():
    stand = lauf(manager(Verbindungsfehler()))
    assert stand.phase == "fehler"
    assert "nicht erreichbar" in stand.fehler["grund"] and "starten" in stand.fehler["naechster_schritt"]


def test_fehlschlag_der_pruefung_wird_zum_fehler():
    def nachher(modell, rolle):
        raise Fehlschlag(Fehlergrund("Prüfung nicht bestanden.", "Anderes Modell wählen."))
    stand = lauf(manager(FakeOllama(), nachher))
    assert stand.phase == "fehler" and stand.fehler["naechster_schritt"] == "Anderes Modell wählen."


def test_unerwarteter_fehler_in_der_pruefung_zeigt_keinen_rohtext():
    def nachher(modell, rolle):
        raise RuntimeError("geheimer Pfad /home/nutzer/privat")
    stand = lauf(manager(FakeOllama(), nachher))
    assert stand.phase == "fehler" and "nutzer" not in str(stand.as_dict() if hasattr(stand, "as_dict") else stand.als_dict())


def test_immer_nur_ein_ladevorgang_zugleich():
    import threading
    frei = threading.Event()
    fake = FakeOllama(warte=frei)
    m = manager(fake)
    erster = m.starte("qwen3.5:4b", "antwort")
    with pytest.raises(PullBelegt):
        m.starte("bge-m3", "einbettung")
    assert m.aktuell().id == erster.id
    frei.set()
    m.warte()
    assert m.stand(erster.id).phase == "fertig" and m.aktuell() is None
    m.starte("bge-m3", "einbettung")  # danach wieder möglich
    m.warte()


def test_bestaetigungssatz_nennt_groesse_und_dauer():
    satz = bestaetigungssatz("qwen3.6:35b", 24.0)
    assert "24 GB" in satz and "Minuten" in satz and "qwen3.6:35b" in satz
    von, bis = dauer_minuten(24.0)
    assert 1 <= von < bis
    assert dauer_minuten(1.2)[0] >= 1
    assert "6,6 GB" in bestaetigungssatz("x", 6.6)


def test_deute_fehler_ohne_treffer_ist_allgemein_aber_erklaert():
    fehler = deute_fehler("völlig anderer Fehler")
    assert fehler.grund and fehler.naechster_schritt
