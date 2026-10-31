"""Nur die Modellprojektion packen: identische Werte, keine neuen Quellenbehauptungen."""
import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from icarus_memory import absatzauswahl as auswahl, local_context_profile as context
from icarus_memory import working_memory_answers as wma
from icarus_memory.providers import OpenAICompatible, ProviderError


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def synthetic_rows():
    rows = []
    for i in range(16):
        mail = i // 4
        body = (f'Von: Person {mail} <person{mail}@synthetic.example>\n'
                'Die Kalkulation ist NICHT fertig. Die Frist bleibt bedingt. '
                + 'Weitere künstliche Information. ' * 4)
        # Zwei verschiedene Kontexte derselben Mail bleiben verschieden.
        if i % 4 == 3:
            body += '\nEine zusätzliche Bedingung bleibt bestehen.'
        rows.append(dict(id=f'S{i + 1}', text=f'Unveränderte künstliche Einzelangabe {i + 1}: nicht erledigt.',
                         context=body, title=f'Künstliche Nachricht {mail + 1}: Kalkulation und Rückfrage',
                         kind='fact', occurred_at='2026-10-31T09:00:00+00:00',
                         recorded_at='2026-10-31T10:00:00+00:00', source_ref=f'synthetic-mail-{mail + 1}',
                         participants=[f'Person {mail} <person{mail}@synthetic.example>'],
                         sender=f'Person {mail} <person{mail}@synthetic.example>', project_id=None))
    return rows


def instruction():
    tree = ast.parse(Path(wma.__file__).read_text())
    return next(n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
                and n.value.value.startswith('Wähle Originalstellen'))


def payload(rows, note=''):
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['status', 'ids'], 'properties': {
        'status': {'type': 'string', 'enum': list(wma.MODEL_DECISIONS)},
        'ids': {'type': 'array', 'maxItems': wma.MAX_REFS + 12,
                'items': {'type': 'string', 'enum': [r['id'] for r in rows]}}}}
    return {'model': 'synthetic:8k', 'messages': [
        {'role': 'system', 'content': instruction() + note},
        {'role': 'user', 'content': encode({'question': 'Welche Kalkulationen sind nicht fertig?', 'sources': rows})}],
        'max_tokens': 256, 'response_format': {'type': 'json_schema', 'json_schema': {
            'name': 'local_result', 'strict': True, 'schema': schema}}, 'reasoning_effort': 'none', 'temperature': 0}


def test_sixteen_candidates_keep_every_value_and_fit_full_native_budget(monkeypatch):
    rows = synthetic_rows()
    before = deepcopy(rows)
    provider = OpenAICompatible('synthetic:8k', base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setenv(context.FLAG, provider.model)
    monkeypatch.setattr(context, 'verify_profile', lambda _: 'offline-synthetic')
    original = payload(rows)
    assert 18000 < len(context._encoded(original)) < 22000
    with pytest.raises(ProviderError, match='16.000'):
        context.prepare(provider, original)
    packed = auswahl.modell_zeilen(rows)
    assert packed[1]['context'] == {'$copy': 'S1'}
    assert auswahl.modell_zeilen_entpacken(packed) == rows == before
    for original_row, projected in zip(rows, packed):
        assert set(original_row) == set(projected)
        assert all(projected[k] == original_row[k] for k in ('id', 'kind', 'text'))
    compact = payload(packed, '\n' + auswahl.KOPIERHINWEIS)
    ready = context.prepare(provider, compact)
    assert len(context._encoded(compact)) < 16000
    assert len(context._encoded(ready.payload)) < 16000
    assert ready.payload['format'] == original['response_format']['json_schema']['schema']
    restored = auswahl.modell_zeilen_entpacken(json.loads(ready.payload['messages'][-1]['content'])['sources'])
    assert restored == before


def test_copy_is_same_field_first_literal_not_source_identity_or_normalization():
    rows = synthetic_rows()
    # Identischer Kontext, aber ausdrücklich andere Quellenhalter und Adressen.
    rows[4]['context'] = rows[0]['context']
    rows[5]['context'] = '\n' + rows[0]['context']
    rows[6]['context'] = rows[0]['context'].replace('NICHT fertig', 'fertig')
    rows[7]['context'] = rows[0]['context'].lower()
    rows[1]['andere_person'] = {'adresse_dieser_person': 'other@synthetic.example'}
    rows[2]['ausserhalb_zeitraum'] = True
    packed = auswahl.modell_zeilen(rows)
    assert packed[2]['context'] == packed[4]['context'] == {'$copy': 'S1'}
    assert packed[3]['context'] == rows[3]['context']
    assert all(packed[i]['context'] == rows[i]['context'] for i in (5, 6, 7))
    restored = auswahl.modell_zeilen_entpacken(packed)
    assert restored == rows
    assert restored[4]['source_ref'] != restored[0]['source_ref']
    assert restored[4]['sender'] != restored[0]['sender']
    assert packed[1]['andere_person'] == rows[1]['andere_person']
    assert packed[2]['ausserhalb_zeitraum'] is True


def test_small_savings_do_not_pay_for_an_instruction_and_absent_null_stay_distinct():
    rows = [{'id': 'S1', 'text': 'a', 'context': 'context', 'sender': 'A sender slightly longer than a copy'},
            {'id': 'S2', 'text': 'b', 'context': 'different', 'sender': 'A sender slightly longer than a copy',
             'project_id': None}]
    assert auswahl.modell_zeilen(rows) == rows
    assert auswahl.modell_zeilen_entpacken(rows) == rows


def test_own_context_markers_remain_relative_to_current_row_after_literal_copy():
    rows = synthetic_rows()
    for row in rows:
        row['context'] = auswahl.FUNDSTELLE + '\n' + 'Gemeinsamer weiterer Originalabsatz. ' * 15
    packed = auswahl.modell_zeilen(rows)
    assert packed[1]['context'] == {'$copy': 'S1'}
    restored = auswahl.modell_zeilen_entpacken(packed)
    assert restored == rows and restored[1]['text'] != restored[0]['text']
    assert 'aktuellen Zeile' in auswahl.KOPIERHINWEIS


@pytest.mark.parametrize('rows', [
    [{'id': 'S1', 'context': {'$copy': 'S2'}}, {'id': 'S2', 'context': 'x'}],
    [{'id': 'S1', 'context': {'$copy': 'S1'}}],
    [{'id': 'S1', 'context': {'$copy': 'missing'}}],
    [{'id': 'S1', 'text': 'x'}, {'id': 'S2', 'context': {'$copy': 'S1'}}],
    [{'id': 'S1', 'context': 'x'}, {'id': 'S2', 'context': {'$copy': 'S1', 'extra': True}}],
    [{'id': 'S1', 'context': 'x'}, {'id': 'S2', 'context': {'$copy': ['S1']}}],
    [{'id': 'S1', 'context': 'x'}, {'id': 'S2', 'context': {'$copy': 'S1'}},
     {'id': 'S3', 'context': {'$copy': 'S2'}}],
    [{'id': 'S1', 'context': 'x'}, {'id': 'S2', 'context': 'x'},
     {'id': 'S3', 'context': {'$copy': 'S2'}}],
    [{'id': 'S1', 'context': None}, {'id': 'S2', 'context': {'$copy': 'S1'}}],
    [{'id': 'S1', 'participants': [{'original': True}]}, {'id': 'S2', 'participants': {'$copy': 'S1'}}],
    [{'id': 'S1', 'context': 'x'}, {'id': 'S1', 'context': {'$copy': 'S1'}}],
    [{'id': 'S1', 'text': 'x'}, {'id': 'S2', 'text': {'$copy': 'S1'}}],
])
def test_decoder_rejects_malformed_forward_self_chain_and_ambiguous_references(rows):
    with pytest.raises(ValueError):
        auswahl.modell_zeilen_entpacken(rows)


def test_original_objects_and_reserved_copy_collisions_never_become_forged_references():
    rows = synthetic_rows()
    rows[0]['sender'] = {'original': ['not', 'a', 'reference']}
    rows[1]['sender'] = deepcopy(rows[0]['sender'])
    packed = auswahl.modell_zeilen(rows)
    assert packed[1]['sender'] == rows[1]['sender']
    assert auswahl.modell_zeilen_entpacken(packed) == rows
    rows[1]['sender'] = {'$copy': 'S1'}
    with pytest.raises(ValueError):
        auswahl.modell_zeilen(rows)


def test_full_instruction_overhead_is_paid_and_no_copy_increases_nested_wire_bytes():
    rows = synthetic_rows()
    packed = auswahl.modell_zeilen(rows)
    assert len(context._encoded(payload(packed, '\n' + auswahl.KOPIERHINWEIS))) < len(context._encoded(payload(rows)))
    for before, after in zip(rows, packed):
        for key, value in after.items():
            if isinstance(value, dict) and '$copy' in value:
                assert len(encode(encode(value)).encode()) < len(encode(encode(before[key])).encode())


def test_packing_never_cuts_unique_content_or_weakens_budget(monkeypatch):
    rows = synthetic_rows()
    rows[0]['text'] += ' Eigenständiger unveränderter Originaltext. ' * 300
    packed = auswahl.modell_zeilen(rows)
    assert auswahl.modell_zeilen_entpacken(packed) == rows
    provider = OpenAICompatible('synthetic:8k', base_url='http://127.0.0.1:11434/v1')
    monkeypatch.setenv(context.FLAG, provider.model)
    monkeypatch.setattr(context, 'verify_profile', lambda _: pytest.fail('No metadata/model request for overlimit input'))
    with pytest.raises(ProviderError, match='16.000'):
        context.prepare(provider, payload(packed, '\n' + auswahl.KOPIERHINWEIS))
