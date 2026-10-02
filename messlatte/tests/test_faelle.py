"""Der Weg vom Rückkanal in die Messlatte: Meldung, Fälle-Datei, `lokal` liest sie und fängt die Wiederholung."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from skriptmodell import SkriptModell

from messlatte import lokal
from messlatte.__main__ import main
from messlatte.aufnahme import aufnehmen
from messlatte.instanz import instanz_starten
from messlatte.welt import WeltFehler, lade_welt, pruefe_fragen_lokal

MINI = Path(__file__).parent / 'mini_welt'
BEISPIEL = Path(__file__).resolve().parents[1] / 'beispiel-eigene-fragen.json'
FRAGE = 'Bis wann muss die Umsatzsteuervoranmeldung abgegeben werden?'


@pytest.fixture(scope='module')
def instanz():
    welt = lade_welt(MINI)
    modell = SkriptModell({'Umsatzsteuervoranmeldung': ['Umsatzsteuervoranmeldung']})
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, provider=modell) as instanz:
        aufnehmen(instanz, welt.quellen, welt.stichtag, modell=modell)
        yield instanz


@pytest.fixture(autouse=True)
def frische_ablage(instanz):
    """Jeder Test beginnt ohne Meldungen (die Instanz ist modulweit geteilt)."""
    ablage = instanz.app.state.rueckmeldungen
    ablage._conn.execute('DELETE FROM rueckmeldung')
    ablage._conn.commit()


def _assistent(antwort):
    # Unter der eingefrorenen Uhr haben Frage und Antwort denselben Zeitstempel: die Antwort des Assistenten suchen.
    return next(m for m in reversed(antwort['messages']) if m['role'] == 'assistant')


def _gefragt(instanz):
    """Stellt die Frage wie die Oberfläche und liefert (Gespräch, Antwortnachricht)."""
    c = instanz.client
    gespraech = c.post('/api/v1/conversations', json={}).json()['conversation']['id']
    antwort = c.post(f'/api/v1/conversations/{gespraech}/messages', json={'message': FRAGE, 'answer_mode': 'auto'})
    assert antwort.status_code == 201
    return gespraech, _assistent(antwort.json())


def _melde(instanz, gespraech, nachricht, art, richtig=''):
    r = instanz.client.post('/api/v1/rueckmeldungen', json={
        'conversation_id': gespraech, 'message_id': nachricht['id'], 'art': art, 'richtig': richtig})
    assert r.status_code == 201, r.text
    return r.json()['meldung']


def _fragen_datei(instanz, tmp_path):
    export = instanz.client.get('/api/v1/rueckmeldungen/faelle')
    assert export.status_code == 200
    datei = tmp_path / 'fragen.json'
    datei.write_text(export.text, encoding='utf-8')
    return datei


class OhneSchliessen:
    def __init__(self, client):
        self._client = client

    def request(self, methode, url, **kwargs):
        return self._client.request(methode, url, **kwargs)

    def close(self):
        pass


def test_gemeldete_falsche_antwort_wird_fall_und_die_wiederholung_faellt_auf(instanz, tmp_path):
    gespraech, nachricht = _gefragt(instanz)
    assert 'Quelle berichtet' in nachricht['content']
    _melde(instanz, gespraech, nachricht, 'falsch')
    fragen = lokal.lade_fragen(_fragen_datei(instanz, tmp_path))   # dieselbe Prüfung wie bei „lokal“
    (frage,) = fragen
    assert frage.frage == FRAGE and frage.schwere == 'kritisch' and frage.herkunft == 'lokal'
    assert frage.verboten.aussagen == (nachricht['content'].strip(),) and frage.erwartet.aussagen == ()
    # Dieselbe Antwort noch einmal: genau der Fehler, den der Fall festhalten soll.
    ergebnis = lokal.messen(instanz.client, fragen)
    assert ergebnis.auswertung.gesamt.falsche_aussagen == 1 and ergebnis.fragen[0][2].klasse == 'falsch'


def test_richtig_waere_wird_zur_erwarteten_aussage(instanz, tmp_path):
    gespraech, nachricht = _gefragt(instanz)
    _melde(instanz, gespraech, nachricht, 'unvollstaendig', richtig='Umsatzsteuervoranmeldung')
    fragen = lokal.lade_fragen(_fragen_datei(instanz, tmp_path))
    assert fragen[0].erwartet.aussagen == (('Umsatzsteuervoranmeldung',),) and fragen[0].schwere == 'normal'
    assert lokal.messen(instanz.client, fragen).fragen[0][2].klasse == 'richtig'
    # Und ein Wort, das die Antwort nicht enthält, fällt als fehlend auf (der Fall prüft wirklich etwas).
    _melde(instanz, gespraech, nachricht, 'unvollstaendig', richtig='gibt-es-nirgends-42')
    fragen = lokal.lade_fragen(_fragen_datei(instanz, tmp_path))
    assert lokal.messen(instanz.client, fragen).fragen[0][2].klasse == 'falsch'


def test_erledigte_meldung_bleibt_als_fall_in_der_datei(instanz, tmp_path):
    gespraech, nachricht = _gefragt(instanz)
    kennung = _melde(instanz, gespraech, nachricht, 'veraltet', richtig='Umsatzsteuervoranmeldung')['id']
    assert instanz.client.patch(f'/api/v1/rueckmeldungen/{kennung}/erledigt').status_code == 200
    (frage,) = lokal.lade_fragen(_fragen_datei(instanz, tmp_path))
    assert frage.id == f'rueckmeldung-{kennung[:12]}' and 'Regressionstest' in frage.notiz


def test_format_ist_das_der_beispieldatei(instanz, tmp_path):
    gespraech, nachricht = _gefragt(instanz)
    _melde(instanz, gespraech, nachricht, 'falsch', richtig='Umsatzsteuervoranmeldung')
    daten = json.loads(_fragen_datei(instanz, tmp_path).read_text(encoding='utf-8'))
    bekannt = {s for f in json.loads(BEISPIEL.read_text(encoding='utf-8'))['fragen'] for s in f}
    assert set(daten['fragen'][0]) <= bekannt
    assert {'hinweis', 'fragen', 'nicht_messbar'} == set(daten) and 'Antworttexte' in daten['hinweis']


def test_cli_faelle_aus_der_ablage_und_aus_json(instanz, tmp_path, capsys):
    gespraech, nachricht = _gefragt(instanz)
    _melde(instanz, gespraech, nachricht, 'falsch', richtig='Umsatzsteuervoranmeldung')
    zweite = instanz.client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    andere = instanz.client.post(f'/api/v1/conversations/{zweite}/messages',
                                 json={'message': 'Was kostet ein Flug nach Nirgendwo?', 'answer_mode': 'auto'}).json()
    _melde(instanz, zweite, _assistent(andere), 'zu_langsam')   # ohne Text nicht messbar
    # 1. aus der Liste der Routen
    liste = tmp_path / 'meldungen.json'
    liste.write_text(instanz.client.get('/api/v1/rueckmeldungen').text, encoding='utf-8')
    ziel = tmp_path / 'aus-json.json'
    assert main(['faelle', '--aus', str(liste), '--ausgabe', str(ziel)]) == 0
    aus_json = json.loads(ziel.read_text(encoding='utf-8'))
    assert len(aus_json['fragen']) == 1 and len(aus_json['nicht_messbar']) == 1
    assert aus_json == instanz.client.get('/api/v1/rueckmeldungen/faelle').json()   # eine Regel, nicht zwei
    # 2. aus der Ablage selbst, unverändert gelesen
    datei = instanz.app.state.rueckmeldungen._path
    kopie = tmp_path / 'rueckmeldungen.sqlite3'
    instanz.app.state.rueckmeldungen._conn.execute('PRAGMA wal_checkpoint(FULL)')
    kopie.write_bytes(datei.read_bytes())
    vorher = kopie.read_bytes()
    ziel2 = tmp_path / 'aus-db.json'
    assert main(['faelle', '--aus', str(kopie), '--ausgabe', str(ziel2)]) == 0
    assert json.loads(ziel2.read_text(encoding='utf-8')) == aus_json and kopie.read_bytes() == vorher
    # Terminal: Zähler und Hinweis, kein Frage- und kein Antworttext.
    ausgabe = capsys.readouterr()
    assert '2 Meldungen' in ausgabe.err and 'lokal --fragen' in ausgabe.err and 'Antworttexte' in ausgabe.err
    for text in (FRAGE, 'Umsatzsteuervoranmeldung', 'Nirgendwo', 'Quelle berichtet'):
        assert text not in ausgabe.out + ausgabe.err
    lokal.lade_fragen(ziel)


def test_cli_faelle_ohne_messbaren_fall_schreibt_die_datei_und_sagt_warum(instanz, tmp_path, capsys):
    gespraech, nachricht = _gefragt(instanz)
    _melde(instanz, gespraech, nachricht, 'zu_langsam')
    liste = tmp_path / 'meldungen.json'
    liste.write_text(instanz.client.get('/api/v1/rueckmeldungen').text, encoding='utf-8')
    ziel = tmp_path / 'leer.json'
    assert main(['faelle', '--aus', str(liste), '--ausgabe', str(ziel)]) == 0
    assert json.loads(ziel.read_text(encoding='utf-8'))['fragen'] == []
    assert 'Noch kein messbarer Fall' in capsys.readouterr().err


def test_cli_faelle_lehnt_falsche_dateien_verstaendlich_ab(tmp_path, capsys):
    from messlatte import faelle
    assert main(['faelle', '--aus', str(tmp_path / 'gibt-es-nicht.json')]) == 2
    assert 'Datei fehlt' in capsys.readouterr().err
    kaputt = tmp_path / 'x.json'
    kaputt.write_text('{"fragen": []}', encoding='utf-8')
    with pytest.raises(WeltFehler, match='Erwartet die Meldungen'):
        faelle.lese_meldungen(kaputt)
    fremd = tmp_path / 'fremd.sqlite3'
    sqlite3.connect(fremd).execute('CREATE TABLE x(a)').connection.commit()
    with pytest.raises(WeltFehler, match='keine Datei mit Rückmeldungen'):
        faelle.lese_meldungen(fremd)


def test_lokal_nimmt_eine_verbotene_aussage_als_messbar_nicht_aber_nichts():
    ok = pruefe_fragen_lokal([{'id': 'v-1', 'frage': 'Wann?', 'erwartet': {'verhalten': 'antworten'},
                               'verboten': {'aussagen': ['31. Oktober']}}])
    assert ok[0].verboten.aussagen == ('31. Oktober',)
    with pytest.raises(WeltFehler, match='Pflichtaussagen oder verbotene Aussagen'):
        pruefe_fragen_lokal([{'id': 'v-2', 'frage': 'Wann?', 'erwartet': {'verhalten': 'antworten'}}])
    with pytest.raises(WeltFehler, match='Pflichtaussagen oder verbotene Aussagen'):
        pruefe_fragen_lokal([{'id': 'v-3', 'frage': 'Wann?', 'erwartet': {'verhalten': 'antworten'},
                              'verboten': {'belege': ['e1']}}])
