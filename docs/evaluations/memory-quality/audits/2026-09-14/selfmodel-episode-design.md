# Recognized episode support for legacy SelfModel — minimum design

Read-only design against immutable ed39aa0 extracted at `/tmp/kingfisher-memory-work/dependencies-ed39aa0`. Scope: legacy SelfModel inferences and future acceptance through the existing consolidation path. ClaimStore behavior is not claimed repaired or changed. No implementation, production reads, model calls, or migration was performed.

## What authoritative information exists

- `Proposal.evidence` is an ordered list of `{episode_id, quote, digest}` (`proposals.py:111-127`). `Proposal.produced` is the resulting assertion ID, and ACCEPTED records have decided_at. The full list survives serialization in proposals.document.
- `Consolidator.accept` records only evidence[0].episode_id as assertion.provenance.source_ref; then accepts the proposal with produced=assertion.id; finally appends that ID to every evidence episode's produced list (`consolidation.py:417-439`). Final episode writes explicitly tolerate failure. Therefore missing Episode.produced is NOT proof that an accepted Proposal relation is invalid. Conversely produced alone has no quotation or accepted digest and cannot prove complete support.
- `ProposalStore.get(id)` is indexed by PK. There is no produced-assertion reverse lookup. `all_proposals(limit=200)` is newest-first: unsuitable. Existing indexes cover state/kind/fingerprint, not produced.
- `EpisodeStore.get(id)` is indexed by PK. `source_head(source_key)` is indexed by PK. `source_key` and metadata_digest exist as relational columns but are NOT present on the Episode object returned by get. There is no API returning episode identity plus source head/metadata in one snapshot.
- No indexed reverse lookup exists for episode.document.produced. `all_episodes(limit=500)`, pending(), recent(), and analysis batches are not complete dependency lookup mechanisms.
- `Episode.ignore` only writes state=ignored. `reopen` returns it to NEW (and verifies it has not been replaced as a tracked head); neither records a durable revocation generation. `mark_consolidated` later sets consolidated. Body digest alone cannot distinguish never-withdrawn support from withdrawn-and-reopened support.

## Minimum efficient legacy lookup

Add `ProposalStore.accepted_self_model_support(assertion_id)` using exact produced ID, never source-ref string parsing or newest-N scans. Suggested query after the migration below:

```sql
SELECT document FROM proposals
WHERE produced_assertion_id = ? AND state = 'accepted'
LIMIT 2;
```

Inspect kind and produced inside the returned canonical JSON as well; accept only the legacy assertion-producing kinds actually handled by Consolidator.accept, exclude knowledge/task/confirmation/conflict. More than one accepted producer is ambiguous: fail closed rather than selecting newest or unioning potentially independent evidence. One valid producer contributes its ENTIRE evidence list. Apply an explicit maximum evidence count; exceeding it is incomplete support, never “use first N”. Deduplicate reads by episode ID but validate every distinct evidence quote/digest entry. A PK lookup of each episode yields O(k) indexed reads, with k bounded.

Add a derived scalar column and ordinary index in proposals.db:

```sql
ALTER TABLE proposals ADD COLUMN produced_assertion_id TEXT;
UPDATE proposals
SET produced_assertion_id = json_extract(document, '$.produced')
WHERE json_type(document, '$.produced') = 'text';
CREATE INDEX idx_proposals_produced ON proposals(produced_assertion_id);
```

Update `_put` to maintain this scalar atomically with document on insert/update. Verify column/index/backfill using the existing Migration/verify_schema mechanism and runtime canonical-JSON equality. Do NOT make it UNIQUE: contradictory legacy records must be diagnosable, not cause startup failure. This is an index projection of existing provenance, not a second evidence store. A JSON expression index is smaller SQL but needs explicit expression-index verification beyond the current simple column IndexContract; the scalar is easier to audit with current tooling.

No per-turn Episode.produced scan is needed. If there is no authoritative producer and no new typed support record, never manufacture complete support from source_ref or produced. For known INFERENCE legacy entries with no resolvable producer, mark support unknown/review-required and withhold unqualified current inference. Inferences backed only by valid SelfModel parent relations can retain the parent contract; do not fabricate an episode requirement for every INFERENCE. Truly ambiguous inference provenance requires qualification, not a guessed local source identity.

Optional operator-facing orphan inventory can use a one-time migration/maintenance query over json_each(episodes.document,'$.produced'), but cannot certify evidence completeness. It is not required in the hot path and must not become another canonical link store. Arbitrary refs such as URLs, chat labels, and UI refs stay opaque.

## Future accepted records: typed evidence on the assertion

Prefer a versioned typed optional support field on Assertion over a new evidence table. Suggested shape: `{version:1, proposal_id, episodes:[{episode_id,digest,quote,source_key,metadata_digest,support_generation}]}`. Keep it separate from arbitrary domain `structured` (already used for goals and other kinds); support must be validated and preserved by serialization/backends/export. A reserved structured namespace would reduce schema edits but needs equally strict ownership/validation and collision handling, so is not intrinsically safer/smaller.

Capture ALL evidence from the approved proposal plus the exact episode/source identity snapshot at acceptance. Do not create quotes by rereading current text or fill an absent legacy digest with today's digest. Exact quote may duplicate the proposal's existing quote; this bounded duplication buys portable lineage and prevents dependence on proposal retention. Alternatively only embed proposal_id and keep evidence canonical there, but then loss of the proposal must withhold an otherwise valid exported/imported assertion. Choose the typed snapshot for future portability; existing raw source_ref remains unchanged as a display label.

Acceptance must validate every evidence entry before creating the assertion. Existing flow creates assertion before proposal.accept and spans databases. Include typed support in the initial assertion write so a failure before reverse-linking cannot leave a usable orphan; a missing accepted producer or incomplete acceptance state must fail closed. Do not claim multi-database atomicity. Serialize with existing conversation/source mutation locks where available and validate source generations again before publication; interrupted writes stay non-usable until completed/reassessed.

## Liveness and truth rules

Evaluate via one read-only helper shared with fresh context and history signatures; use the frozen root/episode snapshots that actually informed rendering.

- Every required episode must exist; IGNORED or SUMMARY cannot establish support. ARCHIVED original is allowed: archival is not withdrawal. Missing/empty digest or quote is unknown, not automatically repaired. Body digest must match the accepted digest and quote must match using the existing normalized whitespace/case contract; record the original quote, not only its normalized/hash form.
- Check authoritative source_key/head plus metadata_digest when a source is tracked. The selected episode must be the head for its recorded source key, and expected metadata must match. Do not substitute another episode solely because body digest matches. An untracked original with source_key='' has identity episode_id+digest; don't guess a head from provenance.source_ref. Ambiguous legacy head ownership must withhold.
- Add `EpisodeStore.support_snapshot(id)` querying relational identity columns, canonical document, and LEFT JOIN source_heads on source_key in one DB read. Return a frozen value containing episode plus source/head/metadata/generation. If row/document identity, state or digest disagree, fail closed. Preserve one moment/cache per assessment and revalidate on history/provider-boundary paths; state hashes are not authorization.
- Validated source contents are untrusted evidence. No source text in system prompt, no source-ref network request, no relationship inference from labels.
- Episode has NO sensitivity field. For recovered legacy support, enforce at least assertion sensitivity AND accepted proposal sensitivity (maximum); do not invent source-level clearance from its absence. Conservatively keep recognized episode-backed legacy inference local-only until episode classification is explicit, matching the existing broader knowledge boundary. This is a deliberate tightening: test external provider exclusion. Historical/review qualification never grants permission to expose otherwise withheld descendant text.
- A failed source basis does not delete historical decisions/events. Apply the parent patch's basis-review semantics only where complete ancestry and privacy allow it; otherwise omit. SelfModel raw status and visible transcript remain unchanged.

## Reopen requires a durable withdrawal token

A helper checking only state, digest, quote and head is insufficient: ignore -> reopen -> reconsolidate restores the same tuple. Existing ClaimStore can remember invalidation independently; legacy SelfModel cannot. Add a monotonically increasing `support_generation` to episodes, incremented exactly when entering IGNORED (idempotent repeated ignore does not increment). Include it in support snapshots; reopening never decrements it. New explicit acceptance/reassessment captures the current generation. Old support requires exact generation equality even when the source is NEW/CONSOLIDATED again. Carry this token through history signatures without ancestor plaintext.

Migration caveat: generation=0 cannot retrospectively prove that a pre-migration episode was never ignored and reopened. Current data lacks that history. Do NOT write a legacy assertion's expected generation from its current episode on every read. Minimum safe policy: legacy assertion with recoverable accepted proposal but no trustworthy acceptance generation remains `legacy_support_unverified`; preserve it but require explicit reassessment to produce typed support. This trades initial recall for a truthful contract. If product instead accepts a one-time baseline of currently supported legacy records, document that as an explicit migration policy with a historical blind spot; it cannot be described as fully replay-safe. Do not silently select that weaker policy.

For post-migration legacy producer rows created before typed support deployment, the acceptance path must capture support generation at the time of acceptance (typed field or accepted proposal extension); a later lookup cannot reconstruct it. Thus ship acceptance capture and generation migration together, not in separate rollout windows.

## Required migrations and implementation boundary

Two small DB migrations: proposals produced lookup projection; episodes support_generation column. Optional typed Assertion field requires serializer/schema updates but no separate store. Existing legacy contents should not be mass-rewritten or silently re-approved. Read-time resolution can classify unsupported legacy records; explicit reassessment creates the trusted typed support. No background source scans or private data imports.

A narrower patch can immediately withhold recognized ignored/missing sources using exact proposal lookup, but without generation capture it must openly leave ignore/reopen replay unresolved. The complete minimum described here includes the durable token.

## Acceptance tests

1. Producer older than thousands of newer proposals resolves by exact indexed lookup (EXPLAIN QUERY PLAN verifies produced index); all secondary evidence is checked. Newest-N APIs forbidden in this helper.
2. Second evidence ignored/missing/digest-mismatched/quote-mismatched/head-replaced/metadata-changed blocks unqualified current provider input and invalidates persisted prior answer, even when first source remains valid.
3. Duplicate producer => explicit unknown; no producer, empty evidence/quote/digest, oversized evidence list => safe unknown. Episode.produced omissions do not defeat an otherwise complete accepted proposal, and produced-only orphan cannot certify completeness.
4. Same body in unrelated episode/source cannot substitute; archived original remains valid; generated summary rejected.
5. Ignore -> reopen -> reconsolidate before any chat does not revive old support. Repeated ignore is idempotent. Explicit new acceptance under current generation can establish new support. Migration of previously reopened legacy records stays unverified without manufactured expected tokens.
6. Interrupted acceptance before proposal.accept and before episode.mark_consolidated cannot expose a current orphan. Source changes between validation and write/provider boundary are detected with captured signatures.
7. Ancestor/proposal sensitivity escalation and external provider selection cannot export the descendant or hidden source plaintext. API cards and actual provider qualification agree; unchanged qualified follow-up retains its legitimate history.
8. Arbitrary source_ref never triggers network/namespace guessing; exported/imported typed support remains portable and missing source fails closed.

This is a design, not proof these proposed checks already exist. Episode-backed SelfModel validity remains open until implemented and validated.
