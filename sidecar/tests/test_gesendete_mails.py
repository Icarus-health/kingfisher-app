"""Gesendete Mails einlesen: eigene Zusagen kommen ins Gedächtnis (Paket B1, Oktober 2026).

Ein Stabschef kennt die eigenen Zusagen. Bei IMAP-Konten las Kingfisher bisher nur den Posteingang; Gmail
(Gesamtbestand) und Microsoft 365 (SentItems) hatten Gesendet schon. Hier läuft der echte Weg über die API gegen die
IMAP-Attrappe mit Posteingang und Gesendet-Ordner. Alle Mails sind synthetisch (Lena Probe, Anna Berg).

Zusicherungen:
1. Posteingang und Gesendet werden erkannt, beschrieben und eingelesen; die eigene Mail trägt „von mir“.
2. Eine gesendete Mail „Ich schicke dir die Unterlagen bis Freitag“ ergibt eine eigene Zusage (`own_commitment`,
   Modellattrappe) und steht unter „Was habe ich zugesagt?“ (ohne Modell, aus den Akten).
3. Ein Konto von vor dem Umbau (nur Posteingang) holt Gesendet über „Gesendete Mails auch einlesen“ nach; der Stand
   sagt währenddessen „Gesendete Mails werden nachgelesen“, nicht „wird durchgesehen“ fürs ganze Postfach.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import RLock

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from tests.imap_attrappe import PASSWORT, ImapAttrappe, probe_mail, probe_postfach

ADRESSE = 'lena.probe@example.org'
ZUSAGE = 'Ich schicke dir die Unterlagen bis Freitag.'


def gesendete_mails() -> list[bytes]:
    return [probe_mail(f'Lena Probe <{ADRESSE}>', 'Unterlagen', f'Hallo Anna,\n\n{ZUSAGE}\n\nLena',
                       an='Anna Berg <anna.berg@example.org>', minuten=50)]


@pytest.fixture
def postfach(monkeypatch):
    with ImapAttrappe(nachrichten=probe_postfach(), gesendet=gesendete_mails(), uidvalidity=7) as dienst:
        monkeypatch.setenv('SSL_CERT_FILE', str(dienst.zertifikat))
        yield dienst


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(
        SelfModelStore(MemoryBackend(), subject_id='test'),
        audit=AuditLog(tmp_path / 'audit.sqlite3'), tasks=TaskStore(tmp_path / 'tasks.sqlite3'),
        workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'), episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'),
    )
    with TestClient(app) as c:
        yield c
        app.state.scheduler.stop()


def verbinden(client, postfach) -> str:
    antwort = client.post('/api/v1/integrations/mail', json={
        'label': 'Probe-Post', 'imap_host': '127.0.0.1', 'imap_port': postfach.port, 'user': ADRESSE,
        'sender': ADRESSE, 'password': PASSWORT})
    assert antwort.status_code == 201, antwort.text
    return client.get('/api/v1/integrations').json()['mail_accounts'][0]['id']


def takte(client, anzahl: int = 4) -> None:
    client.app.state.scheduler.stop()
    for _ in range(anzahl):
        client.app.state.scheduler._run_mail_intake()


def quellen(client) -> dict[str, object]:
    return {e['title']: e for e in client.get('/episodes', params={'limit': 50}).json()}


def eigene_quelle(client):
    episodes = client.app.state.episodes
    with episodes._lock:
        ids = [i for (i,) in episodes._conn.execute(
            "SELECT episode_id FROM mail_intake_items WHERE folder='Gesendet' AND status='captured'")]
    assert len(ids) == 1, ids
    return episodes.get(ids[0])


def test_posteingang_und_gesendet_werden_erkannt_und_eingelesen(client, postfach):
    konto = verbinden(client, postfach)
    umfang = client.get(f'/api/v1/mail/intake/{konto}/preview').json()
    assert umfang['folders'] == ['INBOX', 'Gesendet']
    assert umfang['description'] == 'Posteingang und Gesendet; ohne Spam und Papierkorb.'
    assert client.post(f'/api/v1/mail/intake/{konto}/start', json={'folders': umfang['folders']}).status_code == 200
    takte(client)
    titel = quellen(client)
    assert 'Unterlagen' in titel and 'Treffen am Montag' in titel, sorted(titel)
    stand = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)
    assert stand['umfang'] == 'Posteingang und Gesendet; ohne Spam und Papierkorb.' and stand['gesendet_dabei'] is True
    ordner = {f['folder']: f for f in stand['folders']}
    assert ordner['Gesendet']['captured'] == 1 and ordner['Gesendet']['failed'] == 0
    assert ordner['INBOX']['captured'] == 4 and ordner['INBOX']['filtered'] == 1  # der Gartenbrief bleibt draußen
    quelle = eigene_quelle(client)
    von = next(k for k in quelle.contacts if k['rolle'] == 'von')
    assert von['ich'] is True and von['adresse'] == ADRESSE
    assert any(k['rolle'] == 'an' and k['adresse'] == 'anna.berg@example.org' for k in quelle.contacts)
    assert client.get('/api/v1/mail/stand').json()['accounts'][0]['zustand'] == 'aktuell'


class Pruefmodell:
    """Lokales Skriptmodell: findet die Zusage und bestätigt sie nur als eigene, wenn die Quelle als eigene gilt."""
    is_local = True
    name = 'test'
    model = 'local'

    def __init__(self):
        self.own_source = []

    def complete(self, messages, tools):
        payload = json.loads(messages[1]['content'])
        if 'candidates' in payload:
            self.own_source.append(payload['own_source'])
            return Reply(text=json.dumps({'reviews': [{'id': 0, 'kind': 'own_commitment', 'title_supported': True}]}))
        if ZUSAGE in payload.get('body', ''):
            return Reply(text=json.dumps({'items': [{'title': 'Unterlagen an Anna schicken', 'quote': ZUSAGE}]}))
        return Reply(text=json.dumps({'items': []}))


def test_gesendete_zusage_wird_eigene_zusage_und_steht_unter_was_habe_ich_zugesagt(client, postfach):
    from icarus_memory.proposals import ProposalKind
    from icarus_memory.task_detection import TaskDetector
    from icarus_memory.working_memory_store import WorkingMemoryStore
    konto = verbinden(client, postfach)
    assert client.post(f'/api/v1/mail/intake/{konto}/start', json={'folders': ['INBOX', 'Gesendet']}).status_code == 200
    takte(client)
    app = client.app
    quelle = eigene_quelle(client)

    # Zusagen: Die Modellattrappe sieht die Quelle als eigene (own_source) und bestätigt die eigene Zusage.
    modell = Pruefmodell()
    detector = TaskDetector(app.state.episodes, app.state.proposals, modell, RLock())
    bericht = detector.run(with_model=True)
    assert bericht.failed == 0 and bericht.proposed >= 1
    assert True in modell.own_source
    vorschlaege = [p for p in app.state.proposals.pending(ProposalKind.TASK) if p.evidence[0].episode_id == quelle.id]
    assert len(vorschlaege) == 1 and vorschlaege[0].evidence[0].quote == ZUSAGE
    assert vorschlaege[0].proposed_by.endswith('task-review-v1'), 'als eigene Zusage bestätigt, nicht nur gefunden'

    # „Was habe ich zugesagt?“ aus den Akten, ohne Modell: Die Textstelle ist als Zusage markiert (wie die
    # Verdichtung sie vorschlägt), die Akte rechnet die Richtung aus dem eigenen Absender.
    store = WorkingMemoryStore(app.state.episodes)
    offen = store.pending(episode_ids=[quelle.id])[0]
    start = quelle.body.index(ZUSAGE)
    assert store.commit(offen, [{'start': start, 'end': start + len(ZUSAGE), 'kind': 'commitment'}], model='local-test')
    assert client.post('/api/v1/akten/aktualisieren').status_code == 200
    gespraech = client.post('/api/v1/conversations', json={}).json()['conversation']['id']
    antwort = client.post(f'/api/v1/conversations/{gespraech}/messages', json={'message': 'Was habe ich zugesagt?'})
    assert antwort.status_code == 201, antwort.text
    text = antwort.json()['messages'][-1]['content']
    assert text.startswith('Du hast vermutlich noch eine Zusage offen'), text
    assert 'Deine Zusage' in text and ZUSAGE in text, text
    assert antwort.json()['messages'][-1]['metadata']['context']['answer_contract']['model_called'] is False


def test_altes_konto_liest_gesendet_nach_und_der_stand_sagt_es(client, postfach):
    konto = verbinden(client, postfach)
    app = client.app
    # Ein Konto von vor dem Umbau: gestartet mit nur dem Posteingang, der ist schon fertig gelesen.
    Intake(app.state.episodes).start(konto, ['INBOX'])
    app.state.settings.schedule.mail_accounts.append(konto)
    app.state.settings.schedule.enabled = True
    takte(client)
    stand = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)
    assert stand['folders'][0]['inventory_complete'] and stand['gesendet_dabei'] is False
    assert stand['umfang'] == 'Nur der Posteingang; gesendete und archivierte Mails sind bei diesem Konto nicht dabei.'
    assert stand['stand']['zustand'] == 'aktuell'

    antwort = client.post(f'/api/v1/mail/intake/{konto}/ordner-ergaenzen')
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()['satz'] == 'Gesendete Mails werden jetzt mit eingelesen.'
    konto_stand = antwort.json()['accounts'][0]
    assert konto_stand['gesendet_dabei'] is True and konto_stand['umfang'] == 'Posteingang und Gesendet; ohne Spam und Papierkorb.'
    # Der Posteingang war fertig: Der Stand fällt nicht auf „wird durchgesehen“ fürs ganze Postfach zurück.
    assert konto_stand['stand']['zustand'] == 'liest'
    assert konto_stand['stand']['satz'] == ('Postfach Probe-Post: Der Posteingang ist gelesen (5 Mails). '
                                            'Gesendete Mails werden nachgelesen: bisher keine gefunden.')
    takte(client)
    assert 'Unterlagen' in quellen(client)
    stand = client.get('/api/v1/mail/stand').json()['accounts'][0]
    assert stand['zustand'] == 'aktuell' and stand['satz'].startswith('Postfach Probe-Post ist gelesen: 6 Mails')
    # Noch einmal: nichts Neues, kein doppelter Ordner.
    assert client.post(f'/api/v1/mail/intake/{konto}/ordner-ergaenzen').json()['satz'] == 'Gesendete Mails sind schon dabei.'


def test_mail_an_sich_selbst_erscheint_in_beiden_ordnern(client, postfach):
    """Bewusste Grenze (wie bei Microsoft): Message-ID wird nicht ordnerübergreifend verglichen; eine Mail an sich
    selbst liegt im Posteingang und in Gesendet und wird zweimal zur Quelle. Dokumentiert in docs/14."""
    an_mich = probe_mail(f'Lena Probe <{ADRESSE}>', 'Notiz an mich', 'Steuer bis 31. Oktober.', an=ADRESSE, minuten=60)
    postfach.nachrichten.append(an_mich)
    postfach.gesendet.append(an_mich)
    konto = verbinden(client, postfach)
    assert client.post(f'/api/v1/mail/intake/{konto}/start', json={'folders': ['INBOX', 'Gesendet']}).status_code == 200
    takte(client, 6)
    episodes = client.app.state.episodes
    with episodes._lock:
        zeilen = episodes._conn.execute(
            "SELECT i.folder, i.status FROM mail_intake_items i JOIN episodes e ON e.id=i.episode_id "
            "WHERE e.title='Notiz an mich' ORDER BY i.folder").fetchall()
    assert [tuple(z) for z in zeilen] == [('Gesendet', 'captured'), ('INBOX', 'captured')]


def test_stand_satz_beim_nachlesen_von_gesendet(monkeypatch):
    from icarus_memory.mail_stand import konto_stand
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')
    jetzt = datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc)
    posteingang = {'folder': 'INBOX', 'inventory_complete': True, 'total': 4300, 'captured': 4200, 'duplicates': 0, 'filtered': 100}
    gesendet = {'folder': 'Gesendet', 'inventory_complete': False, 'total': None, 'captured': 12, 'duplicates': 0}
    intake = {'started': True, 'paused': False, 'error': None, 'folders': [posteingang, gesendet], 'aktualisiert': jetzt.timestamp()}
    stand = konto_stand('Privat', intake=intake, jetzt=jetzt)
    assert stand['zustand'] == 'liest' and stand['gelesen'] == 4312
    assert stand['satz'] == 'Postfach Privat: Der Posteingang ist gelesen (4.300 Mails). Gesendete Mails werden nachgelesen: bisher 12 gefunden.'
    # Ist der Posteingang selbst noch nicht fertig, bleibt es beim bisherigen Satz übers ganze Postfach.
    intake['folders'] = [{**posteingang, 'inventory_complete': False, 'total': None}, gesendet]
    assert konto_stand('Privat', intake=intake, jetzt=jetzt)['satz'] == 'Postfach Privat wird durchgesehen: bisher 4.312 Mails gefunden.'
    # Microsoft: SentItems zählt als Gesendet.
    intake['folders'] = [posteingang, {**gesendet, 'folder': 'SentItems', 'captured': 1}]
    assert konto_stand('Privat', intake=intake, jetzt=jetzt)['satz'].endswith('Gesendete Mails werden nachgelesen: bisher eine gefunden.')
