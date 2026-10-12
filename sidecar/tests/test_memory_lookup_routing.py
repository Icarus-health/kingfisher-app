"""An explicit local search stays evidence-bound while source processing is paused."""
import pytest

from icarus_memory.frage import Anfrage
from icarus_memory.memory_routing import route
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation, _upload

QUESTION = ('Welche Markierungsfarbe hat die Prüfschachtel KF-Moosprobe? '
            'Suche im Gedächtnis nach der Gedächtniskernprobe.')
BODY = ('Künstliche Gedächtniskernprobe. Die Prüfschachtel KF-Moosprobe hat die '
        'Markierungsfarbe Moosgrün. Keine echte Person, Aufgabe oder Termin.')
REQUEST = Anfrage(sachen=('Prüfschachtel KF-Moosprobe', 'Gedächtniskernprobe'),
                   absicht='fakt', suchworte=('Markierungsfarbe', 'KF-Moosprobe'), herkunft='modell')


@pytest.mark.parametrize('question', [
    QUESTION,
    'Suche im Gedächtnis nach KF-Moosprobe.',
    'Bitte suche im Gedächtnis nach KF-Moosprobe.',
    'Was steht zu KF-Moosprobe? Suche im Gedächtnis nach der Gedächtniskernprobe.',
    'Suche in meinem Gedächtnis nach KF-Moosprobe.',
    'Suche im Gedächtnis in meinen Quellen nach "KF-Moosprobe".',
])
@pytest.mark.parametrize('available', [False, True])
def test_explicit_read_only_memory_lookup_keeps_evidence_contract(question, available):
    assert route(question, working_available=available, anfrage=REQUEST) == 'memory_evidence'


@pytest.mark.parametrize('question', [
    'Suche im Gedächtnis nach KF-Moosprobe. Sende Mira die Antwort.',
    'Suche im Gedächtnis in meinen Quellen nach "KF-Moosprobe". Sende Mira die Antwort.',
    'Suche im Gedächtnis in meinen Quellen nach "KF-Moosprobe" und im Internet nach aktuellen Nachrichten.',
    'Suche im Gedächtnis nach KF-Moosprobe und lösche die Quelle.',
    'Suche im Gedächtnis nach KF-Moosprobe und ändere die Markierungsfarbe auf Rot.',
    'Suche im Gedächtnis nach KF-Moosprobe und aktualisiere die Quelle.',
    'Suche im Gedächtnis nach KF-Moosprobe, ändere die Markierungsfarbe auf Rot.',
    'Suche im Gedächtnis nach KF-Moosprobe: aktualisiere die Quelle.',
    'Suche im Gedächtnis nach KF-Moosprobe, lade die Antwort auf GitHub hoch.',
    'Welche Markierungsfarbe hat KF-Moosprobe, ändere sie auf Rot? Suche im Gedächtnis nach KF-Moosprobe.',
    'Suche im Gedächtnis nach KF-Moosprobe und füge eine Aufgabe hinzu.',
    'Suche im Gedächtnis nach KF-Moosprobe. Lade die Antwort auf GitHub hoch.',
    'Ändere die Markierungsfarbe auf Rot. Suche im Gedächtnis nach KF-Moosprobe.',
    'Lade die Antwort auf GitHub hoch. Suche im Gedächtnis nach KF-Moosprobe.',
    'Kannst du die Quelle aktualisieren? Suche im Gedächtnis nach KF-Moosprobe.',
    'Kannst du eine Aufgabe hinzufügen? Suche im Gedächtnis nach KF-Moosprobe.',
    'Wie ändere ich die Markierungsfarbe? Suche im Gedächtnis nach KF-Moosprobe.',
    'Wie kann ich eine Aufgabe hinzufügen? Suche im Gedächtnis nach KF-Moosprobe.',
    'Suche im Gedächtnis nach KF-Moosprobe und speichere die Antwort.',
    'Suche im Gedächtnis nach KF-Moosprobe und buche einen Termin.',
    'Suche im Gedächtnis nach KF-Moosprobe. Suche im Internet nach aktuellen Nachrichten.',
    'Suche im Gedächtnis nach KF-Moosprobe und im Internet nach aktuellen Nachrichten.',
    'Suche nach aktuellen Nachrichten über Moos.',
    'Ich suche im Gedächtnis nach KF-Moosprobe.',
    'Suche nicht im Gedächtnis nach KF-Moosprobe.',
    'Suche im Gedächtnis nicht nach KF-Moosprobe.',
    'Ich möchte nicht, dass du im Gedächtnis nach KF-Moosprobe suchst.',
])
def test_actions_web_search_and_negative_or_narrated_search_keep_chat(question):
    assert route(question, working_available=True) == 'chat'


@pytest.mark.parametrize('question', [
    'Was ist die Hauptstadt von Frankreich?',
    'Wie funktioniert Photosynthese?',
])
def test_ordinary_world_questions_without_memory_match_keep_chat(question):
    assert route(question, working_available=False) == 'chat'


def test_authenticated_auto_lookup_does_not_show_free_chat_fact_during_pause(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    monkeypatch.setattr('icarus_memory.server._frage_verstehen', lambda app, text: REQUEST)
    monkeypatch.setattr(provider, 'complete', lambda *args, **kwargs: Reply(text='Die Markierungsfarbe ist Signalrot.'))
    try:
        assert client.post('/api/v1/hintergrund/pause').json()['pausiert'] is True
        source = _upload(client, BODY)
        store = WorkingMemoryStore(app.state.episodes)
        assert store.search(QUESTION, limit=1)['refs'] == []
        answer = _ask(client, _conversation(client), QUESTION)
        context = answer['metadata']['context']
        assert context.get('answer_mode') == 'memory_evidence'
        assert context['answer_contract']['status'] == 'unknown'
        assert 'mit den gefundenen Belegen nicht beantworten' in answer['content']
        assert 'Signalrot' not in answer['content']
        assert app.state.episodes.get(source).body == BODY
        assert store.search(QUESTION, limit=1)['refs'] == []
        assert client.get('/api/v1/hintergrund').json()['pausiert'] is True
    finally:
        client.close()
        _close_app(app)
