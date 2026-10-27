"""Persona-Prüfung, Befund A4: Die Standardfragen ohne Modell sind schnell, ohne an Richtigkeit zu verlieren.

Gemessen war: „Worauf warte ich?“ 24 bis 30 s, „Was brauche ich morgen?“ 37 bis 40 s, ein gespeichertes Gespräch
öffnen 12 bis 19 s, bei 2.000 Quellen ohne Last. Ursachen: Jede der rund 130 Akten berechnete Namen aller ihrer
Beteiligten (je Name ein Durchgang über den ganzen Bestand), las alle Aufgaben neu, und Senden und Öffnen rechneten
dieselbe Antwort zwei- bis dreimal.

Zusicherungen:
1. Die schlanke Akte (`nur_offen`) liefert dieselben offenen Punkte und Fristen wie die volle Akte.
2. Das Verzeichnis aller Beteiligten ergibt dasselbe wie die Einzelabfrage und gilt nur für den Stand der Datei.
3. Eine Frage über viele Akten liest den Bestand der Beteiligten höchstens einmal und keine Namen von Beteiligten.
4. Gemerkt wird nur, solange sich nichts geändert hat: Eine Entscheidung, eine Aufgabe oder eine neue Quelle
   ändert die Antwort beim nächsten Öffnen.
"""
from datetime import timedelta

from icarus_memory import SourceType, offene_punkte
from icarus_memory.akten_entscheidungen import Entscheidungen
from icarus_memory.akten_routes import nach_stand_gemerkt
from icarus_memory.fristlage import sammeln as fristen_sammeln
from tests.test_akten import akten, einordnen, neu_rechnen  # noqa: F401 - Fixture und Hilfen
from tests.test_akten_routes import api  # noqa: F401 - Fixture
from tests.test_bezuege import ICH, JETZT, quelle, welt  # noqa: F401 - Fixture und Hilfen
from tests.test_context_identity import core  # noqa: F401 - Fixture

LEA = f'Lea Hartmann <{ICH}>'


def _bestand(episodes, anzahl=12):
    """Personen mit Zusagen, Bitten, Fristen und gemeinsamen Quellen (viele Beteiligte je Akte)."""
    for i in range(anzahl):
        person = f'Person {i} <p{i}@firma{i % 3}.example>'
        andere = [f'Kollege {j} <k{j}@firma{j % 3}.example>' for j in range(i % 4)]
        e = quelle(episodes, f'Zusage {i}', f'Ich schicke Ihnen die Unterlagen {i} bis 2. Oktober.', [person, LEA, *andere],
                   tage=2 + i)
        einordnen(episodes, e, [(f'Ich schicke Ihnen die Unterlagen {i} bis 2. Oktober.', 'commitment')])
        e = quelle(episodes, f'Bitte {i}', f'Könnten Sie mir bitte das Protokoll {i} schicken?', [LEA, person], tage=1 + i)
        einordnen(episodes, e, [(f'Könnten Sie mir bitte das Protokoll {i} schicken?', 'request')])


def test_schlanke_akte_hat_dieselben_offenen_punkte_und_fristen(welt, akten):
    episodes, _, bezuege = welt
    _bestand(episodes)
    neu_rechnen(akten)
    for eintrag in bezuege.sachen(limit=100)['sachen']:
        voll = akten.akte(eintrag['sache'], jetzt=JETZT, alle=True)
        schlank = akten.akte(eintrag['sache'], jetzt=JETZT, alle=True, nur_offen=True)
        assert schlank['offen'] == voll['offen'] and schlank['fristen'] == voll['fristen']
        assert schlank['name'] == '' and 'beteiligte' not in schlank and 'verlauf' not in schlank


def test_verzeichnis_der_beteiligten_wie_die_einzelabfrage_und_nur_fuer_den_stand(welt):
    episodes, _, _ = welt
    _bestand(episodes, 5)
    adressen = ['p1@firma1.example', 'k0@firma0.example', 'P3@FIRMA0.EXAMPLE', 'niemand@x.example']
    for anzeigenamen in (False, True):
        alt = episodes._participants_for_addresses(sorted({a.lower() for a in adressen}), anzeigenamen=anzeigenamen)
        assert episodes.participants_for_addresses(adressen, anzeigenamen=anzeigenamen) == alt
    vorher = episodes.participants_for_address('p1@firma1.example')
    quelle(episodes, 'Neu', 'Hallo', ['Paul Eins <p1@firma1.example>', LEA], tage=0)
    nachher = episodes.participants_for_address('p1@firma1.example')
    assert nachher != vorher and {'name': 'Paul Eins <p1@firma1.example>', 'anzahl': 1} in nachher


def test_viele_akten_lesen_den_bestand_der_beteiligten_hoechstens_einmal(welt, akten, monkeypatch):
    episodes, _, bezuege = welt
    _bestand(episodes)
    neu_rechnen(akten)
    akten.akte(bezuege.sachen(limit=1)['sachen'][0]['sache'], jetzt=JETZT)  # Zwischenspeicher der Akten füllen
    for eintrag in bezuege.sachen(limit=100)['sachen']:
        akten.roh(eintrag['sache'])
    durchgaenge, namen = [], []
    echt_alle, echt_einzeln = episodes._alle_teilnehmer, bezuege.beschriftung
    monkeypatch.setattr(episodes, '_alle_teilnehmer', lambda **k: durchgaenge.append(1) or echt_alle(**k))
    monkeypatch.setattr(bezuege, 'beschriftung', lambda *a, **k: namen.append(a) or echt_einzeln(*a, **k))
    episodes._teilnehmer_alle.clear()
    gesammelt = offene_punkte.sammeln(akten, bezuege, 'wartet_auf', jetzt=JETZT)
    assert gesammelt['gesamt'] == 24
    fristen_sammeln(akten, bezuege, jetzt=JETZT, eigene=[ICH])
    assert len(durchgaenge) <= 1
    # Einzelne Namen nur für Organisationen und Projekte; keine Namen der Beteiligten jeder Akte.
    assert all(not str(a[0]).startswith('person:') for a in namen)


def test_gemerkte_antwort_gilt_nur_bis_zur_naechsten_aenderung(api):
    app, client = api
    app.state.settings.mail.user = ICH
    bitte = 'Könnten Sie mir bitte die Druckdaten schicken?'
    e = quelle(app.state.episodes, 'Druckdaten', bitte, [LEA, 'Anna Keller <anna@agentur.example>'], tage=3)
    einordnen(app.state.episodes, e, [(bitte, 'request')])
    client.post('/api/v1/akten/aktualisieren')
    gespraech = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    client.post(f'/api/v1/conversations/{gespraech}/messages', json={'message': 'Worauf warte ich noch?'})

    def antwort():
        nachrichten = client.get(f'/api/v1/conversations/{gespraech}').json()['messages']
        return [n for n in nachrichten if n['role'] == 'assistant'][-1]['content']
    assert bitte in antwort()
    # Eine Entscheidung in der Akte ändert die Antwort beim nächsten Öffnen.
    from icarus_memory.akten_routes import bausteine
    _, akten_ = bausteine(app)
    sache = 'person:a:anna@agentur.example'
    ziel = akten_.akte(sache)['offen']['eintraege'][0]['ziel']
    Entscheidungen(app.state.episodes).setzen(ziel, 'erledigt')
    assert bitte not in antwort()
    Entscheidungen(app.state.episodes).zuruecknehmen(ziel)
    assert bitte in antwort()
    # Eine Aufgabe „wartet auf“ steht beim nächsten Öffnen vorn.
    from icarus_memory.model import Provenance as P
    aufgabe = app.state.tasks.add('Angebot Druckerei', P(SourceType.USER_STATED))
    app.state.tasks.warten_auf(aufgabe.id, 'Druckerei Kranz')
    assert antwort().splitlines()[1].startswith('1. Deine Aufgabe „Angebot Druckerei“, wartet auf Druckerei Kranz')


def test_merken_nach_stand_rechnet_nach_einer_aenderung_neu(api):
    app, _ = api
    zaehler = []

    def rechnen():
        zaehler.append(1)
        return {'n': len(zaehler)}
    assert nach_stand_gemerkt(app, 'probe', 'x', rechnen) == {'n': 1}
    assert nach_stand_gemerkt(app, 'probe', 'x', rechnen) == {'n': 1}
    assert nach_stand_gemerkt(app, 'probe', 'y', rechnen) == {'n': 2}   # andere Frage, anderer Eintrag
    quelle(app.state.episodes, 'Neu', 'Hallo', ['a@b.example'], tage=0)
    assert nach_stand_gemerkt(app, 'probe', 'x', rechnen) == {'n': 3}
    from icarus_memory.model import Provenance as P
    app.state.tasks.add('Neu', P(SourceType.USER_STATED))
    assert nach_stand_gemerkt(app, 'probe', 'x', rechnen) == {'n': 4}
    assert zaehler == [1, 1, 1, 1] and JETZT - timedelta(days=1) < JETZT


def test_schnelles_briefing_zeigt_den_fertigen_teil_mit_zwischenstand(api, monkeypatch):
    """Tageslage (Befund A4): erst der sofort fertige Teil, ohne Akten der Teilnehmer, Wege, Wetter und Welt; er
    zählt nicht als Blick, damit die volle Fassung danach dieselben Zeilen „seit dem letzten Blick“ zeigt."""
    from icarus_memory import logbuch, tag_routes
    app, client = api
    app.state.settings.mail.user = ICH
    langsam = []
    for name in ('vorbereiten_alle', 'wetter_am_termin', '_wetter', '_welt'):
        echt = getattr(tag_routes, name)
        monkeypatch.setattr(tag_routes, name, lambda *a, _n=name, _e=echt, **k: langsam.append(_n) or _e(*a, **k))
    try:
        logbuch.vermerke('export', was='selbstmodell')
        schnell = client.get('/api/v1/tag/briefing', params={'schnell': True}).json()
        assert schnell['zwischenstand'] == tag_routes.ZWISCHENSTAND and langsam == []
        assert 'Export' in schnell['tageslage']['verlauf'][0] and app.state.logbuch._marke('blick') is None
        voll = client.get('/api/v1/tag/briefing').json()
        assert voll['zwischenstand'] is None and set(langsam) == {'vorbereiten_alle', 'wetter_am_termin', '_wetter', '_welt'}
        assert voll['tageslage']['verlauf'] == schnell['tageslage']['verlauf']
        assert app.state.logbuch._marke('blick') is not None
    finally:
        logbuch.verbinde(None)


def test_terminvorbereitung_einmal_je_stand_und_neu_nach_einer_neuen_mail(core, tmp_path, monkeypatch):  # noqa: F811
    """Briefing, „Was brauche ich morgen?“ und Kalender lesen denselben Termin: vorbereitet wird einmal je Stand; eine
    neue Mail des Teilnehmers steht beim nächsten Blick darin."""
    from icarus_memory import terminvorbereitung
    from tests.test_source_answers_http import _api
    from tests.test_terminvorbereitung import ANNA, ICH as LEA_VOLL, _mail, kalender, termin
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.settings.mail.user = ICH
        _mail(app, 'Druckdaten', [('Bitte schick mir die Druckdaten.', 'request')], [ANNA, LEA_VOLL], tage=3)
        kalender(app, termin(tage=1, teilnehmer=(ANNA, LEA_VOLL)))
        aufrufe = []
        echt = terminvorbereitung.vorbereiten
        monkeypatch.setattr(terminvorbereitung, 'vorbereiten', lambda *a, **k: aufrufe.append(1) or echt(*a, **k))
        erste = client.get('/api/v1/tag/briefing').json()['termine'][0]
        client.get('/api/v1/tag/briefing')
        assert len(aufrufe) == 1
        _mail(app, 'Format', [('Das Plakat hätte ich gern im Format A2.', 'fact')], [ANNA, LEA_VOLL], tage=1)
        zweite = client.get('/api/v1/tag/briefing').json()['termine'][0]
        assert len(aufrufe) == 2
        texte = lambda v: [z['text'] for p in v['personen'] for z in p['will']]  # noqa: E731
        assert 'Das Plakat hätte ich gern im Format A2.' in texte(zweite) and 'Das Plakat hätte ich gern im Format A2.' not in texte(erste)
    finally:
        client.close()


def test_beim_start_sind_die_aktiven_akten_vorgerechnet(api):
    """Nach einem Update (neue Fassung der Akten) rechnet der Start die zuletzt aktiven Akten vor; die erste Frage
    findet sie im Zwischenspeicher (Befund A4)."""
    from icarus_memory.akten_routes import bausteine, vorwaermen
    app, _ = api
    _bestand(app.state.episodes, 5)
    bezuege, akten = bausteine(app)
    bezuege.aktualisieren()
    akten.verwerfen()
    vorwaermen(app).join(30)
    for eintrag in bezuege.sachen(limit=100)['sachen']:
        if eintrag['art'] in ('person', 'organisation', 'projekt'):
            akten.roh(eintrag['sache'])
            assert akten.letzte_berechnung['aus_zwischenspeicher'] is True, eintrag['sache']
