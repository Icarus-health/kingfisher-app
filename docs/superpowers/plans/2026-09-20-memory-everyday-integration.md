# Everyday memory implementation plan

> **For agentic workers:** Use superpowers:executing-plans. Execute inline, then request one independent whole-branch review. The user explicitly authorized all six steps and the existing local verification/merge/update workflow.

**Goal:** Connect source-bound memory to everyday conversations, close restore reauthorization risks, improve retrieval and interpretation qualification, extend reversible scoped preferences, and establish an honest everyday acceptance record.

**Architecture:** Keep canonical EpisodeStore, ClaimStore and SelfModelStore. Conversation routing selects bounded read-only evidence paths; restoring historical data cannot grant current operational authority. Derived search and profile views are rebuilt/revalidated against originals. No second knowledge database or automatic external action.

**Tech Stack:** Python 3.10+, FastAPI, SQLite, existing React UI, Docker and installed local models.

**Spec:** docs/release/MEMORY-FIRST-ROADMAP.md; docs/architecture/kingfisher-memory-sicherheitsvertrag-v0.1.md; docs/evaluations/memory-quality/audits/2026-09-14/restore-safety-audit.md; user's six-step approval on 2026-09-20.

## Global constraints

- Source withdrawal, exact provenance, scoped identity, local-only evidence, no implicit authority from imported text.
- Preserve existing private application, backups, keys, user drafts and rollback data.
- Synthetic tests first. No new model download, paid model API, changed billing or forged CI status.
- Changes need observable tests, full local suites, independent review and real API/container acceptance before merge.
- Multi-day usefulness and independent human semantic acceptance cannot be declared complete from synthetic tests.

## Review focus

1. A casual or imperative message must not be silently treated as evidence selection; default routing and retries preserve the selected capability boundary.
2. A backup from before withdrawal must not reauthorize a source, connector, stored rule or scheduled worker, including old images and reopened restored containers.
3. A search index can be incomplete/stale/unavailable; fresh canonical validation and bounded fallback remain required.
4. A hypothetical, quoted statement or proposal must not become a completed action or confirmed personal preference.
5. Conflicting specific preferences, source withdrawal, provider switch and clock expiry must invalidate effective profile selection and history.

## Task 1: Conversation integration

Files: new `sidecar/icarus_memory/memory_routing.py`; existing `server.py`, `test_memory_clarification.py`; new `test_memory_routing.py`.
Interface: `route(message, previous_context, *, new_question=False) -> str` returns `chat`, `memory_evidence`, or `memory_followup`; no model or store access. The server persists the resolved mode for retries and supplies only the last same-conversation context.
- [ ] Add failing API tests for default memory question, pending selection, unrelated new question, explicit action/remember command, remote provider, retry.
- [ ] Implement conservative question routing using existing evidence and calendar paths; make limitations visible and keep explicit chat override.
- [ ] Verify focused tests and full suite; record and commit.

## Task 2: Restore and forgetting boundary

Files: `backup.py`, `recovery_bundle.py`, `server.py`, `scheduler.py`, `agent.py`, recovery launch scripts; new isolated restore-state/inspection implementation and regression tests.
- [ ] Reproduce old-backup reauthorization and ordinary-launch behavior with synthetic data.
- [ ] Preserve historical recovery while requiring inspection before operational use; enforce before constructing providers/connectors/workers, not only at HTTP display.
- [ ] Cover full/legacy/in-place restore, reopen, failure, old image, concurrent work, and preservation of originals.
- [ ] Verify a real isolated recovery and restart with zero model/connector/action calls; commit.

## Task 3: Relevant retrieval

Files: existing search/embedding modules and Agent integration; new live-index invalidation and acceptance tests.
- [ ] Inspect the current bounded snapshot contract and identify the smallest safe runtime update path.
- [ ] Test changed/retracted/expired sources, missing model, capped budgets and irrelevant matches before implementation.
- [ ] Integrate incremental or revision-bound retrieval without making stale index entries authoritative; retain lexical fallback.
- [ ] Run an independent expanded German development collection and growth checks; record false positives and incomplete coverage; commit.

## Task 4: Meaning and state qualification

Files: existing claim/proposal extraction and evidence-answer machinery; synthetic interpretation cases/runner.
- [ ] Test quotation, hypothetical, request, decision, explicit completion, denial and unknown status with actor/time/source fields.
- [ ] Fix demonstrated failures at their actual stage; do not invent a general semantic guarantee from a keyword detector.
- [ ] Run existing local provider with frozen development cases and disclose timeouts and unsupported classes; commit qualified behavior and results.

## Task 5: Working profile

Files: existing SelfModel preferences, mail_style, Agent/context and profile routes/UI; scoped profile tests.
- [ ] Test explicit global/situational preferences, current-turn override, conflict, correction, expiry and withdrawal.
- [ ] Store closed structured preferences in existing assertions; resolve specificity without random conflict winners or executable free-text rules.
- [ ] Expose current rules, provenance and reversible correction through existing profile surfaces; verify actual flow and commit.

## Task 6: Everyday acceptance and delivery

Files: isolated acceptance scripts, release evidence and user report.
- [ ] Full macOS and Linux Python suites, frontend/schema/assets and independent review; fix blockers.
- [ ] Real conversation/import/correction/restart/restore/profile flows with synthetic data; measure cold/warm and under-load latency separately.
- [ ] Merge tested increments and update private Mac app only after backup and isolated data-copy checks; preserve rollback.
- [ ] Prepare concrete multi-day/user acceptance cases and state what requires elapsed use or user judgment. Do not mark that gate passed prematurely.

## Execution ledger

2026-09-20: Baseline main ce001f0, branch feat/memory-everyday-integration; only two unrelated untracked M3 drafts, preserved.
Ruling: execute the already-approved roadmap inline without asking for repeated design/merge permission; record bounded implementation decisions as code inspection resolves them. Human daily-use acceptance remains a separate unsatisfied gate until actual evidence exists.

Task 1: implemented default conservative conversation routing, persisted resolved retry mode, explicit chat override. 42 focused tests passed; first full run 1,954 tests plus four calendar subtests passed. Final immutable whole-branch run still required.
Task 2: implemented persistent inspection markers, pre-bootstrap inspection app, shared request/worker/Agent boundary, snapshot/legacy/bundle coverage, version-pinned launcher capability checks and old-container refusal. 55 recovery regressions and 30 boundary/scheduler tests passed, including concurrent HTTP drain. Actual container proof still required.
Ruling: historical recovery has no blanket activation button. Unknown later revocations cannot be reconstructed from an old snapshot; inspection plus explicit reintroduction through current intake is the supported path. Original data/keys/settings remain preserved. This closes renewed authority, but is not physical erasure of existing backups.

2026-09-20 final implementation evidence: see `docs/release/MEMORY-EVERYDAY-ACCEPTANCE-2026-09-20.md` for precise per-step status. Backend 4e98b41: macOS 1,993 tests plus four subtests; Linux 1,970; independent review 135 focused tests, no blockers. Final e8e3ffc only adjusts existing UI spacing; React build and real desktop save/reload/revoke flow passed. Real default conversation → restart → clarification → withdrawal → old restore → restart stayed source-bound/inspection-only.

Tasks 1, 2 and 5 implemented and technically verified. Tasks 3 and 4 have bounded implementation and frozen local diagnostic evidence, **not broad relevance/semantic qualification**: 15/22 exact semantic retrieval, 6/8 schema-valid evidence answers, one safe fallback and one miss. Semantic runtime remains opt-in/off. 600-row growth check truthfully reports partial (128 validated cached rows). Task 6 technical acceptance passed; merge/private update follows this ledger. Multi-day owner use, independent semantic holdout, broad extraction and acceptable real-model latency remain open; mobile shell was already fixed-width and is not qualified. No assertion that all six product acceptance gates have passed.
