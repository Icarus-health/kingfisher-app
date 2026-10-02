"""Synthetic lexical candidate-index contracts, never semantic/model qualification."""
import json
import sqlite3
from dataclasses import replace
from datetime import timedelta
import pytest
from tests.test_context import _knowledge_agent, AT
from icarus_memory.claims import ClaimStore


def insert_claims(store, claims):
    rows=[]
    for claim in claims:
        d=claim.to_dict()
        rows.append((claim.id,claim.proposal_id,claim.subject_ref,claim.predicate,claim.value,
                     claim.statement,json.dumps(d['evidence']),d['created_at'],claim.status.value,json.dumps(d)))
    with store._conn:
        store._conn.executemany('INSERT INTO knowledge_claims '
            '(id,proposal_id,subject_ref,predicate,value,statement,evidence,created_at,status,document) '
            'VALUES (?,?,?,?,?,?,?,?,?,?)',rows)


def variants(template, count, text):
    return [replace(template,id=f'synthetic:{n}',proposal_id=f'proposal:{n}',
        value=text,statement=text,created_at=AT+timedelta(seconds=n+1)) for n in range(count)]


def test_actual_agent_finds_old_claim_after_5001_newer_distractors(tmp_path):
    agent,provider,_,accept=_knowledge_agent(tmp_path)
    root,_=accept('Kranz leitet das Atlasvorhaben.')
    insert_claims(agent._knowledge,variants(root,5001,'Unabhängige Ablagenotiz'))
    turn=agent.send('Was macht Kranz?')
    assert f'claim:{root.id}' in {item['assertion_id'] for item in turn.context['items']}
    assert any(root.statement in message.get('content','') for message in provider.messages[-1])
    assert turn.context['knowledge_retrieval']['candidates_returned']==1


@pytest.mark.parametrize(('text','query'), [('Straße','STRASSE'),('Łukas','ukas'),('Müller','MÜLLER')])
def test_index_matches_existing_token_normalization(tmp_path,text,query):
    agent,_,_,accept=_knowledge_agent(tmp_path)
    root,_=accept(text)
    found,meta=agent._knowledge.search_context(query)
    assert [item.id for item in found]==[root.id]
    assert not meta['query_truncated']


def test_accent_distractors_cannot_consume_exact_match_cap(tmp_path):
    agent,_,_,accept=_knowledge_agent(tmp_path)
    root,_=accept('Müller')
    insert_claims(agent._knowledge,variants(root,200,'Muller'))
    found,meta=agent._knowledge.search_context('Müller',limit=1)
    assert [item.id for item in found]==[root.id]
    assert not meta['candidates_truncated']


def test_literal_queries_and_sorted_term_cap_are_explicit(tmp_path):
    agent,_,_,accept=_knowledge_agent(tmp_path)
    root,_=accept('Atlas')
    found,_=agent._knowledge.search_context('"Atlas" OR NOT NEAR * ; DROP TABLE knowledge_claims --')
    assert [item.id for item in found]==[root.id]
    assert agent._knowledge.search_context('" * : ()')[0]==[]
    _,meta=agent._knowledge.search_context(' '.join(f'word{n:03}' for n in reversed(range(80))))
    assert meta['query_terms_used']==64
    assert meta['query_terms_total']==80
    assert meta['query_truncated'] is True
    assert agent._knowledge.get(root.id).statement=='Atlas'


def test_matching_invalid_candidates_consume_cap_honestly_in_model_context(tmp_path):
    agent,provider,episodes,accept=_knowledge_agent(tmp_path)
    root,source=accept('Kranz Atlas')
    insert_claims(agent._knowledge,variants(root,130,'Kranz Atlas'))
    episodes.ignore(source.id)
    turn=agent.send('Kranz Atlas?')
    assert turn.context['items']==[]
    metadata=turn.context['knowledge_retrieval']
    assert metadata['candidates_truncated']
    assert metadata['candidates_returned']==128
    assert any('Kandidaten' in m.get('content','') and 'Abwesenheit' in m.get('content','')
               for m in provider.messages[-1])


def test_supported_connections_keep_insert_delete_index_in_sync(tmp_path):
    agent,_,_,accept=_knowledge_agent(tmp_path)
    root,_=accept('Originalnotiz')
    other=ClaimStore(agent._knowledge._path)
    insert_claims(other,variants(root,1,'Querzugriff'))
    assert len(agent._knowledge.search_context('Querzugriff')[0])==1
    with other._conn: other._conn.execute('DELETE FROM knowledge_claims WHERE id=?',('synthetic:0',))
    assert agent._knowledge.search_context('Querzugriff')[0]==[]
    other.close()
    reopened=ClaimStore(agent._knowledge._path)
    assert [c.id for c in reopened.search_context('Originalnotiz')[0]]==[root.id]
    reopened.close()


def test_late_query_term_is_reported_incomplete_to_actual_provider(tmp_path):
    agent, provider, _, accept = _knowledge_agent(tmp_path)
    root, _ = accept('zzrelevant')
    query = ' '.join(f'aaa{n:03}' for n in range(64)) + ' zzrelevant'
    turn = agent.send(query)
    assert not turn.context['items']
    assert turn.context['knowledge_retrieval']['query_truncated']
    assert any('Abwesenheit' in m.get('content', '') for m in provider.messages[-1])
    assert agent._knowledge.get(root.id).statement == 'zzrelevant'


@pytest.mark.parametrize('key', ['id', 'proposal_id', 'rowid'])
def test_replace_rejected_without_destroying_original_index(tmp_path, key):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    root, _ = accept('Originalbeleg')
    connection = agent._knowledge._conn
    columns = [r[1] for r in connection.execute('PRAGMA table_info(knowledge_claims)')]
    row = dict(connection.execute('SELECT * FROM knowledge_claims').fetchone())
    row['id'] = root.id if key == 'id' else 'replacement'
    row['proposal_id'] = root.proposal_id if key == 'proposal_id' else 'replacement-proposal'
    if key == 'rowid':
        columns.append('rowid')
        row['rowid'] = connection.execute('SELECT rowid FROM knowledge_claims').fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match='replacement forbidden'):
        with connection:
            connection.execute('INSERT OR REPLACE INTO knowledge_claims (' + ','.join(columns) +
                               ') VALUES (' + ','.join('?' for _ in columns) + ')',
                               [row[c] for c in columns])
    assert [c.id for c in agent._knowledge.search_context('Originalbeleg')[0]] == [root.id]


def legacy_store(tmp_path):
    from icarus_memory.claims import _MIGRATIONS
    from icarus_memory.migrations import run_migrations
    path = tmp_path / 'legacy.sqlite'
    connection = sqlite3.connect(path)
    run_migrations(connection, store='knowledge_claims', path=path, migrations=_MIGRATIONS[:5])
    return path, connection


def test_v5_backfill_preserves_canonical_document_and_reopen(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path / 'source')
    root, _ = accept('Altbestand Straße')
    path, connection = legacy_store(tmp_path)
    from types import SimpleNamespace
    insert_claims(SimpleNamespace(_conn=connection), [root])
    original = connection.execute('SELECT document FROM knowledge_claims').fetchone()[0]
    connection.close()
    for _ in range(2):
        store = ClaimStore(path)
        assert [c.id for c in store.search_context('STRASSE')[0]] == [root.id]
        assert store._conn.execute('SELECT document FROM knowledge_claims').fetchone()[0] == original
        assert store._conn.execute('PRAGMA user_version').fetchone()[0] == 6
        store.close()


def test_failed_index_migration_rolls_back_version_and_derived_objects(tmp_path, monkeypatch):
    from icarus_memory import claim_index
    from icarus_memory.migrations import MigrationError
    path, connection = legacy_store(tmp_path)
    connection.close()
    monkeypatch.setattr(claim_index, 'FTS', 'CREATE VIRTUAL TABLE claim_search USING missing_fts(tokens)')
    with pytest.raises(MigrationError): ClaimStore(path)
    connection = sqlite3.connect(path)
    assert connection.execute('PRAGMA user_version').fetchone()[0] == 5
    assert connection.execute("SELECT name FROM sqlite_schema WHERE name LIKE 'claim_search%'").fetchall() == []
    connection.close()


@pytest.mark.parametrize('damage', ['view', 'trigger', 'virtual', 'shadow'])
def test_reopen_rejects_corrupt_derived_schema(tmp_path, damage):
    from icarus_memory.migrations import MigrationError
    path = tmp_path / 'claims.sqlite'
    store = ClaimStore(path)
    c = store._conn
    with c:
        if damage == 'view':
            c.execute('DROP VIEW claim_search_content')
            c.execute('CREATE VIEW claim_search_content AS SELECT rowid AS claim_rowid, statement AS tokens FROM knowledge_claims')
        elif damage == 'trigger': c.execute('DROP TRIGGER trg_claim_search_delete')
        elif damage == 'virtual':
            c.execute('DROP TABLE claim_search')
            c.execute("CREATE VIRTUAL TABLE claim_search USING fts5(tokens, content='claim_search_content', content_rowid='claim_rowid')")
        else:
            c.execute('DROP TABLE claim_search_docsize')
            c.execute('CREATE TABLE claim_search_docsize(id INTEGER PRIMARY KEY, sz TEXT)')
    store.close()
    with pytest.raises(MigrationError): ClaimStore(path)


def test_raw_writer_without_normalizer_fails_and_transaction_rollback_keeps_index(tmp_path):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    root, _ = accept('Originalbeleg')
    raw = sqlite3.connect(agent._knowledge._path)
    with pytest.raises(sqlite3.OperationalError, match='memory_tokens_v1'):
        with raw: raw.execute('DELETE FROM knowledge_claims WHERE id=?', (root.id,))
    raw.close()
    with pytest.raises(RuntimeError):
        with agent._knowledge._conn:
            agent._knowledge._conn.execute('DELETE FROM knowledge_claims WHERE id=?', (root.id,))
            raise RuntimeError('rollback')
    assert [c.id for c in agent._knowledge.search_context('Originalbeleg')[0]] == [root.id]


def test_inactive_rows_do_not_consume_candidate_cap_and_status_update_does_not_retokenize(tmp_path):
    from icarus_memory.model import Status
    from icarus_memory.lexical import tokens_v1
    agent, _, _, accept = _knowledge_agent(tmp_path)
    root, _ = accept('Atlasbeleg')
    insert_claims(agent._knowledge, [replace(c, status=Status.RETRACTED)
                                   for c in variants(root, 200, 'Atlasbeleg')])
    found, meta = agent._knowledge.search_context('Atlasbeleg', limit=1)
    assert [c.id for c in found] == [root.id]
    assert not meta['truncated']
    calls = []
    def counted(value):
        calls.append(value)
        return tokens_v1(value)
    agent._knowledge._conn.create_function('memory_tokens_v1', 1, counted, deterministic=True)
    agent._knowledge.retract(root.id, reason='synthetic test')
    assert calls == []
    assert agent._knowledge.search_context('Atlasbeleg')[0] == []


@pytest.mark.parametrize('limit', [0, 129, -1, True, '2'])
def test_candidate_limit_is_strictly_bounded(tmp_path, limit):
    store = ClaimStore(tmp_path / 'claims.sqlite')
    with pytest.raises(ValueError): store.search_context('Atlas', limit=limit)
    store.close()


@pytest.mark.parametrize('alias', ['rowid', '_rowid_', 'oid'])
def test_rowid_update_cannot_replace_another_claim_behind_fts_triggers(tmp_path, alias):
    agent, _, _, accept = _knowledge_agent(tmp_path)
    root, _ = accept('Originalbeleg')
    insert_claims(agent._knowledge, variants(root, 1, 'Zweitbeleg'))
    connection = agent._knowledge._conn
    target = connection.execute('SELECT rowid FROM knowledge_claims WHERE id=?', (root.id,)).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        with connection:
            connection.execute(f'UPDATE OR REPLACE knowledge_claims SET {alias}=? WHERE id=?',
                               (target, 'synthetic:0'))
    assert [c.id for c in agent._knowledge.search_context('Originalbeleg')[0]] == [root.id]
    assert len(agent._knowledge.search_context('Zweitbeleg')[0]) == 1
