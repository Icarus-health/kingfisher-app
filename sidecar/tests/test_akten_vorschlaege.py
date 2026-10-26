"""Vorschlag „Neue Akte?“: ein Projekt, das sich in den Mails bildet, wird erkannt und mit einem Klick angelegt.

Zusicherungen (jede mit Sabotageprobe, docs/30-akten.md, Abschnitt „Neue Akte?“):

1. Ein Vorschlag braucht eine Schwelle: drei Quellen, oder zwei Beteiligte über zwei Quellen, oder 14 Tage.
2. Kein Vorschlag für ein Projekt, das es schon gibt (auch in Umschrift), und keiner für Kurz- oder Zahlennamen.
3. Der Grund ist ein Satz mit Zahl, Datum und Namen; die Quellen tragen ihre Textstelle.
4. Ein Vorschlag schreibt nichts. Erst „Akte anlegen“ legt das Projekt an und ordnet nur Quellen ohne Projekt zu.
   Ein Projekt ist Ablage, kein Fakt: Es entstehen keine Aussagen.
5. Zweimal annehmen ist 409 und ändert nichts; Zurücknehmen stellt den Stand vorher her.
6. „Nein danke“ wird gemerkt und nie wiederholt, bis der Nutzer es zurücknimmt.
7. Das Briefing zeigt höchstens einen Vorschlag; die Akte zeigt die Zeile; das Logbuch hält den Klick fest.
8. Migration 24 legt die Tabelle an und lässt Bestand und frühere Entscheidungen unberührt.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeStore, Provenance, SourceType, briefing
from icarus_memory.akten_routes import bausteine, nachfuehren
from icarus_memory.akten_vorschlaege import (Entscheidungen, kandidaten, kennung_von, MIN_BETEILIGTE, MIN_QUELLEN,
                                             MIN_TAGE)
from icarus_memory.memory_categories import Categories
from tests.test_bezuege import Modell
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_kreis import ICH, api, mail  # noqa: F401 - Fixture und Hilfen

ANNA = 'anna.keller@nordlicht.example'
BEN = 'ben.braun@nordlicht.example'
_PROJEKT = re.compile(r'Projekt [A-ZÄÖÜ][\wäöüß-]*')


def _projekt_modell(nutzer):
    """Ein Skriptmodell, das jede Erwähnung „Projekt <Name>“ als Projekt meldet (absolute Stellen)."""
    entities = []
    for block in nutzer['blocks']:
        for treffer in _PROJEKT.finditer(block['text']):
            entities.append({'kind': 'project', 'name': treffer.group(0), 'start': block['start'] + treffer.start(),
                             'end': block['start'] + treffer.end(), 'role': 'mentioned'})
    return {'categories': [], 'entities': entities}


def erwaehnungen(app):
    Categories(app.state.episodes).run(Modell(_projekt_modell), limit=20)
    nachfuehren(app, warten=True)


def atlas(app, *, tage=(20, 12, 6, 2), von=(ANNA, BEN, ANNA, BEN), name='Atlas'):
    """Mails, in denen „Projekt <name>“ vorkommt: von Anna und Ben, über Wochen verteilt."""
    namen = {ANNA: 'Anna Keller', BEN: 'Ben Braun'}
    quellen = []
    for i, (t, adresse) in enumerate(zip(tage, von)):
        quellen.append(mail(app, adresse, ICH, f'Hallo Lea, zu Projekt {name} gibt es Neues (Stand {i}).',
                            tage=t, name=namen[adresse], titel=f'{name} {i}'))
    return quellen


def vorschlaege(app):
    bezuege, _ = bausteine(app)
    return kandidaten(bezuege, app.state.workspace)


def vorschlag(app, name='Atlas'):
    gefunden = [v for v in vorschlaege(app) if v.sache == f'projekt:n:{name.casefold()}']
    assert len(gefunden) == 1, [v.sache for v in vorschlaege(app)]
    return gefunden[0]


def akte(client, sache):
    antwort = client.get('/api/v1/akten/akte', params={'sache': sache, 'warten': 'true'})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


# -- 1. Schwellen ------------------------------------------------------------------------


def test_drei_quellen_einer_person_reichen(api):
    app, _ = api
    atlas(app, tage=(3, 2, 1), von=(ANNA, ANNA, ANNA))
    erwaehnungen(app)
    v = vorschlag(app)
    assert v.anzahl == 3 and v.anzahl >= MIN_QUELLEN


def test_zwei_beteiligte_ueber_zwei_quellen_reichen(api):
    app, _ = api
    atlas(app, tage=(3, 2), von=(ANNA, BEN))
    erwaehnungen(app)
    v = vorschlag(app)
    assert len(v.beteiligte) == 2 >= MIN_BETEILIGTE and v.anzahl == 2


def test_vierzehn_tage_reichen_auch_mit_einer_person(api):
    app, _ = api
    atlas(app, tage=(16, 1), von=(ANNA, ANNA))
    erwaehnungen(app)
    assert vorschlag(app).tage >= MIN_TAGE


def test_unter_jeder_schwelle_kein_vorschlag(api):
    app, _ = api
    atlas(app, tage=(3, 1), von=(ANNA, ANNA))   # zwei Quellen, eine Person, zwei Tage
    erwaehnungen(app)
    assert vorschlaege(app) == []


# -- 2. Was nie vorgeschlagen wird ---------------------------------------------------------


@pytest.mark.parametrize('vorhanden', ['Atlas', 'atlas', 'Projekt Atlas'])
def test_kein_vorschlag_fuer_ein_vorhandenes_projekt(api, vorhanden):
    app, _ = api
    app.state.workspace.add_project(vorhanden, Provenance(SourceType.USER_STATED))
    atlas(app)
    erwaehnungen(app)
    assert all(v.sache != 'projekt:n:atlas' for v in vorschlaege(app))


def test_kein_vorschlag_in_umschrift_eines_vorhandenen_projekts(api):
    app, _ = api
    app.state.workspace.add_project('Müller', Provenance(SourceType.USER_STATED))
    atlas(app, name='Mueller')
    erwaehnungen(app)
    assert vorschlaege(app) == []


@pytest.mark.parametrize('name', ['X1', '2026', 'Ab'])
def test_kein_vorschlag_fuer_kurz_oder_zahlennamen(api, name):
    app, _ = api
    atlas(app, name=name)
    erwaehnungen(app)
    assert vorschlaege(app) == []


# -- 3. Grund und Quellen -------------------------------------------------------------------


def test_grund_nennt_zahl_datum_und_beteiligte_und_quellen_tragen_die_textstelle(api):
    app, _ = api
    quellen = atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    aelteste = (datetime.now(timezone.utc) - timedelta(days=20)).astimezone()
    from icarus_memory.datumstext import tag_und_monat
    assert v.grund == f'In 4 Mails seit {tag_und_monat(aelteste)} mit Anna Keller und Ben Braun'
    assert v.name == 'Projekt Atlas' and v.kennung == kennung_von('atlas') and len(v.kennung) == 16
    assert {b['name'] for b in v.beteiligte} == {'Anna Keller', 'Ben Braun'}
    assert [q['episode_id'] for q in v.quellen] == [q.id for q in reversed(quellen)]   # jüngste zuerst
    assert all(q['zitat'] == 'Projekt Atlas' and q['titel'] for q in v.quellen)
    daten = v.als_dict()
    assert daten['kennung'] == v.kennung and daten['quellen'][0]['zitat'] == 'Projekt Atlas'


# -- 4. Annehmen -----------------------------------------------------------------------------


def test_vorschlag_schreibt_nichts(api):
    app, _ = api
    atlas(app)
    erwaehnungen(app)
    vorschlag(app)
    assert app.state.workspace.projects(include_closed=True) == []
    assert Entscheidungen(app.state.episodes).alle() == {}


def test_annehmen_legt_projekt_an_und_ordnet_nur_quellen_ohne_projekt_zu(api):
    app, client = api
    quellen = atlas(app)
    zeus = app.state.workspace.add_project('Zeus', Provenance(SourceType.USER_STATED))
    app.state.episodes.link_project(quellen[0].id, zeus.id)
    erwaehnungen(app)
    v = vorschlag(app)
    aussagen_vorher = len(app.state.claims.all_claims())
    vorschlaege_vorher = app.state.proposals.counts()
    antwort = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/annehmen')
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    projekt = app.state.workspace.project(daten['projekt']['id'])
    assert projekt.name == 'Projekt Atlas' and projekt.is_open()
    assert daten['satz'] == 'Akte „Projekt Atlas“ angelegt, 3 Quellen zugeordnet.'
    assert daten['sache'] == f'projekt:{projekt.id}' and daten['link'] == f'/memory/akte/projekt:{projekt.id}'
    assert app.state.episodes.get(quellen[0].id).project_id == zeus.id   # bleibt bei Zeus
    assert all(app.state.episodes.get(q.id).project_id == projekt.id for q in quellen[1:])
    # Ablage, kein Fakt: keine Aussage und kein Wissensvorschlag entsteht.
    assert len(app.state.claims.all_claims()) == aussagen_vorher
    assert app.state.proposals.counts() == vorschlaege_vorher
    gemerkt = Entscheidungen(app.state.episodes).zu(v.kennung)
    assert gemerkt['entscheidung'] == 'angenommen' and gemerkt['projekt_id'] == projekt.id
    assert set(gemerkt['quellen']) == {q.id for q in quellen[1:]}
    # Danach ist der Vorschlag weg und die Akte des Projekts vollständig (Quellen, Beteiligte, Zeitstrahl).
    assert vorschlaege(app) == []
    a = akte(client, f'projekt:{projekt.id}')
    assert a['quellen']['gesamt'] == 4 and a['verlauf']['gesamt'] == 4
    assert {b['name'] for b in a['beteiligte']['eintraege']} >= {'Anna Keller', 'Ben Braun'}
    assert a['zeitstrahl']['quellen'] == 4
    assert a['akte_vorschlag']['entscheidung']['entscheidung'] == 'angenommen'
    assert a['akte_vorschlag']['entscheidung']['kennung'] == v.kennung


def test_annehmen_zweimal_ist_409_und_aendert_nichts(api):
    app, client = api
    atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    erste = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/annehmen').json()
    zweite = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/annehmen')
    assert zweite.status_code == 409, zweite.text
    assert [p.id for p in app.state.workspace.projects(include_closed=True)] == [erste['projekt']['id']]
    assert client.post('/api/v1/akten/vorschlaege/0123456789abcdef/annehmen').status_code == 404
    assert client.post('/api/v1/akten/vorschlaege/nicht-hex/annehmen').status_code == 422


def test_annehmen_ist_idempotent_nach_unterbrechung(api):
    """Projekt schon da (Abbruch nach dem Anlegen), Entscheidung fehlt: Der zweite Versuch ergänzt nur."""
    app, client = api
    quellen = atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    from icarus_memory import akten_vorschlaege
    projekt = app.state.workspace.add_project('Projekt Atlas', Provenance(SourceType.USER_STATED),
                                              _identifier=akten_vorschlaege.projekt_id(v.kennung))
    app.state.episodes.link_project(quellen[0].id, projekt.id)
    antwort = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/annehmen')
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()['projekt']['id'] == projekt.id
    assert [p.id for p in app.state.workspace.projects(include_closed=True)] == [projekt.id]
    assert all(app.state.episodes.get(q.id).project_id == projekt.id for q in quellen)


# -- 5. Zurücknehmen ---------------------------------------------------------------------------


def test_zuruecknehmen_stellt_den_stand_vorher_her(api):
    app, client = api
    quellen = atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    angenommen = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/annehmen').json()
    antwort = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/zuruecknehmen')
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()['satz'] == 'Zurückgenommen: 4 Quellen gelöst, Projekt „Projekt Atlas“ entfernt.'
    assert antwort.json()['sache'] == 'projekt:n:atlas'
    assert all(app.state.episodes.get(q.id).project_id is None for q in quellen)
    assert app.state.workspace.projects(include_closed=True) == []
    assert Entscheidungen(app.state.episodes).alle() == {}
    # Der Vorschlag steht wieder, auch in der Akte.
    assert vorschlag(app).kennung == v.kennung
    assert akte(client, 'projekt:n:atlas')['akte_vorschlag']['vorschlag']['kennung'] == v.kennung
    assert client.get('/api/v1/akten/akte', params={'sache': angenommen['sache']}).status_code == 404
    assert client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/zuruecknehmen').status_code == 404


def test_zuruecknehmen_laesst_ein_projekt_mit_anderen_quellen_stehen(api):
    app, client = api
    quellen = atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    projekt_id = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/annehmen').json()['projekt']['id']
    # Der Nutzer hängt danach selbst eine weitere Quelle an das Projekt.
    weitere = mail(app, BEN, ICH, 'Hallo Lea, noch eine Notiz dazu.', tage=1, name='Ben Braun', titel='Nachtrag')
    app.state.episodes.link_project(weitere.id, projekt_id)
    antwort = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/zuruecknehmen').json()
    assert antwort['satz'] == ('Zurückgenommen: 4 Quellen gelöst. Das Projekt „Projekt Atlas“ bleibt, '
                               'weil noch eine andere Quelle dazugehört.')
    assert all(app.state.episodes.get(q.id).project_id is None for q in quellen)
    assert app.state.episodes.get(weitere.id).project_id == projekt_id
    assert app.state.workspace.project(projekt_id).is_open()


# -- 6. Ablehnen -----------------------------------------------------------------------------


def test_ablehnen_wird_gemerkt_und_nie_wiederholt_bis_zum_zuruecknehmen(api):
    app, client = api
    atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    antwort = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/ablehnen')
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()['satz'] == 'Gemerkt: „Projekt Atlas“ wird nicht mehr vorgeschlagen.'
    assert vorschlaege(app) == []
    # Mehr Quellen ändern daran nichts.
    atlas(app, tage=(1,), von=(BEN,))
    erwaehnungen(app)
    assert vorschlaege(app) == []
    assert client.get('/dashboard').json()['akten_vorschlaege']['vorschlag'] is None
    a = akte(client, 'projekt:n:atlas')
    assert a['akte_vorschlag']['vorschlag'] is None
    assert a['akte_vorschlag']['entscheidung']['entscheidung'] == 'abgelehnt'
    # Annehmen bleibt möglich (der Nutzer darf es sich anders überlegen), Ablehnen zweimal ist 409.
    assert client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/ablehnen').status_code == 409
    zurueck = client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/zuruecknehmen')
    assert zurueck.status_code == 200 and zurueck.json()['satz'] == 'Zurückgenommen: „Projekt Atlas“ kann wieder vorgeschlagen werden.'
    assert vorschlag(app).anzahl == 5


def test_nach_annehmen_ist_ablehnen_409(api):
    app, client = api
    atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    assert client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/annehmen').status_code == 200
    assert client.post(f'/api/v1/akten/vorschlaege/{v.kennung}/ablehnen').status_code == 409


# -- 7. Briefing, Akte, Logbuch --------------------------------------------------------------------


def test_briefing_zeigt_hoechstens_einen_vorschlag_den_aeltesten_mit_den_meisten_quellen(api):
    """Einer nach dem anderen (nicht einer am Tag): Nach einer Entscheidung steht der nächste da. Nur Anna schreibt,
    deshalb ist keiner klar genug, um ihn selbst anzulegen (`projekt_automatik.py`); alle bleiben Frage."""
    app, client = api
    atlas(app, von=(ANNA,) * 4)                                # 4 Quellen, älteste vor 20 Tagen
    atlas(app, name='Orion', tage=(30, 25, 22), von=(ANNA,) * 3)   # 3 Quellen, älter
    atlas(app, name='Sirius', tage=(10, 9, 8, 7), von=(ANNA,) * 4)   # 4 Quellen, jünger
    erwaehnungen(app)
    assert len(vorschlaege(app)) == 3
    daten = client.get('/dashboard').json()
    assert daten['akten_vorschlaege']['anzahl'] == 3
    gezeigt = daten['akten_vorschlaege']['vorschlag']
    assert gezeigt['name'] == 'Projekt Atlas'
    punkte = [p for p in daten['briefing']['punkte'] if p['quelle'] == 'akte_vorschlag']
    assert len(punkte) == 1 and punkte[0]['ref'] == gezeigt['kennung'] and punkte[0]['aktion'] == 'Akte anlegen'
    assert punkte[0]['text'].startswith('In 4 Mails seit ') and punkte[0]['text'].endswith(
        ' geht es um „Projekt Atlas“. Daraus eine Akte machen?')
    assert 'Orion' not in daten['briefing']['nachsatz'] if daten['briefing']['nachsatz'] else True
    # Die Oberfläche von Heute bekommt denselben einen Punkt mit beiden Kennungen.
    morgen = client.get('/api/v1/morning-briefing').json()
    karten = [k for k in morgen['needs_you'] if k['source'] == 'akte_vorschlag']
    assert len(karten) == 1 and karten[0]['source_ref'] == gezeigt['kennung'] and karten[0]['title'] == punkte[0]['text']
    # Nach „Nein danke“ steht sofort der nächste da, nicht erst morgen.
    assert client.post(f"/api/v1/akten/vorschlaege/{gezeigt['kennung']}/ablehnen").status_code == 200
    assert client.get('/dashboard').json()['akten_vorschlaege']['vorschlag']['name'] == 'Projekt Sirius'


def test_briefing_ohne_vorschlag_und_rein_aus_den_daten():
    daten = {'tasks': {'items': []}, 'calendar': {'items': []}, 'mail': {'unread': 0}, 'episodes': {'pending': 0},
             'akten_vorschlaege': {'anzahl': 2, 'vorschlag': {'kennung': 'abc', 'name': 'Projekt Atlas',
                                                              'grund': 'In 4 Mails seit 3. Oktober mit Anna Keller'}}}
    jetzt = datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc)
    punkte = briefing.erstelle(daten, jetzt=jetzt).punkte
    assert [p.quelle for p in punkte] == ['akte_vorschlag'] and punkte[0].ref == 'abc'
    assert punkte[0].text == 'In 4 Mails seit 3. Oktober mit Anna Keller geht es um „Projekt Atlas“. Daraus eine Akte machen?'
    assert briefing.erstelle({**daten, 'akten_vorschlaege': {'anzahl': 0, 'vorschlag': None}}, jetzt=jetzt).punkte == []
    assert briefing.erstelle({k: v for k, v in daten.items() if k != 'akten_vorschlaege'}, jetzt=jetzt).punkte == []


def test_akte_zeigt_die_zeile_nur_bei_erwaehnten_projekten(api):
    app, client = api
    atlas(app)
    erwaehnungen(app)
    v = vorschlag(app)
    a = akte(client, 'projekt:n:atlas')
    assert a['akte_vorschlag'] == {'vorschlag': v.als_dict(), 'entscheidung': None}
    assert a['akte_vorschlag']['vorschlag']['grund'].startswith('In 4 Mails seit ')
    # Eine Personenakte trägt die Zeile nicht.
    assert akte(client, f'person:a:{ANNA}').get('akte_vorschlag') is None


def test_logbuch_haelt_annehmen_und_ablehnen_fest(api):
    app, client = api
    atlas(app)
    atlas(app, name='Orion')
    erwaehnungen(app)
    seit = datetime.now(timezone.utc) - timedelta(minutes=1)
    client.post(f'/api/v1/akten/vorschlaege/{vorschlag(app).kennung}/annehmen')
    client.post(f'/api/v1/akten/vorschlaege/{vorschlag(app, "Orion").kennung}/ablehnen')
    ereignisse = [e for e in app.state.logbuch.ereignisse(seit) if e.art == 'akte_vorschlag']
    assert [(e.daten['entscheidung'], e.daten['name']) for e in ereignisse] == [
        ('angenommen', 'Projekt Atlas'), ('abgelehnt', 'Projekt Orion')]
    assert all('text' not in e.daten and 'zitat' not in e.daten for e in ereignisse)
    z = app.state.logbuch.seit(seit)
    assert [a['name'] for a in z.akten_neu] == ['Projekt Atlas'] and z.vorschlaege_abgelehnt == 1


# -- 8. Migration ------------------------------------------------------------------------------


def test_migration_24_legt_die_tabelle_an_und_laesst_entscheidungen_stehen(tmp_path):
    pfad = tmp_path / 'episodes.sqlite3'
    store = EpisodeStore(pfad)
    assert store._conn.execute('PRAGMA user_version').fetchone()[0] == 25
    store._conn.execute("INSERT INTO akten_entscheidungen VALUES ('t:e-1', 'erledigt', 1.0)")
    store._conn.commit()
    store.close()
    # Zurück auf 23: ein älterer Bestand ohne die Tabelle, mit einer Entscheidung aus Migration 23.
    verbindung = sqlite3.connect(pfad)
    verbindung.execute('DROP TABLE akten_vorschlag_entscheidungen')
    from icarus_memory.projekt_automatik import TABLES as AUTOMATIK   # Migration 25 kommt danach
    for tabelle in AUTOMATIK:
        verbindung.execute(f'DROP TABLE {tabelle}')
    verbindung.execute('PRAGMA user_version = 23')
    verbindung.commit()
    verbindung.close()
    wieder = EpisodeStore(pfad)
    assert wieder._conn.execute('PRAGMA user_version').fetchone()[0] == 25
    assert wieder._conn.execute("SELECT entscheidung FROM akten_entscheidungen WHERE ziel = 't:e-1'").fetchone()[0] == 'erledigt'
    ablage = Entscheidungen(wieder)
    ablage.merken('0123456789abcdef', 'abgelehnt')
    with pytest.raises(sqlite3.IntegrityError):
        wieder._conn.execute("INSERT INTO akten_vorschlag_entscheidungen VALUES ('x', 'vielleicht', 1.0, '', '', '[]')")
    wieder.close()
    # Erneutes Öffnen ist idempotent und behält die Entscheidung.
    nochmal = EpisodeStore(pfad)
    assert Entscheidungen(nochmal).zu('0123456789abcdef')['entscheidung'] == 'abgelehnt'
    nochmal.close()
