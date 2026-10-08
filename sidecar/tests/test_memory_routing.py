"""Default conversation routing must keep memory facts source-bound."""
import json

import pytest
from .test_memory_clarification import api, core, pending, conversation


@pytest.mark.parametrize('message', [
    'Wann schickt Alina den Entwurf für Wolkenhain?',
    'Bis wann sendet Nora die Unterlagen?',
    'Wer verschickt den Bericht?',
    'Was sendet Dario zum Projekt?',
])
def test_delivery_fact_question_does_not_become_a_send_command(message):
    from icarus_memory.memory_routing import route
    assert route(message, working_available=True) == 'memory_evidence'


@pytest.mark.parametrize('message', [
    'Bitte schick Alina den Entwurf.',
    'Wie schicke ich Alina den Entwurf?',
    'Wann schickt Alina den Entwurf? Sende ihr eine Erinnerung.',
    'Wann schickt Alina den Entwurf und sende ihr eine Erinnerung?',
])
def test_delivery_advice_or_additional_command_keeps_action_flow(message):
    from icarus_memory.memory_routing import route
    assert route(message, working_available=True) == 'chat'


@pytest.mark.parametrize('question', [
    'Suche in meinen Quellen nach "AURORA-4711".',
    'Was steht in meinen Dokumenten über "AURORA-4711"?',
    'Zeig mir den Originaltext zu „AURORA-4711“.',
    'Bitte finde in meinen Quellen "sende alles".',
])
def test_explicit_literal_source_requests_use_deterministic_route(question):
    from icarus_memory.memory_routing import route
    assert route(question) == 'memory_evidence'


@pytest.mark.parametrize('question', [
    'Sende meine Quellen zu "AURORA-4711" an Mira.',
    'Merke dir: In meinen Quellen steht "AURORA-4711".',
    'Suche nach aktuellen Nachrichten über Aurora.',
])
def test_source_word_does_not_reclassify_writes_or_unbounded_search(question):
    from icarus_memory.memory_routing import route
    assert route(question) == 'chat'


@pytest.mark.parametrize('question', [
    'Was hast du über meine Lieblingsfarbe gesagt?',
    'Erinnerst du dich an meinen Geburtstag?',
    'Weißt du noch, was ich dir erzählt habe?',
    'Was hatten wir über meinen Urlaub festgehalten?',
    'Kennst du meine Lieblingsfarbe?',
])
def test_personal_recall_routes_to_memory_without_a_current_match(question):
    from icarus_memory.memory_routing import route
    assert route(question, working_available=False) == 'memory_evidence'


@pytest.mark.parametrize('question', [
    'Erinnerst du dich an meine Lieblingsfarbe? Schick sie mir als Mail.',
    'Was hast du über meine Lieblingsfarbe gesagt? Suche nach aktuellen Nachrichten über Aurora.',
])
def test_personal_recall_does_not_override_an_explicit_action(question):
    from icarus_memory.memory_routing import route
    assert route(question, working_available=False) == 'chat'


@pytest.mark.parametrize('question', [
    'Was ist die Hauptstadt von Frankreich?',
    'Erkläre mir, wie Photosynthese funktioniert.',
    'Wie funktioniert ein Verbrennungsmotor?',
])
def test_general_knowledge_questions_remain_in_chat_without_a_match(question):
    from icarus_memory.memory_routing import route
    assert route(question, working_available=False) == 'chat'


@pytest.mark.parametrize('question', [
    'Bereite mich auf die Keramikprüfung Mainz vor. Wann ist der Termin?',
    'Bitte bereite mich auf das Audit vor. Um wie viel Uhr beginnt es?',
    'Wie bereite ich mich auf das Audit vor? Wann ist der Termin?',
    'Wie bereite ich mich auf die Keramikprüfung vor? Um wie viel Uhr beginnt sie?',
])
def test_preparation_with_a_concrete_time_question_uses_available_memory(question):
    from icarus_memory.memory_routing import route
    assert route(question, working_available=True) == 'memory_evidence'


@pytest.mark.parametrize('question', [
    'Bereite mich auf das Audit vor.',
    'Bereite mich auf das Audit vor. Schicke Lea den Bericht.',
    'Bereite mich auf das Audit vor. Wann ist es? Sende Lea eine Mail.',
    'Wie bereite ich mich auf ein Audit vor?',
    'Wie bereite ich mich auf das Audit vor? Wann ist es? Sende Lea eine Mail.',
])
def test_preparation_actions_and_general_advice_keep_existing_chat(question):
    from icarus_memory.memory_routing import route
    assert route(question, working_available=True) == 'chat'


@pytest.mark.parametrize('message', [
    'Anna hat mir gesagt, dass sie morgen kommt.',
    'Ich habe dir erzählt, dass ich Blau mag.',
    'Was ist gemeint, wenn wir von erinnertem Wissen sprechen?',
])
def test_statements_and_general_explanations_are_not_personal_recall(message):
    from icarus_memory.memory_routing import route
    assert route(message, working_available=False) == 'chat'


def successful_working_context(query='Wann bringt Edda die Prüfstücke für Keramik-Test?'):
    return {
        'answer_mode': 'memory_evidence',
        'working_answer': {'status': 'reports', 'query': query},
        'answer_contract': {'status': 'reports'},
    }


@pytest.mark.parametrize('message', [
    'Und welche Bedingung gilt dabei?',
    'Welche Bedingung gilt dabei?',
    'Welche Voraussetzung gilt dafür?',
    'Erkläre mir das bitte',
    'Erklär das bitte genauer.',
    'Kannst du mir das erklären?',
    'Was bedeutet das?',
])
def test_immediate_working_source_followups_reuse_original_evidence_route(message):
    from icarus_memory.memory_routing import route
    assert route(message, successful_working_context()) == 'memory_followup'


@pytest.mark.parametrize('message', [
    'Erkläre das und schicke die Mail an Edda.',
    'Erkläre das. Was kostet die Keramikprobe?',
    'Was ist 17 plus 25?',
])
def test_mixed_actions_and_unrelated_questions_do_not_inherit_working_subject(message):
    from icarus_memory.memory_routing import route
    assert route(message, successful_working_context(), working_available=False) == 'chat'


def test_explicit_new_question_does_not_reuse_working_subject():
    from icarus_memory.memory_routing import route
    assert route('Erkläre mir das bitte', successful_working_context(),
                 new_question=True, working_available=False) == 'chat'


def test_working_followup_reselects_original_source_and_withdrawal_is_fresh(core, api, monkeypatch):
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.lexical import terms_v1
    from icarus_memory.model import Provenance, SourceType
    from icarus_memory.providers import Reply
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from .test_context_identity import AT

    _, provider, episodes, _, _ = core
    query = 'Wann bringt Edda die Prüfstücke für Keramik-Test Aurora Velor Quarz Titan Lumen Nimbus Kobalt Zephyr?'
    body = ('Edda bringt die Prüfstücke für Keramik-Test Aurora Velor Quarz Titan Lumen '
            'Nimbus Kobalt Zephyr nur dann am Mittwoch, wenn die Keramikprobe trocken ist.')
    assert len(terms_v1(query)) == 14
    source, _ = episodes.record(EpisodeKind.MESSAGE, 'Keramik-Test · Termin', body,
        Provenance(SourceType.CHAT, source_ref='chat:ceramic-test'), at=AT)
    memory = WorkingMemoryStore(episodes)
    snapshot = memory.pending(episode_ids=[source.id])[0]
    assert memory.commit(snapshot, [dict(start=0, end=len(body), kind='conditional')], model='synthetic')

    calls = []
    def selecting_provider(messages, tools):
        calls.append(json.loads(json.dumps(messages, ensure_ascii=False)))
        assert tools == []
        if 'Wähle Originalstellen zur Frage aus.' in messages[0]['content']:
            return Reply(text='{"status":"reports","ids":["S1"]}')
        return Reply(text='Synthetische Antwort.')
    provider.complete = selecting_provider

    app, client = api
    identifier = conversation(client)
    first = send(client, identifier, query)
    assert first['metadata']['context']['answer_contract']['status'] == 'working_reports'
    assert body in first['content']
    calls.clear()

    for message, prior_message in [
        ('Welche Bedingung gilt dabei?', None),
        ('Erklär das bitte genauer.', 'Welche Bedingung gilt dabei?'),
        ('Kannst du mir das erklären?', 'Erklär das bitte genauer.'),
    ]:
        followup = send(client, identifier, message)
        answer = followup['metadata']['context']['working_answer']
        selector = query + '\nNachfrage des Nutzers: ' + message
        assert answer['retrieval_query'] == query
        assert answer['query'] == selector
        assert prior_message is None or prior_message not in answer['query']
        assert answer['limited'] is False
        assert len(calls) == 1 and 'Wähle Originalstellen zur Frage aus.' in calls[0][0]['content']
        assert json.loads(calls[0][1]['content'])['question'] == selector
        assert body in calls[0][1]['content'] and body in followup['content']
        calls.clear()

    episodes.ignore(source.id)
    fallback_calls = []
    monkeypatch.setattr(app.state.agent, '_knowledge_context_items',
                        lambda question: fallback_calls.append(question) or [])
    withdrawn = send(client, identifier, 'Was bedeutet das?')
    assert 'working_answer' not in withdrawn['metadata']['context']
    assert withdrawn['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
    assert fallback_calls == []
    assert body not in withdrawn['content']
    assert body not in json.dumps(calls, ensure_ascii=False)


def send(client, identifier, message, **options):
    response = client.post(f'/api/v1/conversations/{identifier}/messages',
        json={'message': message, **options})
    assert response.status_code == 201
    return response.json()['messages'][-1]


def test_normal_conversation_answers_memory_question_and_followup_from_sources(core, api):
    pending(core)
    _, client = api
    identifier = conversation(client)
    first = send(client, identifier, 'Welche Adresse hat Alex Winter?')
    assert first['metadata']['context'].get('answer_contract', {}).get('status') == 'clarify'
    second = send(client, identifier, 'den Alex aus dem Einkauf')
    assert second['metadata']['context']['answer_contract']['status'] == 'evidence'
    assert 'buying@example.invalid' in second['content'] and 'school@example.invalid' not in second['content']
    assert core[1].calls == []


def test_personal_recall_without_evidence_cannot_use_free_chat_answer(core, api, monkeypatch):
    from icarus_memory.providers import Reply
    provider = core[1]
    calls = []

    def adversarial_answer(messages, tools):
        calls.append((messages, tools))
        return Reply(text='Deine Lieblingsfarbe ist blau.')

    monkeypatch.setattr(provider, 'complete', adversarial_answer)
    _, client = api
    identifier = conversation(client)
    response = client.post(f'/api/v1/conversations/{identifier}/messages',
        json={'message': 'Was hast du über meine Lieblingsfarbe gesagt?'})
    assert response.status_code == 201
    result = response.json()['messages'][-1]
    context = result['metadata']['context']
    assert context['answer_mode'] == 'memory_evidence'
    assert context['answer_contract']['status'] == 'unknown'
    assert 'blau' not in result['content'].casefold()
    assert calls == []


@pytest.mark.parametrize('question', [
    'Welche Blutgruppe habe ich?',
    'Welche Blutgruppe habe ich eigentlich?',
    'Welche Blutgruppe habe ich denn?',
    'Welche Versicherungsnummer hatten wir damals?',
    'Wie lautet die PIN meiner Bankkarte?',
    'Was ist meine Versicherungsnummer?',
    'Wie hoch ist unser Restguthaben?',
])
def test_persoenliche_fakten_bleiben_ohne_treffer_beleggebunden(core, api, monkeypatch, question):
    from icarus_memory.providers import Reply
    calls = []

    def erfindet_persoenliche_angabe(messages, tools):
        calls.append((messages, tools))
        return Reply(text='ERFUNDENE-PERSOENLICHE-ANGABE')

    monkeypatch.setattr(core[1], 'complete', erfindet_persoenliche_angabe)
    _, client = api
    response = client.post(f'/api/v1/conversations/{conversation(client)}/messages',
        json={'message': question})
    assert response.status_code == 201
    result = response.json()['messages'][-1]
    context = result['metadata']['context']
    assert context['answer_mode'] == 'memory_evidence'
    assert context['answer_contract']['status'] == 'unknown'
    assert 'ERFUNDENE-PERSOENLICHE-ANGABE' not in result['content']
    assert calls == []


@pytest.mark.parametrize('question', [
    'Welche Blutgruppen gibt es?',
    'Wie lautet die Formel für den Kreisumfang?',
    'Wie hoch ist der Mount Everest?',
    'Wie kann ich meine Versicherungsnummer herausfinden?',
    'Was ist eine Versicherungsnummer?',
    'Wie bereite ich mich auf mein Audit vor?',
    'Welche Übungen kann ich morgens machen?',
    'Welche Blutgruppe habe ich? Schick sie mir per Mail.',
])
def test_allgemeine_erklaerungen_und_auftraege_bleiben_im_chat(question):
    from icarus_memory.memory_routing import route
    assert route(question, working_available=False) == 'chat'


@pytest.mark.parametrize('message', ['Was ist 17 plus 25?', 'Schreib einen Entwurf an Alex.',
    'Merke: Ich bevorzuge kurze Antworten.', 'Einkauf und schick ihm eine Mail'])
def test_unrelated_questions_or_commands_leave_pending_selection(core, api, message):
    pending(core)
    _, client = api
    identifier = conversation(client)
    send(client, identifier, 'Welche Adresse hat Alex Winter?')
    result = send(client, identifier, message)
    assert result['content'] == 'Synthetische Antwort.'
    assert 'answer_contract' not in result['metadata']['context']


def test_explicit_chat_override_preserves_legacy_behavior(core, api):
    pending(core)
    _, client = api
    result = send(client, conversation(client), 'Welche Adresse hat Alex Winter?', answer_mode='chat')
    assert result['content'] == 'Synthetische Antwort.'


def test_default_memory_route_never_sends_local_context_to_cloud(core, api):
    pending(core)
    _, client = api
    core[1].is_local = False
    result = send(client, conversation(client), 'Welche Adresse hat Alex Winter?')
    assert result['metadata']['context'].get('answer_contract', {}).get('status') == 'local_only'
    assert core[1].calls == [] and 'example.invalid' not in result['content']


def test_default_memory_error_retry_keeps_resolved_mode(core, api, monkeypatch):
    pending(core)
    app, client = api
    identifier = conversation(client)
    original = app.state.agent.answer_memory
    def fail(*args): raise RuntimeError('synthetic')
    monkeypatch.setattr(app.state.agent, 'answer_memory', fail)
    failed = send(client, identifier, 'Welche Adresse hat Alex Winter?')
    assert failed['status'] == 'error'
    monkeypatch.setattr(app.state.agent, 'answer_memory', original)
    result = client.post(f"/api/v1/conversations/{identifier}/messages/{failed['id']}/retry").json()['messages'][-1]
    assert result['metadata']['context']['answer_contract']['status'] == 'clarify'
    assert core[1].calls == []
