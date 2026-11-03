"""Generic questions read the chosen original; receipts never imply verification."""
import json

from fastapi.testclient import TestClient
import pytest

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from .test_local_module_controller import env, begin, terminal, MODEL, MODE


@pytest.mark.parametrize('body,read,complete', [
    ('Bitte senden Sie die Unterlagen bis Freitag.', 44, True),
    ('A' * 900, 800, False),
])
def test_generic_question_returns_actual_selected_receipts_and_truthful_coverage(env, body, read, complete):
    source = env['episodes'].record(EpisodeKind.DOCUMENT, 'Ausgewähltes künstliches Original', body,
        Provenance(source_type=SourceType.DOCUMENT))[0]
    question = 'Welche Bitten und Fristen stehen darin?'
    controller = env['create']()
    original = source.to_dict()

    def run(token, _question, _cancelled, _deadline):
        with TestClient(controller.worker_app()) as client:
            def tool(name, arguments):
                response = client.post('/worker/mcp', headers={'Authorization': 'Bearer ' + token},
                    json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                          'params': {'name': name, 'arguments': arguments}})
                assert response.status_code == 200
                result = response.json()['result']
                assert result['isError'] is False
                return json.loads(result['content'][0]['text'])
            assert tool('memory_search', {'query': 'Fristen'})['items'] == []
            chosen = tool('selected_original', {})
            assert chosen['id'] == source.id and chosen['quote'] == body[:400]
            if len(body) > 400:
                tool('source_excerpt', {'id': source.id, 'start': 400, 'end': 800})
        return dict(status='complete', text='Künstlicher unbestätigter Entwurf.', mode=MODE,
                    model=MODEL, syntheticOnly=False, instance='a' * 32)

    env['gateway'].run = run
    review = controller.prepare(source.id, question)
    job = begin(controller, source, review=review, question=question)
    result = terminal(controller, job)
    assert result['status'] == 'completed', result
    assert result['verified'] is False and result['label'] == 'DRAFT'
    assert result['evidence'][0]['quote'] == body[:400]
    assert result['coverage'] == {'source_characters': len(body), 'opened_characters': read,
                                  'complete_text_opened': complete}
    assert env['outside'].id not in json.dumps(result)
    assert env['episodes'].get(source.id).to_dict() == original


def test_empty_original_does_not_create_evidence_or_visible_model_prose(env):
    source = env['episodes'].record(EpisodeKind.DOCUMENT, 'Leeres künstliches Original', '',
        Provenance(source_type=SourceType.DOCUMENT))[0]
    controller = env['create']()

    def run(token, _question, _cancelled, _deadline):
        with TestClient(controller.worker_app()) as client:
            result = client.post('/worker/mcp', headers={'Authorization': 'Bearer ' + token},
                json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                      'params': {'name': 'selected_original', 'arguments': {}}})
            assert result.status_code == 200
        return dict(status='complete', text='Unbelegter Inhalt.', mode=MODE, model=MODEL,
                    syntheticOnly=False, instance='a' * 32)

    env['gateway'].run = run
    result = terminal(controller, begin(controller, source))
    assert result['status'] == 'failed'
    assert 'text' not in result and 'evidence' not in result
