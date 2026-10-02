# M2c concrete design: exact knowledge semantics and source time

Preimplementation design only. Based on immutable 504c845 time audit and proposed `/tmp/kingfisher-memory-work/m1d-design.md`, especially section 9. M1d's snapshot provider is NOT implemented/verified by this review. Re-read its final implementation before coding M2c; do not create another resolver because a proposed name changed. No code, model or production data changes.

## Scope and result

Preserve canonical predicate/value and claim dates, plus distinguish original event time from import time, in the actual local knowledge JSON. Bind every rendered source field to persisted history and current context cards. Maintain existing transitive claim/evidence validity and egress rules. No timeline UI, new claims, source authorization, approval operation or data migration.

## Production projection

Add one pure `knowledge_render.py` (or equivalently cohesive functions in context.py): constructs a frozen knowledge-context-v3 projection from the EXACT selected Claim and primary EpisodeSupportSnapshot. No store lookups inside serialization/hash helpers.

```
format: knowledge-context-v3
assertion_id, statement, subject_ref, target_ref, scope_ref
predicate, value, claim_created_at, valid_from, valid_until
primary_evidence: {
  episode_id, digest, source_type, source_ref,
  occurred_at, recorded_at
}
reason
```

Null bounds/event date remain explicit. All timestamps aware/canonical UTC; semantic interval is start-inclusive/end-exclusive. `claim_created_at` is claim acceptance time, `recorded_at` is source import/storage time, `occurred_at` is the separately recorded event time. No fallback may populate occurred_at from recorded_at. Preserve existing ContextItem.evidence_at for compatibility if needed, but add explicit evidence_at_basis and derive both from the same primary snapshot. Primary is first canonical evidence, not earliest/only evidence or a complete chronology.

Use one fixed instruction explaining these time distinctions outside the JSON; source values stay escaped JSON data in the user context block. No title, participant labels, mutable entity labels or new source fields beyond those listed. Existing source_type/source_ref may remain duplicated on ContextItem for existing clients, with equality enforced against primary_evidence.

ContextItem gains a typed knowledge projection/signature field and canonical semantic/time fields (or one nested projection consumed consistently by serializer, API, tests). Avoid independent field lists for packet and prompt. Do not mutate Claim or Episode. Claim fields are already immutable in the canonical DB contract, so no ClaimStore schema change is needed.

## Reuse M1d seam, not its permission model

Consume the low-level EpisodeSnapshotProvider callback and shared physical identity/original/quote validators from M1d. Do not import reassessment, SelfModel producer commitment or support-generation approval semantics into ClaimStore: ClaimStore has its existing acceptance/invalidation rules.

Add a per-build `KnowledgeInputBuild` with frozen claim and source caches, one evaluation instant, and existing distinct-claim traversal bound. Route evidence_chain_available through optional supplied frozen resolvers so the checked primary source and rendered primary source are the SAME object. Every evidence entry of every traversed claim must still pass; don't cache a boolean for one quote and skip a second quote from that episode. Preserve allowed archived originals and all current interval/status checks. Missing snapshot callback for actual application ClaimStore use is unavailable, not permission to fall back to untracked metadata reads.

A per-turn shared episode cache may be reused by M1d/M2c if it preserves separate validity policies; don't force a broad cross-domain refactor. Cache values are immutable copies, not mutable Episode object references. Explicitly separate caches used to CAPTURE input from a NEW cache used to REVALIDATE against current authoritative state.

## Exact lineage v2

Bump `knowledge_claim_lineage_version` from 1 to 2. Keep `knowledge_claim_ids` for compatibility/complete dependency roots, and add bounded `knowledge_inputs` mapping claim ID to strict versioned snapshot signature. Every context knowledge item carries its exact captured signature. Metadata uses that signature, never a later lookup.

Signature covers the canonical semantic claim projection and rendered primary_evidence, excluding selection reason (query-relative) and formatting-only fields. Bind claim ID and primary episode ID explicitly. Dates hash canonically so offset spelling changes at the same instant do not invalidate. Existing evidence/status/interval validators independently enforce ALL transitive dependencies. The signature need not hash entire Episode documents, produced lists or unrelated metadata and should not force archive/consolidation noise into resets.

`from_items`/`read_lineage` validate shape, duplicate IDs, selected-item subset/equality, version and bounded map. Union signatures across actual supplied turns; if an existing root ID appears with a different signature, invalidate instead of replacing its old signature and laundering the previous answer. v1 history is unknown for reuse once it contains knowledge roots; conservatively reset once, retain transcript, and persist the new boundary. Empty v1 knowledge roots may be upgraded as empty only with strict existing metadata validation; choose this explicitly in tests.

`available` performs current transitive evidence checks AND fresh projection-signature comparison for every supplied root. Missing/changed source dates/refs invalidate even without a ClaimStore revision. Unchanged signature with valid evidence keeps history. Reset/approval-resolve/scoped agents carry the new map exactly like existing SelfModel inputs; per-conversation load rebuilds, not unions across conversations.

## Actual Agent boundary and races

At the examined Agent, integration points are context_packet/_knowledge_context_items; send's selected-input merge before provider loop; `_knowledge_history_available`; `_knowledge_inputs_changed`; `_invalidated_turn`; load_history/reset; and approval resolve. `_knowledge_inputs_changed` already executes before each complete(), after complete() before accepting text/returned tools, and on ProviderError. Make its knowledge branch check the new captured signatures using fresh authoritative snapshots. Existing assert_egress_allowed and local-only `_knowledge_context_items` remain independent safeguards. Forward the snapshot dependency via Agent.scoped and actual server construction, including injected test Agent wiring.

This is optimistic compare-and-revalidate, NOT a writing CAS transaction and NOT a lock held across model inference. Don't add Backend support CAS methods merely for this patch. Frozen capture supplies the expected value; revalidation compares current value without modifying the expected value. A mutation before first provider call must suppress that call via invalidated-turn behavior. A mutation inside recording provider complete() must suppress returned text/tool execution, including ProviderError paths. Pending approval resolve must likewise reject obsolete context before any action.

No finite pre-call check can prevent a source mutation immediately after validation while external computation runs; existing post-call guard is the accepted publication boundary. Do not claim atomic cross-database/model execution. Deterministic hooks/fake providers should test both windows without timing sleeps.

Server `_conversation_payload` currently rechecks knowledge evidence only. Add exact signature validation using one fresh per-response build; if the captured item changed, omit it from CURRENT context rather than rewriting its metadata to a timestamp the previous provider never saw. Historical messages keep original captured data. This mirrors M1c current-card behavior.

## Payload and work budgets

Retain maximum five selected knowledge rows. Add proposed serialized UTF-8 bounds: 8 KiB per JSON row; 32 KiB total knowledge data rows, accounting for prefix/newline overhead. These are initial explicit choices to validate, not preexisting guarantees. Omit an oversize row completely and set existing retrieval truncation plus a specific payload_omitted count; continue considering smaller candidates within bounded retrieval. Only rendered rows enter items/signatures. Never cut a predicate/value/identifier/date or interval half and call it canonical.

The new rendered block contains one fixed-size timestamp set per selected claim and no additional quote/body copies. Source field length is included in the byte budget. Keep evidence traversal complete under the existing traversal contract; oversized malformed source/evidence data must report unavailable rather than bypass quote checks. Any new shared-source-node cap must be explicitly reviewed against M1d's limits and fail closed; don't silently inherit a cache eviction policy that changes validity. Budget only the knowledge block, do not claim the entire conversation payload is now 32 KiB.

## Recorder and reference compatibility

`RecordingProvider` in scripts/memory_probe_support.py already deep-copies requests before delegation. Keep it independent and unchanged unless extra output metadata is needed; do not reconstruct provider payload from turn.context.

`scripts/probe_memory_pipeline.py` recognizes only exact v2 records and exact field sets (~116-150 and ~183-193). Update with a strict v3 parser/matcher in addition to v2 historical support, checking every semantic/time field and nested primary source identity. Unknown keys, wrong versions, altered time/value/interval, undeclared rows and wrong source remain integrity failures. Reverse and forward checks both required. Do not loosen to statement substring or accept arbitrary supersets to make tests pass.

Verifier expectations should come from immutable synthetic fixture expectations/captured source snapshot, not a fresh mutable source lookup after the provider returns. Keep verifier logic independent of the production serializer to avoid identical bugs satisfying both sides.

Preserve existing reference_context and reference_identity_context request bytes/mode meaning and old raw attempt files. If a time-rich reference is wanted, add a separately named/versioned reference mode; M2c itself needs no real-model rerun or silent reference rewrite. Update test_context_identity's v2 assertion for new production v3, add strict fixture time/semantic mutations, and preserve legacy parsing/regression cases. Bump evaluation result format or record actual payload version so old and new runs cannot be compared as identical prompts.

## Minimal implementation order and gates

1. After M1d review, confirm final snapshot seam and actual Agent/server constructors; freeze production base.
2. Add red recording-provider tests for old occurred/new import/new acceptance and canonical predicate/value/interval loss. Add source metadata mutation race tests and strict v3 verifier negatives.
3. Implement projection/build and bounded selection; then lineage v2 and all existing publication/current-card guards. Update API types only as needed to preserve/display accurate metadata, no timeline feature.
4. Update recorder extraction/reference-version compatibility independently; run context/history/identity, source-validator, approval-resolution and pipeline harness suites, then normal supported backend checks. No real model required for payload correctness.

Acceptance includes missing occurred_at, canonical offset equality, first-vs-secondary evidence identity, interval boundary, same-agent/reloaded history, current-card omission, unchanged post-reset follow-up, metadata mutation before/during provider and error/tool return, local-to-cloud switch, huge multibyte values, correct visible truncation, and raw reference modes unchanged.

M1d SelfModel support and restore limitations are not solved by M2c. This design only closes knowledge-context semantic/time loss and the exact rendered-source lineage it introduces.
