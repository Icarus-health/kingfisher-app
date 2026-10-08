# Dauerhafter abgeleiteter Vektorcache: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline; one independent review after the completed storage component. Steps use checkbox syntax.

**Goal:** Persist local source vectors in a bounded, source-validated, independently testable cache, without activating an unfinished search path.

**Architecture:** sqlite-vec 0.1.9 in a separate derived SQLite file per EpisodeStore; original database attached read-only. Store references and vectors only. Stable keyset backfill, atomic commit/cursor, model epoch isolation, resolve before results. Background/model/API/UI integration follows as a separate next plan; this component alone is not a finished memory feature or a Mac upgrade.

**Tech Stack:** Python 3.10+, SQLite, sqlite-vec 0.1.9, pytest.

**Spec:** docs/superpowers/specs/2026-10-08-durable-memory-search.md; measured evidence docs/runs/2026-10-08-vector-store-fitness/README.md.

## Constraints and files

No original schema migration, source copying, query-time source embedding, Python full-vector scan, global cache, new daemon, cloud calls or CI reruns. Existing opt-in runtime stays unchanged until worker/integration checks pass. Source snapshots are resolved at commit and result boundaries; structural index coverage does not certify semantic answerability. Preserve unrelated untracked files. Use existing worktree and publish only explicit files.

Create `working_memory_semantic_index.py` and focused real-store tests. Pin sqlite-vec and include upstream MIT notice in package. Follow-up integration must bind exact local embedding role, current source inventory signature, scheduler gates, cache lifecycle, restore boundary, API and UI progress.

## Task 1: durable storage and identity

Produces `DurableSemanticIndex(episodes, model_key)` with `close()`, `pending(limit)` returning immutable `IndexBatch(refs, token, cursor, ceiling)`, `commit(batch, vectors)`, `coverage()` and `search(vector, limit, threshold)`. Cache is per database under `.search-cache`; sources attached read-only; reject in-memory store, symlink, source-file replacement, invalid model key. Model change atomically resets derived data and invalidates stale handles/batches. Dimension change with same model is an error, not a destructive reset.

- [x] Write failing tests for reopening/reuse, source DB extension-free integrity, model separation and batch rollback.
- [x] Run RED; implement minimal cache, exact native KNN, version/format guards and finite normalized vectors.
- [x] GREEN targeted new file plus existing store/semantic tests, commit with skip ci.

## Task 2: fair bounded backfill and withdrawal

Stable SQL insertion-position keyset with persisted finite cycle ceiling, no OFFSET/newest window. One pending batch <=64, no cursor advancement until commit/failure; repeat after restart. Failures advance cursor with 300-second per-item cooldown. Before persisting, resolve against live store under source lock; no external/model call in this module. Revalidate hits after native search; stale rejected hits mark result partial. Counts join current eligible source items; ignored/archived/non-head/conversation-lookup rows are excluded. Old stale rows can be pruned in bounded groups. Successful progress survives a later error.

- [x] RED: old reference beyond2048, constant new arrivals, ignore/change during batch, stale concurrent batch/model handles, malformed embeddings and cooldown.
- [x] Implement fair cursor and atomic vector/reference/progress transaction; source generation/digest binding and bounded prune.
- [x] GREEN focused suites; commit.

## Task 3: failure boundaries and independent review

- [x] RED/GREEN: corrupt cache fails closed without changing originals, read-only attached DB, source replacement forces reopen, no plaintext source storage, no cross-store leakage, persisted delete and missed candidates report partial.
- [x] Inspect diff; run affected suites once, package and Linux arm64 smoke test. Record actual commands/results and remaining integration work.
- [x] Fresh independent review of storage branch; fix important findings with failing tests first. No automatic production activation, Mac replacement or claim of complete memory from this component.

## Review Focus

Concurrent cache handles/model reset; source replacement during read; ignored source before prune; failed transaction losing cursor or existing vectors; dimension/model mismatch; incomplete/corrupt candidates masquerading as complete; bounded scheduling starvation; license inclusion and optional loader behavior. Confirm originals open and back up without extension. SQL counts certify classified eligible keys only; final answer validity continues through resolve and later integration.
