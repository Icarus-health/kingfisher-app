"""„In die Akte übernehmen“: Vorschlag statt Fakt, Dopplung, Kennzeichnung, Akte, Routen. Nur synthetische Daten."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import akten_kontext, uebernehmen, working_memory_answers as wma
from icarus_memory.akten_routes import bausteine
from icarus_memory.frage import Anfrage
from icarus_memory.kennzeichnung import Kennzeichen, ANDERE_PERSON
from icarus_memory.proposals import ProposalKind, ProposalState
from icarus_memory.satzantwort import AntwortBeleg
from tests.test_akten import STIFTUNG, mail
from tests.test_bezuege import JETZT
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_satzantwort import Skript, nr
from tests.test_source_answers_http import _api

DIENSTAG = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)
FRAGE = 'Bis wann läuft die Einreichfrist beim Förderteam?'
SACHE = 'person:a:foerderung@stiftung.example'
SATZ_NEU = 'Die neue Einreichfrist ist der 12. November 2026.'
SATZ_WANDEL = 'Die Einreichfrist wurde von 15. Oktober 2026 auf 12. November 2026 verschoben.'


def _saetze(nutzer):
    return {'status': 'antwort', 'saetze': [
        {'text': SATZ_NEU, 'belege': [nr(nutzer, 'Verlängerung')]},
        {'text': SATZ_WANDEL, 'belege': [nr(nutzer, 'Ausschreibung'), nr(nutzer, 'Verlängerung')]}]}


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    monkeypatch.setattr(akten_kontext, '_heute', lambda: DIENSTAG.date())
    monkeypatch.setattr(wma, 'now', lambda: DIENSTAG)
    try:
        yield app, client
    finally:
        client.close()


def _quellen(app):
    episodes = app.state.episodes
    alt = mail(episodes, 'Ausschreibung', [('Die Laufzeit beträgt bis zu 18 Monate.', 'fact'),
                                           ('Die Einreichfrist ist der 15. Oktober 2026.', 'fact')], tage=30)
    neu = mail(episodes, 'Verlängerung', [(SATZ_NEU, 'change')], tage=10)
    return alt, neu


def _antwort(app, client, *, anfrage=True, saetze=_saetze, quellen=True, frage=FRAGE):
    """Zwei Mails, eine Satzantwort dazu und ein Gespräch, in dem sie steht: (Gespräch, Nachricht, Quellen)."""
    quellen = _quellen(app) if quellen else ()
    bausteine(app)[0].aktualisieren()
    episodes, claims = app.state.episodes, app.state.claims
    gespeichert = wma.prepare(frage, episodes, claims, Skript(saetze), saetze=True,
                              anfrage=Anfrage(sachen=('Förderteam',), absicht='frist') if anfrage else None)
    turn = app.state.agent._working_turn(frage, gespeichert, model_called=False)
    gespraech = app.state.conversations.create('Frist')
    app.state.conversations.add_message(gespraech.id, 'user', frage)
    nachricht = app.state.conversations.add_message(gespraech.id, 'assistant', turn.reply, metadata={'context': turn.context})
    return gespraech.id, nachricht.id, quellen


def _zustand(app):
    return (app.state.claims.revision, len(app.state.claims.all_claims()), app.state.proposals.counts())


def _vorschlagen(client, gespraech, nachricht, saetze, **mehr):
    return client.post('/api/v1/antworten/uebernehmen', json={
        'conversation_id': gespraech, 'message_id': nachricht, 'saetze': saetze, **mehr})


# -- Die Rückfrage --------------------------------------------------------------------------------------


def test_vorschau_zeigt_saetze_mit_vorgabe_hinweis_und_die_sachen_der_frage(api):
    app, client = api
    gespraech, nachricht, (alt, neu) = _antwort(app, client)
    r = client.get('/api/v1/antworten/uebernehmen', params={'conversation_id': gespraech, 'message_id': nachricht})
    assert r.status_code == 200
    daten = r.json()
    assert [s['text'] for s in daten['saetze']] == [SATZ_NEU, SATZ_WANDEL]
    sauber, gekennzeichnet = daten['saetze']
    assert sauber['vorgabe'] is True and sauber['hinweise'] == [] and sauber['steht_schon'] is False
    # Der Satz mit der überholten Quelle ist wählbar, aber nicht vorgewählt, und sagt warum.
    assert gekennzeichnet['vorgabe'] is False and 'überholt' in gekennzeichnet['hinweise'][0]
    assert daten['ziele'] == [{'sache': SACHE, 'name': 'Förderteam', 'art_text': 'Person'}] and daten['sache'] == SACHE
    assert daten['bisher'] == []


def test_ohne_sache_in_der_frage_kommt_das_ziel_aus_den_belegen(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client, anfrage=False)
    daten = client.get('/api/v1/antworten/uebernehmen',
                       params={'conversation_id': gespraech, 'message_id': nachricht}).json()
    assert SACHE in [z['sache'] for z in daten['ziele']] and daten['sache'] == daten['ziele'][0]['sache']


# -- Vorschlag statt Fakt -------------------------------------------------------------------------------


def test_vorschlagen_erzeugt_nur_einen_vorschlag_mit_beleg_und_keine_aussage(api):
    app, client = api
    gespraech, nachricht, (alt, neu) = _antwort(app, client)
    vorher = _zustand(app)
    nachrichten = len(app.state.conversations.messages(gespraech))
    r = _vorschlagen(client, gespraech, nachricht, [1], notiz='Wichtig für die Planung')
    assert r.status_code == 201
    daten = r.json()
    assert daten['sache'] == SACHE and daten['name'] == 'Förderteam'
    (ergebnis,) = daten['ergebnisse']
    assert ergebnis['status'] == 'vorgeschlagen' and ergebnis['nr'] == 1 and ergebnis['hinweise'] == []
    vorschlag = ergebnis['vorschlag']
    assert vorschlag['kind'] == 'knowledge' and vorschlag['state'] == 'pending' and vorschlag['produced'] is None
    assert vorschlag['statement'] == SATZ_NEU and vorschlag['subject_ref'] == SACHE and vorschlag['predicate'] == 'aussage'
    assert 'Notiz: Wichtig für die Planung' in vorschlag['rationale'] and FRAGE in vorschlag['rationale']
    (beleg,) = vorschlag['evidence']
    assert beleg['episode_id'] == neu.id and beleg['digest'] == neu.digest and beleg['quote'] in neu.body
    assert beleg['quote'] == SATZ_NEU
    # Die Regel des Gedächtnisses: kein Claim, keine Änderung am Bestand außer dem offenen Vorschlag, nichts im Gespräch.
    nachher = _zustand(app)
    assert nachher[0] == vorher[0] and nachher[1] == 0
    assert nachher[2].get('pending', 0) == vorher[2].get('pending', 0) + 1
    assert len(app.state.conversations.messages(gespraech)) == nachrichten
    (offen,) = app.state.knowledge_service.pending()
    assert offen.id == vorschlag['id'] and offen.kind is ProposalKind.KNOWLEDGE


def test_nach_der_annahme_steht_der_satz_als_aussage_mit_beleg_in_der_akte(api):
    app, client = api
    gespraech, nachricht, (alt, neu) = _antwort(app, client)
    kennung = _vorschlagen(client, gespraech, nachricht, [1]).json()['ergebnisse'][0]['vorschlag']['id']
    assert client.get('/api/v1/akten/akte', params={'sache': SACHE, 'warten': True}).json()['aussagen']['gesamt'] == 0
    # Die Antwort findet ihre Vorschläge wieder (etwa nach dem Neuladen der Seite), solange sie noch gilt.
    bisher = client.get('/api/v1/antworten/uebernehmen',
                        params={'conversation_id': gespraech, 'message_id': nachricht}).json()['bisher']
    assert [(v['id'], v['state']) for v in bisher] == [(kennung, 'pending')]
    angenommen = client.post(f'/api/v1/memory/candidates/{kennung}/accept', json={'supersedes': []})
    assert angenommen.status_code == 200 and angenommen.json()['statement'] == SATZ_NEU
    akte = client.get('/api/v1/akten/akte', params={'sache': SACHE, 'warten': True}).json()
    assert akte['aussagen']['gesamt'] == 1
    (aussage,) = akte['aussagen']['eintraege']
    assert aussage['text'] == SATZ_NEU and aussage['ueberholt'] is None
    assert [(b['episode_id'], b['titel'], b['zitat']) for b in aussage['belege']] == [(neu.id, 'Verlängerung', SATZ_NEU)]
    # Der Vorschlag kennt seine Aussage. Die Quelle ist damit in Wissen eingegangen: Die alte Antwort gilt als veraltet
    # (vorhandene Frischeprüfung), übernehmen lässt sich aus ihr nichts mehr.
    (angenommen_vorschlag,) = app.state.proposals.von(uebernehmen.vorschlag_von(gespraech, nachricht))
    assert angenommen_vorschlag.state is ProposalState.ACCEPTED and angenommen_vorschlag.produced
    assert _vorschlagen(client, gespraech, nachricht, [2]).status_code == 409


def test_zwei_saetze_zwei_vorschlaege_und_eine_aussage_entkraeftet_die_andere_nicht(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client)
    ergebnisse = _vorschlagen(client, gespraech, nachricht, [1, 2]).json()['ergebnisse']
    assert [e['status'] for e in ergebnisse] == ['vorgeschlagen', 'vorgeschlagen']
    for e in ergebnisse:
        assert client.post(f"/api/v1/memory/candidates/{e['vorschlag']['id']}/accept",
                           json={'supersedes': []}).status_code == 200
    aussagen = client.get('/api/v1/akten/akte', params={'sache': SACHE, 'warten': True}).json()['aussagen']
    assert {a['text'] for a in aussagen['eintraege']} == {SATZ_NEU, SATZ_WANDEL}


# -- Dopplung -----------------------------------------------------------------------------------------


def test_ein_satz_der_schon_in_der_akte_steht_wird_nicht_noch_einmal_vorgeschlagen(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client)
    kennung = _vorschlagen(client, gespraech, nachricht, [1]).json()['ergebnisse'][0]['vorschlag']['id']
    client.post(f'/api/v1/memory/candidates/{kennung}/accept', json={'supersedes': []})
    # Eine zweite Quelle sagt dasselbe; eine neue Antwort stützt sich auf sie. Der Satz steht schon in der Akte.
    mail(app.state.episodes, 'Erinnerung', [('Zur Erinnerung: ' + SATZ_NEU, 'change')], tage=3)
    g2, n2, _ = _antwort(app, client, quellen=False, frage='Was gibt es Neues beim Förderteam?', saetze=lambda nutzer: {'status': 'antwort', 'saetze': [
        {'text': SATZ_NEU, 'belege': [nr(nutzer, 'Erinnerung')]}]})
    zustand = _zustand(app)
    (ergebnis,) = _vorschlagen(client, g2, n2, [1]).json()['ergebnisse']
    assert ergebnis['status'] == 'steht_schon' and ergebnis['grund'] == 'Steht schon in der Akte.'
    assert 'vorschlag' not in ergebnis and _zustand(app) == zustand
    # Die Rückfrage zeigt es vorher an: nicht vorgewählt, als „steht schon“ gekennzeichnet.
    satz = client.get('/api/v1/antworten/uebernehmen', params={'conversation_id': g2, 'message_id': n2}).json()['saetze'][0]
    assert satz['steht_schon'] is True and satz['vorgabe'] is False


def test_ein_offener_vorschlag_wird_nicht_verdoppelt(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client)
    erster = _vorschlagen(client, gespraech, nachricht, [1]).json()['ergebnisse'][0]
    zweiter = _vorschlagen(client, gespraech, nachricht, [1]).json()['ergebnisse'][0]
    assert erster['status'] == 'vorgeschlagen' and zweiter['status'] == 'liegt_vor'
    assert zweiter['vorschlag']['id'] == erster['vorschlag']['id']
    assert len(app.state.knowledge_service.pending()) == 1


# -- Kennzeichnung ------------------------------------------------------------------------------------


def test_ein_satz_aus_ueberholter_quelle_wird_nur_mit_hinweis_vorgeschlagen(api):
    app, client = api
    gespraech, nachricht, (alt, neu) = _antwort(app, client)
    (ergebnis,) = _vorschlagen(client, gespraech, nachricht, [2]).json()['ergebnisse']
    assert ergebnis['status'] == 'vorgeschlagen' and len(ergebnis['hinweise']) == 1
    hinweis = ergebnis['hinweise'][0]
    assert 'Ausschreibung' in hinweis and 'überholt' in hinweis and '15. Oktober 2026' in hinweis
    assert ergebnis['vorschlag']['rationale'].startswith('Hinweis: ')
    assert {b['episode_id'] for b in ergebnis['vorschlag']['evidence']} == {alt.id, neu.id}


def test_hinweise_nennen_namensvetter_und_zeitraum():
    beleg = AntwortBeleg(1, {}, 'Quelle', 'e1', 'Mail von Alex', 'Kopf', 'Text', None,
                         kennzeichen=(Kennzeichen(ANDERE_PERSON, 'alex@b.example', 'Alex Winter', 'alex@a.example'),))
    (h,) = uebernehmen.hinweise([beleg])
    assert 'Mail von Alex' in h and 'Andere Person gleichen Namens' in h
    assert uebernehmen.hinweise([]) == []


def test_eine_aussage_wird_von_einer_juengeren_quelle_als_ueberholt_gekennzeichnet(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client)
    kennung = _vorschlagen(client, gespraech, nachricht, [1]).json()['ergebnisse'][0]['vorschlag']['id']
    client.post(f'/api/v1/memory/candidates/{kennung}/accept', json={'supersedes': []})
    # Eine fremde, ältere Mail ändert nichts; eine jüngere mit anderem Datum überholt die Aussage.
    mail(app.state.episodes, 'Nachtrag', [('Die Einreichfrist ist jetzt der 10. Dezember 2026.', 'change')], tage=2)
    akte = client.get('/api/v1/akten/akte', params={'sache': SACHE, 'warten': True}).json()
    (aussage,) = akte['aussagen']['eintraege']
    assert aussage['text'] == SATZ_NEU
    assert aussage['ueberholt']['titel'] == 'Nachtrag' and '10. Dezember 2026' in aussage['ueberholt']['text']
    # Die Aussage selbst bleibt unverändert: Überholt ist ein Hinweis, kein Widerruf.
    assert all(c.status.value == 'active' for c in app.state.claims.all_claims())


def test_eine_juengere_quelle_mit_demselben_datum_bestaetigt_statt_zu_ueberholen(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client)
    kennung = _vorschlagen(client, gespraech, nachricht, [1]).json()['ergebnisse'][0]['vorschlag']['id']
    client.post(f'/api/v1/memory/candidates/{kennung}/accept', json={'supersedes': []})
    mail(app.state.episodes, 'Bestätigung', [('Die Einreichfrist bleibt der 12. November 2026.', 'status')], tage=2)
    (aussage,) = client.get('/api/v1/akten/akte', params={'sache': SACHE, 'warten': True}).json()['aussagen']['eintraege']
    assert aussage['ueberholt'] is None


# -- Fehlerfälle und Schutz ---------------------------------------------------------------------------


def test_fehlerfaelle(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client)
    basis = {'conversation_id': gespraech, 'message_id': nachricht}
    assert client.post('/api/v1/antworten/uebernehmen', json={**basis, 'saetze': []}).status_code == 422
    assert _vorschlagen(client, gespraech, nachricht, [9]).status_code == 422
    assert _vorschlagen(client, gespraech, nachricht, [0]).status_code == 422
    assert _vorschlagen(client, gespraech, nachricht, [1], sache='person:a:fremd@example.org').status_code == 422
    assert client.post('/api/v1/antworten/uebernehmen', json={**basis, 'saetze': [1], 'frage': 'x'}).status_code == 422
    assert _vorschlagen(client, gespraech, 'fremd', [1]).status_code == 404
    nutzer = next(m for m in app.state.conversations.messages(gespraech) if m.role == 'user')
    assert _vorschlagen(client, gespraech, nutzer.id, [1]).status_code == 404
    # Eine Antwort ohne Sätze (hier: eine einfache Textantwort) hat nichts zum Übernehmen.
    einfach = app.state.conversations.add_message(gespraech, 'assistant', 'Das weiß ich nicht.')
    assert _vorschlagen(client, gespraech, einfach.id, [1]).status_code == 409
    assert client.get('/api/v1/antworten/uebernehmen',
                      params={'conversation_id': gespraech, 'message_id': einfach.id}).status_code == 409
    assert app.state.knowledge_service.pending() == [] and app.state.claims.all_claims() == []


def test_routen_brauchen_das_token(api):
    app, client = api
    offen = TestClient(app)
    try:
        assert offen.post('/api/v1/antworten/uebernehmen', json={}).status_code in (401, 403)
        assert offen.get('/api/v1/antworten/uebernehmen',
                         params={'conversation_id': 'g', 'message_id': 'm'}).status_code in (401, 403)
    finally:
        offen.close()


def test_eine_ausgeschlossene_quelle_ergibt_keinen_vorschlag(api):
    app, client = api
    gespraech, nachricht, (alt, neu) = _antwort(app, client)
    app.state.episodes.ignore(neu.id)
    # Die Antwort gilt nicht mehr (409); nie ein Vorschlag auf einer Quelle, die ausgeschlossen wurde.
    assert _vorschlagen(client, gespraech, nachricht, [1]).status_code == 409
    assert app.state.knowledge_service.pending() == []


# -- Bausteine ------------------------------------------------------------------------------------------


def test_textstelle_ist_der_passende_satz_der_quelle_wortlich():
    body = 'Guten Tag. Die Laufzeit beträgt 18 Monate. Die Einreichfrist ist der 15. Oktober 2026. Viele Grüße'
    stelle = uebernehmen.textstelle(body, 'Die Einreichfrist endet am 15. Oktober 2026.')
    assert stelle == 'Die Einreichfrist ist der 15. Oktober 2026.' and stelle in body
    assert uebernehmen.textstelle('Nur ein Satz hier', 'xyz qqq') == 'Nur ein Satz hier'
    lang = 'Wort ' * 400
    assert len(uebernehmen.textstelle(lang, 'nichts gemeinsames')) <= uebernehmen.MAX_ZITAT


def test_ein_satz_gilt_als_vorhanden_bis_auf_schreibweise_und_schlusspunkt():
    class Claim:
        statement = 'Die Frist ist der 12. November 2026.'
        value = 'x'

    class Bestand:
        def by_reference(self, sache):
            return [Claim()] if sache == SACHE else []

    assert uebernehmen.schon_aussage(Bestand(), SACHE, '  die FRIST ist der 12. November   2026 ')
    assert not uebernehmen.schon_aussage(Bestand(), 'projekt:x', 'Die Frist ist der 12. November 2026.')
    assert not uebernehmen.schon_aussage(None, SACHE, 'egal')


def test_vorschlaege_einer_antwort_sind_wiederzufinden(api):
    app, client = api
    gespraech, nachricht, _ = _antwort(app, client)
    _vorschlagen(client, gespraech, nachricht, [1, 2])
    assert len(app.state.proposals.von(uebernehmen.vorschlag_von(gespraech, nachricht))) == 2
    assert app.state.proposals.von(uebernehmen.vorschlag_von(gespraech, 'andere')) == []


def test_verschiedene_saetze_derselben_sache_widersprechen_sich_nicht():
    from icarus_memory.relations import values_conflict
    assert not values_conflict('aussage', 'Satz eins.', 'Satz zwei.')
    assert values_conflict('unbekannt', 'Satz eins.', 'Satz zwei.')
