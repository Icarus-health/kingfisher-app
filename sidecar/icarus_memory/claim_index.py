"""Derived lexical candidates; canonical claims and evidence remain authoritative."""
import sqlite3
from .lexical import terms_v1, tokens_v1
from .word_forms import alternatives, synonym_alternatives
from .migrations import _normalized_sql

CANDIDATE_LIMIT = 128
TERM_LIMIT = 64
VIEW = """CREATE VIEW claim_search_content AS
SELECT rowid AS claim_rowid,
 memory_tokens_v1(statement || ' ' || predicate || ' ' || value) AS tokens
FROM knowledge_claims"""
FTS = """CREATE VIRTUAL TABLE claim_search USING fts5(
 tokens, content='claim_search_content', content_rowid='claim_rowid',
 tokenize='unicode61 remove_diacritics 0')"""
TABLES = {'claim_search': {'tokens'}, 'claim_search_data': {'id', 'block'},
          'claim_search_idx': {'segid', 'term', 'pgno'},
          'claim_search_docsize': {'id', 'sz'}, 'claim_search_config': {'k', 'v'}}
PRIMARY_KEYS = {'claim_search': set(), 'claim_search_data': {'id'},
                'claim_search_idx': {'segid', 'term'},
                'claim_search_docsize': {'id'}, 'claim_search_config': {'k'}}
_OLD = "memory_tokens_v1(OLD.statement || ' ' || OLD.predicate || ' ' || OLD.value)"
_NEW = "memory_tokens_v1(NEW.statement || ' ' || NEW.predicate || ' ' || NEW.value)"
TRIGGERS = {
    'trg_claims_rowid_immutable': """CREATE TRIGGER trg_claims_rowid_immutable
BEFORE UPDATE ON knowledge_claims WHEN NEW.rowid != OLD.rowid
BEGIN SELECT RAISE(ABORT,'claim rowid is immutable'); END""",
    'trg_claim_search_insert': f"""CREATE TRIGGER trg_claim_search_insert
AFTER INSERT ON knowledge_claims BEGIN
INSERT INTO claim_search(rowid,tokens) VALUES(NEW.rowid,{_NEW}); END""",
    'trg_claim_search_delete': f"""CREATE TRIGGER trg_claim_search_delete
AFTER DELETE ON knowledge_claims BEGIN
INSERT INTO claim_search(claim_search,rowid,tokens) VALUES('delete',OLD.rowid,{_OLD}); END""",
    'trg_claim_search_update': f"""CREATE TRIGGER trg_claim_search_update
AFTER UPDATE OF statement,predicate,value,rowid ON knowledge_claims BEGIN
INSERT INTO claim_search(claim_search,rowid,tokens) VALUES('delete',OLD.rowid,{_OLD});
INSERT INTO claim_search(rowid,tokens) VALUES(NEW.rowid,{_NEW}); END""",
    'trg_claims_no_replace': """CREATE TRIGGER trg_claims_no_replace
BEFORE INSERT ON knowledge_claims WHEN EXISTS(
SELECT 1 FROM knowledge_claims WHERE id=NEW.id OR proposal_id=NEW.proposal_id
OR rowid=NEW.rowid) BEGIN SELECT RAISE(ABORT,'claim replacement forbidden'); END""",
}


def register(connection):
    connection.create_function('memory_tokens_v1', 1, tokens_v1, deterministic=True)


def install(connection):
    connection.execute(VIEW)
    connection.execute(FTS)
    for sql in TRIGGERS.values():
        connection.execute(sql)
    connection.execute("INSERT INTO claim_search(claim_search) VALUES('rebuild')")


SHADOW_SQL = {
    'claim_search_data': "CREATE TABLE 'claim_search_data'(id INTEGER PRIMARY KEY, block BLOB)",
    'claim_search_idx': "CREATE TABLE 'claim_search_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID",
    'claim_search_docsize': "CREATE TABLE 'claim_search_docsize'(id INTEGER PRIMARY KEY, sz BLOB)",
    'claim_search_config': "CREATE TABLE 'claim_search_config'(k PRIMARY KEY, v) WITHOUT ROWID",
}


def verify(connection):
    views = dict(connection.execute("SELECT name,sql FROM sqlite_schema WHERE type='view'"))
    if set(views) != {'claim_search_content'} or _normalized_sql(views['claim_search_content']) != _normalized_sql(VIEW):
        raise sqlite3.DatabaseError('claim search view differs from v1 contract')
    actual = connection.execute("SELECT sql FROM sqlite_schema WHERE name='claim_search'").fetchone()
    if actual is None or _normalized_sql(actual[0]) != _normalized_sql(FTS):
        raise sqlite3.DatabaseError('claim search FTS configuration differs')
    for name, expected in SHADOW_SQL.items():
        actual = connection.execute('SELECT sql FROM sqlite_schema WHERE name=?', (name,)).fetchone()
        if actual is None or _normalized_sql(actual[0]) != _normalized_sql(expected):
            raise sqlite3.DatabaseError(f'claim search shadow schema differs: {name}')


def search(connection, query, limit=CANDIDATE_LIMIT):
    if type(limit) is not int or not 1 <= limit <= CANDIDATE_LIMIT:
        raise ValueError('candidate limit must be an integer from 1 to 128')
    all_terms = sorted(terms_v1(query))
    terms = all_terms[:TERM_LIMIT]
    # Candidate search must expand the same alternatives the later context
    # selection in agent.py recognizes (word forms and the closed noun
    # synonyms), or a synonym-only match would never reach that step.
    word_forms = set().union(*(alternatives(term) for term in terms)) - set(terms)
    synonyms = (set().union(*(synonym_alternatives(term) for term in terms))
                - set(terms) - word_forms)
    expanded = sorted(word_forms | synonyms)
    metadata = dict(query_terms_total=len(all_terms), query_terms_used=len(terms),
                    query_truncated=len(all_terms)>TERM_LIMIT, candidate_limit=limit,
                    candidates_returned=0, candidates_truncated=False,
                    selection_truncated=False, truncated=len(all_terms)>TERM_LIMIT,
                    word_form_version=1, word_forms_used=len(word_forms), word_form_candidates=0,
                    synonym_version=1, synonyms_used=len(synonyms), synonym_candidates=0)
    if not terms:
        return [], metadata
    def expression(words):
        return ' OR '.join('"' + term.replace('"', '""') + '"' for term in words)

    def find(match, count):
        return connection.execute("""SELECT c.document,
c.statement || ' ' || c.predicate || ' ' || c.value AS search_text FROM claim_search
JOIN knowledge_claims c ON c.rowid=claim_search.rowid
WHERE claim_search MATCH ? AND c.status='active'
ORDER BY bm25(claim_search), c.created_at DESC, c.id LIMIT ?""", (match, count)).fetchall()

    exact = expression(terms)
    rows = find(exact, limit + 1)
    if expanded and len(rows) <= limit:
        # Literal hits own the budget first. NOT removes duplicate candidates;
        # the extra row still exposes truncation when no output slots remain.
        additional = find('(' + expression(expanded) + ') NOT (' + exact + ')',
                          limit + 1 - len(rows))
        # Nur die tatsächlich zurückgegebenen Erweiterungskandidaten zählen,
        # nicht die zusätzliche Zeile zur Erkennung eines abgeschnittenen Ergebnisses.
        # Ein Kandidat kann über beide Arten passen; die Zähler sind nicht disjunkt.
        for row in additional[:limit - len(rows)]:
            matched = terms_v1(row['search_text'])
            metadata['word_form_candidates'] += bool(word_forms & matched)
            metadata['synonym_candidates'] += bool(synonyms & matched)
        rows.extend(additional)
    metadata.update(candidates_returned=min(len(rows),limit), candidates_truncated=len(rows)>limit,
                    truncated=metadata['query_truncated'] or len(rows)>limit)
    return rows[:limit], metadata
