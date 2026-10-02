"""Erkannte Aufgaben aus Mails stehen im Briefing — als Frage, nicht als Aufgabe."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from icarus_memory import MemoryBackend, SelfModelStore, briefing
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalKind
from icarus_memory.server import create_app
from tests.test_briefing import JETZT, aufgabe, leer

BODY = 'Hallo, bitte sende mir die Orion-Rechnung bis Freitag. Danke, Anna'


def _vorschlag(**felder):
    return {'id': 'v-1', 'statement': 'Orion-Rechnung an Anna senden', 'quote': BODY,
            'episode_id': 'e-1', 'sender': 'Anna Keller',
            'received_at': datetime(2026, 8, 17, 9, tzinfo=timezone.utc).isoformat(), **felder}


def test_candidate_is_asked_with_sender_and_date():
    daten = leer()
    daten['task_candidates'] = {'pending': 3, 'items': [_vorschlag()]}
    b = briefing.erstelle(daten, jetzt=JETZT)
    [punkt] = b.punkte
    assert punkt.quelle == 'zusage' and punkt.ref == 'v-1'
    assert punkt.aktion == 'Als Aufgabe übernehmen'
    assert punkt.text == ('Aus einer Mail von Anna Keller vom 17. August: „Orion-Rechnung an Anna senden“. '
                          'Als Aufgabe übernehmen? 2 weitere Vorschläge warten auf Prüfung.')
    # Der fremde Wortlaut steht nicht im Briefing, nur der Vorschlag.
    assert 'Freitag' not in punkt.text


def test_candidate_without_sender_or_more_items():
    daten = leer()
    daten['task_candidates'] = {'pending': 1, 'items': [_vorschlag(sender=None, received_at=None)]}
    [punkt] = briefing.erstelle(daten, jetzt=JETZT).punkte
    assert punkt.text == 'Aus einer Quelle: „Orion-Rechnung an Anna senden“. Als Aufgabe übernehmen?'


def test_overdue_work_comes_before_a_suggestion():
    daten = leer()
    daten['tasks']['items'] = [aufgabe('Steuer', JETZT - timedelta(days=2), ueberfaellig=True)]
    daten['task_candidates'] = {'pending': 1, 'items': [_vorschlag()]}
    punkte = briefing.erstelle(daten, jetzt=JETZT).punkte
    assert [p.quelle for p in punkte] == ['aufgabe', 'zusage']


def test_someone_waiting_on_you_outranks_old_knowledge_and_mail():
    """Eine Bitte von jemandem wiegt mehr als eine alte Angabe oder ungelesene Post."""
    daten = leer()
    daten['tasks']['items'] = [aufgabe('Steuer', JETZT - timedelta(days=2), ueberfaellig=True)]
    daten['mail']['unread'] = 4
    daten['task_candidates'] = {'pending': 1, 'items': [_vorschlag()]}
    vorschlaege = [{'id': 'p-1', 'kind': 'confirmation', 'statement': 'Ich wohne in Mainz.'}]
    punkte = briefing.erstelle(daten, jetzt=JETZT, vorschlaege=vorschlaege).punkte
    assert [p.quelle for p in punkte] == ['aufgabe', 'zusage', 'bestaetigung']


def test_no_candidates_no_sentence():
    daten = leer()
    daten['task_candidates'] = {'pending': 0, 'items': []}
    assert briefing.erstelle(daten, jetzt=JETZT).punkte == []


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Rechnung', BODY, Provenance(source_type=SourceType.EMAIL),
        participants=['Anna Keller <anna@example.test>'],
        occurred_at=datetime(2026, 9, 22, 9, tzinfo=timezone.utc))
    app.state.proposals.record_task_analysis(episode.id, episode.digest,
        [{'title': 'Orion-Rechnung an Anna senden', 'quote': 'bitte sende mir die Orion-Rechnung'}],
        proposed_by='test/local')
    client = TestClient(app)
    yield app, client, episode, app.state.proposals.pending(ProposalKind.TASK)[0]
    client.close()
    app.state.scheduler.stop()


def _zusagen(client):
    response = client.get('/api/v1/morning-briefing')
    assert response.status_code == 200
    return [item for item in response.json()['needs_you'] if item['source'] == 'zusage']


def test_morning_briefing_offers_candidate_and_forgets_it_after_acceptance(env):
    app, client, episode, candidate = env
    [item] = _zusagen(client)
    assert item['title'] == 'Orion-Rechnung an Anna senden'
    assert item['detail'] == 'Vorschlag aus einer Mail von Anna Keller · 22.9.'
    assert item['source_ref'] == candidate.id and item['episode_id'] == episode.id
    assert item['action'] == 'Als Aufgabe übernehmen'
    # Ansehen legt nichts an.
    assert app.state.tasks.all_tasks() == []

    response = client.post(f'/api/v1/task-candidates/{candidate.id}/accept',
                           json={'title': item['title']})
    assert response.status_code == 200
    assert response.json()['provenance']['source_ref'] == f'episode:{episode.id}'
    assert _zusagen(client) == []


def test_ignored_source_takes_the_candidate_out_of_the_briefing(env):
    app, client, episode, _ = env
    app.state.episodes.ignore(episode.id)
    assert _zusagen(client) == []
    assert client.get('/dashboard').json()['task_candidates']['pending'] == 0
