"""Verfahren sind bestätigte Arbeitsweisen, niemals zusätzliche Befugnisse."""
import json
import pytest

from icarus_memory.procedures import ProcedureStore, ProcedureError, parse_markdown


def spec(**changes):
    return dict(name='zunftmail', title='Offizielle Zunftmail',
        description='Offizielle Mail im Zunftkontext vorbereiten.', area='mail',
        triggers=['zunft', 'zunftmail'], steps=['Zuerst Anlass und Empfänger prüfen.',
            'Bestätigten Kontaktstil beachten. Entwurf knapp gegenlesen.'],
        positive='Schreibe eine Mail für die Zunft.',
        negative='Schreibe eine private Mail zur Urlaubsplanung.', **changes)


def test_pending_is_never_loaded_and_acceptance_survives_restart(tmp_path):
    path = tmp_path / 'procedures.sqlite3'
    store = ProcedureStore(path)
    candidate = store.propose(spec())
    assert store.select('Schreibe eine Zunftmail.', area='mail')['contextual'] == []
    store.accept(candidate['id'])
    store.close()
    restored = ProcedureStore(path)
    selection = restored.select('Schreibe eine Zunftmail.', area='mail')
    assert [x['name'] for x in selection['contextual']] == ['zunftmail']
    assert 'gegenlesen' in selection['instructions']
    restored.close()


def test_duplicate_proposal_and_stale_revision_are_not_double_activated(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    first = store.propose(spec())
    assert store.propose(spec())['id'] == first['id']
    store.accept(first['id'])
    one = store.propose({**spec(), 'steps': ['Erst Anlass prüfen, dann knapp entwerfen.']})
    two = store.propose({**spec(), 'steps': ['Anlass und Stil prüfen, dann entwerfen.']})
    store.accept(one['id'])
    with pytest.raises(ProcedureError, match='Stand'):
        store.accept(two['id'])
    assert store.select('Schreibe eine Zunftmail.', area='mail')['contextual'][0]['version'] == 2


def test_router_uses_task_and_whole_tokens_not_quoted_text_or_substrings(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    store.accept(store.propose(spec())['id'])
    for message, area in [('Erkläre den Begriff Zunft.', 'analysis'),
                          ('Schreibe eine Zukunftsmail.', 'mail'),
                          ('Schreibe eine private Mail.\nZitat: Zunft', 'mail')]:
        assert not store.select(message, area=area)['contextual']
    assert store.select('Schreibe eine Mail für die Zunft.', area='mail')['contextual']


def test_conflicting_matches_are_withheld_not_arbitrarily_picked(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    store.accept(store.propose(spec())['id'])
    store.accept(store.propose({**spec(), 'name': 'zunftmail-anders', 'title': 'Andere Zunftmail'})['id'])
    chosen = store.select('Schreibe eine Zunftmail.', area='mail')
    assert not chosen['contextual']
    assert chosen['conflicts'] == ['zunftmail', 'zunftmail-anders']


def test_local_only_and_revocation_signature(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    candidate = store.propose(spec())
    store.accept(candidate['id'])
    selection = store.select('Schreibe eine Zunftmail.', area='mail')
    assert store.current(selection)
    assert not store.select('Schreibe eine Zunftmail.', area='mail', local=False)['contextual']
    store.revoke(candidate['id'])
    assert not store.current(selection)
    assert not store.select('Schreibe eine Zunftmail.', area='mail')['contextual']


def test_roundtrip_export_is_readable_markdown_and_exact_metadata(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    candidate = store.propose(spec())
    exported = store.export(candidate['id'])
    assert exported.startswith('---\n') and '# Offizielle Zunftmail' in exported
    parsed = parse_markdown(exported)
    assert parsed['name'] == 'zunftmail'
    assert parsed['steps'] == spec()['steps']


@pytest.mark.parametrize('change', [
    {'name':'../../escape'}, {'area':'shell'}, {'triggers':[]},
    {'steps':[]}, {'negative':'Schreibe eine Zunftmail.'},
    {'positive':'Was ist Urlaub?'}, {'steps':['x' * 5001]},
    {'tools':['mail_send']},
])
def test_invalid_or_unbounded_procedures_are_rejected(tmp_path, change):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    with pytest.raises(ProcedureError):
        store.propose({**spec(), **change})


def test_source_dependency_changed_blocks_acceptance_and_selected_instructions(tmp_path):
    stamps = {'source-1': 'v1'}
    store = ProcedureStore(tmp_path / 'p.sqlite3', dependency=lambda key: stamps.get(key))
    candidate = store.propose(spec(), sources={'source-1':'v1'})
    stamps['source-1'] = 'v2'
    with pytest.raises(ProcedureError, match='Grundlage'):
        store.accept(candidate['id'])
    current = store.propose({**spec(), 'name':'fresh'}, sources={'source-1':'v2'})
    store.accept(current['id'])
    selected = store.select('Schreibe eine Zunftmail.', area='mail')
    del stamps['source-1']
    assert not store.current(selected)
    assert not store.select('Schreibe eine Zunftmail.', area='mail')['contextual']


def test_core_procedures_are_bounded_and_cannot_be_replaced(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    selected = store.select('Hallo!', area=None)
    assert [x['name'] for x in selected['essential']] == ['skill-router', 'source-safety']
    assert not selected['contextual']
    assert len(selected['instructions']) < 4000
    with pytest.raises(ProcedureError):
        store.propose({**spec(), 'name':'source-safety'})


def test_pending_revision_cannot_bypass_later_revoke(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    old = store.propose(spec())
    newer = store.propose({**spec(), 'steps':['Anlass prüfen. Dann entwerfen.']})
    store.accept(newer['id'])
    store.revoke(newer['id'])
    with pytest.raises(ProcedureError, match='Stand'):
        store.accept(old['id'])


def test_same_known_procedure_is_reused_across_different_learning_requests(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    first = store.propose(spec(), request_key='first-explicit-learning')
    store.accept(first['id'])
    again = store.propose(spec(), request_key='same-procedure-different-wording')
    assert again['id'] == first['id'] and again['state'] == 'active'
    assert len(store.items()) == 1


def test_real_local_draft_negative_explanation_does_not_broaden_official_context(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    generated = {**spec(), 'triggers':['Zunft','offiziell'],
        'positive':'Mail ist offiziell für die Zunft, daher Anlass prüfen.',
        'negative':'Mail ist privat (z.B. Urlaub), daher keine Prüfung des offiziellen Kontaktstils oder der Zunft-Vorgaben durchführen.'}
    item = store.propose(generated)
    store.accept(item['id'])
    assert item['triggers'] == ['Zunft']
    assert store.select('Schreibe eine Mail für die Zunft.',area='mail')['contextual']
    assert not store.select('Schreibe eine Mail, ganz offiziell.',area='mail')['contextual']
    assert not store.select('Schreibe eine Mail, nicht für die Zunft.',area='mail')['contextual']


def test_learning_catalog_retrieves_relevant_headers_without_bodies(tmp_path):
    store = ProcedureStore(tmp_path / 'p.sqlite3')
    first = store.propose(spec())
    store.accept(first['id'])
    for i in range(15):
        item = store.propose({**spec(), 'name':f'unrelated-{i}', 'triggers':[f'thema{i}'],
            'positive':f'Schreibe eine Mail für thema{i}.'})
        store.accept(item['id'])
    headers = store.learning_catalog('Lerne diesen Ablauf: Eine Mail für die Zunft vorbereiten.')
    assert [item['name'] for item in headers] == ['zunftmail']
    assert not any(key in headers[0] for key in ('steps','markdown','sources'))


def test_learning_catalog_finds_pending_without_activating_or_duplicating_it(tmp_path):
    store=ProcedureStore(tmp_path/'p.sqlite3')
    first=store.propose(spec(),request_key='first-explicit-request')
    headers=store.learning_catalog('Merke dir für die Zunft: zuerst Anlass prüfen, danach gegenlesen.')
    assert len(headers)==1 and headers[0]['name']==first['name']
    assert headers[0]['state']=='pending' and headers[0]['version']==1
    assert not any(k in headers[0] for k in ('steps','markdown','sources'))
    assert not store.select('Schreibe eine Mail für die Zunft.',area='mail')['contextual']
    again=store.propose(spec(),request_key='second-wording-same-procedure')
    assert again['id']==first['id'] and len(store.items())==1
    assert store.learning_catalog('Merke dir für Nichtzunftmail: zuerst prüfen, danach gegenlesen.')==[]


def test_learning_catalog_keeps_latest_live_revision_and_rejects_stale_sources(tmp_path):
    stamps={'source':'one'}
    store=ProcedureStore(tmp_path/'p.sqlite3',dependency=stamps.get)
    first=store.propose(spec(),sources={'source':'one'});store.accept(first['id'])
    second=store.propose({**spec(),'description':'Neue dauerhafte Reihenfolge bei Zunftmails.'},sources={'source':'one'})
    headers=store.learning_catalog('Lerne diesen Ablauf: Für Zunftmails zuerst prüfen, dann gegenlesen.')
    assert len(headers)==1 and headers[0]['version']==second['version'] and headers[0]['state']=='pending'
    stamps['source']='two'
    assert store.learning_catalog('Lerne diesen Ablauf: Für Zunftmails zuerst prüfen, dann gegenlesen.')==[]


def test_learning_catalog_excludes_rejected_revoked_superseded_and_obsolete_pending(tmp_path):
    store=ProcedureStore(tmp_path/'p.sqlite3')
    rejected=store.propose({**spec(),'name':'rejected'});store.reject(rejected['id'])
    revoked=store.propose({**spec(),'name':'revoked'});store.accept(revoked['id']);store.revoke(revoked['id'])
    original=store.propose(spec());store.accept(original['id'])
    obsolete=store.propose({**spec(),'description':'Dieser offene Entwurf wird bald überholt.'})
    newer=store.propose({**spec(),'description':'Diese Fassung wird ausdrücklich übernommen.'});store.accept(newer['id'])
    rows=store.learning_catalog('Lerne diesen Ablauf: Für Zunftmails zuerst prüfen, dann gegenlesen.')
    assert [(r['name'],r['version'],r['state']) for r in rows]==[('zunftmail',newer['version'],'active')]


def test_pending_learning_catalog_obeys_count_and_utf8_byte_budget(tmp_path):
    import json
    store=ProcedureStore(tmp_path/'p.sqlite3')
    for i in range(20):
        store.propose({**spec(),'name':f'pending-{i}','description':'Ä'*380})
    headers=store.learning_catalog('Lerne diesen Ablauf: Für Zunftmails zuerst prüfen, dann gegenlesen.')
    assert 0<len(headers)<=8
    assert sum(len(json.dumps(h,ensure_ascii=False).encode()) for h in headers)<=2400
    assert all(h['state']=='pending' for h in headers)
