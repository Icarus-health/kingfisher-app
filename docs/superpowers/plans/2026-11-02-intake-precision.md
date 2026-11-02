# Intake precision before modular execution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep optional mail details optional and communication constraints out of standalone tasks; guide topical classification by substantive content.

**Architecture:** Preserve the existing extractor, whole-mail semantic reviewer and source-bound proposal stores. Add a narrow shared modality validator, a closed reviewer category and shared topic guidance. Prompt behavior requires separate live-model evidence.

**Tech Stack:** Existing Python 3.10+/FastAPI/Pydantic/pytest, existing local Ollama provider.

**Spec:** docs/superpowers/specs/2026-11-02-modular-chief-of-staff-design.md, Phase A.

## Global Constraints

- No original-source rewrite, schema migration, active-task creation, implicit identity merge, global reanalysis or bulk-import resume.
- No new paid API request or permanent model-role change.
- German optional cues: `idealerweise`, `vorzugsweise`, `nach Möglichkeit`, `wenn möglich`; shared validation through `hard_details_supported(title, quote)`.
- Prospective repair: no analysis-version bump or global reanalysis; prior saved proposals retain existing fresh acceptance gates.
- `communication_constraint` is an additional closed semantic-review kind; operational waiting and negative duties keep existing review paths.
- Keep existing quote/currentness/ownership gates and all existing context/time/output budgets.

## Review Focus

- Optional detail about a different object must not erase an unrelated mandatory task.
- Preserving the word `idealerweise` about another detail must not excuse turning PDF into a mandatory condition.
- Waiting for a release and a confidentiality prohibition must not be rejected by a blanket negative-word rule.
- Real substantive newsletters and mixed-source categories remain supported.
- Source withdrawal or correction must still invalidate a saved candidate; no retroactive rewrite of prior stored records.

### Task 1: Supported task modality and communication constraints

**Files:**
- Create: sidecar/icarus_memory/task_modality.py
- Modify: sidecar/icarus_memory/task_review.py
- Modify: sidecar/icarus_memory/memory_analysis.py
- Create: sidecar/tests/test_task_modality.py

**Interfaces:**
- Consumes: `interpret(provider,title,body,...)`, `review_tasks(provider,subject,body,items,...)` and existing `hard_details_supported(title,quote)`.
- Produces: unchanged item/quote dictionaries; additional accepted reviewer kind `communication_constraint`, excluded from proposals.

- [ ] Write behavior tests: unconditional PDF against optional source is unsupported even if semantic judge approves; core task omitting PDF survives; qualified/exact-source and mandatory PDF controls survive; qualifier on another object is not sufficient; independent optional clause does not erase core task; extraction uses exact quote fallback. Mixed real task + communication_constraint yields one task; waiting and negative-duty controls survive; original text remains exact.
- [ ] Run the new file against unchanged code and verify the expected failures.
- [ ] Implement the narrow shared support check and extraction/review guidance. Preserve the existing exact-quote fallback; no fabricated rewritten wording or global negation regex.
- [ ] Run new tests plus existing task_review, task_candidate_retention, task_detection, memory_analysis suites; fix regressions and commit.

### Task 2: Topic substance guidance and synthetic evaluation fixture

**Files:**
- Modify: sidecar/icarus_memory/memory_categories.py
- Create: scripts/probe_intake_precision.py
- Create: scripts/test_probe_intake_precision.py

**Interfaces:**
- Consumes: existing normal Categories and task extraction/review paths, existing configured local provider.
- Produces: synthetic-only quality report with separate person/task/date/category outcomes, elapsed time and model identity; no private data access or role changes.

- [ ] Add shared topic guidance to both prompt paths: transport headers/branding alone do not establish a topic; preserve substantive general information and mixed messages.
- [ ] Write and run failing probe tests proving synthetic cases pass through real application analysis, local-only admission, timeout/failed cases stay visible, and reports never equate an injected fixture with live model acceptance.
- [ ] Implement the bounded synthetic probe and mixed portal/newsletter/optional-detail/constraint controls. Limit model calls and run one source at a time; do not scan personal stores.
- [ ] Run script tests and affected category tests; inspect the source/offset/currentness controls and commit. If the Mac lacks safe memory reserve or the local model cannot finish, record that as an unpassed live gate rather than weaken checks.

### Task 3: Verify the repair package before Harness integration

**Files:**
- Create: docs/runs/2026-11-02-intake-precision/README.md

**Interfaces:**
- Consumes: Task 1 and 2 tests/report; frozen commit and independent public-source review.
- Produces: explicit completed/uncompleted acceptance evidence; no universal accuracy claim.

- [ ] Run the affected complete suites and the whole sidecar regression once after the final product delta.
- [ ] Obtain a fresh independent public-source review; reproduce/fix critical or important findings with red/green tests.
- [ ] Run the controlled local synthetic probe if resource checks permit; retain all failures and timing evidence. Keep private data and API keys out of agents/GitHub.
- [ ] Record exact tested commit, test results, live-model limitations and remaining import pause. Continue to the separate Harness integration design, without claiming this broad goal complete.
