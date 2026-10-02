# Knowledge context semantic/time audit — immutable 504c845

Scope: context loss in actual Agent provider payload, not timeline UI or general knowledge redesign. Read `agent.py`, `context.py`, `knowledge_history.py`, `knowledge_context.py`, ClaimStore immutable trigger and EpisodeStore metadata paths from `git archive 504c845` in `/tmp/kingfisher-memory-work/time-504c845`. Synthetic standalone reproduction: `/tmp/kingfisher-memory-work/context-time-repro.py`; captured result `/tmp/kingfisher-memory-work/context-time-repro.json`. No repository edits, real model, production records or network access.

## Confirmed payload loss

Created one original episode with occurred_at=2024-09-14 and recorded_at=2026-09-14, then accepted a canonical Claim with predicate=role, value=Coordinator, and valid interval 2026-09-04 through 2026-09-24. Queried the neutral statement keyword ORION using an actual Agent with a recording provider.

The ContextItem includes evidence_at=2024-09-14, correctly derived from Episode.reference_time(). The actual provider JSON is:

```json
{"format":"knowledge-context-v2","assertion_id":"claim:k-…","statement":"ORION approved.","subject_ref":"person:…","target_ref":null,"scope_ref":null,"source_type":"chat","source_ref":"synthetic:time","reason":"Passt zum Gespräch: orion"}
```

It omits predicate, value, created_at, valid_from, valid_until and even the already-computed evidence_at. It also does not distinguish occurred_at from recorded_at. This is a verified application payload defect, not a claim that a model answered incorrectly. A model cannot recover these canonical values reliably from the synthetic statement; neither should production code require statement wording to redundantly encode structured semantics.

Locations at 504c845: `agent.py:278-288` manually selects fields for knowledge-context-v2; `agent.py:336-347` constructs ContextItem and drops the canonical predicate/value/claim dates; `episodes.py:163-165` defines reference_time as occurred_at OR recorded_at. That fallback is useful for sorting but insufficient to tell a model whether the date is event time or import time.

## History binding: what exists and what does not

Canonical Claim semantic fields, created_at, intervals and evidence are protected by the SQLite immutable trigger (`claims.py:157-184`); content changes require another claim. Knowledge history stores IDs only and rechecks claim status/interval plus transitive evidence availability (`knowledge_history.py:14-48`). Thus adding immutable claim fields to the rendered JSON does not itself introduce mutable registry/source-label dependencies. Existing status and interval boundary checks must remain.

Evidence validation (`knowledge_context.py:35-49`) checks every required original's not-ignored/not-summary status, body digest and quote. It does NOT bind source occurred_at, recorded_at, source_ref, provenance metadata or an exact rendered source snapshot. `knowledge_history` has no per-source fingerprint.

Synthetic metadata-change probe: after the first turn, changed the original's occurred_at by 90 days using existing EpisodeStore._put (internal store method, not a public metadata-edit endpoint). Claim revision remained 1, second ContextItem.evidence_at changed, knowledge_history_reset=false, and the persisted first assistant answer remained in actual provider input. Therefore current history checks do not detect this class of metadata change. This is a reproduced validation gap relevant to adding time fields, NOT a claim that current application UI exposes arbitrary episode time editing. At present the first provider did not receive the date, so this probe alone is not an already-observed stale date answer.

The tracked-document import path has stronger operational behavior: source metadata digest includes occurred_at; a changed tracked source becomes a new version and track_source ignores the old source/invalidates claims. That usual path does not remove the need to bind rendered source times: untracked records, internal updates and retrieval races are not covered by a ClaimStore revision. Source metadata digest itself is not enough: it excludes recorded_at and provenance.source_ref and is not currently checked by this validator.

## Smallest safe rendering contract

Keep the existing JSON data block and exact claim identity. Extend a single versioned knowledge payload/ContextItem contract rather than adding an independent prompt string. Proposed knowledge-context-v3:

- Existing assertion_id, statement, subject_ref, target_ref, scope_ref, reason.
- Canonical predicate, value, claim_created_at, valid_from, valid_until copied from the EXACT checked Claim object. Explicit null for absent bounds; interval semantics are [valid_from,valid_until). created_at is acceptance/storage time, not when the underlying event happened.
- Explicit primary_evidence object from the EXACT source snapshot actually used: episode_id, digest, source_type, source_ref, occurred_at (nullable), recorded_at. If retaining evidence_at for API compatibility, also declare evidence_at_basis as occurred_at or recorded_at. Never supply recorded_at under a field implying event time when occurred_at is absent.

Primary means first stored evidence, not earliest event, complete timeline or sole supporting source. The current full evidence validator continues checking all sources and dependencies; this narrow patch need not duplicate every quote/body/date into the prompt. Multiple evidence dates must not be collapsed into an invented single “event date”. One fixed instruction can state the field meanings and that absent event time is unknown. No new event inference, registry labels, system-prompt source text or timeline UI.

Canonicalize offset-aware dates (prefer UTC for fingerprints while retaining an explicit offset in rendered values). Same instant with a different offset spelling must not reset history. Source occurrence in the future can be a planned event; don't reinterpret it as import corruption or remove it without a separate domain rule.

## Minimum added lineage

Because source time/reference metadata is mutable, add a versioned per-rendered-claim input signature binding the exact canonical claim payload and exact primary-source fields above. Capture it with rendering, never by a later reread. Keep the existing set of all claim roots and transitive status/evidence checks; supplement it, do not replace them. Revalidation reloads authoritative claim/source and recomputes the same projection; changed source event/import time, identity/ref, or other actually rendered field invalidates old assistant derivations even if body digest and ClaimStore revision are unchanged.

Use one per-turn frozen source cache/shared evidence read path so the source used in ContextItem and the source evidence validator cannot silently be different snapshots. A post-render mutation must be detected by the existing publication/provider history-boundary strategy. Persist IDs/hashes of rendered snapshots, not source bodies or ancestor plaintext. Legacy lineage version 1 cannot certify the new time-bearing signature: when needed, reset unknown history conservatively once, then persist the new boundary so unchanged follow-ups retain history.

Do not hash full mutable Episode documents: archive/consolidated flags, produced lists, unrelated tags or UI-only metadata would cause unnecessary resets. Existing evidence checks separately handle ignored/summary semantics; the new signature covers the fields actually supplied. If a source field is omitted from the prompt and otherwise irrelevant to evidence validity, it need not become a history dependency.

## Payload bounds

Five selected claims is NOT a character bound: the creation API does not impose maximum lengths on predicate/value/statement. Adding value can significantly duplicate the statement text. Keep the existing five-row cap and add explicit per-row and aggregate serialized-character/byte budgets for the entire knowledge JSON block. E.g. 8 KiB per row and 32 KiB total are implementation choices to validate against existing fixtures, not required magic constants.

If a canonical semantic field or identifier makes a row exceed the bound, omit the entire row with explicit truncation/coverage metadata; do not silently truncate a value or identifier and present it as the canonical relation. Only add signatures for rows actually rendered. Do not truncate dates, drop the second half of an interval or silently use the first N evidence entries during validation. Escape every data string through JSON as today.

## Acceptance tests for this bounded patch

1. Actual provider JSON contains predicate/value and canonical interval even when absent from statement; ContextItem/API metadata matches exactly.
2. Old occurred_at + new recorded_at + new claim_created_at remain three distinct facts. Missing occurred_at stays null, with import fallback explicitly labeled if used. Offset-equivalent instants remain stable.
3. Interval expiry/future start still excludes current claims and invalidates historical derivations; serializing bounds must not weaken existing eligibility.
4. Change selected source occurred_at, recorded_at or rendered source_ref while digest/quote unchanged: both same-agent and persisted reload reject the prior answer. Unchanged follow-up after reset retains the new history. Mutation between selection and signature construction cannot certify mismatched source data.
5. Operational tracked-source replacement still invalidates; archive-only original remains valid; secondary evidence ignore still invalidates even though only primary time is displayed.
6. Huge predicate/value/source_ref, multibyte text, hostile newline/JSON fragments: actual total payload stays bounded, omission is visible, identity/interval semantics never partially rendered.
7. Cloud provider receives no automatic knowledge block or source-time metadata; no new network resolution.

No full timeline feature is required. Minimal implementation files are context.py/agent.py for one canonical rendering projection, knowledge_history.py plus the shared evidence snapshot path for exact signatures, and focused provider/context tests. ClaimStore content schema need not change for adding existing immutable semantic/time fields. Source timestamps must NOT simply be appended without the new lineage binding described above.
