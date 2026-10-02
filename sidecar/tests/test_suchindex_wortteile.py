"""Wortteile nur für die letzten N Jahre: zweiter, wortbasierter Index für ältere Quellen.

Einstellung `suchindex.wortteile_jahre` (0 = alle Quellen mit Wortteilen, Vorgabe). Die Suche fragt beide
Indizes und vereint die Treffer; eine Quelle steht in genau einem. Eine Änderung der Einstellung baut um,
ohne dass zwischendurch eine Quelle fehlt.
"""
import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType, config, source_index, suchindex_routes
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api

STICHTAG = datetime(2026, 9, 29, 7, 30, tzinfo=timezone.utc)
JAHR = 365


@pytest.fixture(autouse=True)
def heute(monkeypatch):
    """„Jetzt“ des Index ist der Stichtag, nicht die Uhr des Rechners."""
    monkeypatch.setattr(source_index, 'now', lambda: STICHTAG)


@pytest.fixture
def episodes(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    yield store
    store.close()


def put(store, titel, text, *, vor_tagen=0):
    episode, angelegt = store.record(
        EpisodeKind.MESSAGE, titel, f'{text} Aktenzeichen {titel}/{vor_tagen}', Provenance(SourceType.DOCUMENT, source_ref=f'test:{titel}:{vor_tagen}'),
        occurred_at=STICHTAG - timedelta(days=vor_tagen), at=STICHTAG)
    assert angelegt
    return episode


def finde(store, frage, **optionen):
    return source_index.suchen(store._conn, frage, **optionen)


def stufen(store):
    """Episode -> steht mit Wortteilen (True) oder nur als Wörter (False) im Index."""
    return {episode: bool(stufe) for episode, stufe in
            store._conn.execute('SELECT episode_id, wortteile FROM source_index_docs')}


def einstellen(store, jahre):
    return store.suchindex_einstellen(jahre)


@pytest.fixture
def bestand(episodes):
    """Je eine junge (vor 30 Tagen), mittlere (vor 1,5 Jahren) und alte (vor 4 Jahren) Quelle mit demselben Kompositum."""
    return (put(episodes, 'Jung', 'Die Stromrechnung liegt vor.', vor_tagen=30),
            put(episodes, 'Mittel', 'Die Stromrechnung liegt vor.', vor_tagen=int(1.5 * JAHR)),
            put(episodes, 'Alt', 'Die Stromrechnung liegt vor.', vor_tagen=4 * JAHR))


# -- Vorgabe: alles wie bisher -----------------------------------------------

def test_vorgabe_null_laesst_alle_quellen_im_trigramm_index(episodes, bestand):
    assert source_index.wortteile_jahre(episodes._conn) == 0
    assert set(stufen(episodes).values()) == {True}
    assert source_index.verteilung(episodes._conn) == {'mit_wortteilen': 3, 'nur_woerter': 0}
    assert set(finde(episodes, 'Rechnung').episoden) == {q.id for q in bestand}  # Wortteil in allen


def test_wortindex_bleibt_bei_null_leer(episodes, bestand):
    assert episodes._conn.execute('SELECT count(*) FROM source_index_woerter').fetchone()[0] == 0
    assert not source_index._woerter_gefuellt(episodes._conn)


# -- Umbau ---------------------------------------------------------------------

def test_zwei_jahre_verschiebt_nur_aeltere_quellen_in_den_wortindex(episodes, bestand):
    jung, mittel, alt = bestand
    ergebnis = einstellen(episodes, 2)
    assert ergebnis['umgestuft'] == 1 and ergebnis['geaendert'] and ergebnis['wortteile_jahre'] == 2
    assert stufen(episodes) == {jung.id: True, mittel.id: True, alt.id: False}
    assert episodes.suchindex_stand()['nur_woerter'] == 1
    assert episodes._conn.execute('SELECT count(*) FROM source_index_woerter').fetchone()[0] == 1


def test_die_grenze_liegt_bei_n_jahren_vor_dem_stichtag(episodes):
    knapp_drin = put(episodes, 'Drin', 'Stromrechnung', vor_tagen=2 * JAHR - 3)
    knapp_draussen = put(episodes, 'Draussen', 'Stromrechnung', vor_tagen=2 * JAHR + 3)
    einstellen(episodes, 2)
    assert stufen(episodes) == {knapp_drin.id: True, knapp_draussen.id: False}


def test_umbau_gleicht_einem_neuaufbau(episodes, bestand):
    einstellen(episodes, 2)
    umgebaut = stufen(episodes)
    with episodes.transaction():
        source_index.neu_aufbauen(episodes._conn)
    assert stufen(episodes) == umgebaut
    einstellen(episodes, 0)
    assert set(stufen(episodes).values()) == {True}
    assert episodes._conn.execute('SELECT count(*) FROM source_index_woerter').fetchone()[0] == 0


def test_beim_umbau_fehlt_zwischendurch_keine_quelle(episodes):
    quellen = [put(episodes, f'Q{nummer}', 'Stromrechnung', vor_tagen=nummer * 300) for nummer in range(12)]
    alle = {q.id for q in quellen}
    with episodes.transaction():
        source_index.einstellen(episodes._conn, 1)
    schritte = 0
    for _ in range(len(alle)):  # begrenzt: Ohne Fortschritt soll der Test scheitern, nicht hängen
        with episodes.transaction():
            geschafft = source_index.umstufen(episodes._conn, grenze=2)
        schritte += 1
        assert set(finde(episodes, 'Stromrechnung', limit=50).episoden) == alle
        if geschafft < 2:
            break
    assert geschafft < 2, 'Der Umbau kommt nicht zum Ende'
    assert schritte > 2 and 0 < sum(stufen(episodes).values()) < len(alle)


def test_einstellung_ueberlebt_den_neustart(tmp_path):
    pfad = tmp_path / 'e.sqlite3'
    store = EpisodeStore(pfad)
    alt = put(store, 'Alt', 'Stromrechnung', vor_tagen=4 * JAHR)
    einstellen(store, 2)
    store.close()
    store = EpisodeStore(pfad)
    try:
        assert store.suchindex_stand()['wortteile_jahre'] == 2 and stufen(store) == {alt.id: False}
    finally:
        store.close()


def test_ungueltige_jahre_werden_abgewiesen(episodes):
    for falsch in (-1, 101, 1.5, '2', True):
        with pytest.raises(ValueError):
            with episodes.transaction():
                source_index.einstellen(episodes._conn, falsch)


def test_umbau_macht_den_index_kleiner(episodes):
    """Der Zweck der Einstellung: Nach dem Umbau belegt der Index weniger Platz (FTS5 gibt ihn erst beim Zusammenführen frei)."""
    zufall = random.Random(3)
    woerter = [''.join(zufall.choices('abcdefghilmnoprstuw', k=zufall.randint(5, 12))) for _ in range(600)]
    for nummer in range(240):
        text = ' '.join(zufall.choices(woerter, k=220))
        put(episodes, f'Q{nummer}', text, vor_tagen=nummer * 12)  # rund acht Jahre
    vorher = source_index.groesse(episodes._conn)
    if vorher is None:
        pytest.skip('Diese SQLite kann den belegten Platz nicht nennen (dbstat fehlt).')
    ergebnis = einstellen(episodes, 1)
    nachher = source_index.groesse(episodes._conn)
    assert ergebnis['umgestuft'] > 150 and nachher < vorher * 0.7, (vorher, nachher)
    assert finde(episodes, woerter[0]).episoden  # und die Suche nach ganzen Wörtern findet weiter


# -- Aufnahme und Alterung -----------------------------------------------------------

def test_neue_quellen_kommen_je_nach_alter_in_den_richtigen_index(episodes):
    einstellen(episodes, 2)
    jung = put(episodes, 'Jung', 'Stromrechnung', vor_tagen=10)
    alt = put(episodes, 'Alt', 'Stromrechnung', vor_tagen=5 * JAHR)  # etwa ein Import alter Mails
    assert stufen(episodes) == {jung.id: True, alt.id: False}


def test_mit_der_zeit_alternde_quellen_zieht_der_abgleich_um(episodes, monkeypatch):
    einstellen(episodes, 2)
    quelle = put(episodes, 'Jung', 'Stromrechnung', vor_tagen=100)
    assert stufen(episodes) == {quelle.id: True} and source_index.stimmt(episodes._conn)
    monkeypatch.setattr(source_index, 'now', lambda: STICHTAG + timedelta(days=3 * JAHR))
    assert not source_index.stimmt(episodes._conn)
    with episodes.transaction():
        ergebnis = source_index.abgleichen(episodes._conn)
    assert ergebnis.umgestuft == 1 and ergebnis.offen == 0
    assert stufen(episodes) == {quelle.id: False} and source_index.stimmt(episodes._conn)


def test_neustart_stuft_gealterte_quellen_um(tmp_path, monkeypatch):
    pfad = tmp_path / 'e.sqlite3'
    store = EpisodeStore(pfad)
    einstellen(store, 1)
    quelle = put(store, 'Q', 'Stromrechnung', vor_tagen=100)
    store.close()
    monkeypatch.setattr(source_index, 'now', lambda: STICHTAG + timedelta(days=2 * JAHR))
    store = EpisodeStore(pfad)
    try:
        assert stufen(store) == {quelle.id: False}
    finally:
        store.close()


def test_ignorierte_alte_quelle_verschwindet_aus_dem_wortindex(episodes):
    einstellen(episodes, 2)
    alt = put(episodes, 'Alt', 'Stromrechnung', vor_tagen=5 * JAHR)
    assert finde(episodes, 'Stromrechnung').episoden == (alt.id,)
    episodes.ignore(alt.id)
    assert finde(episodes, 'Stromrechnung').episoden == () and stufen(episodes) == {}
    assert episodes._conn.execute('SELECT count(*) FROM source_index_woerter').fetchone()[0] == 0


# -- Suche über beide Indizes ---------------------------------------------------------------

def test_suche_findet_junge_und_alte_quellen_zusammen(episodes, bestand):
    einstellen(episodes, 2)
    ergebnis = finde(episodes, 'Stromrechnung')
    assert set(ergebnis.episoden) == {q.id for q in bestand} and ergebnis.gesamt == 3 and not ergebnis.begrenzt


def test_alte_quelle_findet_ganze_woerter_und_wortanfaenge(episodes):
    einstellen(episodes, 1)
    alt = put(episodes, 'Alt', 'Die Rechnungen liegen im Ordner Weinbergweg.', vor_tagen=3 * JAHR)
    assert finde(episodes, 'Rechnung').episoden == (alt.id,)  # Wortanfang: „Rechnungen“
    assert finde(episodes, 'Weinbergweg').episoden == (alt.id,)
    assert finde(episodes, 'Ordner').episoden == (alt.id,)


def test_wortteil_mitten_im_wort_findet_nur_die_junge_quelle(episodes):
    """Der Preis der Einstellung: „Rechnung“ steckt in „Stromrechnung“, aber nur der Trigramm-Index sieht das."""
    einstellen(episodes, 1)
    jung = put(episodes, 'Jung', 'Die Stromrechnung liegt vor.', vor_tagen=10)
    put(episodes, 'Alt', 'Die Stromrechnung liegt vor.', vor_tagen=3 * JAHR)
    assert finde(episodes, 'Rechnung').episoden == (jung.id,)


def test_zerlegte_fragewoerter_finden_auch_alte_quellen(episodes):
    einstellen(episodes, 1)
    alt = put(episodes, 'Alt', 'Rechnung Strom für den Monat Mai', vor_tagen=3 * JAHR)
    ergebnis = finde(episodes, 'Stromrechnung')  # zerlegt in „strom“ und „rechnung“, beide als ganze Wörter im Bestand
    assert ergebnis.episoden == (alt.id,) and set(ergebnis.zusatz) == {'strom', 'rechnung'}


def test_woerter_ohne_vorkommen_werden_auch_mit_wortindex_gemeldet(episodes, bestand):
    einstellen(episodes, 2)
    ergebnis = finde(episodes, 'Stromrechnung Quantenfluktuation')
    assert ergebnis.ohne_treffer == ('quantenfluktuation',)


@pytest.mark.parametrize('stark_alt', [False, True])
def test_treffer_beider_indizes_stehen_nach_punkten_nicht_nach_herkunft(episodes, stark_alt):
    """Zwei starke Treffer in einem Index stehen vor dem schwachen im anderen. (Ein Abwechseln nach Rang
    hätte den einzigen Treffer des kleineren Index auf Platz 2 gehoben.)"""
    einstellen(episodes, 2)
    for nummer in range(8):  # Bestand ohne das Suchwort, in beiden Indizes
        put(episodes, f'Fuell jung {nummer}', f'Nichts davon{nummer}', vor_tagen=20 + nummer)
        put(episodes, f'Fuell alt {nummer}', f'Nichts davon{nummer}', vor_tagen=4 * JAHR + nummer)
    tage_stark, tage_schwach = (4 * JAHR, 10) if stark_alt else (10, 4 * JAHR)
    stark = [put(episodes, f'Stark {n}', 'Stromrechnung', vor_tagen=tage_stark + n) for n in range(2)]
    schwach = put(episodes, 'Schwach', 'Stromrechnung ' + 'füllwort ' * 300, vor_tagen=tage_schwach)
    reihenfolge = list(finde(episodes, 'Stromrechnung', limit=10).episoden)
    assert reihenfolge[2] == schwach.id and set(reihenfolge[:2]) == {q.id for q in stark}


def test_begrenztes_ergebnis_zaehlt_beide_indizes(episodes):
    einstellen(episodes, 2)
    for n in range(4):
        put(episodes, f'Jung{n}', 'Stromrechnung', vor_tagen=10 + n)
        put(episodes, f'Alt{n}', 'Stromrechnung', vor_tagen=4 * JAHR + n)
    ergebnis = finde(episodes, 'Stromrechnung', limit=3)
    assert len(ergebnis.episoden) == 3 and ergebnis.begrenzt and ergebnis.gesamt == 8


def test_bereich_und_arten_gelten_fuer_beide_indizes(episodes):
    einstellen(episodes, 2)
    jung = put(episodes, 'Jung', 'Stromrechnung', vor_tagen=10)
    alt = put(episodes, 'Alt', 'Stromrechnung', vor_tagen=4 * JAHR)
    assert finde(episodes, 'Stromrechnung', episode_ids=[alt.id]).episoden == (alt.id,)
    assert finde(episodes, 'Stromrechnung', episode_ids=[jung.id]).episoden == (jung.id,)
    assert finde(episodes, 'Stromrechnung', arten=['document']).episoden == ()


def test_lesepruefung_gilt_auch_fuer_den_wortindex(episodes):
    """Ein veralteter Eintrag im Wortindex bringt eine ignorierte Quelle nicht zurück."""
    einstellen(episodes, 1)
    alt = put(episodes, 'Alt', 'Stromrechnung', vor_tagen=3 * JAHR)
    with episodes.transaction():  # Zustand ändern, ohne die Pflege zu rufen
        episodes._conn.execute("UPDATE episodes SET state='ignored' WHERE id=?", (alt.id,))
    assert finde(episodes, 'Stromrechnung').episoden == ()


def test_woertliche_suche_findet_alte_quellen_bei_ganzen_woertern(episodes):
    einstellen(episodes, 1)
    alt = put(episodes, 'Alt', 'Anschrift: Weinbergweg 12, Mainz', vor_tagen=3 * JAHR)
    jung = put(episodes, 'Jung', 'Neue Anschrift: Weinbergweg 12a', vor_tagen=5)
    gefunden = list(source_index.literal_kandidaten(episodes._conn, 'Weinbergweg 12'))
    assert gefunden == sorted([alt.id, jung.id])


def test_woertliche_suche_blaettert_ueber_beide_indizes(episodes):
    einstellen(episodes, 1)
    quellen = [put(episodes, f'Q{n}', 'Weinbergweg 12', vor_tagen=(10 if n % 2 else 3 * JAHR) + n) for n in range(9)]
    gefunden = list(source_index.literal_kandidaten(episodes._conn, 'Weinbergweg', seite=2))
    assert gefunden == sorted(q.id for q in quellen)


# -- Schema ----------------------------------------------------------------------------------

def test_schemapruefung_kennt_den_wortindex(episodes):
    source_index.verify(episodes._conn)
    with episodes.transaction():
        episodes._conn.execute('DROP TABLE source_index_meta')
    with pytest.raises(sqlite3.DatabaseError):
        source_index.verify(episodes._conn)


def test_groesse_nennt_belegte_bytes_des_index(episodes, bestand):
    platz = source_index.groesse(episodes._conn)
    assert platz is None or platz > 0


# -- Verdrahtung: Einstellung, Routen ---------------------------------------------------------

def test_jahre_aus_den_einstellungen_sind_immer_brauchbar():
    def einst(wert):
        s = config.Settings()
        s.suchindex = wert
        return suchindex_routes.jahre_aus(s)
    assert einst({}) == 0 and einst({'wortteile_jahre': 3}) == 3
    assert einst({'wortteile_jahre': -2}) == 0 and einst({'wortteile_jahre': 'x'}) == 0 and einst({'wortteile_jahre': True}) == 0
    assert einst('kaputt') == 0


def test_einstellungen_speichern_und_lesen_die_jahre(tmp_path):
    s = config.Settings()
    s.suchindex = {'wortteile_jahre': 4}
    config.save(tmp_path, s)
    assert config.load(tmp_path).suchindex == {'wortteile_jahre': 4}
    assert 'suchindex' in json.loads((tmp_path / config.DATEINAME).read_text(encoding='utf-8'))


@pytest.fixture
def api(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        yield app, client, tmp_path
    finally:
        client.close()


def test_route_nennt_stand_und_setzt_die_einstellung(api):
    app, client, daten = api
    put(app.state.episodes, 'Jung', 'Stromrechnung', vor_tagen=10)
    put(app.state.episodes, 'Alt', 'Stromrechnung', vor_tagen=4 * JAHR)
    stand = client.get('/api/v1/suchindex').json()
    assert stand['wortteile_jahre'] == 0 and stand['quellen'] == 2 and stand['nur_woerter'] == 0
    assert stand['groesse_mb'] is None or stand['groesse_mb'] > 0

    antwort = client.put('/api/v1/suchindex', json={'wortteile_jahre': 2})
    assert antwort.status_code == 200
    assert antwort.json()['nur_woerter'] == 1 and antwort.json()['umgestuft'] == 1
    assert client.get('/api/v1/suchindex').json()['wortteile_jahre'] == 2
    assert app.state.settings.suchindex == {'wortteile_jahre': 2}
    assert config.load(daten / 'source-answer-api').suchindex == {'wortteile_jahre': 2}


@pytest.mark.parametrize('body', [{'wortteile_jahre': -1}, {'wortteile_jahre': 101}, {'wortteile_jahre': 'zwei'},
                                  {'wortteile_jahre': 1.5}, {}, {'wortteile_jahre': 1, 'mehr': 2}])
def test_route_weist_ungueltige_jahre_ab(api, body):
    app, client, _ = api
    assert client.put('/api/v1/suchindex', json=body).status_code == 422
    assert app.state.episodes.suchindex_stand()['wortteile_jahre'] == 0


def test_start_bringt_den_index_auf_die_gespeicherte_einstellung(api):
    app, _, _ = api
    alt = put(app.state.episodes, 'Alt', 'Stromrechnung', vor_tagen=4 * JAHR)
    app.state.settings.suchindex = {'wortteile_jahre': 1}
    suchindex_routes.anwenden(app)
    assert stufen(app.state.episodes) == {alt.id: False}
    assert app.state.episodes.suchindex_stand()['wortteile_jahre'] == 1
