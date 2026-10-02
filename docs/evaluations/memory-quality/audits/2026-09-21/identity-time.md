# Identity and temporal memory audit — 2026-09-21

Baseline read-only audit of main `7e397db` at `work/memory-audit-20260921`, followed by root-authorized bounded fixes below. Target: `docs/architecture/kingfisher-memory-sicherheitsvertrag-v0.1.md` §3.3, §3.5, TEMP-01…06, T-ID-01, T-TIME-01/02, T-MAT-01; `docs/23-vernetztes-gedaechtnis.md`. No external model calls, private data/config inspection or full suite. All reproductions use newly created synthetic SQLite stores. Baseline line references/findings below describe `7e397db`; post-fix status is explicitly separated.

## Authorized fix status

**ID-2 fixed and verified:** `personen.wartet_auf` now requires an explicit waiting assignment; title-only references never assign a task. Existing name matching on explicit waiting assignments is unchanged. Task records remain intact.

**TIME-1 fixed in examined person/project/digest projections and verified:** unknown source event times remain null in person/profile APIs, graph episode metadata, project contact dates and person digest input. `recorded_at` is carried separately. Undated imports no longer claim a latest contact or replace an older known contact. A related independently reproduced bug is also fixed: claim digest input previously used `claim.created_at` as `occurred_at`; it now uses the first original evidence's event/import times and supplies `claim_created_at` separately. Digest citations preserve null event times plus recorded time; source periods include dated sources only and are null if none are dated. Digest cache fingerprint version advanced to 3 to invalidate prior output semantics. No global change to `Episode.reference_time()`.

**ID-1 remains open:** source-name aggregation is unchanged; the concrete protection/data-model plan below remains necessary. Time precision/relative-date/matter/temporal-alias model gaps are likewise not solved by these fixes.

Files changed by this subagent: `sidecar/icarus_memory/personen.py`, `graph.py`, `person_digest_context.py`, `person_digests.py`; new `sidecar/tests/test_person_identity_time.py`; updated old expectations in `test_menschen.py` and digest citation expectations in `test_person_digests.py`. Root owns corresponding frontend type/display adaptation. No commits.

Before/after: new regressions were run against original production code and failed for task-substring assignment, unknown import/contact/digest date, and late claim-created time substitution. The mixed dated/undated fixture was corrected to use distinct source bodies (otherwise import deduplication made that fixture ineffective), then also failed before its fix. Final focused run: **137 passed, 2 dependency deprecation warnings in 10.49s** across `test_person_identity_time.py`, `test_menschen.py`, `test_person_digests.py`, `test_graph.py`, `test_graph_memory_foundation.py`, `test_person_merges.py`, `test_context_identity.py`, `test_knowledge_time.py`. Real local API/SQLite paths and a deterministic fake model boundary were used; no browser or real-model semantic qualification is claimed. `git diff --check` passed.

Root review follow-up: the extra primary-source metadata lookup was tested for source withdrawal/removal between chain validation and lookup. Both new cases failed first. The lookup now handles `EpisodeError`, rechecks ignored/summary/digest/quote state, and discards an already captured raw-source row when the new check detects unavailability. This avoids adding a 500 or retaining that source in the examined race window; it does not claim a new global transaction/snapshot guarantee. After this final change, **23 passed, 2 dependency deprecation warnings in 5.21s** for `test_person_identity_time.py` (now 7 cases) plus `test_person_digests.py`. No other production files changed afterward.

Second root-authorized review follow-up (after commit `33a5bfc`): independent reviewer proved an inherited earlier withdrawal window: raw source collected, then source ignored immediately before `_evidence_available`; the false result skipped the new primary check and left raw text in model input. A new real Digest-HTTP regression first failed because `WITHDRAWN_MARKER` appeared in the deterministic provider's actual request context. The unavailable-claim branch now conservatively removes already collected rows overlapping that claim's direct evidence episode IDs before continuing. The regression proves the removed text never reaches the provider while an independent valid source still reaches the model and produces a ready response. **24 passed, 2 dependency deprecation warnings in 5.50s** across `test_person_identity_time.py` (8 cases) and `test_person_digests.py`; `git diff --check` passes. This four-line production change is uncommitted by this subagent. It closes the demonstrated claim-check window; unrelated raw-only concurrency windows are not claimed tested or solved.

## Confirmed findings

### P1 / ID-1 — Equal display names become one person and one AI overview context

**Status: partial implementation, unsafe legacy projection remains.** Stable registry IDs preserve distinct accepted claims, but raw participants are merged solely by `name.strip().casefold()`:

- `sidecar/icarus_memory/graph.py:34-36`, `292-304`: one hash/node for equal names, labelled `exact_normalized_name`.
- `sidecar/icarus_memory/personen.py:234-253`: merges source count, latest contact and topics by that same name.
- `sidecar/icarus_memory/graph.py:523-529`: one person profile selects every matching source.
- `sidecar/icarus_memory/person_digest_context.py:18-26`, `48-56`: same node is one person/member; all matching single-participant sources reach the person's AI overview input.
- `app/kingfisher/src/MemoryProfile.tsx:54-60`: user sees **PERSONENPROFIL**, its contact count, summary and AI overview; this is not presented as a list of unresolved name search hits.
- `sidecar/icarus_memory/person_digests.py:53-62`: prompt explicitly requests an overview of exactly the specified person. A sentence warning that names do not prove identity does not recover the lost source/person distinction.

**Repro:** Record one synthetic school source and one purchasing source, both with `participants=['Alex Winter']`, unrelated source refs, and different phone numbers. Graph returns one node `person:89c705d90c77c9d4`, `quality_category='person'`, empty duplicate hints. `person_profile('Alex Winter')` contains both interactions and count 2. `person_digest_context.collect` yields one member and both phone-number texts.

**Observed limit:** No deterministic extraction into a dedicated phone/email field was found in this profile component. The proven error is one-person aggregation and combined AI input, not a demonstrated real-model phone-number hallucination or mutation of accepted registry claims.

**Minimal safe protection, needs root scope decision:** Keep source records/IDs intact; mark participant-only name groups as unresolved name references in graph and profile. Present linked sources as mentions, not contacts of a proved person. Do not create a person-specific AI overview from an unresolved aggregate; retain source inspection and explicit registry claims. A flag only in the API/prompt is insufficient because current UI ignores it. Avoid a large identity migration; this protection makes the still-missing data model visible. Cost: legacy name-only profiles lose automatic person summaries/contact aggregation until explicitly resolved. Be careful: an explicit merge of already name-collapsed buckets cannot by itself prove every underlying mention belongs to the same human.

### P1 / ID-2 — Task-title substring assigns another person's task

**Status: implemented incorrectly; bounded fix available.** `sidecar/icarus_memory/personen.py:149-168` falls back to `name in task.title` whenever `Task.wartet_auf` is unset. `_bauen` at `273-278` presents these as `offene_aufgaben` of the person. UI `MemoryProfile.tsx:59` then counts them as tasks assigned to that person.

**Repro:** Person `Ann`, explicit user task `Rückfrage an Joanna`, `wartet_auf=None`. `person_profile('Ann')['person']['offene_aufgaben']` contains that task. This is deterministic, no model or same-name ambiguity required.

**Minimal fix:** When no explicit `wartet_auf` exists, return false; preserve current explicit matching. Word boundaries merely reduce the bug and still invent attribution from task wording. Tasks remain in their actual task list; no records need deletion. Longer term, replace free-text waiting names with stable subject references.

### P1 / TIME-1 — Unknown event time becomes today's contact and an asserted source date

**Status: partial implementation; TEMP-04 violation in projections.** Core episode preserves `occurred_at=None` and a separate `recorded_at`. However `Episode.reference_time()` (`sidecar/icarus_memory/episodes.py:165-167`) substitutes recorded time. Person consumers then relabel that fallback:

- `sidecar/icarus_memory/personen.py:238`, `251-253`, `288-293`: import time becomes `letzter_kontakt`, `kontakt_text='heute'`.
- `sidecar/icarus_memory/graph.py:544`, `553`: emits fallback under `last_interaction`/`occurred_at`.
- `sidecar/icarus_memory/person_digest_context.py:55`: emits fallback as `occurred_at`, omits `recorded_at` and time basis. Digest source sort/prompt uses this as actual source date.
- `sidecar/icarus_memory/person_digests.py:53`, `62`: requests the actual month/year of old correspondence based on that substituted date.
- `app/kingfisher/src/MemoryProfile.tsx:58`, `60`, `64-66`: surfaces this as **Letzter Kontakt heute** and source dates.

**Repro:** Undated imported source `Wir treffen uns Freitag zur Planung.`, `occurred_at=None`, captured at `2026-09-21T10:00Z`. Stored time remains null, but profile and digest emit `2026-09-21T12:00+02:00` as occurred time; profile says `heute`. Thus a relative expression reaches the model with an invented event-time anchor. No actual false deadline extraction was invoked or claimed.

**Minimal fix:** Change the person/profile/digest boundary, not the generic `reference_time()` helper: keep unknown event times null, carry `recorded_at` separately with explicit basis, use fallback only for technical sorting, and do not use undated imports as evidence of a last contact date. Existing dated sources should retain ordering. Digest rendering/validator must accept unknown event dates without slicing/parsing null; fingerprint must include new semantic time fields.

## Contract status

| Contract | Status | Current evidence / gap |
|---|---|---|
| Stable identity of accepted claims; same label distinct IDs | Implemented in examined path | `entities.py:201-238`, `251-292`; `test_context_identity.py` demonstrates canonical refs at actual fake-provider boundary; no label merging. |
| T-ID-01 same name in source-derived person views | Partial / blocked | ID-1; normalized name is still one person node/profile and digest context. |
| T-ID-01 same mailbox / functional mailbox / reversible merge | Partial | `people_quality.py:25-66` marks generic/automated mailboxes, suggests duplicates only; `person_merges.py:64-114` requires explicit confirmation, preserves member IDs, supports undo. Focused tests pass. Does not resolve collapsed name buckets. |
| Time-bounded aliases, contact validity, identity decision history | Missing model | `entities.py:39-42`, `72-79`: aliases store only source/account/native_id/entity_id. `link_source:330-383`, `unlink_source:408-425`, `rename:309-328` have no valid interval or identity-decision journal. Removing link deletes its binding; confirmed person merges have separate created/undone timestamps. No migration proposed in this audit. |
| TEMP-01 / T-TIME-02 known time versus source possession | Implemented in examined claim history path | `memory_history.py:123-133`, `186-195` separates claim creation from valid time; focused `test_memory_history.py::test_old_source_does_not_backdate_recognition` passes. |
| TEMP-02 / T-TIME-01 late old source versus newer correction | Partial | Accepted claim replacement requires explicit supersedes; no automatic import-date override in examined claim acceptance. Person/digest fallback still creates apparent current contact from undated import (TIME-1). Semantic real-model end-to-end historical correction not qualified. |
| TEMP-03 retroactive correction without backdating knowledge | Implemented in examined claim history path | `test_correction_preserves_earlier_knowledge` passes; source/valid/claim-created fields reach knowledge provider distinctly. |
| TEMP-04 missing date, time zone, precision, relative expressions | Partial / blocked | Known claim bounds validate timezone and half-open intervals (`relations.py:126-167`). Core knowledge payload retains null times. TIME-1 violates unknown event semantics. No separate date precision/original-expression/zone-ID model; null claim bounds treated as open (`claims.py:69-73`, `relations.py:178-179`) rather than explicit unknown validity. |
| TEMP-05 replacement depends on subject/context/decision | Implemented for accepted claim path | Explicit conflict/supersedes path and contextual predicates; not a universal semantic correctness proof. |
| TEMP-06 time can invalidate context with no source change | Implemented in examined knowledge path | `test_knowledge_time.py::test_valid_interval_is_start_inclusive_end_exclusive` and context-history tests pass. |
| T-MAT-01 request/conditional commitment/deadline update/partial delivery/receipt | Missing as full matter model | `tasks.py:41-75` only OPEN/DONE/DROPPED, due timestamp, name waiting field; no Matter stable identity or request-vs-commitment/completion-reported-vs-verified states. `memory_analysis.py:55-73` explicitly omits conditional promises and only emits title/quote; `task_candidates.py:15-53` requires user acceptance and explicit due. `task_events` (`tasks.py:491-499`) persist changes but do not supply full matter semantics. Existing request candidates are not silently finalized. |

## Verification

- New synthetic current-behavior reproductions: **3 passed in 0.25s**. These tests assert the observed wrong behavior to capture audit evidence; they are not post-fix acceptance tests.
- Existing focused tests: **140 passed in 5.74s**, 2 dependency deprecation warnings. Files: `test_context_identity.py`, `test_knowledge_time.py`, `test_memory_history.py`, `test_entities.py`, `test_person_merges.py`, `test_people_quality.py`, `test_task_history.py`, `test_memory_clarification.py`.
- Runtime `python`; `PYTHONPATH=sidecar:scripts`; isolated `ICARUS_DATA_DIR` and pytest temp/cache under `identity-time-scratch/`.
- Repro script: `identity-time-scratch/test_identity_time_repro.py`. Run from checkout with `python -m pytest -q -s ../memory-audit-evidence-20260921/identity-time-scratch/test_identity_time_repro.py --basetemp=../memory-audit-evidence-20260921/identity-time-scratch/tmp -o cache_dir=../memory-audit-evidence-20260921/identity-time-scratch/pytest-cache` plus the runtime/env above.
- No browser flow or real-model run; these results prove current deterministic input/projection behavior only. Prior green tests do not establish the product's no-wrong-person/no-wrong-deadline goal.

