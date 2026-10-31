"""Nur bewiesene native Raw-Zeilen überleben eine irrelevante Modelleinstufung."""
import json
from types import SimpleNamespace

import pytest

from icarus_memory import docx_native_rows as native, working_memory_store as wms
from icarus_memory.mail_ingestion import remember
from icarus_memory.working_memory_analysis import interpret
from icarus_memory.working_memory_store import KINDS, WorkingMemoryStore
from tests.test_docx_native_rows import form, prepare, stores  # noqa: F401
from tests.test_answer_source_boundaries import Auswahl
from tests.test_mail_docx_attachments import DOCX_MIME, fetch
from tests.test_satzpruefung_modell import Pruefer
from tests.test_docx_table_context import p, packed


class AllesIrrelevant:
    is_local = True
    name = model = 'synthetic-irrelevant'

    def __init__(self):
        self.calls = 0

    def complete_json(self, messages, **kwargs):
        self.calls += 1
        blocks = json.loads(messages[-1]['content'])['blocks']
        return SimpleNamespace(text=json.dumps({'items': {b['block_id']: 'irrelevant' for b in blocks}}))


def intake(stores, monkeypatch, data=None):
    message = fetch(monkeypatch, ('Formular.docx', data or form(label='Prüfdatum'), DOCX_MIME))
    result = remember(stores[0], message, claims=stores[1])
    child, = result['anhaenge']
    return stores[0].get(child), result['episode']['id']


def refs(memory, source):
    return memory.items_all([source.id], list(KINDS))['refs']


@pytest.mark.parametrize('single', [True, False])
def test_irrelevante_mime_klassifikation_bewahrt_nur_native_zeile_als_unsicheren_originalverweis(stores, monkeypatch, single):
    data = packed('<w:tbl><w:tr><w:tc>' + p('Prüfdatum') + p('18.11.2026')
                  + '</w:tc></w:tr></w:tbl>') if single else None
    source, _ = intake(stores, monkeypatch, data)
    classifier = AllesIrrelevant()
    items = interpret(classifier, source)
    assert items == [] and classifier.calls == 1
    memory = WorkingMemoryStore(stores[0])
    assert memory.commit(stores[0].support_snapshot(source.id), items, model=classifier.model)
    found = refs(memory, source)
    assert len(found) == 1 and found[0]['kind'] == 'uncertain'
    row = source.body[found[0]['start']:found[0]['end']]
    assert row == 'Prüfdatum\n18.11.2026' + ('' if single else '\tfrist der rücksendung:')
    assert memory.resolve(found[0]).episode.body == source.body
    assert memory.search('Prüfdatum')['refs'] == found
    judge = Pruefer()
    saved, _, rendered, _ = prepare(stores, judge=judge, needle='Prüfdatum\n18.11.2026',
                                    question='Welches Prüfdatum nennt das Formular?')
    assert saved['satzantwort']['status'] == 'saetze' and 'Quelle berichtet: „' + row + '“' in rendered
    assert len(judge.anfragen) == 1 and source.body in json.loads(judge.anfragen[0][-1]['content'])['belege']
    assert stores[1].all_claims() == [] and stores[0].get(source.id).body == source.body


@pytest.mark.parametrize('kind', sorted(KINDS))
@pytest.mark.parametrize('cover', ['whole', 'larger', 'partial', 'adjacent'])
def test_vorhandene_ueberlappende_arten_haben_vorrang_und_recheck_ist_idempotent(stores, monkeypatch, kind, cover):
    source, _ = intake(stores, monkeypatch)
    row = 'Prüfdatum\n18.11.2026\tfrist der rücksendung:'
    start, end = source.body.index(row), source.body.index(row) + len(row)
    a, b = ((start - 2, end + 2) if cover == 'larger' else (0, start)
            if cover == 'adjacent' else (start, end - (cover == 'partial')))
    items = [{'start': a, 'end': b, 'kind': kind}]
    memory = WorkingMemoryStore(stores[0])
    snapshot = stores[0].support_snapshot(source.id)
    assert memory.commit(snapshot, items, model='synthetic')
    found = refs(memory, source)
    assert {tuple(r[k] for k in ('start', 'end', 'kind')) for r in found} == (
        {(a, b, kind), (start, end, 'uncertain')} if cover == 'adjacent' else {(a, b, kind)})
    assert items == [{'start': a, 'end': b, 'kind': kind}]
    revision = memory.revision()
    assert not memory.commit(snapshot, [], model='synthetic')
    assert memory.revision() == revision
    recheck = [{k: r[k] for k in ('start', 'end', 'kind')} for r in found]
    assert memory.commit(snapshot, recheck, model='synthetic', explicit_recheck=True)
    assert refs(memory, source) == found
    assert stores[0].get(source.id).body == source.body


@pytest.mark.parametrize('case', ['no_tag', 'bad_tag', 'duplicate', 'truncated', 'quoted', 'draft', 'long', 'free_value', 'unsupported'])
def test_nur_gueltiger_geeigneter_kompletter_proof_ergibt_unsicheren_verweis(stores, monkeypatch, case):
    data = form(label='Prüfdatum', extra=p('Ein "Zitat".') if case == 'quoted' else p('Entwurf') if case == 'draft' else '')
    if case == 'long':
        data = form(label='Prüfdatum', extra=p('Unabhängige Zusatzinformation. ' * 150))
    elif case == 'free_value':
        data = form(label='Prüfdatum', value='Anna Beispiel')
    elif case == 'unsupported':
        data = packed('<w:tbl><w:tr><w:tc><w:p><w:hyperlink><w:r><w:t>Prüfdatum</w:t></w:r>'
                      '</w:hyperlink></w:p>' + p('18.11.2026') + '</w:tc></w:tr></w:tbl>')
    source, _ = intake(stores, monkeypatch, data)
    if case == 'no_tag':
        from icarus_memory.source_versions import track_source
        snapshot = stores[0].support_snapshot(source.id)
        source, _ = stores[0].record(source.kind, source.title, source.body, source.provenance,
            occurred_at=source.occurred_at, participants=source.participants, contacts=source.contacts,
            tags=[t for t in source.tags if not t.startswith(native.TAG)], source_key=snapshot.source_key)
        track_source(stores[0], stores[1], snapshot.source_key, source)
    elif case in {'bad_tag', 'duplicate', 'truncated'}:
        tag = next(t for t in source.tags if t.startswith(native.TAG))
        stores[0].add_mail_headers(source.id, ['source:truncated'] if case == 'truncated'
                                  else [native.TAG + '{"v":false}'] if case == 'bad_tag' else [tag + ' '])
    memory = WorkingMemoryStore(stores[0])
    assert memory.commit(stores[0].support_snapshot(source.id), [], model='synthetic')
    assert refs(memory, source) == [] and memory.source_state(source.id) == 'empty'
    assert stores[0].get(source.id).body == source.body


def test_items_budget_und_doppelte_modellreferenzen_bleiben_verbindlich(stores, monkeypatch):
    source, _ = intake(stores, monkeypatch)
    memory = WorkingMemoryStore(stores[0])
    snapshot = stores[0].support_snapshot(source.id)
    item = {'start': 0, 'end': 10, 'kind': 'historical'}
    monkeypatch.setattr(wms, 'MAX_ITEMS', 1)
    assert memory.commit(snapshot, [item], model='synthetic')
    found = refs(memory, source)
    assert len(found) == 1 and found[0]['kind'] == 'historical'
    with pytest.raises(ValueError, match='at most'):
        memory.commit(snapshot, [item, item], model='synthetic', explicit_recheck=True)
    monkeypatch.setattr(wms, 'MAX_ITEMS', 2)
    with pytest.raises(ValueError, match='duplicate'):
        memory.commit(snapshot, [item, item], model='synthetic', explicit_recheck=True)
    assert refs(memory, source) == found


@pytest.mark.parametrize('change', ['parent', 'source', 'dismiss'])
def test_stale_oder_entzogene_quelle_erreicht_native_merge_nicht(stores, monkeypatch, change):
    source, parent = intake(stores, monkeypatch)
    memory = WorkingMemoryStore(stores[0])
    snapshot = stores[0].support_snapshot(source.id)
    if change == 'parent':
        stores[0].ignore(parent)
    elif change == 'source':
        stores[0].add_mail_headers(source.id, ['synthetic:metadata-change'])
    else:
        memory.dismiss(source.id)
    def forbidden(*args, **kwargs):
        pytest.fail('Native-Proof darf erst nach bestehenden Frischeprüfungen gelesen werden')
    monkeypatch.setattr(native, 'read', forbidden)
    assert not memory.commit(snapshot, [], model='synthetic', explicit_recheck=True)
    assert refs(memory, source) == []


def test_proof_wird_im_commit_lock_aus_frischem_snapshot_gelesen(stores, monkeypatch):
    source, _ = intake(stores, monkeypatch)
    snapshot = stores[0].support_snapshot(source.id)
    read, calls = native.read, []
    def bound(current, fingerprint, visible):
        assert current is not snapshot and stores[0]._conn.in_transaction
        assert wms.source_fingerprint(current) == fingerprint and visible == source.body
        calls.append(current)
        return read(current, fingerprint, visible)
    monkeypatch.setattr(native, 'read', bound)
    assert WorkingMemoryStore(stores[0]).commit(snapshot, [], model='synthetic')
    assert len(calls) == 1


def test_expliziter_recheck_aktualisiert_antwortsignatur_und_semantic_caches_ohne_neue_klassifikation(stores, monkeypatch):
    from icarus_memory import working_memory_answers as wma
    from icarus_memory.working_memory_semantic import WorkingMemorySemantic
    from icarus_memory.working_memory_semantic_index import DurableSemanticIndex
    source, parent = intake(stores, monkeypatch)
    memory = WorkingMemoryStore(stores[0])
    snapshot = stores[0].support_snapshot(source.id)
    # Alter b8-Stand: vollständiger Proof, aber die leere Einordnung wurde ohne
    # native Indexbewahrung gespeichert. Keine Versionsmigration/Backfill.
    with monkeypatch.context() as old:
        old.setattr(native, 'read', lambda *args: None)
        assert memory.commit(snapshot, [], model='synthetic-old')
    assert memory.source_state(source.id) == 'empty' and memory.pending(episode_ids=[source.id]) == []
    question = 'Welches Prüfdatum nennt das Formular?'
    assert wma.prepare(question, *stores, Auswahl('Prüfdatum\n18.11.2026'), semantic_search=None) is None
    signature, revision = memory.semantic_signature(), memory.revision()
    class Vectors:
        is_local = True
        model_key = 'synthetic-vectors'
        def embed(self, texts):
            return [[1., 0.] for _ in texts]
    transient = WorkingMemorySemantic(Vectors())
    assert transient.search(stores[0], 'Prüfdatum') == []
    cache = DurableSemanticIndex(stores[0], 'synthetic-vectors:' + 'd' * 64)
    try:
        assert cache.pending(1).refs == ()
        assert not memory.commit(snapshot, [], model='synthetic-old')
        assert memory.commit(snapshot, [], model='synthetic-old', explicit_recheck=True)
        assert wms.ANALYSIS_VERSION == 1 and memory.revision() == revision + 1
        assert memory.semantic_signature() != signature
        found = refs(memory, source)
        saved = prepare(stores, judge=Pruefer(), needle='Prüfdatum\n18.11.2026', question=question)[0]
        rendered = wma.render(saved, *stores)
        assert rendered[2] == 'working_reports' and 'Quelle berichtet:' in rendered[0]
        assert transient.search(stores[0], 'Prüfdatum') == found
        batch = cache.pending(1)
        assert list(batch.refs) == found and cache.commit(batch, [[1., 0.]]) == 1
        assert list(cache.search([1., 0.]).refs) == found
        # Keine doppelten Keys oder vermeintlich neuen Vektoren beim nächsten
        # expliziten Recheck derselben unveränderten vorhandenen Items.
        items = [{k: ref[k] for k in ('start', 'end', 'kind')} for ref in found]
        assert memory.commit(snapshot, items, model='synthetic-old', explicit_recheck=True)
        assert cache.pending(1).refs == () and refs(memory, source) == found
        assert wma.render(saved, *stores) == rendered
        stores[0].ignore(parent)
        assert memory.resolve(found[0]) is None
        assert wma.render(saved, *stores)[2] == 'working_unavailable'
        assert transient.search(stores[0], 'Prüfdatum') == [] and cache.search([1., 0.]).refs == ()
    finally:
        cache.close()
