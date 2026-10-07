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

- [x] Add meaningful route/parser tests; run them red before implementation.
- [x] Implement native structured completion, source guards, bounded process cache and duplicate-request protection.
- [x] Pass tests for valid/empty/truncated/malformed/forged quotes, cache invalidation, model/account change and concurrent requests.

## Task 2: Compact mail workflow

Files: new `MailBriefing.tsx/.css`; existing `MailReader.tsx`, `MailTaskForm.tsx`, `api.ts`, focused frontend contracts.

Interface: briefing loads once on mail open, with visible local-analysis progress, cancellation and retry. Selecting a task calls parent with `{title,quote,source_digest}`; existing form opens and prefills that evidence. No inferred deadline/person/project fields. Original mail displayed in a disclosure that can be opened immediately. Existing own drafts and reply approvals preserved.

- [x] Add contract tests before UI changes.
- [x] Implement load/abort/stale generation guards and task prefill, retain original and sender/date visible.
- [x] Typecheck and frontend tests/build.
- [x] Real rendered interaction test: selection opens form without saving; mail switch cannot show previous briefing.

## Task 3: Versioned memory upkeep

Files: `working_memory_store.py`, `working_memory_worker.py` if required, `episodes.py` migration, working-memory/migration tests.

Interface: explicit `ANALYSIS_VERSION=1` recorded with current interpretation status. Migration stamps existing entries with version 1. Same-source older-version complete results are eligible for existing bounded `pending()`/`commit()` refresh. Original excerpts stay readable until successful atomic replacement. Fingerprint changes retain existing source-withdrawal semantics; dismissed results stay dismissed; failed refresh observes retry backoff. Progress/source status must reflect outdated interpretation rather than claim current completion.

- [x] Write red tests for old-version selection/replacement/failure and unchanged-version no-op.
- [x] Add migration and bounded refresh logic without changing original episodes or confirmed claims.
- [x] Pass lifecycle, backoff, withdrawal, migration, progress and candidate-signature tests.

## Task 4: Review and Mac acceptance

- [x] Inspect final diff independently; fix actionable findings and run affected tests.
- [x] Run full backend regression on the main implementation, full UI suite/build and Mac launcher checks; rerun affected mail tests after isolated final corrections. Exact commit and scope recorded below.
- [x] Build versioned isolated candidate. No production installation performed; production backup remains a prerequisite for that later step.
- [x] Verify rendered briefing, original disclosure and task prefill on fictional sources in the native Mac app. Real-mail checks deferred: no production accounts used.
- [x] Record actual results and open limits, commit/push a reviewable PR and attach it. Prepare normal release/updater path without claiming an unpublished candidate is downloadable.

## Execution ledger

- Code baseline: `1791565`; complete backend regression: 4,788 passed, 1 skipped. Final cache race correction: `7a86237`, reproduced red then green. Later prompt clarification excludes pure greetings/signatures; final affected mail tests: 47 passed. The complete suite was not repeated after these isolated mail changes.
- Frontend: 282 passed; typecheck and production build passed. Known large-bundle warning remains. These are source-contract tests, not a rendered DOM acceptance result.
- Mac launcher: 26 passed, 1 skipped; arm64 native test window built and signed. No new native production code in this patch.
- Independent review found stale analyses counted as complete and excluded from background priority. Corrected classification, prioritization, retry handling and completion counts; targeted regression tests passed. The final cache-only delta also received independent review with no further actionable finding.
- Local Qwen 9B/32k probe on fictional text preserved both the Friday request and the complete hotel approval condition; final response 2.72 seconds, identical cached response, zero tasks written. An isolated Docker candidate also answered correctly. Neither check proves comprehensive real-mail accuracy.
- Native Mac acceptance completed on 2026-10-07 after the test-app grant: original disclosure, task prefill/edit protection, explicit save with null deadline/project/waiting, cancellation and mail switch verified on fictional sources. Empty-date hint verified in the actual window. Earlier access denial was not bypassed.
- Production container, originals and credentials were not changed. Release publication, manifest/version update and normal updater installation remain separate delivery steps after acceptance.

### Decisions

- Select numeric IDs of full source paragraphs instead of asking the model to invent quote text. The code supplies the original excerpts. At most 8,000 input characters and 1,200 characters per complete paragraph; skipped material produces an explicit incomplete state.
- Partial overviews can display valid excerpts with a warning; task proposals are actionable only for a ready, digest-matching response. Retry explicitly bypasses the cache. Edited/saved task forms cannot be overwritten by another overview proposal.
- Analysis-version migration stamps existing entries at version 1. No immediate blanket reprocessing, timer-based full rescan or changes to confirmed claims. Future interpretation-rule changes must intentionally advance the version and use existing bounded background processing.

**Run record:** `docs/runs/mail-workflow-memory-care-20261006/README.md`. Open checkboxes are intentionally not presented as completed.

**Draft PR:** https://github.com/Icarus-health/kingfisher-app/pull/3. Final Docker candidate on code `73f5478`: fictional-mail API response in 3.85 seconds, both meaningful original passages, zero created tasks. Native UI acceptance completed on 2026-10-07; public release remains open.

### 2026-10-07 final corrections

Short task evidence is kept as an overview passage but excluded from task proposals below the existing eight-character save minimum. Integration regression and exact boundary passed. Current affected backend set: 76 passed; frontend: 284 passed and production build passed. Independent review accepted the final fix. Cloud preparation requested for both Mistral and OpenRouter, without activation or paid calls; documented separately in `docs/58-cloud-vorbereitung-mistral-openrouter.md`.
