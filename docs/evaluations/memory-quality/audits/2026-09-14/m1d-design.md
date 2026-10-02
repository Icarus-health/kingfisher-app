# M1d concrete preimplementation design

Read-only preflight, 2026-09-14. M1c production is stable at504c845 while parent handles integration. No repository edit, test, private read, model, download or migration was performed for this design. Read the committed M1d plan and both copied audits in full. Re-resolve HEAD and re-read integration files after the implementation handoff.

Parent has accepted two additions identified during this preflight: (a) a complete indexed Episode.produced projection for orphan recognition, installed in the same episode migration; (b) an application-owned authorization commitment on the accepted producer, so imported typed support cannot manufacture a legacy generation baseline. These are derived lookup plus an application decision on the existing producer, not new canonical truth stores.

## 1. Exact shared integration

Add `self_model_support.py` for typed support parsing/capture and episode/producer resolution, and `support_review.py` for preview/reassessment orchestration. Keep token handling/routes out of the parent graph algorithm.

`EpisodeSupportResolver(proposals, episodes)` produces a per-assessment `SupportBuild(at, local, max_sensitivity, budget)` with immutable caches. `FrozenBuild` gains an explicit support-build dependency and assesses episode support for EVERY captured SelfModel node, not just the selected root. Otherwise an unselected episode-backed parent could launder evidence into an apparently parent-only child. Exact producer/orphan lookup is cheap and indexed; direct user assertions with no recognized support remain unchanged.

Support result needs separate dimensions:

- `recognized`: none / accepted / orphan / typed_without_producer.
- `complete_private`: complete and permitted, versus missing/malformed/ambiguous/protected/incomplete.
- `usable`: current support matches canonical authorization, source snapshots and generation.
- `signature`: hash of exact frozen producer/source/commitment/support inputs and effective state.
- Public bounded status such as supported, review_required, unavailable; do not put hidden evidence IDs/quotes in omission diagnostics.

Feed support into M1c priority: incomplete or privacy-forbidden support withholds the whole candidate; complete privacy-safe but withdrawn support can qualify eligible historical decisions, while ordinary inferred roots are omitted. Stable qualified historical context must revalidate against its qualified signature, not require source generation to equal the old acceptance generation merely to retain the fact that its basis needs review. It must still prove the same complete visible invalid basis and unchanged qualification. Ignored sources cannot be reauthorized by this qualification.

Bump SelfModel history to version3 (keep M1c basis qualifier version unless its public enum changes). Version2 does not certify previously untracked episode dependencies, so it remains unknown for model-history reuse. Preserve transcript/reset/approval semantics. Aggregate signature now includes parent and support assessment; never capture a fresh source lookup after rendering and substitute it for the original snapshot.

Exact production wiring:

1. server `_agent_fuer` (Agent constructor around697) creates/injects the resolver from `app.state.proposals` and `app.state.episodes`.
2. `create_app` also wires the resolver for a supplied Agent, as it currently wires app stores; tests that supply agents must not leave an accidental unvalidated production route. Ensure store identities correspond instead of silently mixing the agent's test stores with app defaults.
3. Agent constructor stores it; Agent.scoped forwards it. This covers routing_runtime's scoped roles and provider reconfiguration. Revalidate localness from the actual provider on every call, not from resolver construction time.
4. Agent.context_packet -> build_context_packet -> FrozenBuild receives one SupportBuild. Existing `/context` delegates to Agent.context(), so this path is covered too.
5. Agent._self_model_history_available passes the resolver/actual provider mode to self_model_history.available on send, all provider/tool checks, provider-error handling, approval resolve and loaded history. Both normal external sensitivity AND recognized-episode local-only rule apply.
6. server `_conversation_payload` constructs its shared current-card FrozenBuild with the same resolver, one instant and authenticated local-display mode. Changed captured cards disappear; never fabricate a new unseen review rendering. Historical message metadata remains intact.
7. Preview/reassessment uses the same parent/support functions, with a specifically allowed prospective evidence capture for the selected root. This prospective override must never leak into normal retrieval; ancestors still need their real existing authorization and privacy.
8. No resolver is a valid explicit test/minimal-API configuration for ordinary direct-user records. Recognized typed support must fail closed without it. Parent-only inference can be established only when the actual resolver proves absence of an accepted/orphan episode linkage; do not silently treat unavailable stores as an empty producer set. Update positive fixtures to wire stores explicitly.

Proposed bounds pending independent review:16 evidence entries per typed support (every quote, including distinct quotes from the same episode), at most128 distinct external support nodes per whole build (producer/source caches), in addition to M1c's128 SelfModel nodes. Bound quotes (e.g.4096characters each) and identifiers; reject oversized support rather than silently use a prefix. Separate budgets keep M1c's accepted parent contract unchanged while keeping combined work bounded. These numbers are implementation choices to confirm, not existing product guarantees.

## 2. Durable episode migration and snapshot

Current episodes migrations end atv5. v6 adds relational `support_generation INTEGER NOT NULL DEFAULT 0 CHECK(support_generation>=0)` and derived `episode_produced_assertions(assertion_id TEXT, episode_id TEXT, PRIMARY KEY(assertion_id,episode_id))` with reverse maintenance/query indexing as needed. Backfill only the reverse relation from canonical document.produced; do NOT populate any assertion support field or authorization commitment. Generation0 is storage initialization, not historical evidence of no prior withdrawal.

`EpisodeStore.support_snapshot(episode_id)` returns one frozen snapshot from one SQL SELECT joining episodes to source_heads by source_key. Include canonical Episode and relational id/digest/kind/state/source_key/metadata_digest/generation/head ID. Verify row/document correspondence and tracked metadata using existing source_metadata_digest semantics. Untracked source_key='' binds exact episode ID+digest; tracked keys require an unambiguous matching current head. SUMMARY is never an original; ARCHIVED original remains valid. Missing/ambiguous source identity is unknown. Same-body unrelated episodes cannot substitute.

`EpisodeStore.produced_support_links(assertion_id, limit=2)` queries the reverse index exactly; its use is orphan recognition, never proof of complete support. Missing Episode.produced entries do not invalidate a complete accepted producer, because current consolidation tolerates those writes failing. A produced-only link without accepted proposal evidence cannot supply permission or missing quotes.

Generation transition must be decided from the authoritative old row inside BEGIN IMMEDIATE (or equivalent single conditional SQL), not the caller's stale Episode object. Increment exactly once on a transition from a non-IGNORED state to IGNORED; repeated ignore is idempotent; reopen never decreases it. Ordinary `_put` must not take a caller-supplied generation. Preserve generation on archive/consolidate/project writes.

Concrete concurrency trap: current ignore/reopen/mark_consolidated read outside their final `_put` transaction; `_put` commits itself. A stale consolidation can overwrite IGNORED with CONSOLIDATED and silently reopen permission. Fix lifecycle methods to read/check/write under one transaction, and require an explicit reopen path to leave IGNORED. Background mark_consolidated must not revive ignored sources. Generation alone does not repair that permission race.

Maintain produced projection in the same row mutation transaction (SQL triggers or a centralized transaction-aware `_put`), covering inserts, updates, physical deletion and unsupported replacement writes. No newest-N scan. Verify exact table/index/trigger contracts and canonical row equality on lookup; do not globally enable recursive_triggers or assume OR REPLACE fires delete triggers. If using application maintenance, raw writers must fail rather than silently corrupt the projection. Existing `_put` UPSERT semantics must be considered before adding an INSERT duplicate guard: a naive guard would also reject legitimate ON CONFLICT UPDATE writes.

## 3. Proposal migration, commitment and correspondence

Current proposal migrations end atv4. v5 adds `produced_assertion_id TEXT` plus ordinary `idx_proposals_produced`, backfilled only from canonical string document.produced. Nonunique by design: duplicate accepted producers are an unknown, not a startup deletion/merge decision. Maintain column with document atomically; validate canonical correspondence on every lookup. Unsupported raw document writes must not hide a producer by leaving projection stale. Exact projection/trigger schema belongs in migration verification.

`accepted_self_model_support(assertion_id)` queries produced+accepted with LIMIT2; only ProposalKind.ASSERTION produces this support. Exclude confirmation, conflict, task and knowledge. Validate canonical produced ID/state/kind, statement, assertion_kind default semantics and supersession correspondence against the selected assertion; sensitivity is a privacy minimum, not an equality check that prevents later tightening. Check proposal ID, all evidence and canonical producer fingerprint as well. Do not use source-ref display labels as authority.

Add a strictly parsed optional application-owned support authorization commitment to the accepted proposal's canonical document:

```
{version:1, assertion_id, assertion_content_fingerprint,
 support_hash, operation:'acceptance'|'reassessment',
 authorization_id, authorized_at}
```

The assertion-content fingerprint includes ID, content/kind/provenance/domain fields, excluding only the replaceable episode_support field; avoid a recursive hash definition. Exact final support_hash is bound separately. Ordinary sensitivity/status/freshness changes still invalidate context via M1c; choose which mutable root fields are part of correspondence versus preview freshness carefully so an ordinary confirm does not permanently invalidate unchanged support. Recommended commitment identity hash covers immutable content/provenance/ID and original supersession structure; preview hash covers the FULL current assertion. Status/time/privacy are always rechecked live.

Only Consolidator's successful acceptance and the authenticated reassessment service can issue/replace this commitment. Generic pending proposal or Assertion import data cannot manufacture it. Existing generic ProposalStore.accept callers for other proposal kinds do not gain support capabilities. Normal imported typed support must exactly match the local accepted producer's commitment and source generations; copied support for another assertion fails produced identity/content correspondence. If the local commitment is absent (including all legacy accepted producers), support remains unverified until explicit reassessment. Losing the local producer/commitment fails closed; portable typed quotes are evidence data, not portable authorization.

Proposal.accept needs a transaction-aware pending check/read/write so two connections cannot both accept a stale pending proposal and overwrite its producer commitment. Preserve conflict/confirmation/task workflows while adding the narrow ASSERTION commitment path. Projection backfill must not synthesize a commitment.

## 4. Typed Assertion support and its mutation boundary

Add optional typed `episode_support` with strict version1 parser (small dedicated dataclasses or validated immutable value), fields:

```
{version:1, proposal_id,
 episodes:[{episode_id,digest,quote,source_key,metadata_digest,support_generation}]}
```

No factual confirmation time is necessary inside this snapshot; the producer commitment/audit carries actual support authorization time. Include all original quotes exactly; never backfill empty accepted digest/quote from current text. Validate every distinct evidence entry against proposal.evidence, including secondary quotes, with existing normalized quote-match helper; cache episode reads only, not skip validation of additional quotes. Snapshot only original IDs, not summaries.

Locations: model.Assertion/to_dict, backends.assertion_from_dict, schema/self-model.schema.json (additionalProperties=false), SelfModelStore.record internal support parameter, store.redact, MemoryBackend/SqliteBackend/CogneeBackend and export/import round trips. Generic RecordIn and Agent tool schemas do not accept support. Keep domain structured untouched. Redaction explicitly clears the entire support object to remove quotes, including descendant tombstones.

Provide `SelfModelStore.reassess_support(id, expected_full_fingerprint, support)` backed by atomic compare-and-set support replacement. SQLite implementation: BEGIN IMMEDIATE, read actual current document, compare full preview fingerprint, enforce immutable content and ACTIVE/current explicit interval, update only the support field preserving every other canonical value, commit. MemoryBackend performs the equivalent under a lock; CogneeBackend forwards the dedicated mutation without asking a model or reindexing unchanged statement text.

Current SqliteBackend.put reads old state before its write lock/transaction. A dedicated support CAS alone cannot prevent another stale ordinary put from overwriting a newer support/redaction. Move its read/immutability check/write into a transaction and define stale support preservation/rejection on ordinary status updates. Ordinary writes must not grant/replace support; either preserve the current field or reject a mismatch and retry the caller. A stale redaction must still clear support, never resurrect quotes. Test actual two-connection races with redact/confirm/reassess; route locks alone do not prove this property.

## 5. Acceptance order and publication

Ship generation/projection migrations and acceptance capture together. No intermediate deployment where new assertions lack capture proof.

1. Read exact pending ASSERTION proposal and bounded complete evidence; snapshot all originals/generations/head/metadata under a support build. Reject ignored/missing/summary/quote-mismatched/oversized evidence. Capture typed support BEFORE creating the assertion.
2. Create assertion with typed support but no completed accepted producer linkage. It remains unusable during this interval because exact accepted producer+commitment is required. Assertion ID may be generated by existing record(); support does not need to embed it until commitment creation.
3. In ProposalStore transaction recheck pending and canonical evidence unchanged, accept with produced=assertion.id and commitment binding assertion identity/content+support hash. Competing acceptance rejects cleanly; an orphan from the interrupted attempt is retained but non-usable.
4. Revalidate the captured source snapshots/generations, current assertion and completed commitment before returning a current assertion from acceptance. Failure does not pretend cross-DB rollback: persisted interrupted/mismatched records remain non-usable, returned status must not claim current support. Best-effort Episode.produced updates are bookkeeping only, never a prerequisite for the accepted canonical proof.
5. Provider/current-card guards always recompute source/producer agreement. Source mutation immediately after publication changes effective support; no snapshot can promise immunity to future edits. This is the accepted optimistic boundary, not a multi-database transaction.

## 6. Authenticated reassessment preview/submit

Use proposed /api/v1 routes with existing guard and a dedicated strict request model (extra fields rejected). No Agent tool:

- GET `/api/v1/assertions/support-review?cursor=...&limit=...`: stable keyset page, e.g.25/maximum50, over the union of indexed accepted produced IDs and known orphan IDs. Page/filter after canonical resolution; cursor advances past scanned rows, including blocked/duplicate/stale rows, not just displayed hits. Bound scan work and return next_cursor/truncated so an empty filtered page does not falsely mean no old records exist. Known orphan entries can be listed as blocked but cannot offer reassessment.
- POST `/api/v1/assertions/{id}/support-reassessment/preview`: returns exact root statement/kind/factual evidence date, root currency/basis, producer ID and every original quote plus read-only source links, eligibility and a server-issued opaque random token with expiry (proposed10minutes). Ineligible/hidden/incomplete previews do not expose protected details or an actionable token.
- POST `/api/v1/assertions/{id}/support-reassessment`: body ONLY `{preview_token, confirmed:true}`. Server remembers bounded token records (proposed256 outstanding entries), tied to assertion ID, full root fingerprint, immutable producer/evidence fingerprint/current commitment, all source snapshots/generations, M1c ancestry signature, local display/privacy scope and expiry. No client timestamp/source/support/generation fields.

Preview requires root ACTIVE and explicit interval current; age-outdated ACTIVE can be reassessed and must retain its age warning. All originals must currently be valid/non-ignored/current heads. Legacy missing commitment is the only bypass for a prospective ROOT support capture; missing/invalid producer/evidence or unsupported ancestor is not waived. Accepted-proposal sensitivity plus root/ancestor sensitivity applies. The local user review view may use the existing authenticated local-display ceiling; this is not external-provider permission.

Submit under the shared application mutation lock plus store-level CAS:

1. Authenticate, require true confirmation, find unexpired bound token, reserve/consume it exactly once. Unknown/wrong assertion/reused token -> clean409 (allowed idempotency choice; no duplicate approval).
2. Re-resolve exact root, producer, all evidence and parent ancestry. Recompute token binding from actual current snapshots. Any change ->409/no approval write. Never substitute new source text or current generation silently.
3. CAS replace Assertion support only using the preview full fingerprint. Then CAS update the accepted producer commitment using its expected fingerprint/current commitment, binding the new support hash and same assertion identity. While only one database is updated, normal use fails closed because support and commitment mismatch. If second write fails, keep the intermediate state non-usable and report conflict; do not claim atomic rollback.
4. Revalidate complete agreement and source generations before success response. Audit actual application decision with assertion/producer IDs, authorization ID, old/new support hashes and actual approval time only; no quotes. If audit is required for successful authorization, place commitment creation behind a durable audit success prerequisite or make audit failure explicitly block success; this ordering needs final review.
5. Never call confirm/record/proposal.accept/reopen/mark_consolidated. Preserve last_confirmed_at, recorded_at, captured_at, valid_from/expires_at, status/status_changed_at, kind, confidence and structured. A separate explicit source reopen can make current originals eligible for a new preview, but stale support never revives merely from reopen.

The last step must describe “Belegnutzung erneut geprüft”, not “Aussage heute bestätigt”. Source permissions and factual date are unchanged.

## 7. Real Kingfisher UI

Use app/kingfisher only. MemoryGraph.tsx already owns the /memory shell, sidebar area filters and a “Verarbeitung & Verlauf” subsection. Add a separate “Aussagen prüfen” control/subsection beside that, not under PeopleReview's identity merge flow. New small `SelfModelSupportReview.tsx` reuses current memory card styles, keyset pagination, preview/details and explicit confirmation. It must not require a successful graph fetch to show the review list.

api.ts gains exact list/preview/submit types and methods. Display original factual date and current/outdated state; all bounded quotes are visible before enabled confirmation. Stale preview response clears token and prompts explicit reload; successful reassessment refreshes the item without pretending its statement became factually fresh. No bulk approval.

ProfileSource.tsx gets explicit `readOnly`/action mode that suppresses BOTH ignore and reopen UI and guards both handlers. `allowIgnore=false` alone is insufficient today. Reuse source read view in that mode; evidence viewing cannot trigger permission mutation. Existing source controls outside reassessment remain unchanged.

Server mounts _ui_dir() via StaticFiles and existing /memory SPA route; app/kingfisher build outputs app/dist. No legacy app/src implementation is sufficient acceptance. A synthetic browser flow must discover an old item, view all evidence, reassess, preserve factual date, show restored support and send a recording-provider chat. Include blocked source/viewer controls, stale token, second-source withdrawal and external switch.

## 8. Scope estimate and remaining review decisions

This is materially larger than M1c: approximately20–25 production/UI/schema files across two existing SQLite migrations, two new service modules, backend CAS contracts, actual Agent integration and a small UI section. Expect several coherent tested commits within one nondeployed branch, not an isolated generation rollout. Estimate by scope, not elapsed-time promise: four work packages (store/model contracts; shared resolver/history/acceptance; review service/UI; concurrency/end-to-end verification).

Remaining choices for independent review:

- Confirm numeric evidence/quote/cache/token bounds and response schemas.
- Confirm producer commitment immutable identity hash field set versus full preview fingerprint. Mutable status/sensitivity/freshness must be checked live without making legitimate confirm permanently destroy support.
- Confirm clean409 for same-token replay and audit/commitment success ordering across stores. No source quotation in audit.
- Define ordinary Backend.put support mismatch behavior (preserve authoritative support for status-only updates versus reject/retry) so stale writes cannot grant or resurrect proof.
- Classify unlinked INFERENCE with neither parents nor producer as unknown, not invented episode support; parent-only inference requires proved absence of indexed producer/orphan linkage. Direct-user opaque refs remain unchanged. Missing resolver is not a successful empty lookup.
- Review snapshot-versus-publication response semantics for interrupted acceptance/reassessment; records may persist but must be non-usable, with no fabricated rollback/success claim.

Restore of an old backup cannot retain withdrawal decisions made only in a newer lost installation. Restore quarantine, cross-backup journals, physical erasure and broad model qualification remain explicitly open. No implementation begins until parent branch handoff after this design review.

## 9. Reusable source snapshot seam (later M2c, not implemented here)

Expose the low-level snapshot without importing SelfModel or reassessment types:
`EpisodeSnapshotProvider = Callable[[str], EpisodeSupportSnapshot | None]` (or the equivalent small Protocol method). The returned immutable value contains the exact copied Episode plus relational identity/head/metadata/generation captured by the single SQL read. `EpisodeSupportResolver` accepts that callback, ordinarily `episodes.support_snapshot`, and caches its values. Keep canonical source consistency and original/quote checks in shared low-level functions so a later ClaimStore-context consumer can reuse the same authority rather than invent another source resolver.

The exact copied Episode includes occurred_at, provenance and title as well as body/state; expose a deterministic canonical snapshot/render-binding fingerprint helper from that same value, never from a later store.get. M1d consumes the support-relevant signature; later M2c may bind the exact fields actually rendered into ClaimStore context, including source date. No M2c claim-field rendering, source-time history fix or evaluation-harness prompt change is included in M1d. The separately reported context-time audit remains a distinct follow-up.
