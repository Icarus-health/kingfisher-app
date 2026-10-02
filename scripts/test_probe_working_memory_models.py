"""Der Modellvergleich misst den echten Produktcode, netzfrei prüfbar."""
import json
import subprocess
import sys
from pathlib import Path

import probe_working_memory_models as probe
from icarus_memory.providers import Reply
from icarus_memory.working_memory_answers import MODEL_DECISIONS

SCRIPT = Path(probe.__file__)
CATALOG = json.loads(probe.CATALOG.read_text(encoding='utf-8'))
DECISION = {state: decision for decision, state in MODEL_DECISIONS.items()}


class Oracle:
    """Antwortet nach dem Katalog; schreibt JSON in Codeblöcke wie manche Cloud-Modelle."""
    name, model, is_local = 'oracle', 'oracle', False

    def complete(self, messages, tools):
        payload = json.loads(messages[-1]['content'])
        if 'blocks' in payload:
            kinds = {b['text']: b['kinds'][0] for case in CATALOG['interpretation'] for b in case['blocks']}
            text = json.dumps({'items': [{'block_id': b['block_id'], 'kind': kinds[b['text']]}
                                         for b in payload['blocks']]})
        else:
            case = next(c for c in CATALOG['selection'] if c['question'] == payload['question'])
            wanted = {s['text'] for s in case['sources'] if s['id'] in case['expect']}
            text = json.dumps({'status': DECISION[case['status']],
                               'ids': [row['id'] for row in payload['sources'] if row['text'] in wanted]})
        return Reply(text='```json\n' + text + '\n```')


class Broken:
    name, model, is_local = 'broken', 'broken', True

    def complete(self, messages, tools):
        return Reply(text='Ich denke, die Antwort ist Montag.')


def test_oracle_reaches_full_marks_through_product_code():
    arm = probe.run_arm(probe.Arm('oracle', Oracle()), CATALOG)
    e, a = arm['einordnung'], arm['auswahl']
    assert e['absaetze_richtig'] == e['absaetze'] and e['ungueltige_antworten'] == 0
    assert a['status_richtig'] == a['faelle'], [r for r in a['rows'] if not r['status_ok']]
    assert a['beides_richtig'] == a['faelle'], [r for r in a['rows'] if not r['sources_ok']]
    assert arm['json_aus_codeblock'] == arm['aufrufe'] > 0


def test_broken_model_is_counted_as_invalid_not_as_correct():
    arm = probe.run_arm(probe.Arm('broken', Broken()), CATALOG)
    assert arm['einordnung']['ungueltige_antworten'] == arm['einordnung']['faelle']
    assert arm['einordnung']['absaetze_richtig'] == 0
    assert arm['auswahl']['ungueltige_antworten'] >= arm['auswahl']['faelle'] - 1


def test_cloud_arm_needs_explicit_permission(tmp_path, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    result = subprocess.run([sys.executable, str(SCRIPT), '--arm', 'anthropic:claude-sonnet-5',
                             '--output', str(tmp_path / 'r.json')], capture_output=True, text=True)
    assert result.returncode != 0 and '--cloud-erlaubt' in (result.stderr + result.stdout)
    assert not (tmp_path / 'r.json').exists()


def test_existing_output_is_never_overwritten(tmp_path):
    target = tmp_path / 'r.json'
    target.write_text('{}', encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), '--arm', 'ollama:x', '--output', str(target)],
                            capture_output=True, text=True)
    assert result.returncode != 0 and 'existiert bereits' in result.stderr


class AlwaysFact:
    """Gültige, aber einfältige Antworten: alles „fact“, immer alle Quellen."""
    name, model, is_local = 'fact', 'fact', True

    def complete(self, messages, tools):
        payload = json.loads(messages[-1]['content'])
        if 'blocks' in payload:
            return Reply(text=json.dumps({'items': [{'block_id': b['block_id'], 'kind': 'fact'}
                                                    for b in payload['blocks']]}))
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [r['id'] for r in payload['sources']]}))


def test_valid_but_wrong_answers_score_exactly_what_they_get_right():
    arm = probe.run_arm(probe.Arm('fact', AlwaysFact()), CATALOG)
    allowed = sum('fact' in block['kinds'] for case in CATALOG['interpretation'] for block in case['blocks'])
    assert arm['einordnung']['absaetze_richtig'] == allowed < arm['einordnung']['absaetze']
    assert arm['einordnung']['ungueltige_antworten'] == 0
    assert 0 < arm['auswahl']['beides_richtig'] < arm['auswahl']['faelle']


class RightStatusAllSources(Oracle):
    """Richtiger Status, aber immer alle Quellen."""
    is_local = True

    def complete(self, messages, tools):
        payload = json.loads(messages[-1]['content'])
        if 'blocks' in payload:
            return super().complete(messages, tools)
        case = next(c for c in CATALOG['selection'] if c['question'] == payload['question'])
        ids = [row['id'] for row in payload['sources']] if case['status'] != 'unknown' else []
        return Reply(text=json.dumps({'status': DECISION[case['status']], 'ids': ids}))


def test_wrong_sources_are_not_counted_as_right():
    arm = probe.run_arm(probe.Arm('all', RightStatusAllSources()), CATALOG)
    rows = arm['auswahl']['rows']
    over = [c['id'] for c in CATALOG['selection'] if len(c['expect']) < len(c['sources']) and c['expect']]
    assert over and all(not row['sources_ok'] for row in rows if row['id'] in over)
    assert arm['auswahl']['quellen_richtig'] == arm['auswahl']['faelle'] - len(over)
