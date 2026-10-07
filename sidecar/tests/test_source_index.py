"""Der Suchindex über Rohquellen: Wortteile, Verwendbarkeit, Migration, Ranking, Grenzen, Fusion."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType, source_candidates, source_index
from icarus_memory.episodes import CHAT_LOOKUP_TAG
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.working_memory_legacy import drop_intake_extensions

AT = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def episodes(tmp_path):
    store = EpisodeStore(tmp_path / "episodes.sqlite3")
    yield store
    store.close()


def put(episodes, title, body, *, kind=EpisodeKind.MESSAGE, key="", days=0, participants=None, tags=None):
    episode, created = episodes.record(
        kind, title, body, Provenance(SourceType.DOCUMENT, source_ref=f"test:{title}:{days}"),
        occurred_at=AT + timedelta(days=days), participants=participants, tags=tags, source_key=key, at=AT)
    assert created
    if key:
        episodes.advance_source_head(key, episodes.source_head(key), episode.id)
    return episode


def find(episodes, question, **options):
    return source_index.suchen(episodes._conn, question, **options)


def ids(result):
    return list(result.episoden)


def classify(episodes, paragraphs=False):
    """Alle offenen Quellen einordnen: ein Abschnitt je Quelle oder je Absatz."""
    memory = WorkingMemoryStore(episodes)
    for snapshot in memory.pending(limit=200):
        body = snapshot.episode.body
        spans, start = [], 0
        for part in (body.split("\n\n") if paragraphs else [body]):
            if part.strip():
                spans.append({"start": body.index(part, start), "end": body.index(part, start) + len(part),
                              "kind": "fact"})
            start += len(part) + 2
        assert memory.commit(snapshot, spans, model="test")
    return memory


# -- Faltung und Suchwörter -------------------------------------------------

def test_faltung_ist_klein_ohne_akzente_und_idempotent():
    assert source_index.falte("Straße ÜBER Äpfel\n\n  Café") == "strasse uber apfel cafe"
    gefaltet = source_index.falte("Größe – Ünde")
    assert source_index.falte(gefaltet) == gefaltet


def test_funktionswoerter_der_frage_werden_nicht_gesucht():
    woerter, gekuerzt = source_index.woerter("Wann muss ich eigentlich die Stromrechnung bezahlen?")
    assert woerter == ["bezahlen", "stromrechnung"] and not gekuerzt


def test_zu_viele_woerter_werden_gezaehlt_nicht_still_gekuerzt(episodes):
    put(episodes, "Mail", "wort0000 steht hier")
    frage = " ".join(f"wort{number:04d}" for number in range(source_index.MAX_WOERTER + 4))
    result = find(episodes, frage)
    assert result.frageworte_gekuerzt and len(result.woerter) == source_index.MAX_WOERTER
    assert ids(result)


def test_gesprächsnachschlag_tag_ist_dasselbe_wie_im_episodenspeicher():
    assert source_index.CHAT_LOOKUP_TAG == CHAT_LOOKUP_TAG


def test_indexierte_arten_sind_genau_die_rohquellen_des_episodenspeichers():
    """Eine neue Rohquellenart muss auch im Suchindex stehen (siehe ``episodes.ROHQUELLEN``)."""
    from icarus_memory.episodes import ROHQUELLEN
    assert set(source_index.ARTEN) == {art.value for art in ROHQUELLEN}


def test_termine_landen_im_index_und_entzogene_verschwinden(episodes):
    termin = put(episodes, "Probeverkostung Winter Catering", "Probeverkostung für die Workshop-Reihe.",
                 kind=EpisodeKind.EVENT, key="calendar:kal/1")
    assert ids(find(episodes, "Probeverkostung")) == [termin.id]
    assert ids(find(episodes, "Probeverkostung", arten=["event"])) == [termin.id]
    episodes.ignore(termin.id, grund="kalender")  # das Programm entzieht den Termin selbst
    assert ids(find(episodes, "Probeverkostung")) == [] and termin.id not in indexed(episodes)


# -- Wortteile und Komposita --------------------------------------------------

def test_wortteil_findet_das_kompositum(episodes):
    treffer = put(episodes, "Mail", "Die Stromrechnung für Oktober ist da.")
    put(episodes, "Mail", "Der Wasserzähler wurde abgelesen.")
    assert ids(find(episodes, "Rechnung Strom")) == [treffer.id]


def test_kompositum_in_der_frage_findet_getrennte_woerter(episodes):
    getrennt = put(episodes, "Mail", "Rechnung Strom für Oktober wurde überwiesen.")
    put(episodes, "Mail", "Der Wasserzähler wurde abgelesen.")
    result = find(episodes, "Stromrechnung")
    assert ids(result) == [getrennt.id]
    assert set(result.zusatz) == {"strom", "rechnung"}


def test_zerlegung_teilt_nur_an_woertern_die_im_bestand_stehen(episodes):
    put(episodes, "Mail", "Rechnung Strom für Oktober")
    put(episodes, "Mail", "Rechenschaft über Nutzung")  # enthält „rech“ und „nung“, aber kein Wort so
    result = find(episodes, "Stromrechnung")
    assert set(result.zusatz) == {"strom", "rechnung"}


def test_fugen_s_wird_bei_der_zerlegung_uebersprungen(episodes):
    getrennt = put(episodes, "Mail", "Arbeit und Zeit müssen erfasst werden. Arbeit Zeit Liste.")
    result = find(episodes, "Arbeitszeitnachweis Arbeitszeit")
    assert getrennt.id in ids(result)
    assert {"arbeit", "zeit"} <= set(result.zusatz)


def test_titel_und_beteiligte_sind_durchsuchbar(episodes):
    per_titel = put(episodes, "Angebot Vogelsberg", "kurzer Text")
    per_person = put(episodes, "Mail", "kurzer Text zwei", participants=["Weidner <weidner@beispiel.example>"])
    assert ids(find(episodes, "Vogelsberg")) == [per_titel.id]
    assert ids(find(episodes, "Weidner")) == [per_person.id]


# -- Nur verwendbare Quellen: Pflege am Zustandswechsel ----------------------

def indexed(episodes):
    return {row[0] for row in episodes._conn.execute("SELECT episode_id FROM source_index_docs")}


def test_ignorierte_quelle_kommt_nicht_zurueck_und_kehrt_beim_oeffnen_wieder(episodes):
    quelle = put(episodes, "Mail", "Die Stromrechnung liegt vor.")
    assert ids(find(episodes, "Stromrechnung")) == [quelle.id]
    episodes.ignore(quelle.id)
    assert ids(find(episodes, "Stromrechnung")) == []
    assert quelle.id not in indexed(episodes)  # Pflege: der Eintrag ist weg, nicht nur gefiltert
    episodes.reopen(quelle.id)
    assert ids(find(episodes, "Stromrechnung")) == [quelle.id]
    assert quelle.id in indexed(episodes)


def test_ersetzte_fassung_kommt_nicht_zurueck(episodes):
    alt = put(episodes, "Frist", "Die Frist endet am 15. Oktober.", key="ordner/frist")
    neu = put(episodes, "Frist", "Die Frist endet am 31. Oktober.", key="ordner/frist", days=1)
    assert ids(find(episodes, "Frist endet")) == [neu.id]
    assert alt.id not in indexed(episodes) and neu.id in indexed(episodes)


def test_noch_nicht_freigegebene_neue_fassung_ist_nicht_durchsuchbar(episodes):
    """Eine neue Fassung zählt erst, wenn sie die aktuelle ist; bis dahin bleibt die alte."""
    alt = put(episodes, "Frist", "Die Frist endet am 15. Oktober.", key="ordner/frist")
    neu, _ = episodes.record(EpisodeKind.MESSAGE, "Frist", "Die Frist endet am 31. Oktober.",
                             Provenance(SourceType.DOCUMENT, source_ref="test:neu"), source_key="ordner/frist", at=AT)
    assert ids(find(episodes, "Frist endet")) == [alt.id]
    assert neu.id not in indexed(episodes)


def test_gesprächsnachschlag_zusammenfassung_und_beobachtung_sind_nicht_im_index(episodes):
    put(episodes, "Frage", "Quasar123 gefragt", tags=[CHAT_LOOKUP_TAG])
    put(episodes, "Summe", "Quasar123 zusammengefasst", kind=EpisodeKind.SUMMARY)
    put(episodes, "Beobachtung", "Quasar123 bemerkt", kind=EpisodeKind.OBSERVATION)
    assert ids(find(episodes, "Quasar123")) == []
    assert indexed(episodes) == set()


def test_gelöschte_quelle_wird_beim_lesen_und_im_abgleich_entfernt(episodes):
    quelle = put(episodes, "Mail", "Die Stromrechnung liegt vor.")
    with episodes.transaction():
        episodes._conn.execute("DELETE FROM episodes WHERE id=?", (quelle.id,))  # an der Pflege vorbei
    assert quelle.id in indexed(episodes)  # veralteter Eintrag
    assert ids(find(episodes, "Stromrechnung")) == []  # Prüfung beim Lesen
    with episodes.transaction():
        assert source_index.abgleichen(episodes._conn).entfernt == 1
    assert quelle.id not in indexed(episodes)


def test_lesepruefung_gilt_auch_wenn_die_pflege_versagt(episodes):
    """Fail-closed: Ein Indexeintrag einer ignorierten Quelle bringt sie nicht zurück."""
    quelle = put(episodes, "Mail", "Die Stromrechnung liegt vor.")
    episodes.ignore(quelle.id)
    row = episodes._conn.execute(source_index._ZEILE + "e.id=?", (quelle.id,)).fetchone()
    with episodes.transaction():
        source_index._einfuegen(episodes._conn, row)  # Pflege „vergisst“ den Eintrag
    assert quelle.id in indexed(episodes)
    assert ids(find(episodes, "Stromrechnung")) == []


def test_lesepruefung_gilt_auch_fuer_ersetzte_fassungen(episodes):
    alt = put(episodes, "Frist", "Die Frist endet am 15. Oktober.", key="ordner/frist")
    put(episodes, "Frist", "Die Frist endet am 31. Oktober.", key="ordner/frist", days=1)
    row = episodes._conn.execute(source_index._ZEILE + "e.id=?", (alt.id,)).fetchone()
    with episodes.transaction():
        source_index._einfuegen(episodes._conn, row)
    assert alt.id not in ids(find(episodes, "Frist endet"))


def test_bereich_und_art_schraenken_ein(episodes):
    a = put(episodes, "Mail", "Stromrechnung eins")
    b = put(episodes, "Notiz", "Stromrechnung zwei", kind=EpisodeKind.DOCUMENT)
    assert set(ids(find(episodes, "Stromrechnung"))) == {a.id, b.id}
    assert ids(find(episodes, "Stromrechnung", episode_ids=[b.id])) == [b.id]
    assert ids(find(episodes, "Stromrechnung", arten=["document"])) == [b.id]
    assert ids(find(episodes, "Stromrechnung", episode_ids=[])) == []


# -- Migration mit Erstbefüllung und Start-Abgleich ---------------------------

def downgrade(path, version=11):
    with sqlite3.connect(path) as connection:
        connection.execute('ALTER TABLE working_memory_sources DROP COLUMN analysis_version')
        drop_intake_extensions(connection)  # entfernt auch den Suchindex
        from icarus_memory import mail_intake, memory_categories
        mail_intake.migrate(connection)
        memory_categories.migrate(connection)
        connection.execute(f"PRAGMA user_version={version}")


def test_migration_fuellt_den_index_aus_dem_bestand(tmp_path):
    path = tmp_path / "e.sqlite3"
    store = EpisodeStore(path)
    frisch = put(store, "Mail", "Die Stromrechnung liegt vor.")
    ignoriert = put(store, "Mail", "Stromrechnung ignoriert")
    store.ignore(ignoriert.id)
    alt = put(store, "Frist", "Stromrechnung alte Fassung", key="a/b")
    neu = put(store, "Frist", "Stromrechnung neue Fassung", key="a/b", days=1)
    put(store, "Frage", "Stromrechnung gefragt", tags=[CHAT_LOOKUP_TAG])
    store.close()
    downgrade(path)

    store = EpisodeStore(path)
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] == 18
    assert indexed(store) == {frisch.id, neu.id}
    assert alt.id not in indexed(store) and ignoriert.id not in indexed(store)
    assert set(ids(find(store, "Stromrechnung"))) == {frisch.id, neu.id}
    store.close()


def test_migration_allein_fuellt_den_index_auch_ohne_start_abgleich(tmp_path):
    """Die Erstbefüllung gehört zur Migration; der Abgleich beim Start ist nur das Netz darunter."""
    from icarus_memory import episodes as episodes_module
    from icarus_memory.migrations import run_migrations
    path = tmp_path / "e.sqlite3"
    store = EpisodeStore(path)
    frisch = put(store, "Mail", "Die Stromrechnung liegt vor.")
    ignoriert = put(store, "Mail", "Stromrechnung ignoriert")
    store.ignore(ignoriert.id)
    store.close()
    downgrade(path)
    with sqlite3.connect(path) as connection:
        run_migrations(connection, store="episodes", path=path, migrations=episodes_module._MIGRATIONS)
        docs = {row[0] for row in connection.execute("SELECT episode_id FROM source_index_docs")}
    assert docs == {frisch.id}


def test_migration_mit_grosser_quelle_zaehlt_sie_statt_sie_zu_verschweigen(tmp_path, monkeypatch):
    path = tmp_path / "e.sqlite3"
    store = EpisodeStore(path)
    put(store, "Mail", "Stromrechnung kurz")
    store.close()
    downgrade(path)
    monkeypatch.setattr(source_index, "MAX_TEXT_BYTES", 10)
    store = EpisodeStore(path)
    assert source_index.abdeckung(store._conn) == {"aufgenommen": 0, "zu_gross": 1}
    assert find(store, "Stromrechnung").nicht_indexiert == 1
    store.close()


def test_start_abgleich_repariert_fehlende_und_ueberzaehlige_eintraege(tmp_path):
    path = tmp_path / "e.sqlite3"
    store = EpisodeStore(path)
    fehlt = put(store, "Mail", "Stromrechnung eins")
    zuviel = put(store, "Mail", "Stromrechnung zwei")
    store.ignore(zuviel.id)
    with store.transaction():
        source_index.entfernen(store._conn, fehlt.id)  # Eintrag fehlt
        row = store._conn.execute(source_index._ZEILE + "e.id=?", (zuviel.id,)).fetchone()
        source_index._einfuegen(store._conn, row)  # Eintrag einer ignorierten Quelle
    assert indexed(store) == {zuviel.id}
    store.close()

    store = EpisodeStore(path)  # der Start gleicht ab
    assert indexed(store) == {fehlt.id}
    store.close()


def test_neuaufbau_ist_wiederholbar(episodes):
    put(episodes, "Mail", "Stromrechnung eins")
    put(episodes, "Mail", "Stromrechnung zwei")
    with episodes.transaction():
        assert source_index.neu_aufbauen(episodes._conn) == 2
        assert source_index.neu_aufbauen(episodes._conn) == 2
    assert len(ids(find(episodes, "Stromrechnung"))) == 2


def test_schema_pruefung_erkennt_ein_verändertes_schema(episodes):
    source_index.verify(episodes._conn)
    episodes._conn.execute("DROP TABLE source_index_skipped")
    with pytest.raises(sqlite3.DatabaseError):
        source_index.verify(episodes._conn)


# -- Ranking ------------------------------------------------------------------

def test_seltenes_wort_schlaegt_haeufiges(episodes):
    for nummer in range(8):
        put(episodes, "Mail", f"Angebot Angebot Angebot Nummer {nummer}", days=nummer)
    selten = put(episodes, "Mail", "Angebot für die Klinik Vogelsberg", days=1)
    assert ids(find(episodes, "Angebot Vogelsberg"))[0] == selten.id


def test_ranking_ist_wiederholbar_und_unabhaengig_von_der_einfuegereihenfolge(tmp_path):
    texte = [("Mail", "Stromrechnung Oktober Betrag 120 Euro", 3), ("Mail", "Stromrechnung", 1),
             ("Rechnung", "Rechnung für Strom Oktober", 2), ("Mail", "Wasser Strom Gas Heizung Rechnung", 4)]
    reihenfolgen = []
    for nummer, reihenfolge in enumerate((texte, list(reversed(texte)))):
        store = EpisodeStore(tmp_path / f"e{nummer}.sqlite3")
        for titel, text, tag in reihenfolge:
            put(store, titel, text, days=tag)
        erste = find(store, "Stromrechnung Oktober")
        zweite = find(store, "Stromrechnung Oktober")
        assert ids(erste) == ids(zweite)
        reihenfolgen.append([store.get(e).body for e in ids(erste)])
        store.close()
    assert reihenfolgen[0] == reihenfolgen[1]


def test_bei_gleichem_rang_gewinnt_die_neuere_quelle(episodes):
    # Gleicher Inhalt ist nur über verschiedene Quellenschlüssel aufnehmbar. Die IDs sind zufällig;
    # acht Quellen in genau absteigender Zeit lassen sich nicht durch Zufall so ordnen.
    quellen = [put(episodes, "Mail", "Stromrechnung Oktober", days=tag, key=f"k{tag}") for tag in range(8)]
    assert ids(find(episodes, "Stromrechnung")) == [quelle.id for quelle in reversed(quellen)]


def test_fremde_neue_quellen_aendern_die_reihenfolge_der_treffer_nicht(episodes):
    a = put(episodes, "Mail", "Stromrechnung Oktober Betrag", days=1)
    b = put(episodes, "Mail", "Rechnung Strom", days=2)
    c = put(episodes, "Mail", "Oktober Rechnung", days=3)
    vorher = ids(find(episodes, "Stromrechnung Oktober"))
    for nummer in range(40):
        put(episodes, "Mail", f"Wasserzähler Ablesung Nummer {nummer}", days=nummer)
    assert ids(find(episodes, "Stromrechnung Oktober")) == vorher
    assert set(vorher) == {a.id, b.id, c.id}


# -- Keine stillen Grenzen -----------------------------------------------------

def test_begrenztes_ergebnis_nennt_die_gesamtzahl(episodes):
    for nummer in range(30):
        put(episodes, "Mail", f"Stromrechnung Nummer {nummer}", days=nummer)
    result = find(episodes, "Stromrechnung", limit=10)
    assert len(result.episoden) == 10 and result.begrenzt and result.gesamt == 30
    ganz = find(episodes, "Stromrechnung", limit=64)
    assert len(ganz.episoden) == 30 and not ganz.begrenzt and ganz.gesamt == 30


def test_zu_grosse_quelle_bleibt_draussen_und_wird_gezaehlt(episodes, monkeypatch):
    monkeypatch.setattr(source_index, "MAX_TEXT_BYTES", 50)
    put(episodes, "Mail", "Stromrechnung " + "x" * 200)
    klein = put(episodes, "Mail", "Stromrechnung klein")
    result = find(episodes, "Stromrechnung")
    assert ids(result) == [klein.id] and result.nicht_indexiert == 1
    assert source_index.abdeckung(episodes._conn) == {"aufgenommen": 1, "zu_gross": 1}


def test_wort_ohne_treffer_wird_ausgewiesen(episodes):
    put(episodes, "Mail", "Stromrechnung")
    result = find(episodes, "Stromrechnung Quantenphysik")
    assert result.ohne_treffer == ("quantenphysik",)


# -- Rangfusion und Kandidaten -------------------------------------------------

def test_rangfusion_bevorzugt_elemente_aus_beiden_listen_und_ist_deterministisch():
    assert source_candidates.rangfusion([["a", "b", "c"], ["c", "b", "d"]]) == ["c", "b", "a", "d"]
    assert source_candidates.rangfusion([["a", "b"], ["b", "a"]]) == ["a", "b"]  # Gleichstand: erstes Auftreten
    assert source_candidates.rangfusion([[], []]) == []


def test_index_findet_quelle_die_die_wortsuche_verfehlt(episodes):
    getrennt = put(episodes, "Mail", "Rechnung Strom für Oktober wurde überwiesen.")
    memory = classify(episodes)
    assert memory.search("Stromrechnung")["refs"] == []  # die Wortsuche kennt das Kompositum nicht
    result = source_candidates.zusammenfuehren(memory, "Stromrechnung", limit=12)
    assert [ref["episode_id"] for ref in result.refs] == [getrennt.id]
    assert result.zaehlung["index"] == "ok" and result.zaehlung["ohne_einordnung"] == 0


def test_nicht_eingeordnete_quelle_wird_gezaehlt_und_nicht_zum_beleg(episodes):
    put(episodes, "Mail", "Rechnung Strom für Oktober wurde überwiesen.")
    memory = WorkingMemoryStore(episodes)  # nichts eingeordnet
    result = source_candidates.zusammenfuehren(memory, "Stromrechnung", limit=12)
    assert result.refs == [] and result.zaehlung["ohne_einordnung"] == 1


def test_entzogene_quelle_im_arbeitsgedaechtnis_wird_kein_kandidat(episodes):
    quelle = put(episodes, "Mail", "Rechnung Strom für Oktober wurde überwiesen.")
    memory = classify(episodes)
    assert memory.dismiss(quelle.id)
    assert source_candidates.zusammenfuehren(memory, "Stromrechnung", limit=12).refs == []


def test_ignorierte_quelle_wird_kein_kandidat(episodes):
    quelle = put(episodes, "Mail", "Rechnung Strom für Oktober wurde überwiesen.")
    memory = classify(episodes)
    episodes.ignore(quelle.id)
    assert source_candidates.zusammenfuehren(memory, "Stromrechnung", limit=12).refs == []


def test_je_quelle_hoechstens_ein_abschnitt(episodes):
    body = "\n\n".join(f"Abschnitt {n}: Stromrechnung Oktober Posten {n}" for n in range(4))
    quelle = put(episodes, "Mail", body)
    memory = classify(episodes, paragraphs=True)
    result = source_candidates.zusammenfuehren(memory, "Stromrechnung Oktober", limit=12)
    assert [ref["episode_id"] for ref in result.refs] == [quelle.id] * source_candidates.MAX_PRO_QUELLE


def test_mehr_treffer_als_platz_wird_als_begrenzt_ausgewiesen(episodes):
    for nummer in range(20):
        put(episodes, "Mail", f"Stromrechnung Nummer {nummer}", days=nummer)
    memory = classify(episodes)
    result = source_candidates.zusammenfuehren(memory, "Stromrechnung", limit=12)
    assert len(result.refs) == 12 and result.begrenzt
    assert result.zaehlung["index_treffer"] == 20


def test_index_ausfall_faellt_auf_die_wortsuche_zurueck_und_sagt_es(episodes, monkeypatch):
    quelle = put(episodes, "Mail", "Die Stromrechnung liegt vor.")
    memory = classify(episodes)

    def kaputt(*args, **kwargs):
        raise sqlite3.OperationalError("defekt")
    monkeypatch.setattr(source_index, "suchen", kaputt)
    result = source_candidates.zusammenfuehren(memory, "Stromrechnung", limit=12)
    assert [ref["episode_id"] for ref in result.refs] == [quelle.id]
    assert result.zaehlung["index"] == "nicht verfügbar"


def test_bereich_gilt_fuer_beide_quellen(episodes):
    a = put(episodes, "Mail", "Rechnung Strom für Oktober")
    put(episodes, "Mail", "Rechnung Strom für November")
    memory = classify(episodes)
    result = source_candidates.zusammenfuehren(memory, "Stromrechnung", limit=12, episode_ids=[a.id])
    assert [ref["episode_id"] for ref in result.refs] == [a.id]


def test_begrenzungssatz_nennt_zahlen_wenn_die_suche_sie_ausweist():
    from icarus_memory.working_memory_answers import _limit_count
    basis = [{"episode_id": f"e{nummer}"} for nummer in range(3)]
    mit_zahlen = _limit_count({"basis": basis, "search": {"index_treffer": 37, "wortsuche_quellen": 10}})
    assert "mindestens 37 Quellen; geprüft wurden 3" in mit_zahlen
    allgemein = "mehr passende Quellen, als geprüft werden konnten"
    assert allgemein in _limit_count({"basis": basis})  # ältere Antworten ohne Zählung
    assert allgemein in _limit_count({"basis": basis, "search": {"index_treffer": "viele", "wortsuche_quellen": 10}})
    assert allgemein in _limit_count({"basis": basis, "search": {"index_treffer": 2, "wortsuche_quellen": 1}})


def test_kandidaten_der_antwort_enthalten_die_indexquelle_und_die_zaehlung(episodes):
    from icarus_memory import working_memory_answers
    quelle = put(episodes, "Mail", "Rechnung Strom für Oktober wurde überwiesen.")
    classify(episodes)

    class Claims:
        def source_is_unclaimed(self, episode_id):
            return True

    stats = {}
    refs, rows, limited, _ = working_memory_answers._candidates("Stromrechnung", episodes, Claims(), stats=stats)
    assert [ref["episode_id"] for ref in refs] == [quelle.id] and not limited
    assert stats["index_treffer"] == 1 and stats["geprueft"] == 1 and stats["verworfen"] == 0
