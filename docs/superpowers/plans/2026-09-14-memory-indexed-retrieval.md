# M2: Older relevant evidence remains retrievable

Goal: eliminate reproduced recency starvation before the Agent evaluates relevance.
This is the next bounded implementation after M1 evidence validity is reviewed.
Use superpowers:subagent-driven-development; one implementation worker at a time.
Existing user authorization covers local implementation, verified integration and deployment.
No model downloads, private data reads, cloud exports or new automatic knowledge authority.

## Reproduction and acceptance

A real confirmed claim with its original source answers a synthetic Kranz question.
After 5001 newer unrelated claim rows are added, the same actual Agent provider input
loses that still-valid claim because context_candidates takes newest 5000 first.
Regression must prove the old source reaches actual provider input after the change,
not merely a search helper. Synthetic distractor rows are a retrieval fixture, not a
5001-source ingestion or semantic benchmark.

## Design

Keep canonical claims and current evidence validation. Add derived SQLite FTS5 postings
using identical normalized tokens as existing context._terms. Move normalization to a
small shared module if needed, retaining context._terms compatibility; do not broaden
language/token semantics in this patch. Index tokens from statement, predicate and value.
Register versioned memory_tokens_v1 SQLite function on every ClaimStore connection before
migrations. External-content VIEW computes canonical tokens, virtual FTS5 table uses
unicode61 remove_diacritics 0. Maintenance triggers use identical normalization in the
same transaction; initial migration rebuilds existing rows. A different derived design
is acceptable only with equivalent exact-token semantics and transactional evidence.

Preserve all immutability guards and strict schema verification. Verify view SQL,
virtual table options, explicit FTS shadow tables, maintenance triggers and normalizer
version. Missing FTS or malformed migration fails visibly and rolls back. Do not silently
fall back to newest-only behavior. Raw unsupported SQLite writer connections lacking
normalizer should fail, not corrupt index; document supported connection requirement.

Query only sorted bounded normalized literal tokens, individually quoted in MATCH and
joined OR. No interpolation of raw operators or SQL. Empty query yields no candidates.
Join canonical active claims before candidate cap. BM25 may select bounded candidates;
existing Agent overlap/time/id ranking remains the final ranking unless separately
justified. Keep evidence/source-state/temporal/ancestry checks after candidate selection.
Expose query/candidate truncation through existing context metadata if feasible without
breaking callers; do not pretend bounded search is complete recall. Avoid 5000 expensive
lineage checks per question; choose/document candidate budget from measured fixture.

## Tests and proof

- [ ] Actual Agent input finds old relevant source past 5000 unrelated newer rows.
- [ ] Valid legacy v5 backfill, reopen, cross-connection supported inserts and deletion.
- [ ] Wrong view/tokenizer/missing triggers fail; migration rollback and existing guards remain.
- [ ] Straße/STRASSE, current Łukas/ukas behavior, umlauts and accent distractors at cap.
- [ ] Literal operators/quotes/empty input; deterministic term/ranking caps.
- [ ] Excluded/retracted/expired/damaged and transitive bad evidence remain unavailable.
- [ ] Focused/full supported Python suites and Docker build; index timings separate from model.
- [ ] Independent immutable-diff review, fixes, authorized integration.

## Boundaries

This is lexical candidate retrieval, not semantic hierarchy, alias resolution, autonomous
identity merge, full deletion/backup forgetting, model qualification or scale guarantee.
Index postings are retained derived data and must later follow deletion policy; they are
not a privacy erasure mechanism. Official SQLite FTS5 reference:
https://www.sqlite.org/fts5.html (external content, triggers, rebuild, unicode tokenizer).
