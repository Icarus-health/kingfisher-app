"""Fremdprobe 2, Befunde der ersten Stunde (docs/51-fremdprobe-2.md): Heute, Briefing, Gespräch, Mailstand, Akte.

Je Befund die Zusicherung, die ein Mensch vor dem Bildschirm sieht; nur synthetische Daten.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore, ist_eigene_quelle
from icarus_memory.model import Provenance, SourceType
from icarus_memory.morning import compose

JETZT = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def episoden(tmp_path):
    store = EpisodeStore(tmp_path / 'episodes.sqlite3')
    yield store
    store.close()


def _quelle(store, art, titel, *, ref, kind=EpisodeKind.MESSAGE, tags=None):
    return store.record(kind, titel, f'{titel}: synthetischer Text.', Provenance(source_type=art, source_ref=ref),
                        occurred_at=JETZT, tags=tags)[0]


# -- Befund 22: eigene Gesprächszeilen und hochgeladene Dateien sind keine relevanten Nachrichten --------------------

def test_neu_von_aussen_zaehlt_keine_eigenen_zeilen_und_keine_hochgeladenen_dateien(episoden):
    _quelle(episoden, SourceType.CHAT, 'Frage an Kingfisher', ref='conversation:c1:message:m1')
    _quelle(episoden, SourceType.USER_STATED, 'Eigene Angabe', ref='eigen:1')
    _quelle(episoden, SourceType.DOCUMENT, 'Besprechung', ref='upload:abc', kind=EpisodeKind.DOCUMENT)
    assert episoden.neue_von_aussen() == 0
    _quelle(episoden, SourceType.EMAIL, 'Angebot', ref='imap:probe@example.org:INBOX:1')
    _quelle(episoden, SourceType.DOCUMENT, 'Notiz aus dem Ordner', ref='file:/notizen/a.md', kind=EpisodeKind.DOCUMENT)
    assert episoden.neue_von_aussen() == 2
    assert episoden.counts()['new'] == 5, 'gezählt wird anders, gespeichert bleibt alles'


def _dashboard(**teile):
    return {'briefing': {'punkte': []}, 'tasks': {}, 'mail': {'items': []}, 'calendar': {'items': []},
            'episodes': {}, 'proposals': {}, **teile}


def test_briefing_nennt_eigene_quellen_nicht_als_relevante_nachrichten():
    bericht = lambda art, ref, titel: {'episode_id': titel, 'title': titel, 'kinds': ['commitment'],  # noqa: E731
                                        'source_type': art, 'source_ref': ref}
    ergebnis = compose(_dashboard(
        episodes={'pending': 4, 'neu_von_aussen': 0},
        working_memory={'items': [bericht('chat', 'conversation:c:message:m', 'Gesprächsquelle'),
                                  bericht('document', 'upload:x', 'Besprechung-Atlas.md')], 'truncated': False}),
        now=JETZT, target=date(2026, 10, 1))
    assert ergebnis['happening_now'] == []
    assert ergebnis['working_memory_more'] is False
    # Kommt eine Mail dazu, steht sie da, und die Zählung nennt nur sie.
    ergebnis = compose(_dashboard(
        episodes={'pending': 5, 'neu_von_aussen': 1},
        working_memory={'items': [bericht('email', 'imap:a:INBOX:1', 'Angebot Atlas')], 'truncated': False}),
        now=JETZT, target=date(2026, 10, 1))
    assert [z['title'] for z in ergebnis['happening_now']] == ['Angebot Atlas', 'Neue Hinweise']
    assert ergebnis['happening_now'][1]['detail'] == '1 Quelle aufgenommen'


def test_eigene_quelle():
    assert ist_eigene_quelle('chat', 'conversation:c:message:m')
    assert ist_eigene_quelle('document', 'upload:1')
    assert not ist_eigene_quelle('email', 'imap:x')
    assert not ist_eigene_quelle('document', 'file:/a.md')


# -- Befunde 13 und 14: die eigene Frage heißt so, ein Hinweis des Programms ist als solcher markiert ---------------

class _Schlicht:
    name = model = 'schlicht-probe'
    is_local = True

    def complete(self, messages, tools):
        from icarus_memory.providers import Reply
        return Reply(text='Notiert.', model=self.model)


def test_unter_der_eigenen_frage_steht_dass_es_die_eigene_frage_ist(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.policy import Policy
    from icarus_memory.server import EIGENE_FRAGE_ANSEHEN, create_app
    from icarus_memory.tools import build_registry
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'daten'))
    store = SelfModelStore(MemoryBackend(), subject_id='probe')
    agent = Agent(store, Policy(), AuditLog(tmp_path / 'audit.sqlite3'), build_registry(store), _Schlicht(), max_rounds=1)
    app = create_app(store, agent=agent)
    with TestClient(app) as client:
        gespraech = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
        antwort = client.post(f'/api/v1/conversations/{gespraech}/messages',
                              json={'message': 'Was steht heute an?', 'answer_mode': 'chat'})
        assert antwort.status_code == 201, antwort.text
        frage = antwort.json()['messages'][0]
        assert [link['label'] for link in frage['metadata']['context']['source_links']] == [EIGENE_FRAGE_ANSEHEN]
        assert 'deine Nachricht' in EIGENE_FRAGE_ANSEHEN and 'Gesprächsquelle' not in EIGENE_FRAGE_ANSEHEN


# -- Befund 17: eine Aussage je Postfach, aus einer Quelle für alle Stellen ------------------------------------------

def _ordner(total, gefunden, fertig=True):
    return {'folder': 'INBOX', 'inventory_complete': fertig, 'total': total if fertig else None,
            'captured': gefunden, 'duplicates': 0}


@pytest.fixture()
def berlin(monkeypatch):
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')


def test_mailstand_leer_liest_gelesen_und_fehler(berlin):
    from icarus_memory.mail_stand import konto_stand
    zeit = datetime(2026, 10, 1, 12, 43, tzinfo=timezone.utc).timestamp()
    intake = lambda *ordner, **mehr: {'started': True, 'paused': False, 'error': None, 'folders': list(ordner),  # noqa: E731
                                      'aktualisiert': zeit, **mehr}
    leer = konto_stand('Privat', intake=intake(_ordner(0, 0)), jetzt=JETZT)
    assert leer['zustand'] == 'leer'
    assert leer['satz'] == 'Postfach Privat ist verbunden und leer, abgerufen um 14:43.'
    liest = konto_stand('Privat', intake=intake(_ordner(4300, 120)), jetzt=JETZT)
    assert (liest['zustand'], liest['satz']) == ('liest', 'Postfach Privat wird gelesen: 120 von 4.300 Mails.')
    zaehlt = konto_stand('Privat', intake=intake(_ordner(None, 0, fertig=False)), jetzt=JETZT)
    assert (zaehlt['zustand'], zaehlt['satz']) == ('liest', 'Postfach Privat wird durchgesehen: bisher keine Mails gefunden.')
    fertig = konto_stand('Privat', intake=intake(_ordner(4300, 4300)), jetzt=JETZT)
    assert fertig['satz'] == 'Postfach Privat ist gelesen: 4.300 Mails, zuletzt abgerufen um 14:43.'
    fehler = konto_stand('Privat', intake=intake(_ordner(0, 0), error='inventory_unavailable'), jetzt=JETZT)
    assert fehler['zustand'] == 'fehler' and 'antwortet gerade nicht' in fehler['satz'] and 'nichts tun' in fehler['satz']
    halt = konto_stand('Privat', intake=intake(_ordner(0, 0), paused=True), jetzt=JETZT)
    assert halt['zustand'] == 'pausiert'


def test_mailstand_ohne_einlesen_aus_abruf_und_blick(berlin):
    from icarus_memory.mail_stand import konto_stand
    assert konto_stand('Privat', jetzt=JETZT) == {
        'zustand': 'nicht_abgerufen', 'satz': 'Postfach Privat ist verbunden, aber noch nicht abgerufen.',
        'gelesen': None, 'gesamt': None, 'zuletzt': None, 'technik': None}
    blick = {'zeit': datetime(2026, 10, 1, 12, 43, tzinfo=timezone.utc), 'anzahl': 0}
    assert konto_stand('Privat', blick=blick, jetzt=JETZT)['satz'] == 'Postfach Privat ist verbunden und leer, abgerufen um 14:43.'
    passwort = konto_stand('Privat', abruf={'last_failure': 'credentials_missing'}, jetzt=JETZT)
    assert passwort['zustand'] == 'fehler' and 'Einstellungen → Zugänge' in passwort['satz']
    gestern = {'last_success': '2026-09-30T08:00:00+00:00', 'last_report': {'recorded': 3}}
    assert konto_stand('Privat', abruf=gestern, jetzt=JETZT)['satz'] == \
        'Postfach Privat ist abgerufen am 30. September um 10:00: 3 Mails neu.'
    # Ein erfolgreicher Blick in den leeren Posteingang beendet „wird durchgesehen“, auch wenn die Zählung noch läuft.
    durch = konto_stand('Privat', intake={'started': True, 'folders': [_ordner(None, 0, fertig=False)]}, blick=blick,
                        jetzt=JETZT)
    assert durch['zustand'] == 'leer' and 'im Posteingang liegt nichts' in durch['satz']


def test_ein_stand_fuer_alle_stellen_ueber_die_schnittstelle(tmp_path, monkeypatch, berlin):
    """Heute (Einlesen), „Für Techniker“ (Zeitplan) und die eigene Route sagen über dasselbe Postfach dasselbe."""
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore, config
    from icarus_memory.config import MailAccountSettings
    from icarus_memory.mail_intake import Intake
    from icarus_memory.mail_stand import merke_gelesen
    from icarus_memory.server import create_app
    daten = tmp_path / 'daten'
    monkeypatch.setenv('ICARUS_DATA_DIR', str(daten))
    einstellungen = config.Settings()
    einstellungen.mail_accounts = [MailAccountSettings(id='privat', label='Privat', imap_host='127.0.0.1', imap_port=9,
                                                       user='lena.probe@example.org')]
    config.save(daten, einstellungen)
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='probe'))
    with TestClient(app) as client:
        # Ohne Passwort kommt Kingfisher nicht hinein: Das ist ein Fehler mit Grund, kein „verbunden und leer“.
        ohne = client.get('/api/v1/mail/stand').json()['accounts'][0]
        assert ohne['zustand'] == 'fehler' and 'Passwort fehlt' in ohne['satz']
    monkeypatch.setenv(config.integration_secret_name('mail', 'privat'), 'probe-passwort')
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='probe'))
    with TestClient(app) as client:
        assert client.get('/api/v1/mail/stand').json()['accounts'][0]['zustand'] == 'nicht_abgerufen'
        merke_gelesen(app, {'privat': 0})
        stand = client.get('/api/v1/mail/stand').json()['accounts'][0]
        assert stand['zustand'] == 'leer' and stand['satz'].startswith('Postfach Privat ist verbunden und leer')
        assert client.get('/api/v1/schedule').json()['mail_stand'][0]['satz'] == stand['satz']
        Intake(app.state.episodes).start('privat', ['INBOX'])
        app.state.settings.schedule.enabled = True
        app.state.settings.schedule.mail_accounts = ['privat']
        einlesen = client.get('/api/v1/mail/intake').json()['accounts'][0]['stand']
        assert einlesen == {k: v for k, v in client.get('/api/v1/mail/stand').json()['accounts'][0].items()
                            if k not in ('account_id', 'label')}
        assert client.get('/api/v1/schedule').json()['mail_stand'][0]['satz'] == einlesen['satz']


# -- Befunde 19, 20, 21: Kreis in jeder Akte, Geburtstag im Kalender und in der Akte, Kontakte nur mit Beteiligung ----

ANNA = 'person:n:anna berg'
GEBURTSTAG = 'Anna Berg hat am 12. Oktober Geburtstag.'


@pytest.fixture()
def app_mit_gespraech(tmp_path, monkeypatch, berlin):
    """Ein Sidecar, in dem der Nutzer im Gespräch über Anna Berg spricht (sie schreibt nie selbst)."""
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'daten'))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='probe'))
    with TestClient(app) as client:
        quelle, _ = app.state.episodes.record(
            EpisodeKind.MESSAGE, 'Gespräch', f'Merke dir: {GEBURTSTAG}',
            Provenance(source_type=SourceType.CHAT, source_ref='conversation:c1:message:m1'),
            occurred_at=JETZT, participants=['Anna Berg'])
        yield app, client, quelle


def _geburtstag_bestaetigen(app, quelle, *, annehmen=True, wert='12. Oktober'):
    from icarus_memory.graph import person_id_fuer
    from icarus_memory.proposals import Evidence
    vorschlag, _ = app.state.knowledge_service.propose(
        subject_ref=person_id_fuer('n:anna berg'), predicate='geburtstag', value=wert, statement=GEBURTSTAG,
        evidence=[Evidence(quelle.id, f'Merke dir: {GEBURTSTAG}', quelle.digest)], rationale='Probe')
    if annehmen:
        app.state.knowledge_service.accept(vorschlag.id, supersedes=[])
    return vorschlag


def test_kreis_karte_auch_ohne_adresse_und_ohne_vorschlag(app_mit_gespraech):
    app, client, _ = app_mit_gespraech
    stand = client.get('/api/v1/kreis', params={'sache': ANNA}).json()
    assert stand['bestaetigt'] is False and stand['ohne_vorschlag'] is True
    assert [w['kreis'] for w in stand['wahlen']] == ['innerer_kreis', 'kollegen', 'kontakte']
    # Lesen schreibt nichts; erst der Klick legt den Kreis fest, danach kein „würde anders vorschlagen“.
    assert client.get('/api/v1/kreis/uebersicht').json()['bestaetigt'] == 0
    fest = client.put('/api/v1/kreis', json={'sache': ANNA, 'kreis': 'innerer_kreis'}).json()
    assert fest['bestaetigt'] is True and fest['kreis'] == 'innerer_kreis' and fest['neuer_vorschlag'] is False


def test_geburtstag_nur_nach_bestaetigung_in_akte_kalender_und_briefing(app_mit_gespraech):
    from icarus_memory import wiederkehrendes
    from icarus_memory.akten_routes import bausteine
    app, client, quelle = app_mit_gespraech
    _geburtstag_bestaetigen(app, quelle, annehmen=False)
    # Ein offener Vorschlag ist kein Fakt: nirgends ein Geburtstag.
    assert client.get('/api/v1/geburtstag', params={'sache': ANNA}).json() == {'geburtstag': None}
    assert not [e for e in client.get('/api/v1/calendar', params={'year_view': True}).json()['items']
                if e.get('art') == 'geburtstag']
    _geburtstag_bestaetigen(app, quelle)
    akte = client.get('/api/v1/geburtstag', params={'sache': ANNA}).json()['geburtstag']
    assert akte['wert'] == '10-12' and akte['text'].startswith('Geburtstag am 12. Oktober, ')
    kalender = client.get('/api/v1/calendar', params={'year_view': True}).json()
    eintraege = [e for e in kalender['items'] if e.get('art') == 'geburtstag']
    assert kalender['configured'] is False, 'kein fremder Kalender: der Eintrag steht nur in Kingfisher'
    assert [(e['summary'], e['start'][:10], e['all_day']) for e in eintraege] == \
        [('Geburtstag: Anna Berg', f'{datetime.now().year}-10-12', True)]
    assert 'nur in Kingfisher' in eintraege[0]['source_label']
    # Jedes Jahr wieder.
    naechstes = wiederkehrendes.kalender_eintraege(app.state.claims, date(2027, 1, 1), date(2028, 1, 1))
    assert [e['start'][:10] for e in naechstes] == ['2027-10-12']
    # Briefing: am Vortag und am Tag, aber nur mit bestätigtem innerem Kreis.
    bezuege, _ = bausteine(app)
    vortag = datetime(2026, 10, 11, 8, 0, tzinfo=timezone.utc)
    assert wiederkehrendes.im_briefing(app.state.episodes, app.state.claims, bezuege.beschriftungen, vortag) == []
    client.put('/api/v1/kreis', json={'sache': ANNA, 'kreis': 'innerer_kreis'})
    morgen = wiederkehrendes.im_briefing(app.state.episodes, app.state.claims, bezuege.beschriftungen, vortag)
    assert [(g['sache'], g['wann']) for g in morgen] == [(ANNA, 'morgen')]
    am_tag = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)
    assert [g['wann'] for g in wiederkehrendes.im_briefing(app.state.episodes, app.state.claims,
                                                           bezuege.beschriftungen, am_tag)] == ['heute']
    zwei_tage = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)
    assert wiederkehrendes.im_briefing(app.state.episodes, app.state.claims, bezuege.beschriftungen, zwei_tage) == []
    client.put('/api/v1/kreis', json={'sache': ANNA, 'kreis': 'kollegen'})
    assert wiederkehrendes.im_briefing(app.state.episodes, app.state.claims, bezuege.beschriftungen, vortag) == []


def test_geburtstag_wert_aus_wert_oder_satz():
    from types import SimpleNamespace
    from icarus_memory.wiederkehrendes import geburtstag_wert
    aussage = lambda praedikat, wert, satz='': SimpleNamespace(predicate=praedikat, value=wert, statement=satz)  # noqa: E731
    assert geburtstag_wert(aussage('geburtstag', '10-12')) == '10-12'
    assert geburtstag_wert(aussage('geburtstag', '12. Oktober')) == '10-12'
    assert geburtstag_wert(aussage('birthday', '', 'Sie hat am 3.10. Geburtstag.')) == '10-03'
    assert geburtstag_wert(aussage('wohnort', '12. Oktober')) is None
    assert geburtstag_wert(aussage('geburtstag', 'irgendwann')) is None


def test_letzter_kontakt_zaehlt_kein_gespraech_ueber_die_person(app_mit_gespraech):
    from icarus_memory import personen
    app, client, _ = app_mit_gespraech
    anna = next(p for p in personen.alle(episodes=app.state.episodes, jetzt=JETZT) if p.name == 'Anna Berg')
    assert (anna.episoden_anzahl, anna.kontakte, anna.letzter_kontakt, anna.kontakt_text) == (1, 0, None, '')
    # Schreibt sie selbst eine Mail, ist das ein Kontakt.
    app.state.episodes.record(EpisodeKind.MESSAGE, 'Abstimmung', 'Hallo Lena, anbei der Stand.',
                              Provenance(source_type=SourceType.EMAIL, source_ref='imap:a:INBOX:3'),
                              occurred_at=JETZT, participants=['Anna Berg <anna.berg@example.org>'])
    anna = next(p for p in personen.alle(episodes=app.state.episodes, jetzt=JETZT) if p.adressen == ['anna.berg@example.org'])
    assert anna.kontakte == 1 and anna.letzter_kontakt is not None


# -- Befunde 27 bis 29: „Für Techniker“ ohne Widerspruch ------------------------------------------------------------

def test_geraeteprofil_nimmt_ohne_helfer_die_eigene_messung():
    from icarus_memory.device_profile import _profile, mit_eigener_messung
    ohne = _profile(None)
    assert ohne['source'] == 'unknown'
    gemessen = mit_eigener_messung(ohne, {'memory_gb': 15.7, 'platform': 'linux', 'untergrenze': False})
    assert (gemessen['source'], gemessen['memory_gb']) == ('eigene', 15.7)
    assert 'noch nicht gemeldet' not in gemessen['guidance']['note']
    assert mit_eigener_messung(ohne, {'memory_gb': 7.6, 'platform': 'unknown', 'untergrenze': True})['source'] == 'untergrenze'
    # Ein Bericht des Helfers bleibt, wie er ist; ohne Messung bleibt „unbekannt“ ehrlich.
    bericht = {**ohne, 'source': 'host_report', 'memory_gb': 32.0}
    assert mit_eigener_messung(bericht, {'memory_gb': 15.7}) is bericht
    assert mit_eigener_messung(ohne, {}) is ohne


def test_verdichtung_mit_fehler_sagt_nie_nichts_zu_tun():
    from icarus_memory.consolidation import ConsolidationReport
    assert ConsolidationReport().summary() == 'Nichts zu tun.'
    fehler = ConsolidationReport(errors=['e-1: Zeitüberschreitung', 'e-2: Zeitüberschreitung']).summary()
    assert 'Nichts zu tun' not in fehler
    assert fehler == 'Fehler bei e-1: Zeitüberschreitung (und 1 weitere). Der nächste Lauf versucht es erneut.'
    mit = ConsolidationReport(episodes_seen=2, errors=['e-3: kaputt']).summary()
    assert mit.startswith('2 Episoden angesehen.') and 'Fehler bei e-3' in mit


def test_kostenwarnung_nur_mit_modell_ausserhalb_des_rechners(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory import server as server_modul
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'daten'))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='probe'))

    class Rollen:
        def __init__(self, anbieter):
            self.anbieter = anbieter

        def provider(self, rolle):
            return self.anbieter

    lokal = type('Lokal', (), {'is_local': True, 'model': 'qwen3.5:9b'})()
    fern = type('Fern', (), {'is_local': False, 'model': 'gpt-oss:120b-cloud'})()
    with TestClient(app) as client:
        plan = app.state.settings.schedule
        plan.with_model, plan.local_model_only = True, False
        monkeypatch.setattr(server_modul, 'rollen_von', lambda _app: Rollen(lokal))
        assert client.get('/api/v1/schedule').json()['kosten_modell'] is None
        monkeypatch.setattr(server_modul, 'rollen_von', lambda _app: Rollen(fern))
        assert client.get('/api/v1/schedule').json()['kosten_modell'] == 'gpt-oss:120b-cloud'
        plan.local_model_only = True
        assert client.get('/api/v1/schedule').json()['kosten_modell'] is None
        plan.local_model_only, plan.with_model = False, False
        assert client.get('/api/v1/schedule').json()['kosten_modell'] is None
