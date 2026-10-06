# Mail workflow and memory care implementation plan

> **For agentic workers:** Use `superpowers:executing-plans` task by task. Checkbox steps track implementation and verification.

**Goal:** Understand one mail at a glance, prepare an evidenced task with fewer clicks, and refresh outdated memory interpretations in existing bounded background work.

**Architecture:** Extend the existing mail reader, local-model roles, digest-bound task action and working-memory worker. Selected exact source passages provide a compact overview; model output never becomes source evidence. An analysis-version marker makes existing interpretations eligible for refresh without blanket reprocessing.

**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript, local Ollama, Docker and the native Mac launcher.

**Spec:** `docs/superpowers/specs/2026-10-06-mail-workflow-memory-care.md`

## Global constraints

- Existing originals and confirmed claims remain unchanged; no production test-source insertion or data reset.
- All model work positively verified local; use installed bounded Qwen profile, no new dependencies or model download.
- Original quote must occur literally in the received body; at most three overview quotes and three task suggestions.
- Existing task `source_digest` contract is preserved; sending/calendar changes retain existing approval flow.
- UI request cancellation and account/source/provider changes hide stale output.
- Tests/builds local, `[skip ci]` commits; public release and Mac installation reported separately.

## Review focus

- UID/account/source changes during inference: no stale overview or task prefill.
- Model prompt injection or invented quote: no tool calls, no unsupported output accepted.
- Concurrent opens/retries: bounded cache and inference deduplication; no misleading old result.
- Existing memory interpretation fails to refresh: original remains intact, retry respects backoff and dismissal.
- Legacy migration and unchanged analysis version: no blanket costly reprocessing or lost searchable references.

## Task 1: Local mail briefing API

Files: new `sidecar/icarus_memory/mail_briefing.py`, `sidecar/tests/test_mail_briefing.py`; register route in `server.py`.

Interface: `POST /api/v1/messages/{uid}/briefing` with optional `{refresh: bool}` returns `{uid, available, status, detail, source_digest, quotes: string[], tasks: {title, quote}[], truncated}`. `source_digest` comes from `mail_task_suggestions.source_digest`; exact-message fingerprint additionally guards cached output. Status is `ready`, `empty`, `unavailable` or `incomplete`. Cache maximum 64 messages in memory, no new stored episodes. Selected local `frage` provider; bounded structured output and exact original validation. Re-read current message and confirm mail/provider identity before returning an inferred result. No silent remote fallback.

- [ ] Add meaningful route/parser tests; run them red before implementation.
- [ ] Implement native structured completion, source guards, bounded process cache and duplicate-request protection.
- [ ] Pass tests for valid/empty/truncated/malformed/forged quotes, cache invalidation, model/account change and concurrent requests.

## Task 2: Compact mail workflow

Files: new `MailBriefing.tsx/.css`; existing `MailReader.tsx`, `MailTaskForm.tsx`, `api.ts`, focused frontend contracts.

Interface: briefing loads once on mail open, with visible local-analysis progress, cancellation and retry. Selecting a task calls parent with `{title,quote,source_digest}`; existing form opens and prefills that evidence. No inferred deadline/person/project fields. Original mail displayed in a disclosure that can be opened immediately. Existing own drafts and reply approvals preserved.

- [ ] Add contract tests before UI changes.
- [ ] Implement load/abort/stale generation guards and task prefill, retain original and sender/date visible.
- [ ] Typecheck, frontend tests/build and a real rendered interaction test: selection opens form without saving; mail switch cannot show previous briefing.

## Task 3: Versioned memory upkeep

Files: `working_memory_store.py`, `working_memory_worker.py` if required, `episodes.py` migration, working-memory/migration tests.

Interface: explicit `ANALYSIS_VERSION=1` recorded with current interpretation status. Migration stamps existing entries with version 1. Same-source older-version complete results are eligible for existing bounded `pending()`/`commit()` refresh. Original excerpts stay readable until successful atomic replacement. Fingerprint changes retain existing source-withdrawal semantics; dismissed results stay dismissed; failed refresh observes retry backoff. Progress/source status must reflect outdated interpretation rather than claim current completion.

- [ ] Write red tests for old-version selection/replacement/failure and unchanged-version no-op.
- [ ] Add migration and bounded refresh logic without changing original episodes or confirmed claims.
- [ ] Pass lifecycle, backoff, withdrawal, migration, progress and candidate-signature tests.

## Task 4: Review and Mac acceptance

- [ ] Inspect final diff independently; fix actionable findings and run affected tests.
- [ ] Run full backend and UI suites, frontend production build and Mac launcher checks once on final code.
- [ ] Build versioned candidate; preserve current volume/settings before any local installation.
- [ ] Verify rendered briefing, original disclosure and task prefill on a fictional source; verify real read-only mail overview on the Mac if permitted and available.
- [ ] Record actual results and open limits, commit/push a reviewable PR and attach it. Prepare normal release/updater path without claiming an unpublished candidate is downloadable.
