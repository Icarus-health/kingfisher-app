from probe_cos_workweek import grade


def message(ids, status='working_reports', content='Nora wartet noch auf Freigabe.'):
    return {'content': content, 'metadata': {'context': {'working_answer': {'refs': [{'episode_id': i} for i in ids]}, 'answer_contract': {'status': status}}}}


def test_wrong_source_is_not_saved_by_correct_words():
    case = {'required': ['right'], 'allowed': ['right'], 'status': ['working_reports'], 'contains': ['Freigabe']}
    checks = grade(case, message(['wrong']), {'right': 'right'})
    assert not checks['required_sources'] and not checks['allowed_sources']


def test_unclear_status_and_condition_are_independent_gates():
    case = {'required': ['a'], 'allowed': ['a'], 'status': ['working_unclear'], 'contains': ['noch auf Freigabe']}
    assert not grade(case, message(['a']), {'a': 'a'})['status']
    assert not grade(case, message(['a'], 'working_unclear', 'Nora hat zugesagt.'), {'a': 'a'})['required_text']
    assert all(grade(case, message(['a'], 'working_unclear'), {'a': 'a'}).values())


def test_unknown_rejects_any_selected_source_and_forbidden_detail():
    case = {'required': [], 'allowed': [], 'status': ['working_unknown'], 'excludes': ['HB-731']}
    checks = grade(case, message(['booking'], 'working_unknown', 'HB-731'), {})
    assert not checks['allowed_sources'] and not checks['forbidden_text']


def test_withdrawal_checks_paraphrases_earlier_messages_and_references():
    from probe_cos_workweek import withdrawn_hidden
    old = message(['a'], content='Lea Sommer liefert am 14. Oktober 2026.')
    conversation = {'messages': [old, message([], content='Quelle zurückgezogen.')]}
    assert not withdrawn_hidden(conversation, 'a', ['Lea Sommer', '14. Oktober 2026'])
    old['content'] = 'Inhalt entfernt.'
    assert not withdrawn_hidden(conversation, 'a', ['Lea Sommer'])
    old['metadata'] = {}
    assert withdrawn_hidden(conversation, 'a', ['Lea Sommer'])


def test_run_restores_environment_after_failure(monkeypatch):
    import os
    import pytest
    import probe_cos_workweek as probe
    monkeypatch.setenv('ICARUS_DATA_DIR', '/original')
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.setenv('ICARUS_MEMORY_SEMANTIC', '1')
    def failed(*args):
        os.environ.update(ICARUS_DATA_DIR='/temporary', ICARUS_SIDECAR_TOKEN='synthetic', ICARUS_MEMORY_SEMANTIC='')
        raise RuntimeError('test')
    monkeypatch.setattr(probe, '_run', failed)
    with pytest.raises(RuntimeError): probe.run(None, None, None)
    assert os.environ['ICARUS_DATA_DIR'] == '/original'
    assert 'ICARUS_SIDECAR_TOKEN' not in os.environ
    assert os.environ['ICARUS_MEMORY_SEMANTIC'] == '1'


def test_withdrawn_lineage_is_allowed_only_when_unavailable_without_live_links():
    from probe_cos_workweek import withdrawn_hidden
    stale = message(['a'], 'working_unavailable', 'Bitte frage erneut.')
    assert withdrawn_hidden({'messages': [stale]}, 'a', ['Lea Sommer'])
    stale['metadata']['context']['source_links'] = [{'episode_id': 'a'}]
    assert not withdrawn_hidden({'messages': [stale]}, 'a', ['Lea Sommer'])
