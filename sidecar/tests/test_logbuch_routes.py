"""Logbuch im Briefing und als Verlauf: Zeilen, Sitzungsregel, Route, Nachführen der Akten, Sicherung. Nur synthetische Daten."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import logbuch, logbuch_routes, tagesbriefing
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api
from tests.test_terminvorbereitung import ANNA, BEN, ICH, _mail


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    app.state.settings.mail.user = 'lea@hartmann-beratung.example'
    try:
        yield app, client
    finally:
        client.close()
        logbuch.verbinde(None)


def test_das_logbuch_liegt_im_datenordner_und_ist_aktiv(api, tmp_path):
    app, _ = api
    assert logbuch.aktiv() is app.state.logbuch
    assert (tmp_path / 'source-answer-api' / 'logbuch.sqlite3').is_file()


def test_tagesbriefing_hat_die_zeilen_ganz_oben(api):
    app, client = api
    logbuch.vermerke('quellen', sorte='mail', anzahl=41)
    logbuch.vermerke('akte_neu', sache='person:a:anna@agentur.example', name='Anna Keller')
    logbuch.vermerke('akte_neu', sache='projekt:mainz', name='Mainz')
    logbuch.vermerke('lint', befunde={'widerspruch': 1})
    lage = client.get('/api/v1/tag/briefing').json()['tageslage']
    erste, zweite = lage['verlauf']
    # Das Logbuch ist heute angelegt: „Heute:“, kein „Seit gestern Abend“ am Tag der Einrichtung (Befund 29).
    assert erste == 'Heute: 41 Mails aufgenommen, 2 neue Akten (Anna Keller, Projekt Mainz).'
    assert zweite == '1 Widerspruch gefunden.'


def test_ohne_ereignisse_steht_da_nichts_neues(api):
    _, client = api
    lage = client.get('/api/v1/tag/briefing').json()['tageslage']
    assert lage['verlauf'] == ['Heute noch nichts Neues.']


def test_neuladen_zeigt_dieselben_zeilen(api):
    _, client = api
    logbuch.vermerke('export', was='selbstmodell')
    erste = client.get('/api/v1/tag/briefing').json()['tageslage']['verlauf']
    zweite = client.get('/api/v1/tag/briefing').json()['tageslage']['verlauf']
    assert erste == zweite and 'Export' in erste[0]


def test_stilles_nachladen_zaehlt_nicht_als_blick(api):
    app, client = api
    logbuch.vermerke('export', was='selbstmodell')
    zeilen = client.get('/api/v1/tag/briefing', params={'nachladen': True}).json()['tageslage']['verlauf']
    assert 'Export' in zeilen[0] and app.state.logbuch._marke('blick') is None   # die Zeilen stehen, der Blick ist nicht gebucht
    client.get('/api/v1/tag/briefing')
    assert app.state.logbuch._marke('blick') is not None   # das Öffnen bucht


def test_morgenbriefing_traegt_die_zeilen(api):
    _, client = api
    logbuch.vermerke('export', was='selbstmodell')
    antwort = client.get('/api/v1/morning-briefing')
    assert antwort.status_code == 200
    assert 'Export' in antwort.json()['verlauf'][0]


def test_ein_kaputtes_logbuch_laesst_das_briefing_stehen(api, monkeypatch):
    app, client = api
    monkeypatch.setattr(app.state.logbuch, 'bezugspunkt', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('kaputt')))
    antwort = client.get('/api/v1/tag/briefing')
    assert antwort.status_code == 200 and antwort.json()['tageslage']['verlauf'] == []


def test_verlauf_route_gruppiert_nach_tagen_und_zaehlt_nicht_als_blick(api):
    app, client = api
    logbuch.vermerke('quellen', sorte='mail', anzahl=3)
    logbuch.vermerke('akte_neu', sache='projekt:mainz', name='Mainz')
    antwort = client.get('/api/v1/logbuch')
    assert antwort.status_code == 200
    daten = antwort.json()
    assert [t['titel'] for t in daten['tage']] == ['Heute']
    assert daten['tage'][0]['eintraege'] == ['3 Mails aufgenommen', '1 neue Akte (Projekt Mainz)']
    assert daten['leer'] is False and daten['zeilen'][0].startswith('Heute: ')
    assert app.state.logbuch._marke('blick') is None   # Ansehen ist kein Blick


def test_verlauf_route_mit_seit_und_fehlern(api):
    _, client = api
    logbuch.vermerke('export', was='selbstmodell')
    morgen = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert client.get('/api/v1/logbuch', params={'seit': morgen}).json()['tage'] == []   # Zukunft wird auf jetzt gekürzt
    assert client.get('/api/v1/logbuch', params={'seit': '2020-01-01T00:00:00Z'}).json()['tage'][0]['eintraege'] == ['1 Export angelegt']
    assert client.get('/api/v1/logbuch', params={'seit': 'gestern'}).status_code == 422
    leer = client.get('/api/v1/logbuch', params={'seit': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}).json()
    assert leer['leer'] is True and leer['zeilen'][0].startswith('Nichts Neues')


def test_routen_verlangen_das_zugangswort(api):
    _, client = api
    assert client.get('/api/v1/logbuch', headers={'X-Icarus-Token': 'falsch'}).status_code in (401, 403)


def test_akten_nachfuehren_schreibt_neue_akten_ins_logbuch(api):
    app, client = api
    _mail(app, 'Format', [('Das Plakat hätte ich gern im Format A2.', 'fact')], [ANNA, ICH], tage=30)
    client.get('/api/v1/akten/sachen', params={'warten': True})   # erster Abgleich: nur der Stand, Altes ist nicht neu
    assert [e for e in app.state.logbuch.ereignisse(0) if e.art.startswith('akte')] == []
    _mail(app, 'Angebot', [('Das Angebot der Druckerei liegt bei 1.200 Euro.', 'status')], [BEN, ICH], tage=0)
    client.get('/api/v1/akten/sachen', params={'warten': True})
    neu = [e.daten['name'] for e in app.state.logbuch.ereignisse(0) if e.art == 'akte_neu']
    assert any('Ben' in n for n in neu), neu
    vorher = len(app.state.logbuch.ereignisse(0))
    client.get('/api/v1/akten/sachen', params={'warten': True})
    assert len(app.state.logbuch.ereignisse(0)) == vorher   # nichts doppelt


def test_export_landet_im_logbuch(api, tmp_path):
    app, client = api
    antwort = client.post('/export/file', json={})
    assert antwort.status_code == 200
    assert [e.art for e in app.state.logbuch.ereignisse(0)] == ['export']
    assert 'selbstmodell' in str(app.state.logbuch.ereignisse(0)[0].daten) and str(tmp_path) not in str(app.state.logbuch.ereignisse(0)[0].daten)


def test_tageslage_to_dict_hat_verlauf_und_zaehlt_nicht_zu_den_zeilen():
    lage = tagesbriefing.erstellen([], [], None, jetzt=datetime(2026, 9, 30, 7, 10, tzinfo=timezone.utc),
                                   verlauf=['Seit gestern Abend: 1 Mail aufgenommen.'])
    assert lage.to_dict()['verlauf'] == ['Seit gestern Abend: 1 Mail aufgenommen.'] and lage.zeilen == []
    assert tagesbriefing.erstellen([], [], None, jetzt=datetime(2026, 9, 30, tzinfo=timezone.utc)).verlauf == []


def test_wiederherstellung_oeffnet_das_logbuch_neu(api, tmp_path):
    app, _ = api
    alt = app.state.logbuch
    alt.befunde_lieferant = lambda: {'widerspruch': 1}
    neu = logbuch_routes.verbinden(app, lambda: tmp_path / 'source-answer-api')
    assert neu is app.state.logbuch is logbuch.aktiv() and neu is not alt
    assert neu.befunde_lieferant is alt.befunde_lieferant   # der Lieferant überlebt das Neuöffnen
