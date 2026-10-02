"""Prüfbefunde vom 29.09.: je Befund ein Test, der den Fehler zeigte (siehe docs/37-pruefbefunde.md)."""
from datetime import datetime, timedelta, timezone

import pytest
from icarus_memory import terminvorbereitung as tv
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType


@pytest.fixture
def ep(tmp_path):
    speicher = EpisodeStore(tmp_path / 'e.sqlite3')
    yield speicher
    speicher.close()


class _Bekannter:
    bekannt = True
    organisation = ''
    sache = None

    def __init__(self, name):
        self.name = name


def _termin():
    return tv.Termin(uid='u', titel='Gespräch', beginn=datetime.now(timezone.utc) + timedelta(days=1),
                     ende=None, ort='x', teilnehmer=[])


def _notiz(ep, titel, text, tage=2):
    episode, _ = ep.record(EpisodeKind.DOCUMENT, titel, text, Provenance(SourceType.USER_STATED),
                           occurred_at=datetime.now(timezone.utc) - timedelta(days=tage))
    return episode


# -- Befund 1: Packliste liest nur geltende Quellen -------------------------------------------
def test_packliste_liest_keine_entzogene_notiz(ep):
    geltend = _notiz(ep, 'Keller Probedruck', 'Herr Keller bringt den Probedruck mit.')
    entzogen = _notiz(ep, 'Geheim Keller', 'Herr Keller will vertraulich 50000 Euro mitbringen.')
    ep.ignore(entzogen.id, grund='entzogen:ordner')
    quellen = tv._packquellen(_termin(), [_Bekannter('Anna Keller')], None, ep, [], datetime.now(timezone.utc))
    ids = {q.episode_id for q in quellen}
    assert geltend.id in ids
    assert entzogen.id not in ids


def test_packliste_liest_keine_ueberholte_fassung(ep):
    alt, _ = ep.record(EpisodeKind.DOCUMENT, 'Keller alt', 'Herr Keller bringt Alt mit.', Provenance(
        SourceType.USER_STATED, source_ref='n:1'), source_key='notiz:1',
        occurred_at=datetime.now(timezone.utc) - timedelta(days=2))
    neu, _ = ep.record(EpisodeKind.DOCUMENT, 'Keller neu', 'Herr Keller bringt Neu mit.', Provenance(
        SourceType.USER_STATED, source_ref='n:1'), source_key='notiz:1',
        occurred_at=datetime.now(timezone.utc) - timedelta(days=1))
    assert alt.id != neu.id
    quellen = tv._packquellen(_termin(), [_Bekannter('Anna Keller')], None, ep, [], datetime.now(timezone.utc))
    ids = {q.episode_id for q in quellen}
    assert alt.id not in ids


# -- Befund 16: Nachname nur als ganzes Wort --------------------------------------------------
def test_nachname_nicht_als_teilstring(ep):
    braunschweig = _notiz(ep, 'Reise', 'Am Dienstag Zug nach Braunschweig, Fahrkarte mitnehmen.')
    braun = _notiz(ep, 'Braun', 'Herr Braun will den Vertrag unterschrieben zurück.')
    quellen = tv._packquellen(_termin(), [_Bekannter('Ben Braun')], None, ep, [], datetime.now(timezone.utc))
    ids = {q.episode_id for q in quellen}
    assert braun.id in ids
    assert braunschweig.id not in ids


# -- Befund 2: „Frist“ allein macht keine Frist zum Ersatz einer anderen -----------------------
def _fristen_aus(*texte):
    from icarus_memory import akten
    art = sorted(akten.FRIST_ARTEN)[0]
    abschnitte = [akten.Abschnitt({'episode_id': f'e{i}', 'kind': art, 'start': 0, 'ende': len(text)},
                                  datetime(2026, 9, tag, tzinfo=timezone.utc), text, akten.stamm_menge(text), frozenset())
                  for i, (text, tag) in enumerate(texte)]
    return akten._fristen(abschnitte)[0]


def test_verschiedene_fristen_ersetzen_sich_nicht():
    alle = _fristen_aus(('Die Frist für den Jahresbericht ist der 15.10.2026.', 1),
                        ('Die Frist für die Steuererklärung ist der 30.11.2026.', 10))
    assert len(alle) == 2
    assert all(f['ersetzt_durch'] is None for f in alle)


def test_verschobene_frist_desselben_gegenstands_bleibt_ersetzt():
    alle = _fristen_aus(('Die Frist für den Jahresbericht ist der 15.10.2026.', 1),
                        ('Die Frist für den Jahresbericht wird auf den 30.11.2026 verschoben.', 10))
    alt = next(f for f in alle if f['datum'] == '2026-10-15')
    neu = next(f for f in alle if f['datum'] == '2026-11-30')
    assert alt['ersetzt_durch'] and alt['ersetzt_durch']['datum'] == '2026-11-30'
    assert neu['ersetzt_durch'] is None


# -- Befund 3: Sprecher und Projekt nur nach Bestätigung, Lösen nimmt die Übernahme zurück --------
from tests.test_transkript_zuordnung import event, welt  # noqa: E402,F401 - Fixture


def _auto_zugeordnet(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    assert zeile['status'] == 'zugeordnet' and zeile['von'] == 'auto'
    return episode, zeile


def test_auto_zuordnung_schreibt_keine_sprecher_in_die_quelle(welt):
    episode, _ = _auto_zugeordnet(welt)
    danach = welt.episodes.get(episode.id)
    assert danach.contacts == [] and danach.participants == episode.participants  # nur die Namen aus der Mitschrift


def test_auto_zuordnung_verknuepft_kein_projekt(welt):
    welt.zuordner._termin_projekt = lambda uid: (True, 'projekt-1')
    episode, _ = _auto_zugeordnet(welt)
    assert welt.episodes.get(episode.id).project_id is None


def test_bestaetigen_uebernimmt_und_loesen_nimmt_es_zurueck(welt):
    welt.zuordner._termin_projekt = lambda uid: (True, 'projekt-1')
    episode, zeile = _auto_zugeordnet(welt)
    ursprung = list(welt.episodes.get(episode.id).participants)
    welt.zuordner.bestaetigen(episode.id, zeile['termin'])
    mit = welt.episodes.get(episode.id)
    assert {c['adresse'] for c in mit.contacts} == {'anna.berg@winter.example', 'bert@winter.example'}
    assert mit.project_id == 'projekt-1'
    welt.zuordner.loesen(episode.id)
    ohne = welt.episodes.get(episode.id)
    assert ohne.contacts == [] and ohne.participants == ursprung and ohne.project_id is None


def test_loesen_entfernt_nur_was_die_zuordnung_hinzugefuegt_hat(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    welt.episodes.add_contacts(episode.id, [{'name': 'Dora Rot', 'adresse': 'dora@rot.example', 'rolle': 'beteiligt',
                                             'ich': False}], ['Dora Rot <dora@rot.example>'])
    welt.zuordner.bestaetigen(episode.id, zeile['termin'])
    welt.zuordner.loesen(episode.id)
    assert [c['adresse'] for c in welt.episodes.get(episode.id).contacts] == ['dora@rot.example']


# -- Befund 4: Verzeichnis (Register) folgt Entzug und Nachträgen, ohne den Speicher zu sperren ---
def _mail_von(ep, adresse, ref):
    episode, _ = ep.record(EpisodeKind.MESSAGE, 'Hallo', 'Text ' + ref, Provenance(SourceType.EMAIL, source_ref=ref),
                           participants=[f'Anna Keller <{adresse}>'])
    return episode


def test_register_vergisst_eine_entzogene_quelle_sofort(ep):
    from icarus_memory.bezuege import Bezuege
    bezuege = Bezuege(ep)
    mail = _mail_von(ep, 'anna@x.example', 'm1')
    assert 'anna@x.example' in bezuege.register().verzeichnis.adressen()
    ep.ignore(mail.id, grund='entzogen:ordner')
    assert 'anna@x.example' not in bezuege.register().verzeichnis.adressen()          # Cache erkennt das Ignorieren
    assert 'anna@x.example' not in Bezuege(ep).register().verzeichnis.adressen()      # und frisch gebaut sowieso


def test_register_sieht_nachgetragene_beteiligte(ep):
    from icarus_memory.bezuege import Bezuege
    bezuege = Bezuege(ep)
    notiz = _notiz(ep, 'Mitschrift', 'Text')
    bezuege.register()
    ep.add_contacts(notiz.id, [{'name': 'Ben Braun', 'adresse': 'ben@y.example', 'rolle': 'beteiligt'}],
                    ['Ben Braun <ben@y.example>'])
    assert 'ben@y.example' in bezuege.register().verzeichnis.adressen()


def test_register_bau_haelt_den_speicher_nicht_gesperrt(ep):
    import threading
    from icarus_memory.bezuege import Bezuege
    _mail_von(ep, 'anna@x.example', 'm1')
    _mail_von(ep, 'ben@x.example', 'm2')
    bezuege = Bezuege(ep)
    frei = []
    original = ep.each_geltende

    def beobachtet(*args, **kwargs):
        for episode in original(*args, **kwargs):
            probe = threading.Thread(target=lambda: frei.append(ep._lock.acquire(timeout=1) and ep._lock.release() is None))
            probe.start()
            probe.join()
            yield episode

    ep.each_geltende = beobachtet
    bezuege.register()
    assert frei and all(frei)


# -- Befund 5: Entscheidungen zu Mitschriften gehören in die Sicherung ----------------------------
def test_gespraeche_gehoeren_zur_sicherung_und_zur_schemapruefung():
    from icarus_memory import update_backup
    from icarus_memory.backup import BACKUP_DATA_FILES, SQLITE_DATA_FILES
    assert 'gespraeche.sqlite3' in SQLITE_DATA_FILES and 'gespraeche.sqlite3' in BACKUP_DATA_FILES
    assert 'gespraeche.sqlite3' in update_backup._targets()


def test_wiederherstellung_stellt_die_entscheidungen_zu_mitschriften_her(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import SelfModelStore, SqliteBackend
    from icarus_memory.audit import AuditLog
    from icarus_memory.server import create_app
    from icarus_memory.tasks import TaskStore
    from icarus_memory.transkript_zuordnung import Zuordnungen
    from icarus_memory.workspace import WorkspaceStore
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    backend = SqliteBackend(tmp_path / 'self-model.sqlite3')
    app = create_app(SelfModelStore(backend, subject_id='local'), audit=AuditLog(tmp_path / 'audit.sqlite3'),
                     tasks=TaskStore(tmp_path / 'tasks.sqlite3'), workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'),
                     episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'))
    app.state.backend = backend
    try:
        client = TestClient(app)
        ablage = app.state.zuordnungen
        ablage.schreiben('e1', status='zugeordnet', termin='k|t', von='nutzer', hinweise={}, kandidaten=[],
                         gruende=[], abgelehnt=['k|alt'])
        name = client.post('/backups').json()['name']
        ablage.schreiben('e1', status='allein', termin='', von='nutzer', hinweise={}, kandidaten=[], gruende=[],
                         abgelehnt=['k|alt', 'k|neu'])
        assert client.post('/backups/restore', json={'name': name}).status_code == 200
        with pytest.raises(Exception):   # das alte Handle zeigt auf die ersetzte Datei und ist geschlossen
            ablage.zeile('e1')
        frisch = Zuordnungen(tmp_path / 'gespraeche.sqlite3')
        assert frisch.zeile('e1')['abgelehnt'] == ['k|alt'] and frisch.zeile('e1')['status'] == 'zugeordnet'
        frisch.close()
    finally:
        app.state.scheduler.stop()


# -- Befund 6: Statuswörter als ganze Wortformen, „offen“ als Gegenstatus ----------------------
from tests.test_satzpruefung import belege as _belege, besteht as _besteht, faellt as _faellt  # noqa: E402


def test_fertigung_ist_nicht_fertig():
    b = _belege('Anna Keller: Die Fertigung des Auftrags startet Montag.')
    _faellt('Der Auftrag für Anna Keller ist fertig.', b, 'erledigt')


def test_offen_gegen_bezahlt_im_selben_gegenstand():
    b = _belege('Die Rechnung über 1.200 Euro wurde bezahlt, offen ist noch das Angebot.')
    _faellt('Die Rechnung über 1.200 Euro ist noch offen.', b, 'offen')


def test_abgeschlossen_gegen_offen_beim_selben_projekt():
    b = _belege('Projekt Alpha: Stand offen. Abgeschlossen ist Projekt Beta.')
    _faellt('Das Projekt Alpha ist abgeschlossen.', b, 'offen')


def test_ausstehend_und_noch_nicht_sind_gegenstatus_zu_erledigt():
    _faellt('Die Rechnung ist bezahlt.', _belege('Die Rechnung ist ausstehend.'), 'bezahlt')
    _faellt('Die Rechnung ist ausstehend.', _belege('Die Rechnung wurde bezahlt.'), 'offen')
    _faellt('Die Rechnung ist noch nicht bezahlt.', _belege('Die Rechnung wurde bezahlt.'), 'verneint')


def test_flektierte_statuswoerter_und_wechsel_im_verlauf_bestehen():
    _besteht('Die erledigten Punkte liegen vor.', _belege('Erledigte Punkte: Angebot, Vertrag.'))
    _besteht('Die Rechnung wurde bezahlt.', _belege('Die Rechnung ist offen. Später: Die Rechnung wurde bezahlt.'))
    _besteht('Die Rechnung ist noch offen.', _belege('Die Rechnung ist noch offen, Zahlung bis Freitag.'))


# -- Befund 8: Mailhilfen nutzen die Rolle „hintergrund“, nicht die Rolle „antwort“ ---------------
def test_antwortentwurf_nimmt_das_lokale_modell_der_rolle_hintergrund():
    from types import SimpleNamespace
    from icarus_memory.model_roles import lese_wahlen
    from tests.test_mail_reply_suggestions import Provider, make_client

    class Cloud(Provider):
        is_local = False

        def complete_json(self, messages):
            raise AssertionError('das Modell der Rolle „antwort“ darf hier nicht antworten')

    lokal = Provider()
    app, client = make_client(provider=Cloud())
    app.state.rollen = SimpleNamespace(wahlen=lese_wahlen(None),
                                       provider=lambda rolle: lokal if rolle == 'hintergrund' else app.state.agent.provider)
    antwort = client.post('/api/v1/messages/a%3A1.1/reply-suggestion', json={'instruction': 'locker bleiben'})
    assert antwort.status_code == 200 and antwort.json()['body'] == 'Ja, gern.'


def test_antwortentwurf_bleibt_lokal_pflichtig_auch_bei_der_rolle_hintergrund():
    from types import SimpleNamespace
    from icarus_memory.model_roles import lese_wahlen
    from tests.test_mail_reply_suggestions import Provider, make_client

    class Cloud(Provider):
        is_local = False

    app, client = make_client(provider=Provider())
    app.state.rollen = SimpleNamespace(wahlen=lese_wahlen(None), provider=lambda rolle: Cloud())
    assert client.post('/api/v1/messages/a%3A1.1/reply-suggestion', json={}).status_code == 503

from tests.test_context_identity import core  # noqa: E402,F401 - Fixture

# -- Befund 9: Wegezeit blockiert das Briefing nicht, Fehlschläge werden kurz gemerkt ------------
def _wege_dienst(anbieter, **einstellung):
    from icarus_memory.wegezeit import Einstellung, WegezeitDienst
    daten = {'aktiv': True, 'heimat': 'Musterstraße 1, 65183 Wiesbaden', **einstellung}
    return WegezeitDienst({'apple': anbieter}, einstellung=lambda: Einstellung.aus(daten))


class _Langsam:
    name = 'Langsam'

    def __init__(self):
        import threading
        self.frei = threading.Event()
        self.aufrufe = 0

    def verfuegbar(self):
        return True

    def fahrzeit(self, von, nach, verkehrsmittel, abfahrt):
        from icarus_memory.wegezeit import Fahrzeit
        self.aufrufe += 1
        assert self.frei.wait(10)
        return Fahrzeit(30, verkehrsmittel, self.name)


def test_wegezeit_haelt_das_zeitbudget_ein_und_holt_im_hintergrund_nach():
    import time
    from icarus_memory import wegezeit as w
    beginn = datetime(2026, 9, 30, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    ort = 'Uferweg 7, Wiesbaden-Biebrich'
    anbieter = _Langsam()
    dienst = _wege_dienst(anbieter)
    angefangen = time.monotonic()
    auskunft = dienst.auskunft(ort, beginn=beginn, frist_bis=dienst.frist(0.2))
    assert time.monotonic() - angefangen < 2
    assert (auskunft.status, auskunft.minuten) == (w.WIRD_BERECHNET, None)
    assert 'wird berechnet' in auskunft.satz
    # ein zweiter Aufruf startet keine zweite Anfrage; die erste läuft weiter
    assert dienst.auskunft(ort, beginn=beginn, frist_bis=dienst.frist(0)).status == w.WIRD_BERECHNET
    anbieter.frei.set()
    for _ in range(100):
        nachher = dienst.auskunft(ort, beginn=beginn, frist_bis=dienst.frist(0.5))
        if nachher.status == w.BERECHNET:
            break
        time.sleep(0.05)
    assert (nachher.status, nachher.minuten) == (w.BERECHNET, 30) and anbieter.aufrufe == 1


def test_fehlschlag_wird_kurz_gemerkt_statt_bei_jedem_aufruf_neu_zu_fragen():
    from icarus_memory.wegezeit import WegezeitFehler
    beginn = datetime(2026, 9, 30, 14, 0, tzinfo=timezone(timedelta(hours=2)))

    class Kaputt:
        name = 'Kaputt'
        aufrufe = 0

        def verfuegbar(self):
            return True

        def fahrzeit(self, *args):
            Kaputt.aufrufe += 1
            raise WegezeitFehler('Apple Karten hat nicht rechtzeitig geantwortet.')

    dienst = _wege_dienst(Kaputt())
    erste = dienst.auskunft('Uferweg 7, Wiesbaden', beginn=beginn)
    zweite = dienst.auskunft('Uferweg 7, Wiesbaden', beginn=beginn)
    assert Kaputt.aufrufe == 1
    assert erste.status == zweite.status == 'fehler' and 'rechtzeitig' in zweite.grund


def test_mac_antwort_wird_ohne_einwilligung_nicht_angenommen(core, tmp_path, monkeypatch):
    import threading
    from tests.test_source_answers_http import _api
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        client.get('/api/v1/wegezeit/einstellungen')      # legt Dienst und Briefkasten an
        briefkasten = app.state.wegezeit_briefkasten
        antwort = {}
        frager = threading.Thread(target=lambda: antwort.update(
            briefkasten.fragen('A', 'B', 'auto', None, 3.0) or {}))
        frager.start()
        for _ in range(100):
            if briefkasten._anfragen:
                break
            threading.Event().wait(0.02)
        anfrage_id = next(iter(briefkasten._anfragen))
        aus = client.post('/api/v1/wegezeit/mac/antworten', json={'id': anfrage_id, 'minuten': 5})
        assert aus.json() == {'angenommen': False}
        client.get('/api/v1/wegezeit/mac/anfragen')        # der Mac-Arbeiter meldet sich: Apple Karten ist da
        client.put('/api/v1/wegezeit/einstellungen', json={'aktiv': True, 'heimat': 'Musterstraße 1, Wiesbaden'})
        an = client.post('/api/v1/wegezeit/mac/antworten', json={'id': anfrage_id, 'minuten': 5})
        assert an.json() == {'angenommen': True}
        frager.join(5)
    finally:
        client.close()


# -- Befund 15: „Absage vor dem Termintag“ gilt nach dem Kalendertag des Nutzers, nicht nach UTC ---
def _absage_zu_termin(absage_zeit):
    from datetime import date
    from icarus_memory import akten
    ereignis = {'episode_id': 'ev', 'art': 'event', 'zeit': '2026-09-30T08:00:00+00:00'}   # 30.09., 10:00 Uhr Berlin
    absage = akten.Abschnitt({'episode_id': 'm', 'kind': 'status', 'start': 0, 'ende': 30}, absage_zeit,
                             'Der Termin am 30.09. ist abgesagt.', frozenset(), frozenset({date(2026, 9, 30)}))
    return akten._termine([ereignis], [absage])[0]['abgesagt']


def test_absage_kurz_vor_mitternacht_ortszeit_am_termintag_zaehlt():
    assert _absage_zu_termin(datetime(2026, 9, 30, 21, 30, tzinfo=timezone.utc)) is not None   # 23:30 Uhr Berlin, 30.09.


def test_absage_kurz_nach_mitternacht_ortszeit_nach_dem_termintag_zaehlt_nicht():
    # 00:30 Uhr Berlin am 01.10.: nach dem Tag des Termins, auch wenn das UTC-Datum noch der 30.09. ist.
    assert _absage_zu_termin(datetime(2026, 9, 30, 22, 30, tzinfo=timezone.utc)) is None
