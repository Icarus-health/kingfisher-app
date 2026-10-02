# M1c parent-only basis assessment: read-only implementation design

Prepared against the current shared checkout on 2026-09-14. Repository production and tests were not edited. M2b files are actively changing; re-read relevant integration sites after its immutable handoff. Inputs: binding M1c plan, selfmodel-dependencies audit and basis plan review. This document proposes APIs, not completed implementation or verified fixes.

## Module/API boundary

Add `self_model_basis.py`, depending on model/currency and a minimal `get(id)` resolver, never Agent/server/store mutations. Avoid a circular dependency with self_model_history: put canonical assertion fingerprint serialization in the basis module (or a tiny shared module), then let history import it. Keep history.capture as the compatibility entry point only while converting fixtures; production capture must require the completed assessment rather than silently synthesizing an empty basis.

Suggested public contract:

```
BASIS_VERSION = 1
MAX_BASIS_NODES = 128

FrozenBuild(store, *, at, max_sensitivity, node_limit=128)
  capture_root(assertion) -> FrozenAssertion | Withheld
  assess(frozen_root) -> BasisAssessment

BasisAssessment (frozen)
  disposition: 'include' | 'withhold'
  qualifier: 'none' | 'supported' | 'review'  # only for included roots
  review_reason: 'changed' | 'ambiguous' | 'changed_and_ambiguous' | None
  signature: sha256 | None
  # private frozen root/graph facts retained only in this build

public_qualifier(assessment) -> {'version':1, 'state':..., 'reason':...}
capture_input(frozen_root, assessment, *, at) -> version-2 history entry
```

`none` means no SelfModel parent links, not universal evidence support. `supported` means the completely walked SelfModel parent graph satisfies this limited contract. No episode/source-ref liveness assertion is made by either value. Public labels should say “Verknüpfte Selbstmodell-Grundlage”, not “all sources verified”. Omitted roots receive no public ID, ancestor ID, source text, signature or per-reason diagnostics. One neutral packet coverage flag/note suffices: some potentially relevant statements could not be supplied because their basis could not be established. Do not reuse withheld_count: its existing prompt explicitly describes sensitivity protection, whereas basis omission can have other causes.

## Frozen capture and bounds

Use `copy.deepcopy` on each Assertion immediately when it enters the assessment cache; nested provenance/structured/tags/lists must be isolated. MemoryBackend returns mutable references. Canonical JSON serialization uses to_dict + sorted keys + compact separators + ensure_ascii=False + allow_nan=False, retaining current M1b hash semantics. Fail closed on malformed Assertion/fields/links or serialization failure.

One build has one evaluation instant and one bounded resolver/cache. Count distinct assessment nodes including selected roots, regardless of whether obtained from a candidate object or store.get. A node can only be captured once; diamond ancestors reuse that copy. Store.get is never called again for that ID in the same build. Freeze the candidate root supplied by context selection; do not replace it with a later store.get result. Rendering, source/age description, eligibility and signature all consume that frozen root and the assessment computed from frozen parents.

The existing profile candidate scan/ranking may still read the broader store; the new 128-node limit bounds assessment and ancestor resolution, not all existing profile retrieval. Assess ranked potential selections until the existing item budget is filled or the assessment budget is exhausted. At exhaustion, withhold further candidates and report generic limited coverage. Do not allocate an unbounded snapshot of all possible roots merely to implement caching. Once a candidate is captured, use its frozen value for subsequent scoring/rendering; capturing a ranked candidate can require recomputing its eligibility and score if it changed since initial ranking. A slight selection change is acceptable; certifying text with a different snapshot is not.

Use iterative DFS with visiting/done sets and postorder facts, not Python recursion. Missing/malformed IDs, cycles and budget exhaustion withhold the entire candidate, including decisions and lifecycle roots. Memoize immutable per-node capture and computed traversal facts; edge interpretation must remain edge-local. Do not memoize a parent's SUPERSEDED exemption as a node-wide property: another incoming edge may not qualify.

One cache across history's maximum128 selected roots also caps total distinct nodes per validation. Fresh roots jointly exceeding this bound fail closed rather than expanding to128 ancestors per root. Missing nodes count toward attempted distinct-node budget. The cap need not leak which root exhausted it.

## Evaluation and rule priority

1. Root still follows existing M1b eligibility: ACTIVE/DISPUTED only, valid_from<=at, at<expires_at when present; root sensitivity within ceiling. No change to SelfModelStore.usable(), historical views or redaction cascade.
2. Complete walk and privacy first. Every encountered node must exist and have valid shape, must not be REDACTED and must be within provider sensitivity ceiling. Failure withholds every root whose walk is incomplete or protected, regardless of historical semantics. Never render the descendant text with a privacy review qualifier.
3. Determine ordinary effective parent state directly from frozen status and explicit interval at the shared instant. ACTIVE alone is insufficient if future/expired. Do not require callers to materialize expiry through usable(). Record disputed/retracted/superseded/expired/future as unavailable live basis; only exact goal edges may exempt the intentional SUPERSEDED condition.
4. Complete privacy-safe graph then permits interpretation. DECISION takes priority over source_type=INFERENCE: preserve occurrence, attach review if any nonexempt basis failure/ambiguity exists. Exact lifecycle roots can remain usable through their deliberate status edges, but additional failed/ambiguous edges still produce review. Ordinary inferred roots with unsupported or ambiguous required ancestry are withheld. Other legacy links are review-qualified without declaring the statement false.
5. Edge semantics are explicit: recognized goal lifecycle edge; decision basis edge; ordinary inference premise edge; otherwise ambiguous legacy edge. A valid-looking active parent does not prove the meaning of a legacy link. Ambiguous edges cause review even if statuses are currently active. Propagate graph issues transitively; an inference derived from a review-qualified decision is not silently fully supported.
6. Age-only currency is distinct from explicit validity. Keep existing root current/stale/outdated rendering unchanged. Do not invent global freshness inheritance from a parent's age; parent's currency may enter the signature so its transition invalidates old interpretation, but age alone is not equivalent to withdrawal. Root age-only outdated positive control remains visible with its existing historical qualification.

## Exact lifecycle edge checks

Finish edge C->G qualifies only if C.kind=STATE; C.structured is a dict with goal_outcome in {achieved,stopped} and goal_id=G.id; G.kind=GOAL; G.id occurs in both C.supersedes and C.derived_from; G.superseded_by=C.id. No source_ref or statement matching. Exempt only G's SUPERSEDED status on this edge, not its explicit future/expiry or any privacy/traversal condition.

Reopen edge R->C qualifies only if R.kind=GOAL; C is a typed completion as above whose original G is present in the same bounded graph; C.id occurs in both R.supersedes and R.derived_from; C.superseded_by=R.id; and the C->G reciprocal finish relation validates. R has no required structured marker because actual reopen() writes none. Exempt only C's SUPERSEDED status on R->C. The C->G edge independently qualifies for its own exemption. Still traverse G.derived_from and all additional R/C edges normally. Duplicate/malformed refs fail shape checks; unrelated extra well-shaped edges get no exemption.

Do not require a historical completion to remain ACTIVE when its reopened successor is selected. Root selection itself still excludes superseded roots as before. Repeated finish/reopen chains follow the same local typed patterns.

## Signature and history version

Bump self_model_history.VERSION from1 to2. Keep old root fingerprint/state/currency, add explicit basis contract and aggregate signature:

```
{
 'fingerprint': '<root canonical sha256>',
 'state': 'current|outdated|disputed',
 'currency': 'current|stale|outdated',
 'basis': {'version':1, 'state':'none|supported|review', 'reason': None|...},
 'basis_signature':'<sha256>'
}
```

Aggregate signature hashes a canonical versioned object containing root ID, sorted captured node IDs/fingerprints, each node's effective status/interval result, currency and sensitivity, sorted derived edges and their edge-local interpretation, plus final basis qualifier. No ancestor plaintext is persisted. Do not include the raw evaluation timestamp or provider ceiling in the signature: unchanged qualified context would reset every turn or on a harmless increase in ceiling. Include effective time categories and evaluate privacy separately against the current ceiling; true interval/currency transitions change signature. Root/canonical hashes already bind explicit date and sensitivity fields. Avoid serializing exception details or hidden IDs to diagnostics.

`valid_entry` requires exact keys/types, bounded enums/version, hex hashes and state/currency consistency. `from_items` requires both ContextItem.basis and entry.basis match, as well as state matching; deep-copy nested metadata. `read_lineage` rejects v1/missing/malformed markers instead of certifying untracked ancestors. Reset scope remains model history only; transcript remains untouched. Empty v1 histories are also conservatively treated as unknown unless a separately justified compatibility rule is agreed; simplest implementation rejects all old versions consistently.

`available(inputs, store, ceiling, at=...)` constructs one fresh FrozenBuild and recomputes each included root assessment, requires include, and compares the full entry exactly. Do not call ordinary eligible() on every parent: stable retracted parents legitimately reproduce a stable review-qualified DECISION signature. Parent mutation after initial capture changes later validation; never replace captured hashes with newer reads to force agreement.

## Integration points

- context.py: freeze selected root and assess before creating ContextItem/assertion_map; map contains frozen roots. Add optional explicit `basis` metadata to SelfModel items, separate from state and reason (reason remains relevance). Keep knowledge identity fields from M2b intact. Append one deterministic basis qualifier to the actual line; review-qualified constraints must not appear as unqualified “Bindende Grenzen”. Prefer a separate review-qualified section before normal constraint/current grouping while retaining age/dispute information in the line. This prevents review-qualified instruction-like records retaining accidental stronger authority.
- ContextPacket: optional generic basis-coverage flag/count with a neutral prompt note. Agent reconstructs ContextPacket when adding knowledge items, so carry the new field there without dropping M2/M2b metadata.
- self_model_history.py: version2 parser/capture/available share the new assessor. Agent.send already accumulates exact item entries; existing pre/post provider/tool/resolve checks and reset logic should require minimal wiring/type updates, not new independent validators. Pending approval semantics remain unchanged.
- server.py current conversation cards: validate captured items through the same version2 assessment and same instant, not a newly guessed qualification. If basis changed since the actual prompt, hide the old current card; do not rewrite it into a new review card that the model never saw. A subsequent actual turn may persist the new qualified decision item. Keep historical message metadata and visible transcript unchanged. Current API uses broad local-display sensitivity; preserve that behavior while honoring any explicitly stored/provider scope as applicable, and never manufacture model-egress authorization.
- Frontend card label: if basis=review, show deterministic review text from explicit field (or server-generated fixed qualifier), preserving existing state chips. If this is considered outside worker ownership, parent must wire/review it before claiming visible cards convey review semantics; merely returning a field is API correctness, not demonstrated UI behavior.

## Test sequence

Write synthetic regressions before implementation using real Agent and recording provider, ensuring only the child root is selected. Matrix: parent/grandparent retract, dispute, supersede, explicit expiry/future without usable() call, mutated fingerprint and sensitivity; same Agent, persisted reload, fresh first query, follow-up after reset. Assert prior assistant text absent from actual provider input, fresh inference omitted, transcript preserved.

Decision controls: historical DECISION+INFERENCE with withdrawn parent gets separate basis=review in actual prompt and cards; unchanged second/third turn keeps qualified assistant history without repeated resets. Test malformed v2, v1/missing marker, all-prior-input validation, resolve paths and external egress checks.

Goal controls call actual finish/reopen APIs, including repeated lifecycle. Negative near-matches: arbitrary supersedes pair, wrong root/parent kind, broken reciprocal links, malformed structured goal_id/outcome, extra protected/invalid ancestry. Incomplete graphs (missing/cycle/budget) withhold decisions and goals too. Diamond must capture shared ancestor once and not spend the budget twice.

Race tests mutate an unselected MemoryBackend parent after graph capture but before metadata construction and during provider completion. Assert captured entry remains old, fresh validation fails and existing invalidated-turn response behavior runs. Include nested structured/provenance/list mutation to prove deep copies.

Normal age-only outdated root remains qualified as before; valid basis preserves history. Current API old card disappears after parent change while message body remains; new review decision card agrees with its actual model input. Run existing profile_history, context, decisions, goals, claim/evidence history, server persistence and full backend suites. No model or private data.

## Remaining ambiguities / explicit boundaries

- Binding refinements supersede the audit's earlier suggestion to include episode state in the same signature. M1c signature covers SelfModel parents only. Ignored episode and secondary consolidation evidence failures remain OPEN; no namespace guessing or episode scan here.
- Root status eligibility is intentionally preserved: “historical decisions may remain visible” means an otherwise eligible decision whose basis changes, not reviving a root that is itself retracted/superseded. Historical views continue displaying those roots independently.
- The plan does not explicitly specify parent age-only semantics. Proposed resolution above preserves validity-vs-age separation, with currency captured but no age-only premise failure. If stricter freshness propagation is wanted, it needs explicit acceptance beyond this patch.
- Exact goal expiry exemption is narrower than broad historical validity: only SUPERSEDED is exempt, so a genuinely explicit expired/future original goal can lead to review/withholding even in a typed lifecycle. This follows the binding “never other ancestry/privacy” rule; tests should codify it.
- Snapshot capture is deterministic and immutable, not a global transactional snapshot across MemoryBackend or store connections. A concurrent edit during the multi-node read is detected by existing revalidation against the captured signature before/after provider use; a new store-wide transaction/version mechanism is not introduced. Repeated adversarial ABA writes remain beyond that existing optimistic boundary.
- Two budget interpretations were possible. This proposal explicitly uses128 distinct nodes across a build/validation rather than128 per root to keep worst-case work bounded; exhaustion may conservatively omit otherwise valid roots. No completeness guarantee.
- No implementation has begun. Wait for explicit post-M2b implementation handoff and independent review sequencing.
