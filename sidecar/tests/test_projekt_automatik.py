"""Projekte von selbst (Paket P, docs/66-automatik.md): klare Projekte anlegen, Mails nach Absender zuordnen.

Zusicherungen (jede mit Sabotageprobe, docs/runs/2026-10-26-automatik-projekte/README.md):

1. Klar heißt: mindestens drei Quellen **und** zwei Personen, jüngste Quelle höchstens 30 Tage alt, kein ähnlicher
   vorhandener oder erwähnter Name, nicht gesperrt. Sonst bleibt es die Frage „Neue Akte?“ mit Begründung.
2. Klare Projekte legt Kingfisher vor dem Briefing selbst an (wie der Klick: Quellen ohne Projekt zugeordnet, keine
   Aussage), höchstens drei am Tag; Heute bekommt sie über `/api/v1/projekte/automatik` mit Grund.
3. „Rückgängig“ entfernt das Projekt und genau Kingfishers eigene Zuordnungen; was der Nutzer gesetzt hat, bleibt.
   Es wird gemerkt: Das Projekt kommt weder als Projekt noch als Frage wieder.
4. Absenderregel: eine neue Mail kommt in das Projekt, in dem alle früheren Mails des Absenders liegen (mindestens
   zwei); nie bei Absendern mit Mails in mehreren Projekten oder ohne Projekt, nie bei Rundmails oder eigenen Mails.
   Sichtbar als „Zugeordnet nach Absender“, mit Rückgängig, das gemerkt wird.
5. Personen werden nur abgeleitet zugeordnet: keine Aussage, aber das Projekt steht im Personenprofil.
6. Migration 25 legt die Tabellen an und lässt den Bestand stehen.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeStore, Provenance, SourceType
from icarus_memory import projekt_automatik as automatik
from icarus_memory.akten_routes import bausteine
from icarus_memory.akten_vorschlaege import Entscheidungen, Vorschlag, kandidaten
from icarus_memory.episodes import EpisodeKind
from icarus_memory.workspace import ProjectStatus
from tests.test_akten_vorschlaege import ANNA, BEN, atlas, erwaehnungen, vorschlaege
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_kreis import ICH, api, mail  # noqa: F401 - Fixture und Hilfen

JETZT = datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc)


def _vorschlag(**x) -> Vorschlag:
    werte = dict(kennung='0123456789abcdef', sache='projekt:n:umbaupraxis', name='Umbau Praxis',
                 grund='In 4 Mails seit 3. Oktober mit Anna Keller und Ben Braun', anzahl=4, tage=20,
                 erste=(JETZT - timedelta(days=23)).isoformat(), letzte=(JETZT - timedelta(days=2)).isoformat(),
                 arten=('message',), quellen=(),
                 beteiligte=({'sache': 'person:a:anna', 'name': 'Anna Keller', 'anzahl': 2},
                             {'sache': 'person:a:ben', 'name': 'Ben Braun', 'anzahl': 2}),
                 quellen_ids=('a', 'b', 'c', 'd'))
    werte.update(x)
    return Vorschlag(**werte)


def _schaetzen(v=None, vorhandene=None, andere=None, gesperrt=False):
    return automatik.einschaetzen(v or _vorschlag(), jetzt=JETZT, vorhandene=vorhandene or {}, andere=andere or {},
                                  gesperrt=gesperrt)


def dashboard(client):
    antwort = client.get('/dashboard')
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def projekte(app):
    return {p.name: p for p in app.state.workspace.projects(include_closed=True)}


# -- 1. Klar oder unklar -------------------------------------------------------------------------


def test_klar_braucht_alles_zugleich_und_begruendet_sonst():
    klar = _schaetzen()
    assert klar.klar and klar.gruende == () and klar.satz.startswith('In 4 Mails')
    assert _schaetzen(_vorschlag(anzahl=2)).gruende == ('nur 2 Quellen',)
    assert _schaetzen(_vorschlag(beteiligte=_vorschlag().beteiligte[:1])).gruende == ('nur eine Person beteiligt',)
    alt = _vorschlag(letzte=(JETZT - timedelta(days=31)).isoformat())
    assert _schaetzen(alt).gruende == ('seit über 30 Tagen still',)
    assert _schaetzen(_vorschlag(letzte=(JETZT - timedelta(days=29)).isoformat())).klar
    assert _schaetzen(gesperrt=True).gruende == ('früher zurückgenommen',)
    assert _schaetzen(vorhandene={'umbau': 'Umbau'}).gruende == ('ähnlich wie das Projekt „Umbau“',)
    assert _schaetzen(andere={'umbaupraxisnord': 'umbaupraxisnord'}).gruende == (
        'Name nicht eindeutig (auch „umbaupraxisnord“)',)
    # Mehrere Gründe stehen alle da; unklar bleibt unklar.
    beides = _schaetzen(_vorschlag(anzahl=1, beteiligte=()))
    assert not beides.klar and beides.gruende[:2] == ('nur eine Quelle', 'keine Person beteiligt')


@pytest.mark.parametrize('a, b, erwartet', [
    ('atlas', 'atlas', True), ('umbau', 'umbaupraxis', True), ('atlas', 'atlass', True), ('mueller', 'muller', True),
    ('atlas', 'orion', False), ('abc', 'abcd', False), ('kita', 'kitz', False), ('', 'atlas', False)])
def test_aehnliche_namen(a, b, erwartet):
    assert automatik.aehnlich(a, b) is erwartet


# -- 2. Automatisch anlegen ---------------------------------------------------------------------------


def test_klares_projekt_wird_vor_dem_briefing_angelegt_mit_grund_und_ohne_aussage(api):
    app, client = api
    quellen = atlas(app)
    erwaehnungen(app)
    aussagen_vorher = len(app.state.claims.all_claims())
    vorschlaege_vorher = app.state.proposals.counts()
    daten = dashboard(client)
    projekt = projekte(app)['Projekt Atlas']
    assert all(app.state.episodes.get(q.id).project_id == projekt.id for q in quellen)
    # Keine Frage mehr: Es ist schon angelegt.
    assert daten['akten_vorschlaege']['vorschlag'] is None
    assert not [p for p in daten['briefing']['punkte'] if p['quelle'] == 'akte_vorschlag']
    # Ablage, kein Fakt: keine Aussage, kein Wissensvorschlag.
    assert len(app.state.claims.all_claims()) == aussagen_vorher
    assert app.state.proposals.counts() == vorschlaege_vorher
    ablage = automatik.Ablage(app.state.episodes)
    assert set(ablage.zuordnungen_von(projekt.id)) == {q.id for q in quellen}
    neu = client.get('/api/v1/projekte/automatik').json()['neu']
    assert [(n['name'], n['anzahl'], n['wort'], n['personen']) for n in neu] == [
        ('Projekt Atlas', 4, 'Mails', ['Anna Keller', 'Ben Braun'])]
    assert neu[0]['grund'].startswith('In 4 Mails seit ') and neu[0]['link'] == f'/memory/akte/projekt:{projekt.id}'
    # Die Akte nennt die Herkunft mit Grund.
    akte = client.get('/api/v1/akten/akte', params={'sache': f'projekt:{projekt.id}', 'warten': 'true'}).json()
    entscheidung = akte['akte_vorschlag']['entscheidung']
    assert entscheidung['herkunft'] == 'automatisch' and entscheidung['grund'].endswith('mit Anna Keller und Ben Braun')
    # Das Logbuch zählt sie als neue Akte.
    seit = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert [a['name'] for a in app.state.logbuch.seit(seit).akten_neu] == ['Projekt Atlas']
    # Ein zweiter Lauf legt nichts doppelt an.
    dashboard(client)
    assert list(projekte(app)) == ['Projekt Atlas']


def test_unklares_bleibt_frage_einer_nach_dem_anderen(api):
    app, client = api
    atlas(app, tage=(3, 2, 1), von=(ANNA, ANNA, ANNA))                     # nur eine Person
    atlas(app, name='Orion', tage=(50, 45, 40), von=(ANNA, BEN, ANNA))       # seit über 30 Tagen still
    erwaehnungen(app)
    daten = dashboard(client)
    assert projekte(app) == {}
    assert daten['akten_vorschlaege']['anzahl'] == 2
    punkte = [p for p in daten['briefing']['punkte'] if p['quelle'] == 'akte_vorschlag']
    assert len(punkte) == 1 and 'Projekt Orion' in punkte[0]['text']   # gleiche Zahl: der ältere zuerst


def test_vorhandener_aehnlicher_name_wird_nicht_angelegt(api):
    app, client = api
    app.state.workspace.add_project('Atlas Nord', Provenance(SourceType.USER_STATED))
    atlas(app)
    erwaehnungen(app)
    daten = dashboard(client)
    assert list(projekte(app)) == ['Atlas Nord']
    assert daten['akten_vorschlaege']['vorschlag']['name'] == 'Projekt Atlas'


def test_hoechstens_drei_am_tag(api):
    app, _ = api
    for name in ('Atlas', 'Orion', 'Sirius', 'Vega'):
        atlas(app, name=name)
    erwaehnungen(app)
    bezuege, _ = bausteine(app)
    jetzt = datetime.now(timezone.utc)
    erste = automatik.projekte_anlegen(bezuege, app.state.workspace, jetzt=jetzt)
    assert len(erste) == automatik.MAX_JE_TAG == 3
    assert [v.name for v in vorschlaege(app)] == ['Projekt Vega']
    assert automatik.projekte_anlegen(bezuege, app.state.workspace, jetzt=jetzt) == []
    morgen = automatik.projekte_anlegen(bezuege, app.state.workspace, jetzt=jetzt + timedelta(days=1))
    assert [a['projekt']['name'] for a in morgen] == ['Projekt Vega']


# -- 3. Rückgängig ------------------------------------------------------------------------------------


def test_rueckgaengig_loest_nur_eigene_zuordnungen_und_kommt_nicht_wieder(api):
    app, client = api
    quellen = atlas(app)
    erwaehnungen(app)
    dashboard(client)
    projekt = projekte(app)['Projekt Atlas']
    kennung = Entscheidungen(app.state.episodes).nach_projekt(projekt.id)['kennung']
    # Der Nutzer setzt eine Quelle selbst (weg und wieder zurück) und hängt eine weitere Mail selbst an.
    for ziel in (None, projekt.id):
        assert client.put(f'/api/v1/episodes/{quellen[0].id}/project', json={'project_id': ziel}).status_code == 200
    eigene = mail(app, BEN, ICH, 'Hallo Lea, noch etwas dazu.', tage=1, name='Ben Braun', titel='Nachtrag')
    assert client.put(f'/api/v1/episodes/{eigene.id}/project', json={'project_id': projekt.id}).status_code == 200
    antwort = client.post(f'/api/v1/akten/vorschlaege/{kennung}/zuruecknehmen')
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()
    assert daten['automatisch'] is True and daten['satz'].endswith('Kingfisher legt es nicht wieder an.')
    assert daten['satz'].startswith('Zurückgenommen: 3 Quellen gelöst.')
    # Kingfishers Zuordnungen sind weg, die des Nutzers bleiben, und deshalb auch das Projekt.
    assert all(app.state.episodes.get(q.id).project_id is None for q in quellen[1:])
    assert app.state.episodes.get(quellen[0].id).project_id == projekt.id
    assert app.state.episodes.get(eigene.id).project_id == projekt.id
    assert projekte(app)['Projekt Atlas'].is_open()


def test_rueckgaengig_entfernt_das_projekt_und_merkt_es(api):
    app, client = api
    quellen = atlas(app)
    erwaehnungen(app)
    dashboard(client)
    projekt = projekte(app)['Projekt Atlas']
    kennung = Entscheidungen(app.state.episodes).nach_projekt(projekt.id)['kennung']
    daten = client.post(f'/api/v1/akten/vorschlaege/{kennung}/zuruecknehmen').json()
    assert daten['satz'] == ('Zurückgenommen: 4 Quellen gelöst, Projekt „Projekt Atlas“ entfernt. '
                             'Kingfisher legt es nicht wieder an.')
    assert projekte(app) == {} and all(app.state.episodes.get(q.id).project_id is None for q in quellen)
    assert client.get('/api/v1/projekte/automatik').json()['neu'] == []
    # Mehr Mails und weitere Läufe: weder Projekt noch Frage.
    atlas(app, tage=(1,), von=(BEN,))
    erwaehnungen(app)
    nochmal = dashboard(client)
    assert projekte(app) == {} and nochmal['akten_vorschlaege']['vorschlag'] is None
    akte = client.get('/api/v1/akten/akte', params={'sache': 'projekt:n:atlas', 'warten': 'true'}).json()
    assert akte['akte_vorschlag']['entscheidung']['entscheidung'] == 'abgelehnt'
    assert akte['akte_vorschlag']['entscheidung']['herkunft'] == 'automatisch'
    # „Doch vorschlagen“: wieder eine Frage, aber Kingfisher legt es nie mehr selbst an.
    assert client.post(f'/api/v1/akten/vorschlaege/{kennung}/zuruecknehmen').status_code == 200
    wieder = dashboard(client)
    assert projekte(app) == {} and wieder['akten_vorschlaege']['vorschlag']['kennung'] == kennung


def test_selbst_angelegt_und_zurueckgenommen_wird_nie_automatisch(api):
    app, client = api
    atlas(app, tage=(3, 2, 1), von=(ANNA, ANNA, ANNA))   # unklar: bleibt Frage
    erwaehnungen(app)
    kennung = dashboard(client)['akten_vorschlaege']['vorschlag']['kennung']
    assert client.post(f'/api/v1/akten/vorschlaege/{kennung}/annehmen').status_code == 200
    assert client.post(f'/api/v1/akten/vorschlaege/{kennung}/zuruecknehmen').status_code == 200
    # Jetzt wäre es klar (Ben kommt dazu), aber der Nutzer hat es einmal zurückgenommen: nur Frage.
    atlas(app, tage=(1,), von=(BEN,))
    erwaehnungen(app)
    daten = dashboard(client)
    assert projekte(app) == {} and daten['akten_vorschlaege']['vorschlag']['kennung'] == kennung


# -- 4. Absenderregel -------------------------------------------------------------------------------------


def _start(app):
    """Der erste Takt setzt nur den Stand; der Bestand wird nicht neu gedeutet."""
    assert automatik.absender_schritt(app.state.episodes, app.state.workspace, eigene=[ICH]) == []


def _projekt(app, name='Umbau Praxis'):
    return app.state.workspace.add_project(name, Provenance(SourceType.USER_STATED)).id


def _takt(app):
    return automatik.absender_schritt(app.state.episodes, app.state.workspace, eigene=[ICH])


def test_neue_mail_folgt_dem_absender_sichtbar_und_mit_rueckgaengig(api):
    app, client = api
    umbau = _projekt(app)
    for t in (9, 8):
        app.state.episodes.link_project(mail(app, ANNA, ICH, 'Zum Umbau.', tage=t, name='Anna Keller').id, umbau)
    alt = mail(app, ANNA, ICH, 'Vor dem Start.', tage=7, name='Anna Keller')   # vor dem ersten Takt: Bestand
    app.state.episodes.link_project(alt.id, umbau)
    _start(app)
    neu = mail(app, ANNA, ICH, 'Die Fliesen sind da.', tage=0, name='Anna Keller')
    assert _takt(app) == [neu.id]
    assert app.state.episodes.get(neu.id).project_id == umbau
    hinweis = client.get(f'/api/v1/episodes/{neu.id}/project-suggestion').json()['automatisch']
    assert hinweis == {'art': 'absender', 'projekt_id': umbau, 'satz': 'Zugeordnet nach Absender'}
    assert _takt(app) == []   # jede Mail einmal
    antwort = client.post(f'/api/v1/projekte/automatik/zuordnung/{neu.id}/zuruecknehmen')
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()['satz'] == 'Wieder keinem Projekt zugeordnet. Kingfisher ordnet diese Mail nicht wieder zu.'
    assert app.state.episodes.get(neu.id).project_id is None
    assert automatik.Ablage(app.state.episodes).gesperrt('mail:' + neu.id)
    assert automatik.absender_ziel(app.state.episodes, app.state.episodes.get(neu.id), eigene=[ICH]) is None
    assert client.post(f'/api/v1/projekte/automatik/zuordnung/{neu.id}/zuruecknehmen').status_code == 404
    assert client.get(f'/api/v1/episodes/{neu.id}/project-suggestion').json()['automatisch'] is None


def test_was_der_nutzer_aendert_gilt_und_rueckgaengig_ist_dann_409_oder_404(api):
    app, client = api
    umbau, orion = _projekt(app), _projekt(app, 'Orion')
    for t in (9, 8):
        app.state.episodes.link_project(mail(app, ANNA, ICH, 'Zum Umbau.', tage=t, name='Anna Keller').id, umbau)
    _start(app)
    neu = mail(app, ANNA, ICH, 'Zu Orion.', tage=0, name='Anna Keller')
    assert _takt(app) == [neu.id]
    assert client.put(f'/api/v1/episodes/{neu.id}/project', json={'project_id': orion}).status_code == 200
    assert client.get(f'/api/v1/episodes/{neu.id}/project-suggestion').json()['automatisch'] is None
    assert client.post(f'/api/v1/projekte/automatik/zuordnung/{neu.id}/zuruecknehmen').status_code == 404
    assert app.state.episodes.get(neu.id).project_id == orion
    # 409: der Eintrag steht noch, die Mail liegt aber woanders (etwa nach einem Wechsel ohne den gewohnten Weg).
    weitere = mail(app, ANNA, ICH, 'Noch einmal Umbau.', tage=0, name='Anna Keller')
    app.state.episodes.link_project(weitere.id, umbau, automatisch=True)
    automatik.Ablage(app.state.episodes).zuordnen([weitere.id], umbau, 'absender', 1.0)
    app.state.episodes.link_project(weitere.id, orion, automatisch=True)
    assert client.post(f'/api/v1/projekte/automatik/zuordnung/{weitere.id}/zuruecknehmen').status_code == 409


def test_absender_mit_mails_in_zwei_projekten_oder_ohne_projekt_bekommt_keine_zuordnung(api):
    app, _ = api
    umbau, orion = _projekt(app), _projekt(app, 'Orion')
    for t, ziel in ((9, umbau), (8, umbau), (7, orion)):
        app.state.episodes.link_project(mail(app, ANNA, ICH, 'Zwei Projekte.', tage=t, name='Anna Keller').id, ziel)
    for t, ziel in ((9, umbau), (8, umbau), (7, None)):
        episode = mail(app, BEN, ICH, 'Eine ohne Projekt.', tage=t, name='Ben Braun')
        if ziel:
            app.state.episodes.link_project(episode.id, ziel)
    _start(app)
    mail(app, ANNA, ICH, 'Neu von Anna.', tage=0, name='Anna Keller')
    mail(app, BEN, ICH, 'Neu von Ben.', tage=0, name='Ben Braun')
    assert _takt(app) == []


def test_nie_bei_rundmail_eigener_mail_nur_einer_frueheren_oder_geschlossenem_projekt(api):
    app, _ = api
    umbau = _projekt(app)
    for t in (9, 8):
        app.state.episodes.link_project(mail(app, ANNA, ICH, 'Zum Umbau.', tage=t, name='Anna Keller').id, umbau)
        app.state.episodes.link_project(mail(app, ICH, ANNA, 'Meine Antwort.', tage=t, name='Anna Keller').id, umbau)
    app.state.episodes.link_project(mail(app, BEN, ICH, 'Nur eine.', tage=9, name='Ben Braun').id, umbau)
    _start(app)
    kontakte = [{'name': 'Anna Keller', 'adresse': ANNA, 'rolle': 'von', 'ich': False}] + [
        {'name': f'Leser {i}', 'adresse': f'leser{i}@example.org', 'rolle': 'an', 'ich': False} for i in range(6)]
    rund, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Rundbrief', 'An alle: Neuigkeiten.',
                                        Provenance(SourceType.EMAIL, source_ref='kreis:<rund@example.invalid>'),
                                        participants=[f'Anna Keller <{ANNA}>'], contacts=kontakte)
    eigene = mail(app, ICH, ANNA, 'Meine neue Mail.', tage=0, name='Anna Keller')
    ben = mail(app, BEN, ICH, 'Ben neu.', tage=0, name='Ben Braun')
    assert _takt(app) == []
    assert {app.state.episodes.get(e.id).project_id for e in (rund, eigene, ben)} == {None}
    # Ein abgeschlossenes Projekt nimmt nichts mehr auf.
    app.state.workspace.update_project(umbau, status=ProjectStatus.DONE)
    mail(app, ANNA, ICH, 'Nach dem Abschluss.', tage=0, name='Anna Keller')
    assert _takt(app) == []


def test_neue_mails_eines_absenders_im_selben_takt_folgen_nacheinander(api):
    app, _ = api
    umbau = _projekt(app)
    for t in (9, 8):
        app.state.episodes.link_project(mail(app, ANNA, ICH, 'Zum Umbau.', tage=t, name='Anna Keller').id, umbau)
    _start(app)
    erste = mail(app, ANNA, ICH, 'Erste neue.', tage=2, name='Anna Keller')
    zweite = mail(app, ANNA, ICH, 'Zweite neue.', tage=1, name='Anna Keller')
    assert _takt(app) == [erste.id, zweite.id]


def test_rueckgaengig_des_projekts_loest_auch_die_absenderzuordnungen(api):
    app, client = api
    atlas(app)
    erwaehnungen(app)
    _start(app)
    dashboard(client)
    projekt = projekte(app)['Projekt Atlas']
    neu = mail(app, ANNA, ICH, 'Hallo Lea, ein Nachtrag ohne Namen.', tage=0, name='Anna Keller')
    assert _takt(app) == [neu.id]
    kennung = Entscheidungen(app.state.episodes).nach_projekt(projekt.id)['kennung']
    client.post(f'/api/v1/akten/vorschlaege/{kennung}/zuruecknehmen')
    assert app.state.episodes.get(neu.id).project_id is None and projekte(app) == {}


# -- 5. Personen ↔ Projekte: nur abgeleitet ------------------------------------------------------------


def test_personen_sehen_das_projekt_ohne_gespeicherte_aussage(api):
    app, client = api
    atlas(app)
    erwaehnungen(app)
    aussagen = len(app.state.claims.all_claims())
    dashboard(client)
    profil = client.get(f'/api/v1/memory/people/{ANNA}').json()
    assert [c['project']['name'] for c in profil['contexts']] == ['Projekt Atlas']
    assert len(app.state.claims.all_claims()) == aussagen


# -- 6. Migration -----------------------------------------------------------------------------------------


def test_migration_25_legt_die_tabellen_an_und_laesst_den_bestand(tmp_path):
    pfad = tmp_path / 'episodes.sqlite3'
    store = EpisodeStore(pfad)
    assert store._conn.execute('PRAGMA user_version').fetchone()[0] == 26
    Entscheidungen(store).merken('0123456789abcdef', 'abgelehnt')
    store.close()
    verbindung = sqlite3.connect(pfad)
    for tabelle in automatik.TABLES:
        verbindung.execute(f'DROP TABLE {tabelle}')
    verbindung.execute('DROP TABLE personen_sperre')   # Migration 26 kommt danach
    verbindung.execute('PRAGMA user_version = 24')
    verbindung.commit()
    verbindung.close()
    wieder = EpisodeStore(pfad)
    assert wieder._conn.execute('PRAGMA user_version').fetchone()[0] == 26
    assert Entscheidungen(wieder).zu('0123456789abcdef')['entscheidung'] == 'abgelehnt'
    ablage = automatik.Ablage(wieder)
    ablage.sperren('akte:0123456789abcdef', 1.0)
    with pytest.raises(sqlite3.IntegrityError):
        wieder._conn.execute("INSERT INTO projekt_automatik_zuordnungen VALUES ('e', 'p', 'vielleicht', 1.0)")
    wieder.close()
    nochmal = EpisodeStore(pfad)
    assert automatik.Ablage(nochmal).gesperrt('akte:0123456789abcdef')
    nochmal.close()


def test_kandidaten_tragen_letzte_aktivitaet(api):
    app, _ = api
    atlas(app)
    erwaehnungen(app)
    bezuege, _ = bausteine(app)
    v = kandidaten(bezuege, app.state.workspace)[0]
    assert v.letzte > v.erste and v.arten == ('message',) and v.als_dict()['letzte'] == v.letzte
