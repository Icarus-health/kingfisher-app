"""Alles zu einer Person: Auskunft, Löschen und Sperrvermerk (Persona-Prüfung, Paket P, D7). Nur synthetische Daten."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.kontakte import fuer_mail, teilnehmer_texte
from icarus_memory.person_sperre import GesperrteQuelle

from .test_conversation_retraction import _close_app, _make_app

LEA = 'lea@kanzlei.example'
DORA = 'Dora Lind <dora.lind@lind-verwaltung.example>'
DORA_ADR = 'dora.lind@lind-verwaltung.example'
ANNA = 'Anna Keller <anna.keller@praxis-umbau.example>'
ANNA_ADR = 'anna.keller@praxis-umbau.example'
BEN = 'Ben Braun <ben.braun@tischlerei.example>'
NAME = 'Dora Lind <dora.lind@lind-verwaltung.example>'
JETZT = datetime.now(timezone.utc)


def _mail(app, titel, text, *, von, an=(), cc=(), stunden=2, schluessel=None):
    empf = [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'an'} for a in an]
    empf += [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'cc'} for a in cc]
    kontakte = fuer_mail(von, empf, eigene=[LEA])
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, text,
        Provenance(SourceType.EMAIL, source_ref=f'test:<{titel}@x.invalid>'),
        participants=teilnehmer_texte(kontakte, absender_text=von), contacts=kontakte,
        occurred_at=JETZT - timedelta(hours=stunden), source_key=schluessel or f'mail:test:{titel}')
    # Wie die Mailaufnahme: Die Quelle wird die geltende Fassung (und kommt damit in den Suchindex).
    from icarus_memory.source_versions import track_source
    track_source(app.state.episodes, app.state.claims, schluessel or f'mail:test:{titel}', episode)
    return episode


@pytest.fixture
def welt(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    app.state.settings.mail.user = LEA
    lea = f'Lea Hartmann <{LEA}>'
    nur = _mail(app, 'Entwurf', 'Hallo Lea,\nkannst du mir bitte bis Freitag den Entwurf schicken?\nDora',
                von=DORA, an=[lea])
    nur2 = _mail(app, 'Nebenkosten', 'Hallo Lea,\ndie Nebenkostenabrechnung liegt bei.\nDora Lind',
                 von=DORA, an=[lea], stunden=30)
    geteilt = _mail(app, 'Rechnung 4711',
                    'Hallo Lea,\nAnna prüft die Rechnung 4711 bis Mittwoch.\nDora Lind bekommt eine Kopie, '
                    'Anna (anna.keller@praxis-umbau.example) auch.\nGruß Ben',
                    von=BEN, an=[lea, ANNA], cc=[DORA], stunden=5)
    anna = _mail(app, 'Vollmacht', 'Hallo Lea,\nbitte die Vollmacht schicken.\nAnna', von=ANNA, an=[lea], stunden=3)
    from icarus_memory.model import Provenance as P
    aufgabe = app.state.tasks.add('Entwurf an Dora schicken', P(SourceType.INFERENCE, source_ref=f'episode:{nur.id}'))
    fremde = app.state.tasks.add('Vollmacht an Anna schicken', P(SourceType.INFERENCE, source_ref=f'episode:{anna.id}'))
    client = TestClient(app)
    yield app, client, {'nur': nur, 'nur2': nur2, 'geteilt': geteilt, 'anna': anna, 'aufgabe': aufgabe,
                        'fremde': fremde}
    _close_app(app)


def _personen(client):
    return {p['name'] for p in client.get('/people').json()}


def test_vorschau_zaehlt_was_geloescht_wird_und_was_bleibt(welt):
    app, client, d = welt
    antwort = client.get(f'/api/v1/memory/people/{NAME}/loeschen')
    assert antwort.status_code == 200, antwort.text
    zahlen = antwort.json()['zahlen']
    assert zahlen['quellen_nur_ihre'] == 2
    assert zahlen['quellen_geteilt'] == 1
    assert zahlen['aufgaben'] == 1
    assert antwort.json()['name'] == 'Dora Lind'


def test_unbekannte_person_antwortet_mit_grund(welt):
    _, client, _ = welt
    antwort = client.get('/api/v1/memory/people/Niemand%20Da/loeschen')
    assert antwort.status_code == 404
    assert 'kommt' in antwort.json()['detail']
    assert client.post('/api/v1/memory/people/Niemand%20Da/loeschen').status_code == 404


def test_auskunft_ist_zip_mit_html_und_json_nur_zu_ihr(welt):
    app, client, d = welt
    antwort = client.get(f'/api/v1/memory/people/{NAME}/auskunft')
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers['content-type'] == 'application/zip'
    assert 'attachment' in antwort.headers['content-disposition']
    archiv = zipfile.ZipFile(io.BytesIO(antwort.content))
    assert sorted(archiv.namelist()) == ['Auskunft.html', 'Auskunft.json']
    daten = json.loads(archiv.read('Auskunft.json'))
    seite = archiv.read('Auskunft.html').decode()
    assert daten['person']['name'] == 'Dora Lind'
    assert DORA_ADR in daten['person']['adressen']
    titel = {q['titel'] for q in daten['quellen']}
    assert titel == {'Entwurf', 'Nebenkosten', 'Rechnung 4711'}
    assert any('Entwurf an Dora schicken' == a['titel'] for a in daten['aufgaben'])
    # Ihre eigenen Mails ganz, aus der geteilten nur die Zeile, die sie nennt.
    entwurf = next(q for q in daten['quellen'] if q['titel'] == 'Entwurf')
    assert 'Entwurf schicken' in ' '.join(entwurf['auszug'])
    geteilt = next(q for q in daten['quellen'] if q['titel'] == 'Rechnung 4711')
    assert geteilt['auszug'] == ['Dora Lind bekommt eine Kopie, Anna ([Adresse]) auch.']
    assert geteilt['weitere_beteiligte'] == 2
    # Nichts von anderen: weder Adressen noch Sätze ohne sie, weder Annas Mail noch ihre Aufgabe.
    for text in (json.dumps(daten, ensure_ascii=False), seite):
        assert ANNA_ADR not in text and 'ben.braun' not in text
        assert 'Anna prüft die Rechnung' not in text
        assert 'Vollmacht' not in text
        assert LEA not in text
    assert '<script' not in seite.lower()
    assert 'Was Kingfisher über Dora Lind weiß' in seite


def test_auskunft_maskiert_html(welt):
    app, client, d = welt
    _mail(app, '<b>Fett</b>', 'Hallo <script>alert(1)</script>', von=DORA, an=[f'Lea <{LEA}>'])
    archiv = zipfile.ZipFile(io.BytesIO(client.get(f'/api/v1/memory/people/{NAME}/auskunft').content))
    seite = archiv.read('Auskunft.html').decode()
    assert '<script>' not in seite and '&lt;script&gt;' in seite and '&lt;b&gt;Fett' in seite


def test_loeschen_entfernt_alles_und_sperrt(welt):
    app, client, d = welt
    assert 'Dora Lind' in _personen(client)
    antwort = client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    assert antwort.status_code == 200, antwort.text
    ergebnis = antwort.json()
    assert ergebnis['zahlen']['quellen_nur_ihre'] == 2 and ergebnis['sperre']
    # Sie ist weg, Anna und Ben bleiben.
    namen = _personen(client)
    assert 'Dora Lind' not in namen and 'Anna Keller' in namen and 'Ben Braun' in namen
    assert client.get(f'/api/v1/memory/people/{NAME}').status_code == 404
    # Quellen nur mit ihr: aus Kingfisher entfernt.
    from icarus_memory.episodes import EpisodeError
    for schluessel in ('nur', 'nur2'):
        with pytest.raises(EpisodeError):
            app.state.episodes.get(d[schluessel].id)
    # Geteilte Quelle bleibt, ohne sie als Beteiligte, Text unverändert.
    geteilt = app.state.episodes.get(d['geteilt'].id)
    assert all(DORA_ADR not in t for t in geteilt.participants)
    assert all(c.get('adresse') != DORA_ADR for c in geteilt.contacts)
    assert 'Dora Lind bekommt eine Kopie' in geteilt.body
    assert any(ANNA_ADR in t for t in geteilt.participants)
    # Ihre Aufgabe weg, Annas bleibt.
    assert app.state.tasks.get(d['aufgabe'].id) is None
    assert app.state.tasks.get(d['fremde'].id) is not None
    # Sperrvermerk ohne Adresse im Klartext.
    sperren = client.get('/api/v1/personen/sperre').json()['sperren']
    assert [s['anzeige'] for s in sperren] == ['Dora Lind']
    with app.state.episodes._lock:
        roh = app.state.episodes._conn.execute('SELECT schluessel FROM personen_sperre').fetchone()[0]
    assert DORA_ADR not in roh and 'dora' not in roh.lower()


def test_loeschen_laesst_keine_spur_in_suche_und_akten(welt):
    app, client, d = welt
    from icarus_memory import source_index
    from icarus_memory.akten_routes import nachfuehren
    nachfuehren(app, warten=True)
    with app.state.episodes._lock:
        # Vorbedingung: Ihre Quellen und ihre Adresse stehen im Volltextindex.
        assert len(app.state.episodes._conn.execute("SELECT episode_id FROM source_index_docs WHERE episode_id IN (?, ?)",
                                                    (d['nur'].id, d['nur2'].id)).fetchall()) == 2
        assert app.state.episodes._conn.execute("SELECT COUNT(*) FROM source_index WHERE source_index MATCH ?",
                                                ('"lind-verwaltung"',)).fetchone()[0] >= 3
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    nachfuehren(app, warten=True)
    conn = app.state.episodes._conn
    with app.state.episodes._lock:
        # Volltext: weder ihre Quellen noch ihre Adresse als Beteiligte.
        treffer = conn.execute("SELECT episode_id FROM source_index_docs WHERE episode_id IN (?, ?)",
                               (d['nur'].id, d['nur2'].id)).fetchall()
        assert treffer == []
        assert conn.execute("SELECT COUNT(*) FROM source_index WHERE source_index MATCH ?",
                            ('"lind-verwaltung"',)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sach_bezuege WHERE sache LIKE 'person:%dora%' "
                            "OR sache LIKE 'person:n:doralind%'").fetchone()[0] == 0
        for tabelle in ('working_memory_items', 'working_memory_sources', 'source_heads', 'sach_quellen'):
            assert conn.execute(f'SELECT COUNT(*) FROM {tabelle} WHERE episode_id IN (?, ?)',
                                (d['nur'].id, d['nur2'].id)).fetchone()[0] == 0, tabelle
    # Die Volltextsuche der App findet ihre Mails nicht mehr, Annas schon.
    assert all(e.id not in (d['nur'].id, d['nur2'].id) for e in app.state.episodes.search('Nebenkostenabrechnung'))
    assert app.state.episodes.search('Vollmacht')
    # Zwischenspeicher (Verzeichnis, Akten) liefern sie nicht.
    verzeichnis = client.get('/api/v1/memory/verzeichnis').json()
    assert 'Dora Lind' not in json.dumps(verzeichnis, ensure_ascii=False)
    akten = client.get('/api/v1/akten').json() if client.get('/api/v1/akten').status_code == 200 else {}
    assert 'dora.lind' not in json.dumps(akten)


def test_naechstes_einlesen_legt_sie_nicht_wieder_an(welt):
    app, client, d = welt
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    lea = f'Lea Hartmann <{LEA}>'
    # Dieselbe Mail nur mit ihr kommt nicht wieder herein.
    with pytest.raises(GesperrteQuelle):
        _mail(app, 'Entwurf', 'Hallo Lea,\nkannst du mir bitte bis Freitag den Entwurf schicken?\nDora',
              von=DORA, an=[lea])
    # Eine neue Mail an sie und Anna kommt ohne sie herein.
    neu = _mail(app, 'Termin', 'Treffen am Montag.', von=ANNA, an=[lea, DORA])
    assert all(DORA_ADR not in t for t in neu.participants)
    assert 'Dora Lind' not in _personen(client)
    # Ein Nachtrag der Beteiligten bringt sie nicht zurück.
    nachtrag = app.state.episodes.add_contacts(neu.id, [{'adresse': DORA_ADR, 'name': 'Dora Lind', 'rolle': 'cc'}],
                                               [DORA])
    assert all(c.get('adresse') != DORA_ADR for c in nachtrag.contacts)
    assert 'Dora Lind' not in _personen(client)
    # Ein Termin nur mit ihr (ohne Kontaktliste, eigene Adresse aus den Einstellungen) bleibt draußen.
    with pytest.raises(GesperrteQuelle):
        app.state.episodes.record(EpisodeKind.EVENT, 'Kaffee', 'Kaffee mit Dora',
                                  Provenance(SourceType.CALENDAR, source_ref='kal:1'),
                                  participants=[DORA, lea], source_key='kal:1')


def test_namensvetter_mit_anderer_adresse_bleibt(welt):
    app, client, d = welt
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    andere = _mail(app, 'Andere Dora', 'Hallo', von='Dora Lind <dora@anderswo.example>', an=[f'Lea <{LEA}>'])
    assert any('dora@anderswo.example' in t for t in andere.participants)


def test_sperre_aufheben_laesst_sie_wieder_herein(welt):
    app, client, d = welt
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    kennung = client.get('/api/v1/personen/sperre').json()['sperren'][0]['kennung']
    antwort = client.delete(f'/api/v1/personen/sperre/{kennung}')
    assert antwort.status_code == 200 and antwort.json()['aufgehoben']['anzeige'] == 'Dora Lind'
    assert client.delete(f'/api/v1/personen/sperre/{kennung}').status_code == 404
    _mail(app, 'Wieder da', 'Hallo Lea', von=DORA, an=[f'Lea <{LEA}>'])
    assert 'Dora Lind' in _personen(client)


def test_verlaeufe_bleiben_nach_dem_loeschen_geschuetzt(welt, tmp_path):
    app, client, d = welt
    app.state.tasks.complete(d['aufgabe'].id)
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    with app.state.tasks._lock:
        conn = app.state.tasks._conn
        assert conn.execute('SELECT COUNT(*) FROM task_events WHERE task_id=?', (d['aufgabe'].id,)).fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM task_events WHERE task_id=?', (d['fremde'].id,)).fetchone()[0] >= 1
        import sqlite3
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute('DELETE FROM task_events')
        conn.rollback()
    # Die Ablagen öffnen sich wieder (Schemaprüfung samt Schutz).
    from icarus_memory.tasks import TaskStore
    TaskStore(tmp_path / 'tasks.sqlite3').close()


def test_aussagen_und_vorschlaege_zu_ihr_fallen_weg(welt):
    app, client, d = welt
    from icarus_memory.graph import person_id_fuer
    from icarus_memory.proposals import Evidence
    kennung = person_id_fuer('a:' + DORA_ADR)
    vorschlag, _ = app.state.knowledge_service.propose(
        subject_ref=kennung, predicate='works_at', value='Lind Verwaltung', statement='Dora arbeitet bei Lind.',
        rationale='Signatur', evidence=[Evidence(episode_id=d['nur2'].id, quote='Dora Lind', digest=d['nur2'].digest)],
        proposed_by='test')
    claim = app.state.knowledge_service.accept(vorschlag.id, supersedes=[])
    offen, _ = app.state.knowledge_service.propose(
        subject_ref=kennung, predicate='role', value='Verwalterin', statement='Dora ist Verwalterin.',
        rationale='Text', evidence=[Evidence(episode_id=d['nur'].id, quote='Dora', digest=d['nur'].digest)],
        proposed_by='test')
    zahlen = client.get(f'/api/v1/memory/people/{NAME}/loeschen').json()['zahlen']
    assert zahlen['aussagen'] == 1 and zahlen['offene_vorschlaege'] == 1
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    with app.state.claims._lock:
        assert app.state.claims._conn.execute('SELECT COUNT(*) FROM knowledge_claims WHERE id=?',
                                              (claim.id,)).fetchone()[0] == 0
    with app.state.proposals._lock:
        assert app.state.proposals._conn.execute('SELECT COUNT(*) FROM proposals WHERE id IN (?, ?)',
                                                 (vorschlag.id, offen.id)).fetchone()[0] == 0


def test_erwaehnung_im_text_wird_keine_akte(welt):
    """Eine geteilte Quelle nennt sie im Text; das Modell hat den Namen als Person erkannt. Gesperrt: keine Akte."""
    app, client, d = welt
    from icarus_memory import bezuege
    from icarus_memory.person_sperre import fuer
    episode = app.state.episodes.get(d['geteilt'].id)
    start = episode.body.index('Dora Lind')
    auszug = {'entities': [{'kind': 'person', 'name': 'Dora Lind', 'start': start, 'end': start + 9, 'role': 'mentioned'}]}
    ohne = bezuege.Register.bauen([], eigene=[LEA])
    assert any(b.sache.startswith('person:') and b.grundlage == 'modell'
               for b in bezuege.berechnen(episode, auszug, ohne, [LEA]))
    fuer(app.state.episodes).eintragen('Dora Lind', [DORA_ADR], ['Dora Lind'])
    mit = bezuege.Register.bauen([], eigene=[LEA], gesperrt=fuer(app.state.episodes).schluessel())
    assert mit.token != ohne.token
    assert not any(b.sache.startswith('person:') and b.grundlage == 'modell'
                   for b in bezuege.berechnen(episode, auszug, mit, [LEA]))


def test_logbuch_vermerke_zu_ihr_fallen_weg_und_der_schutz_bleibt(welt, tmp_path):
    app, client, d = welt
    from icarus_memory import logbuch
    from icarus_memory.akten_routes import nachfuehren
    nachfuehren(app, warten=True)
    buch = app.state.logbuch
    buch.vermerke('akte_neu', sache='person:a:' + DORA_ADR, name='Dora Lind')
    buch.vermerke('akte_neu', sache='person:a:' + ANNA_ADR, name='Anna Keller')

    def alle():
        with buch._lock:
            return [r[0] for r in buch._conn.execute('SELECT daten FROM ereignis').fetchall()]
    assert any('dora' in z for z in alle())
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    rest = alle()
    assert not any('dora' in z.lower() for z in rest)
    assert any('anna.keller' in z for z in rest)
    import sqlite3
    with buch._lock, pytest.raises(sqlite3.DatabaseError):
        buch._conn.execute('DELETE FROM ereignis')
    buch._conn.rollback()
    # Die Ablage öffnet sich wieder mit geprüftem Schutz.
    logbuch.Logbuch(tmp_path / 'logbuch.sqlite3').close()


def test_aufheben_laesst_sich_zuruecknehmen(welt):
    app, client, d = welt
    client.post(f'/api/v1/memory/people/{NAME}/loeschen')
    kennung = client.get('/api/v1/personen/sperre').json()['sperren'][0]['kennung']
    antwort = client.delete(f'/api/v1/personen/sperre/{kennung}').json()
    assert 'schluessel' not in antwort['aufgehoben']
    assert client.post(f'/api/v1/personen/sperre/{kennung}/zurueck').status_code == 200
    assert [s['kennung'] for s in client.get('/api/v1/personen/sperre').json()['sperren']] == [kennung]
    with pytest.raises(GesperrteQuelle):
        _mail(app, 'Nochmal', 'Hallo Lea', von=DORA, an=[f'Lea <{LEA}>'])
    assert client.post(f'/api/v1/personen/sperre/{kennung}/zurueck').status_code == 404


def test_bedeutungssuche_liefert_nichts_mehr_und_vergisst_die_vektoren(welt):
    """Semantische Suche: Ihre Quelle hatte einen Vektor; nach dem Löschen findet die Suche sie nicht, der Vektor ist weg."""
    import threading
    from icarus_memory.working_memory_semantic_index import DurableSemanticIndex
    from icarus_memory.working_memory_store import WorkingMemoryStore
    app, client, d = welt
    speicher = WorkingMemoryStore(app.state.episodes)
    for schluessel in ('nur', 'anna'):
        snapshot = speicher._snapshot(d[schluessel].id)
        assert speicher.commit(snapshot, [{'start': 0, 'end': len(d[schluessel].body), 'kind': 'fact'}], model='test')
    index = DurableSemanticIndex(app.state.episodes, 'local-test:' + 'c' * 64)
    stapel = index.pending(8)
    assert {r['episode_id'] for r in stapel.refs} == {d['nur'].id, d['anna'].id}
    vektoren = [[1., 0., 0.] if r['episode_id'] == d['nur'].id else [0., 1., 0.] for r in stapel.refs]
    assert index.commit(stapel, vektoren) == 2
    assert [r['episode_id'] for r in index.search([1., 0., 0.]).refs] == [d['nur'].id]

    class Dienst:
        _index = index
        _lock = threading.RLock()
    app.state.semantic_search = Dienst()
    try:
        assert client.post(f'/api/v1/memory/people/{NAME}/loeschen').json()['vektoren'] == 1
        assert index.search([1., 0., 0.]).refs == ()
        assert [r['episode_id'] for r in index.search([0., 1., 0.]).refs] == [d['anna'].id]
        with index._lock:
            assert index._conn.execute('SELECT COUNT(*) FROM entries WHERE episode_id=?', (d['nur'].id,)).fetchone()[0] == 0
    finally:
        app.state.semantic_search = None
        index.close()
