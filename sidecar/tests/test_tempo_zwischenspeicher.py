"""V7, Tempo: Was schneller wurde, liefert dasselbe, und jeder Zwischenspeicher wird mit seiner Grundlage ungültig.

Synthetische Daten. Je Beschleunigung: gleiche Inhalte wie der Weg ohne Zwischenspeicher, ein Treffer beim zweiten
Aufruf (sonst wäre er wirkungslos) und neue Inhalte nach einer Änderung der Quellen, Zuordnungen oder Aufgaben.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import akten_routes
from icarus_memory.episodes import EpisodeKind, EpisodeStore, mail_address, sql_aktuell
from icarus_memory.kontakte import anzeigename
from icarus_memory.model import Provenance, SourceType
from icarus_memory.nachbereitung import frage_zu, name_von, offene
from icarus_memory.zwischenspeicher import Zwischenspeicher
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_mappe import _projekt, _quelle
from tests.test_nachbereitung import JETZT, Kalender, _vorbei
from tests.test_organisation_group_suggestions import preview, world  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api

ANNA = 'Anna Keller <anna@agentur.example>'


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        yield app, client
    finally:
        client.close()


def _mail(episodes, titel, teilnehmer, *, tage=1, project=None, art=SourceType.EMAIL, occurred_at=None):
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE, titel, f'Text zu {titel}.',
        Provenance(art, source_ref=f'work:<{titel}@example.invalid>'), participants=list(teilnehmer),
        project_id=project, occurred_at=occurred_at or datetime.now(timezone.utc) - timedelta(days=tage))
    return episode


# -- Beteiligte je Adresse ----------------------------------------------------------------------------------------

def _referenz(episodes: EpisodeStore, adressen, *, anzeigenamen=False):
    """Ohne Vorfilter und ohne Zwischenspeicher: jede geltende Quelle, jeder Beteiligte, genau verglichen."""
    gesucht = sorted({mail_address(a) for a in adressen if mail_address(a)})
    ergebnis = {a: {'namen': {}, 'zuletzt': None, 'quellen': {}} for a in gesucht}
    with episodes._lock:
        zeilen = episodes._conn.execute(
            "SELECT id, json_extract(document, '$.participants'), COALESCE(occurred_at, recorded_at), project_id, "
            f"json_extract(document, '$.provenance.source_type') FROM episodes WHERE {sql_aktuell()} ORDER BY rowid"
        ).fetchall()
    for episode_id, teilnehmer, zeit, projekt, art in zeilen:
        for wert in json.loads(teilnehmer or '[]'):
            adresse = mail_address(str(wert))
            if adresse not in ergebnis:
                continue
            eintrag, name = ergebnis[adresse], str(wert).strip()
            lesbar = anzeigename(name, kopfzeile=art == 'email')
            if anzeigenamen:
                name = lesbar or adresse
            else:
                eintrag.setdefault('anzeige', {}).setdefault(name, lesbar)
            eintrag['namen'][name] = eintrag['namen'].get(name, 0) + 1
            eintrag['quellen'][episode_id] = projekt
            if zeit and (eintrag['zuletzt'] is None or zeit > eintrag['zuletzt']):
                eintrag['zuletzt'] = zeit
    return ergebnis


@pytest.fixture
def episodes(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        yield store
    finally:
        store.close()


def test_beteiligte_gleiche_inhalte_wie_der_volle_durchgang(episodes):
    _mail(episodes, 'Eins', [ANNA, 'Ben <ben@druck.example>'], tage=3)
    _mail(episodes, 'Zwei', ['ANNA@Agentur.example', '=?utf-8?q?J=C3=BCrgen_M=C3=BCller?= <juergen@x.example>'], tage=2)
    _mail(episodes, 'Drei', ['Keller, Anna <anna@agentur.example>'], tage=1, art=SourceType.USER_STATED)
    _mail(episodes, 'Vier', ['anna_x@agentur.example', 'anna%y@agentur.example'], tage=1)
    entzogen = _mail(episodes, 'Fünf', [ANNA], tage=0)
    episodes.ignore(entzogen.id)
    adressen = [ANNA, 'juergen@x.example', 'ben@druck.example', 'anna_x@agentur.example', 'niemand@x.example',
                'anna%y@agentur.example']
    for anzeigenamen in (False, True):
        assert episodes.participants_for_addresses(adressen, anzeigenamen=anzeigenamen) == _referenz(
            episodes, adressen, anzeigenamen=anzeigenamen)
    assert episodes.participants_for_addresses([]) == {} == episodes.participants_for_addresses(['kein name'])
    assert episodes.participants_for_addresses(['juergen@x.example'])['juergen@x.example']['anzeige'] == {
        '=?utf-8?q?J=C3=BCrgen_M=C3=BCller?= <juergen@x.example>': 'Jürgen Müller'}


def test_beteiligte_aus_dem_zwischenspeicher_werden_mit_jeder_aenderung_neu_gelesen(episodes, tmp_path):
    from icarus_memory.workspace import WorkspaceStore
    erste = _mail(episodes, 'Eins', [ANNA], tage=3)
    vorher = episodes.participants_for_addresses([ANNA])
    vorher['anna@agentur.example']['namen']['verändert'] = 99  # die Antwort ist eine Kopie
    treffer = episodes._teilnehmer_zwischen.treffer
    zweite = episodes.participants_for_addresses([ANNA])
    assert episodes._teilnehmer_zwischen.treffer == treffer + 1
    assert zweite == _referenz(episodes, [ANNA]) and 'verändert' not in zweite['anna@agentur.example']['namen']
    # Neue Quelle
    neue = _mail(episodes, 'Zwei', ['Anna K. <anna@agentur.example>'], tage=1)
    assert set(episodes.participants_for_addresses([ANNA])['anna@agentur.example']['quellen']) == {erste.id, neue.id}
    # Zuordnung zu einem Projekt
    workspace = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    try:
        projekt = workspace.add_project('Mainz', Provenance(SourceType.USER_STATED))
    finally:
        workspace.close()
    episodes.link_project(neue.id, projekt.id)
    assert episodes.participants_for_addresses([ANNA])['anna@agentur.example']['quellen'][neue.id] == projekt.id
    # Entzug
    episodes.ignore(erste.id)
    assert episodes.participants_for_addresses([ANNA]) == _referenz(episodes, [ANNA])
    assert set(episodes.participants_for_addresses([ANNA])['anna@agentur.example']['quellen']) == {neue.id}


def test_beteiligte_sehen_auch_was_eine_andere_verbindung_schreibt(episodes, tmp_path):
    episodes.participants_for_addresses([ANNA])
    zweite = EpisodeStore(tmp_path / 'episodes.sqlite3')
    try:
        neu = _mail(zweite, 'Von nebenan', [ANNA])
    finally:
        zweite.close()
    assert neu.id in episodes.participants_for_addresses([ANNA])['anna@agentur.example']['quellen']


def test_zwischenspeicher_gibt_kopien_und_vergisst_die_aeltesten():
    speicher = Zwischenspeicher(2)
    wert = speicher.holen('a', lambda: {'liste': [1]})
    wert['liste'].append(2)
    assert speicher.holen('a', lambda: pytest.fail('neu berechnet')) == {'liste': [1]}
    speicher.holen('b', lambda: 2)
    speicher.holen('c', lambda: 3)
    assert speicher.nachsehen('a') is None and speicher.nachsehen('c') == 3
    assert speicher.holen(None, lambda: 'ohne') == 'ohne' and speicher.nachsehen(None) is None


# -- Sachen der Akten ---------------------------------------------------------------------------------------------

def _sachen(client, **params):
    antwort = client.get('/api/v1/akten/sachen', params={'warten': True, **params})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def test_sachen_aus_dem_zwischenspeicher_und_neu_nach_jeder_aenderung(api):
    app, client = api
    _quelle(app, 'Druckdaten', [('Bitte schicke mir die Druckdaten.', 'request')], tage=3)
    erste = _sachen(client, art='person')
    bezuege = akten_routes.bausteine(app)[0]
    treffer = bezuege.zwischen.treffer
    assert _sachen(client, art='person')['sachen'] == erste['sachen']
    assert bezuege.zwischen.treffer == treffer + 1
    anna = 'person:a:anna@agentur.example'
    assert {s['sache']: s['quellen'] for s in erste['sachen']}[anna] == 1
    # Neue Quelle derselben Person
    _quelle(app, 'Nachtrag', [('Hier noch die Datei.', 'fact')], tage=1)
    assert {s['sache']: s['quellen'] for s in _sachen(client, art='person')['sachen']}[anna] == 2
    # Zuordnung des Nutzers
    notiz = _quelle(app, 'Notiz', [('Kurze Notiz.', 'fact')], absender='Ben <ben@druck.example>', tage=2)
    assert client.put(f'/api/v1/akten/quellen/{notiz.id}/zuordnung',
                      json={'sache': 'ort:mainz', 'aktion': 'zu'}).status_code == 200
    assert [s['sache'] for s in _sachen(client, art='ort')['sachen']] == ['ort:mainz']
    # Zuordnung zu einem Projekt
    projekt = _projekt(app, 'Mainz')
    app.state.episodes.link_project(notiz.id, projekt.id)
    assert [s['name'] for s in _sachen(client, art='projekt')['sachen']] == ['Mainz']


def test_zuletzt_liegt_nie_in_der_zukunft(api):
    app, client = api
    vergangen = datetime.now(timezone.utc) - timedelta(days=3)
    _quelle(app, 'Gestern', [('Bitte um Rückruf.', 'request')], occurred_at=vergangen)
    _quelle(app, 'Termin', [('Termin im Dezember.', 'fact')], occurred_at=datetime.now(timezone.utc) + timedelta(days=60))
    nur_kuenftig = _quelle(app, 'Später', [('Erst im Dezember.', 'fact')], absender='Carla <carla@zukunft.example>',
                           occurred_at=datetime.now(timezone.utc) + timedelta(days=90))
    sachen = {s['sache']: s for s in _sachen(client, art='person')['sachen']}
    anna = sachen['person:a:anna@agentur.example']
    # Beide Quellen zählen, „zuletzt“ ist die vergangene.
    assert anna['quellen'] == 2
    assert datetime.fromisoformat(anna['letzte']) == vergangen
    # Nur Künftiges: ohne „zuletzt“ und am Ende der Liste.
    carla = sachen['person:a:carla@zukunft.example']
    assert carla['letzte'] is None and carla['quellen'] == 1
    assert list(sachen)[-1] == 'person:a:carla@zukunft.example'
    assert nur_kuenftig.id
    # Ohne Grenze (Logbuch, Lint) bleibt es wie bisher.
    ohne = {s['sache']: s for s in akten_routes.bausteine(app)[0].sachen(art='person')['sachen']}
    assert datetime.fromisoformat(ohne['person:a:anna@agentur.example']['letzte']) > datetime.now(timezone.utc)


# -- Gruppenvorschläge der Organisationen -------------------------------------------------------------------------

def test_gruppenvorschlaege_aus_dem_zwischenspeicher_und_neu_nach_entzug(world):
    client, app, episodes = world
    erste = preview(client)
    bezuege = akten_routes.bausteine(app)[0]
    treffer = bezuege.zwischen.treffer
    zweite = preview(client)
    assert bezuege.zwischen.treffer == treffer + 1
    assert zweite == erste and erste['total'] == 3
    app.state.episodes.ignore(episodes[0].id)
    danach = preview(client)
    assert danach['total'] == 2 and danach['source_revision'] != erste['source_revision']
    assert 'organisation:de' not in {e['id'] for e in danach['entries']}


# -- Verzeichnis für Menschen, Projekte und Suche -----------------------------------------------------------------

def _letzter_kontakt_wie_die_oberflaeche(graph: dict, kennung: str) -> str | None:
    """`contactDateFromGraph` aus `WorkspaceMemoryModel.ts`, nachgebaut über den ganzen Graphen."""
    quellen = {e['target'] for e in graph['edges']
               if e['source'] == kennung and e['relation'] == 'participated_in' and e.get('actual_contact') is True}
    jetzt = datetime.fromisoformat(graph['generated_at'])
    zeiten = []
    for knoten in graph['nodes']:
        a = knoten['attributes']
        if knoten['id'] not in quellen or a.get('source_current') is False or a.get('state') == 'ignored':
            continue
        wert = a.get('occurred_at')
        if not isinstance(wert, str):
            continue
        if a.get('episode_kind') == 'event' and datetime.fromisoformat(wert) > jetzt:
            continue
        zeiten.append(wert)
    return max(zeiten, key=datetime.fromisoformat) if zeiten else None


def test_verzeichnis_hat_dieselben_personen_und_projekte_wie_der_graph(api):
    app, client = api
    projekt = _projekt(app, 'Mainz')
    _quelle(app, 'Druckdaten', [('Bitte schicke mir die Druckdaten.', 'request')], project=projekt.id, tage=5)
    _quelle(app, 'Muster', [('Ich schicke die Muster.', 'commitment')], absender='Ben <ben@druck.example>', tage=2)
    termin, _ = app.state.episodes.record(
        EpisodeKind.EVENT, 'Künftige Runde', 'Runde', Provenance(SourceType.CALENDAR, source_ref='cal:runde'),
        participants=[ANNA, 'Dora <dora@zukunft.example>'],
        occurred_at=datetime.now(timezone.utc) + timedelta(days=4))
    app.state.tasks.add('Bei Ben nachfragen', Provenance(SourceType.USER_STATED), project_id=projekt.id)
    verzeichnis = client.get('/api/v1/memory/verzeichnis').json()
    graph = client.get('/api/v1/memory/graph').json()
    assert verzeichnis['nodes'] == [n for n in graph['nodes'] if n['kind'] in ('person', 'project')]
    assert verzeichnis['edges'] == [] and verzeichnis['verzeichnis']['hat_quellen'] is True
    personen = [n['id'] for n in verzeichnis['nodes'] if n['kind'] == 'person']
    assert len(personen) >= 3
    erwartet = {k: z for k in personen if (z := _letzter_kontakt_wie_die_oberflaeche(graph, k))}
    assert verzeichnis['verzeichnis']['letzter_kontakt'] == erwartet
    assert termin.id and any(n['label'].startswith('Dora') for n in verzeichnis['nodes'])
    assert len(json.dumps(verzeichnis)) < len(json.dumps(graph))


def test_verzeichnis_aus_dem_zwischenspeicher_und_neu_nach_jeder_aenderung(api):
    app, client = api
    _quelle(app, 'Druckdaten', [('Bitte schicke mir die Druckdaten.', 'request')], tage=5)
    erste = client.get('/api/v1/memory/verzeichnis').json()
    zwischen = app.state.verzeichnis_zwischen
    treffer = zwischen.treffer
    assert client.get('/api/v1/memory/verzeichnis').json() == erste
    assert zwischen.treffer == treffer + 1

    def namen():
        return {n['label'] for n in client.get('/api/v1/memory/verzeichnis').json()['nodes']}
    # Neue Quelle mit neuer Person
    _quelle(app, 'Muster', [('Ich schicke die Muster.', 'commitment')], absender='Ben <ben@druck.example>', tage=1)
    assert any(name.startswith('Ben') for name in namen())
    # Neues Projekt
    _projekt(app, 'Messe Mainz')
    assert 'Messe Mainz' in namen()
    # Aufgabe, die auf jemanden wartet (Personenknoten über `wartet_auf`)
    aufgabe = app.state.tasks.add('Freigabe', Provenance(SourceType.USER_STATED))
    app.state.tasks.warten_auf(aufgabe.id, 'Carla Neu')
    assert 'Carla Neu' in namen()
    # Bereich eines Projekts (Arbeitsbereich)
    projekt = next(n for n in client.get('/api/v1/memory/verzeichnis').json()['nodes'] if n['label'] == 'Messe Mainz')
    app.state.workspace.update_project(projekt['id'].removeprefix('project:'), area='work')
    neu = next(n for n in client.get('/api/v1/memory/verzeichnis').json()['nodes'] if n['label'] == 'Messe Mainz')
    assert neu['attributes']['area'] == 'work'
    # Eine Aussage im Selbstmodell (in Prüfungen ein Speicher ohne Datei) rechnet ebenfalls neu.
    from icarus_memory.model import Kind
    treffer = zwischen.treffer
    client.get('/api/v1/memory/verzeichnis')
    assert zwischen.treffer == treffer + 1
    app.state.store.record('Mag knappe Antworten.', Kind.PREFERENCE, Provenance(SourceType.USER_STATED))
    client.get('/api/v1/memory/verzeichnis')
    assert zwischen.treffer == treffer + 1


# -- Heute: schnelle und volle Fassung ----------------------------------------------------------------------------

def test_schnelle_fassung_laesst_neue_akte_und_quellenberichte_aus(api, monkeypatch):
    app, client = api
    from icarus_memory import akten_vorschlaege_routes, working_memory_context
    aufrufe = []
    echt_vorschlag, echt_berichte = akten_vorschlaege_routes.fuer_briefing, working_memory_context.reports
    monkeypatch.setattr(akten_vorschlaege_routes, 'fuer_briefing',
                        lambda app: aufrufe.append('akte') or echt_vorschlag(app))
    monkeypatch.setattr(working_memory_context, 'reports',
                        lambda *a, **k: aufrufe.append('berichte') or echt_berichte(*a, **k))
    _quelle(app, 'Druckdaten', [('Bitte schicke mir die Druckdaten.', 'request')], tage=0)
    schnell = client.get('/api/v1/morning-briefing', params={'post': 'false'}).json()
    assert aufrufe == [] and schnell['post_ausstehend'] is True
    assert not any(p['section'] == 'working_memory' for p in schnell['partial_failures'])
    voll = client.get('/api/v1/morning-briefing').json()
    assert 'akte' in aufrufe and voll['post_ausstehend'] is False
    for feld in ('greeting', 'later_today', 'naechster_termin', 'timezone'):
        assert schnell[feld] == voll[feld], feld


def test_verzeichnis_der_bezuege_wird_beim_start_gebaut(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        _quelle(app, 'Druckdaten', [('Bitte schicke mir die Druckdaten.', 'request')], tage=1)
        bezuege = akten_routes.bausteine(app)[0]
        assert bezuege._register is None
        with TestClient(app, headers={'X-Icarus-Token': 'local-owner-token'}):
            # Der Faden kann schon fertig sein, bevor wir nachsehen; dann ist auch nichts zu warten.
            for faden in [f for f in threading.enumerate() if f.name == 'akten-verzeichnis']:
                faden.join(10)
        assert bezuege._register is not None
        assert bezuege._register_stand[0] == app.state.episodes.geltender_stand()
    finally:
        client.close()


# -- Nachfrage nach dem Termin: Namen statt Adressen --------------------------------------------------------------

def test_nachfrage_nennt_namen_aus_dem_bestand_statt_adressen():
    index = {'agidius@privat.example': {'namen': {'=?utf-8?q?Prof=2E_Dr=2E_=C3=84gidius_Zimmermann?= <agidius@privat.example>': 3,
                                                   'agidius@privat.example': 5},
                                         'anzeige': {'=?utf-8?q?Prof=2E_Dr=2E_=C3=84gidius_Zimmermann?= <agidius@privat.example>':
                                                     'Prof. Dr. Ägidius Zimmermann', 'agidius@privat.example': ''}}}
    zwoelf = ['agidius@privat.example'] + [f'gast{n}@extern.example' for n in range(11)]
    assert name_von('agidius@privat.example', index) == 'Prof. Dr. Ägidius Zimmermann'
    assert frage_zu('Runde', zwoelf, index) == 'Wie war das Gespräch mit Prof. Dr. Ägidius Zimmermann und 11 weiteren?'
    # Kein Name bekannt: nie eine Adresse, sondern Termin und Zahl.
    assert frage_zu('Runde', zwoelf[1:]) == 'Wie war „Runde“ mit 11 Teilnehmenden?'
    assert frage_zu('Runde', ['gast@extern.example']) == 'Wie war „Runde“?'
    assert frage_zu('Runde', ['gast@extern.example', ANNA]) == 'Wie war das Gespräch mit Anna Keller und einer weiteren Person?'
    karten = offene([{'uid': 'r', 'summary': 'Runde', 'start': (JETZT - timedelta(hours=3)).isoformat(),
                      'end': (JETZT - timedelta(hours=2)).isoformat(), 'attendees': zwoelf}],
                    jetzt=JETZT, eigene=['ich@firma.example'], erledigt={}, index=index)
    assert karten[0]['mit'] == ['Prof. Dr. Ägidius Zimmermann'] and '@' not in karten[0]['frage']


def test_nachfrage_im_briefing_nimmt_den_namen_aus_den_mails(api):
    app, client = api
    _mail(app.state.episodes, 'Vorgespräch', ['=?utf-8?q?Prof=2E_Dr=2E_=C3=84gidius_Zimmermann?= <agidius@privat.example>'],
          tage=3)
    gaeste = tuple(['agidius@privat.example'] + [f'gast{n}@extern.example' for n in range(11)])
    app.state.calendar = Kalender([_vorbei(uid='runde', summary='Runde', attendees=gaeste)])
    karten = client.get('/dashboard').json()['calendar']['nachzubereiten']
    assert [k['frage'] for k in karten] == ['Wie war das Gespräch mit Prof. Dr. Ägidius Zimmermann und 11 weiteren?']
    assert karten[0]['mit'] == ['Prof. Dr. Ägidius Zimmermann']


def test_ein_treffer_aus_dem_zwischenspeicher_ist_eine_kopie(episodes):
    _mail(episodes, 'Eins', [ANNA], tage=3)
    episodes.participants_for_addresses([ANNA])
    treffer = episodes.participants_for_addresses([ANNA])
    treffer['anna@agentur.example']['quellen'].clear()
    assert episodes.participants_for_addresses([ANNA]) == _referenz(episodes, [ANNA])


def test_gruppenvorschlaege_warten_auf_offene_quellen(world, monkeypatch):
    client, app, _ = world
    assert preview(client)['total'] == 3
    # Eine neue Quelle, deren Bezüge (etwa wegen eines gleichzeitigen Abgleichs) noch nicht berechnet sind.
    app.state.episodes.record(EpisodeKind.DOCUMENT, 'Amazon.co', 'Amazon.co',
                              Provenance(SourceType.USER_STATED, source_ref='synthetic:co'))
    bezuege = akten_routes.bausteine(app)[0]
    monkeypatch.setattr(bezuege, 'aktualisieren', lambda **_: {'berechnet': 0, 'entfernt': 0, 'offen': 1})
    antwort = client.get('/api/v1/organisation-group-suggestions')
    assert antwort.status_code == 409


def test_heute_schlaegt_die_teilnehmer_einmal_nach(api, monkeypatch):
    app, client = api
    _mail(app.state.episodes, 'Vorgespräch', [ANNA, 'Ben <ben@druck.example>'], tage=3)
    jetzt = datetime.now(timezone.utc).replace(microsecond=0)
    from icarus_memory.connectors.calendar import Event
    app.state.calendar = Kalender([
        _vorbei(uid='vorbei', attendees=(ANNA,)),
        Event(uid='gleich', summary='Druckfreigabe', start=jetzt + timedelta(hours=2), end=jetzt + timedelta(hours=3),
              attendees=['ben@druck.example'])])
    durchgaenge = []
    echt = app.state.episodes._participants_for_addresses

    def zaehlen(gesucht, **k):
        if not k.get('anzeigenamen'):
            durchgaenge.append(gesucht)
        return echt(gesucht, **k)
    monkeypatch.setattr(app.state.episodes, '_participants_for_addresses', zaehlen)
    schnell = client.get('/api/v1/morning-briefing', params={'post': 'false'}).json()
    # Ein Durchgang über den Bestand: seit Paket A-II (Befund A4) einer für alle Adressen (`None`), aus dem jede Abfrage liest.
    assert len(durchgaenge) == 1 and (durchgaenge[0] is None
                                      or set(durchgaenge[0]) == {'anna@agentur.example', 'ben@druck.example'})
    client.get('/api/v1/morning-briefing')
    # Die volle Fassung fragt für die Termine dieselben Adressen: aus dem Zwischenspeicher. (Namen der Akten fragt sie
    # mit `anzeigenamen` eigens; die zählen hier nicht.)
    assert len(durchgaenge) == 1
    assert schnell['needs_you'] or schnell['later_today']
