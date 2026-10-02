"""Rückkanal für Fehler: Ablage, Routen, Export, Sicherung. Nur synthetische Daten."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from icarus_memory import rueckmeldung_faelle
from icarus_memory.rueckmeldung import ARTEN, Rueckmeldungen, RueckmeldungFehler
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api, _ask, _conversation, _upload


@pytest.fixture
def ablage(tmp_path):
    a = Rueckmeldungen(tmp_path / 'rueckmeldungen.sqlite3')
    yield a
    a.close()


def _melde(a, nr='m1', art='falsch', **mehr):
    return a.melden(frage='Bis wann muss das Angebot raus?', antwort='Bis zum 31. Oktober.', art=art,
                    nachricht_id=nr, **mehr)


# -- Ablage -------------------------------------------------------------------------------


def test_meldung_haelt_alles_fest_und_bleibt_nach_dem_neuoeffnen(tmp_path):
    a = Rueckmeldungen(tmp_path / 'r.sqlite3')
    m = _melde(a, richtig='15. November', belege=['e2', 'e1', 'e1'], gespraech_id='g1',
               struktur={'saetze': [{'text': 'Bis zum 31. Oktober.', 'belege': [1]}]},
               modell={'antwort': {'modell': 'synthetisch', 'lokal': True}})
    a.close()
    a = Rueckmeldungen(tmp_path / 'r.sqlite3')
    try:
        (g,) = a.liste()
        assert g['id'] == m['id'] and g['status'] == 'offen' and g['erledigt_am'] == ''
        assert (g['frage'], g['antwort'], g['art'], g['art_text'], g['richtig']) == (
            'Bis wann muss das Angebot raus?', 'Bis zum 31. Oktober.', 'falsch', 'Falsch', '15. November')
        assert g['belege'] == ['e1', 'e2'] and g['gespraech_id'] == 'g1' and g['nachricht_id'] == 'm1'
        assert g['struktur']['saetze'][0]['belege'] == [1] and g['modell']['antwort']['lokal'] is True
        assert g['erstellt'].endswith('+00:00')
    finally:
        a.close()


def test_alle_arten_gehen_unbekannte_nicht(ablage):
    for i, art in enumerate(ARTEN):
        assert _melde(ablage, nr=f'm{i}', art=art)['art'] == art
    with pytest.raises(RueckmeldungFehler):
        _melde(ablage, nr='x', art='boese')
    with pytest.raises(RueckmeldungFehler):
        ablage.melden(frage='  ', antwort='a', art='falsch', nachricht_id='y')
    with pytest.raises(RueckmeldungFehler):
        ablage.melden(frage='f', antwort='a', art='falsch', nachricht_id='')
    assert ablage.zaehlen()['gesamt'] == len(ARTEN)


def test_erledigt_bleibt_stehen_und_zaehlt_um(ablage):
    m = _melde(ablage)
    _melde(ablage, nr='m2')
    assert ablage.zaehlen() == {'gesamt': 2, 'offen': 2, 'erledigt': 0}
    e = ablage.erledigt(m['id'])
    assert e['status'] == 'erledigt' and e['erledigt_am']
    assert ablage.zaehlen() == {'gesamt': 2, 'offen': 1, 'erledigt': 1}
    assert [x['id'] for x in ablage.liste(status='erledigt')] == [m['id']]
    assert ablage.erledigt('gibt-es-nicht') is None


def test_dieselbe_antwort_zweimal_gemeldet_ersetzt_und_oeffnet_wieder(ablage):
    m = _melde(ablage, art='sonstiges')
    ablage.erledigt(m['id'])
    n = _melde(ablage, art='falsch', richtig='15. November')
    assert n['id'] == m['id'] and n['art'] == 'falsch' and n['richtig'] == '15. November' and n['status'] == 'offen'
    assert ablage.zaehlen()['gesamt'] == 1


def test_nur_lesen_veraendert_nichts(tmp_path, ablage):
    _melde(ablage)
    vorher = (tmp_path / 'rueckmeldungen.sqlite3').read_bytes()
    assert [m['art'] for m in Rueckmeldungen.nur_lesen(tmp_path / 'rueckmeldungen.sqlite3')] == ['falsch']
    assert (tmp_path / 'rueckmeldungen.sqlite3').read_bytes() == vorher
    fremd = tmp_path / 'fremd.sqlite3'
    sqlite3.connect(fremd).execute('CREATE TABLE x(a)').connection.commit()
    with pytest.raises(RueckmeldungFehler):
        Rueckmeldungen.nur_lesen(fremd)


# -- Export -------------------------------------------------------------------------------


def _m(**felder):
    basis = {'id': 'a' * 32, 'erstellt': '2026-09-30T08:00:00+00:00', 'frage': 'Wann ist die Frist?',
             'antwort': 'Die Frist ist der 31. Oktober.', 'struktur': {}, 'art': 'falsch', 'richtig': '',
             'belege': [], 'status': 'offen'}
    return {**basis, **felder}


def test_falsch_mit_richtig_wird_fall_mit_erwartet_und_verboten():
    (fall,) = rueckmeldung_faelle.faelle([_m(richtig='15. November', belege=['e1'])])['fragen']
    assert fall['id'] == 'rueckmeldung-' + 'a' * 12 and fall['frage'] == 'Wann ist die Frist?'
    assert fall['schwere'] == 'kritisch' and fall['kategorie'] == 'eigene'
    assert fall['erwartet'] == {'verhalten': 'antworten', 'aussagen': [['15. November']]}
    assert fall['verboten'] == {'aussagen': ['Die Frist ist der 31. Oktober.'], 'belege': ['e1']}


def test_ein_einzelner_satz_ist_die_verbotene_aussage():
    struktur = {'saetze': [{'text': 'Die Frist ist der 31. Oktober.', 'belege': [1]}]}
    (fall,) = rueckmeldung_faelle.faelle([_m(art='veraltet', antwort='Die Frist ist der 31. Oktober. [1]',
                                              struktur=struktur)])['fragen']
    assert fall['verboten']['aussagen'] == ['Die Frist ist der 31. Oktober.'] and fall['schwere'] == 'kritisch'


def test_unvollstaendig_mit_richtig_hat_nur_erwartet():
    (fall,) = rueckmeldung_faelle.faelle([_m(art='unvollstaendig', richtig='Anna Keller')])['fragen']
    assert fall['schwere'] == 'normal' and 'verboten' not in fall
    assert fall['erwartet']['aussagen'] == [['Anna Keller']]


def test_was_sich_am_text_nicht_messen_laesst_steht_getrennt():
    daten = rueckmeldung_faelle.faelle([_m(art='zu_langsam'), _m(id='b' * 32, art='unvollstaendig')])
    assert daten['fragen'] == [] and [n['art'] for n in daten['nicht_messbar']] == ['zu_langsam', 'unvollstaendig']
    assert 'Antworttexte' in daten['hinweis']


def test_erledigt_bleibt_in_der_datei():
    (fall,) = rueckmeldung_faelle.faelle([_m(richtig='15. November', status='erledigt')])['fragen']
    assert 'Regressionstest' in fall['notiz']


def test_reihenfolge_ist_aelteste_zuerst_und_stabil():
    a = _m(id='1' * 32, erstellt='2026-09-01T00:00:00+00:00', richtig='x')
    b = _m(id='2' * 32, erstellt='2026-09-02T00:00:00+00:00', richtig='y')
    assert [f['id'][-12:] for f in rueckmeldung_faelle.faelle([b, a])['fragen']] == ['1' * 12, '2' * 12]


# -- Routen -------------------------------------------------------------------------------


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        yield app, client
    finally:
        client.close()


def _antwort(client):
    quelle = _upload(client)
    gespraech = _conversation(client)
    nachricht = _ask(client, gespraech)
    return quelle, gespraech, nachricht


def test_melden_liest_frage_antwort_belege_und_modell_selbst(api):
    app, client = api
    quelle, gespraech, nachricht = _antwort(client)
    r = client.post('/api/v1/rueckmeldungen', json={
        'conversation_id': gespraech, 'message_id': nachricht['id'], 'art': 'falsch', 'richtig': ' bis Freitag '})
    assert r.status_code == 201
    m = r.json()['meldung']
    assert r.json()['offen'] == 1 and m['status'] == 'offen' and m['richtig'] == 'bis Freitag'
    assert 'AURORA-4711' in m['frage'] and m['antwort'] == nachricht['content']
    assert m['belege'] == [quelle] and m['gespraech_id'] == gespraech and m['nachricht_id'] == nachricht['id']
    assert m['struktur']['status'] == 'source_report'
    assert set(m['modell']) >= {'antwort', 'frage', 'hintergrund'}
    assert all(set(v) == {'anbieter', 'modell', 'lokal', 'eigene_wahl'} for v in m['modell'].values())


def test_melden_schreibt_nichts_ins_gedaechtnis(api):
    app, client = api
    _, gespraech, nachricht = _antwort(client)
    vorher = (app.state.claims.revision, app.state.proposals.counts(), app.state.episodes.count()
              if hasattr(app.state.episodes, 'count') else None, len(app.state.conversations.messages(gespraech)))
    client.post('/api/v1/rueckmeldungen', json={'conversation_id': gespraech, 'message_id': nachricht['id'],
                                                 'art': 'falsch', 'richtig': 'etwas ganz anderes'})
    nachher = (app.state.claims.revision, app.state.proposals.counts(), app.state.episodes.count()
               if hasattr(app.state.episodes, 'count') else None, len(app.state.conversations.messages(gespraech)))
    assert nachher == vorher


def test_liste_erledigt_und_fehlerfaelle(api):
    app, client = api
    _, gespraech, nachricht = _antwort(client)
    leer = client.get('/api/v1/rueckmeldungen').json()
    assert leer['meldungen'] == [] and leer['zaehlung'] == {'gesamt': 0, 'offen': 0, 'erledigt': 0}
    assert [a['id'] for a in leer['arten']] == list(ARTEN)
    kennung = client.post('/api/v1/rueckmeldungen', json={
        'conversation_id': gespraech, 'message_id': nachricht['id'], 'art': 'veraltet'}).json()['meldung']['id']
    assert client.get('/api/v1/rueckmeldungen', params={'status': 'offen'}).json()['zaehlung']['offen'] == 1
    e = client.patch(f'/api/v1/rueckmeldungen/{kennung}/erledigt')
    assert e.status_code == 200 and e.json()['meldung']['status'] == 'erledigt' and e.json()['offen'] == 0
    assert client.get('/api/v1/rueckmeldungen', params={'status': 'offen'}).json()['meldungen'] == []
    assert client.get('/api/v1/rueckmeldungen', params={'status': 'erledigt'}).json()['zaehlung']['erledigt'] == 1
    assert client.get('/api/v1/rueckmeldungen', params={'status': 'quatsch'}).status_code == 422
    assert client.patch('/api/v1/rueckmeldungen/gibtsnicht/erledigt').status_code == 404
    basis = {'conversation_id': gespraech, 'message_id': nachricht['id']}
    assert client.post('/api/v1/rueckmeldungen', json={**basis, 'art': 'boese'}).status_code == 422
    assert client.post('/api/v1/rueckmeldungen', json={**basis, 'art': 'falsch', 'frage': 'x'}).status_code == 422
    assert client.post('/api/v1/rueckmeldungen', json={**basis, 'message_id': 'fremd', 'art': 'falsch'}).status_code == 404
    # Die Frage des Nutzers ist keine Antwort: Gemeldet werden nur Antworten von Kingfisher.
    nutzer = next(m for m in app.state.conversations.messages(gespraech) if m.role == 'user')
    assert client.post('/api/v1/rueckmeldungen', json={**basis, 'message_id': nutzer.id, 'art': 'falsch'}).status_code == 404


def test_routen_brauchen_das_token(api):
    app, client = api
    offen = TestClient(app)
    try:
        assert offen.get('/api/v1/rueckmeldungen').status_code in (401, 403)
        assert offen.get('/api/v1/rueckmeldungen/faelle').status_code in (401, 403)
        assert offen.post('/api/v1/rueckmeldungen', json={}).status_code in (401, 403)
    finally:
        offen.close()


def test_export_ueber_die_route_enthaelt_auch_erledigtes(api):
    app, client = api
    _, gespraech, nachricht = _antwort(client)
    kennung = client.post('/api/v1/rueckmeldungen', json={
        'conversation_id': gespraech, 'message_id': nachricht['id'], 'art': 'falsch',
        'richtig': 'bis Freitag'}).json()['meldung']['id']
    client.patch(f'/api/v1/rueckmeldungen/{kennung}/erledigt')
    antwort = client.get('/api/v1/rueckmeldungen/faelle')
    assert antwort.status_code == 200
    assert 'attachment' in antwort.headers['content-disposition'] and antwort.headers['cache-control'] == 'no-store'
    daten = antwort.json()
    (fall,) = daten['fragen']
    assert fall['id'] == f'rueckmeldung-{kennung[:12]}' and fall['erwartet']['aussagen'] == [['bis Freitag']]
    assert 'Regressionstest' in fall['notiz'] and daten['nicht_messbar'] == []


def test_meldungen_sind_nach_der_wiederherstellung_da(tmp_path, monkeypatch):
    from icarus_memory import SelfModelStore, SqliteBackend
    from icarus_memory.audit import AuditLog
    from icarus_memory.episodes import EpisodeStore
    from icarus_memory.server import create_app
    from icarus_memory.tasks import TaskStore
    from icarus_memory.workspace import WorkspaceStore
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    backend = SqliteBackend(tmp_path / 'self-model.sqlite3')
    app = create_app(SelfModelStore(backend, subject_id='local'), audit=AuditLog(tmp_path / 'audit.sqlite3'),
                     tasks=TaskStore(tmp_path / 'tasks.sqlite3'), workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'),
                     episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'))
    app.state.backend = backend
    try:
        client = TestClient(app)
        alt = app.state.rueckmeldungen
        m = alt.melden(frage='f', antwort='a', art='falsch', nachricht_id='m1')
        name = client.post('/backups').json()['name']
        alt.melden(frage='g', antwort='b', art='falsch', nachricht_id='m2')
        alt.erledigt(m['id'])
        assert client.post('/backups/restore', json={'name': name}).status_code == 200
        with pytest.raises(Exception):   # das alte Handle ist geschlossen
            alt.liste()
        frisch = Rueckmeldungen(tmp_path / 'rueckmeldungen.sqlite3')
        try:
            (da,) = frisch.liste()
            assert da['id'] == m['id'] and da['status'] == 'offen'
        finally:
            frisch.close()
    finally:
        app.state.scheduler.stop()


def test_rueckmeldungen_gehoeren_zur_sicherung_und_zur_schemapruefung():
    from icarus_memory import update_backup
    from icarus_memory.backup import BACKUP_DATA_FILES, SQLITE_DATA_FILES
    assert 'rueckmeldungen.sqlite3' in SQLITE_DATA_FILES and 'rueckmeldungen.sqlite3' in BACKUP_DATA_FILES
    assert 'rueckmeldungen.sqlite3' in update_backup._targets()
