# Correct a pending task title without creating a task — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct an explicitly selected, source-bound pending task title while retaining its original evidence and decision history.

**Architecture:** Add an immutable pending successor and supersede the original in one proposal transaction. The existing application lock and episode transaction protect source-currentness through commit. No reanalysis, global version bump, task creation or source rewrite. Legacy unbound candidates fail explicitly.

**Tech Stack:** Existing Python/FastAPI/SQLite/Pydantic/pytest.

**Spec:** docs/superpowers/specs/2026-11-02-modular-chief-of-staff-design.md, Phase A item4. The user authorized targeted fixes of old incorrect proposals before broader import.

## Global constraints

- Only title correction for existing context-bound TASK proposals. No new source or task; no model request or paid call.
- Request carries expected old statement, source episode ID, digest, task_context and corrected title. Reject extra fields.
- Exact original evidence, source time and context retained. Preserve accepted/rejected decisions and partial-acceptance task crash gaps.
- Add optional `task_amends` proposal JSON lineage, only for TASK successors; no schema migration. Do not overload assertion `supersedes` or generic `propose(TASK)` fingerprints.
- Use deterministic revision ID/fingerprint bound to predecessor and title, atomically supersede and insert. Same retry returns existing successor with its current decision intact; competing correction fails. No positive semantic review marker inherited.
- Validate current source context/head/metadata/digest/exact quote with source transaction held through proposal commit. A correction is an unconfirmed proposal, never a verified fact.
- Existing quote/context canonical ID remains a tombstone; normal detector reruns cannot resurrect obsolete wording.
- Keep communication-rule retirement as a separately explicit existing reject operation after source QA. Bulk import remains paused.

### Task1 — Atomic source-bound amendment and API

Files: `sidecar/icarus_memory/proposals.py`, `task_candidates.py`, `server.py`; tests `sidecar/tests/test_task_candidate_amendment.py`.

- [x] Write failing behavior tests for optional-detail title correction, original+successor history, no task/source change, same-title idempotence after restart/terminal decision, competing edits, protected accepted/rejected/legacy/crash-gap cases, stale digest/context/head/contacts, invalid/invented title, source revoke, separate equal-title sources, rollback after insert fault, no auto acceptance and normal detector rerun.
- [x] Verify RED against existing implementation.
- [x] Implement bounded optional lineage serialization, atomic store primitive and guarded service. Add POST `/api/v1/task-candidates/{id}/amend` with strict request and409 conflict/422 malformed-input behavior. Keep unrelated APIs unchanged.
- [x] Run focused tests and existing candidate/review/retention/proposal/page/automatic-acceptance suites. Inspect diff and obtain independent review; reproduce and fix important findings in one wave.
- [ ] Record evidence. Deliver by normal release after the already frozen1.0.40, then apply only root-reviewed repairs to the previously approved source sample. Confirm originals, active tasks and import pause unchanged in native readback.

## Deliberate limits

No new UI in this slice. No automatic full-source refresh; no legacy maintenance ledger. A later general maintenance worker can use a separately authorized source-scoped interface. UI tests and the complete application regression are rerun only where the final delta warrants them; independent semantic source QA remains separate from unit-test evidence.
