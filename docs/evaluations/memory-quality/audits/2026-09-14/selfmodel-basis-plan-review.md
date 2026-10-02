# Preimplementation review: M1c parent basis plan

Reviewed `docs/superpowers/plans/2026-09-14-self-model-basis-validity.md` against the ed39aa0 audit and existing goal/context/history contracts. Read-only review; no production edits, models, tests, or subagents in this turn. Recognized episode evidence remains explicitly open.

**Conclusion:** the bounded parent-only patch is coherent and appropriately non-destructive. Before implementation, make the following four choices explicit; otherwise reasonable implementations can violate the plan's own invariants.

## 1. Unknown traversal must be withheld, not merely qualified

Plan lines 37-46 allow qualification for ambiguous historical links and forbid laundering a “missing protected basis”, but a missing node or exhausted traversal cannot tell whether unseen ancestry is protected. Choose fail-closed withholding of the entire candidate when traversal is incomplete (missing node, cycle, budget exhaustion), including DECISION and goal patterns. Only offer a review-qualified item after a complete walk establishes that all ancestry is visible at the provider's ceiling and not redacted. Diagnostics should report a generic incomplete/withheld condition without identifiers or parent text. This resolves the otherwise underspecified privacy precedence.

Add tests where a decision or goal edge reaches a cycle/cap with protected ancestry beyond the cap, not just a generic inferred STATE. A historical exception exempts relevance/status interpretation, never traversal/privacy.

## 2. Fix rule priority and represent basis separately from age/root status

An assertion can be both INFERENCE and DECISION: audit executed that combination. The first interpretation bullet suggests omission while the next allows historical visibility. Choose privacy/completeness first, then DECISION and exact lifecycle handling, then ordinary inferred current assertions, then ambiguous legacy links. A visible decision must say its basis needs review; it must not be reclassified as a false decision or merely age-outdated.

Specify a separate effective basis field/assessment (or consciously version the complete ContextItem state schema). Existing self_model_history valid_entry/from_items only accept current/outdated/disputed and require input state to equal ContextItem state. Silently inventing “review” without updating this contract will cause perpetual history invalidation. Keeping item.state=current while adding no machine-readable basis field would leave API cards misleading. Prompt and card should consume one explicit basis qualifier with no redundant inference.

For unchanged review-qualified decisions, history revalidation compares the complete current assessment and dependency signature against its captured assessment. It must NOT apply eligible() to every ancestor: a stable retracted parent must be compatible with a stable qualified decision, while ancestor redaction/sensitivity escalation must still withhold it. Version legacy lineage so root-only metadata cannot silently certify an untracked basis.

## 3. Make goal pattern recognition exact and edge-local

Existing finish(): STATE + structured goal_outcome in {achieved,stopped} + goal_id referencing a GOAL + supersedes and derived_from referencing that same goal + parent.superseded_by == completion.id. Existing reopen(): GOAL derives from/supersedes the typed completion, whose goal_id resolves the original GOAL; reciprocal supersession must match at each stage. Reopened GOAL has no new structured marker; requiring one would break actual existing data. Parent status can change during subsequent lifecycle steps, so validate expected historical relationships rather than “parent ACTIVE”.

The exemption is for that edge's deliberate SUPERSEDED status, not the entire subtree. Continue traversing original goal ancestry for privacy and other unsupported premises. Multiple or malformed extra edges must not gain the exemption from one matching edge. Source strings or statement wording alone are not proof. Include negative tests for arbitrary supersedes/derived_from pairs, broken reciprocal IDs, wrong original kind, and extra protected ancestry, alongside positive real finish()/reopen() calls.

## 4. Freeze exact assessment inputs once and preserve the existing M1b race boundary

“Exact selected-object snapshots” (lines 24-26) needs to cover both selected root and every parent used to make/render its assessment. Use one per-build bounded resolver/cache of frozen objects and one evaluation time; do not independently reread parents for display then history metadata. The MemoryBackend can expose mutable object references, so holding references alone is not a frozen snapshot. If a parent changes after capture, subsequent validation must invalidate the answer/history against that captured signature rather than certify it with a later lookup. Never overwrite captured fingerprints with the latest authoritative ones before comparing.

Add deterministic tests that mutate an unselected parent between assessment and signature construction and during provider completion (using the existing M1b race mechanism). Validate rendered item, persisted dependency signature, and whether a stale answer is retained. These tests require only a recording provider, no real model or thread timing. Preserve established invalidation/response semantics; no new global revision tracker is necessary.

## Scope and acceptance

The plan correctly separates episode evidence and correctly avoids automatic retract/redact cascades. Do not count ignored-episode reproduction as repaired by M1c. The proposed acceptance list covers the principal validity cases; add the four edge-case clusters above and enforce effective ancestor sensitivity even for historical exemptions.

Do not broaden this patch into changing all SelfModelStore.usable() callers: goal lifecycle and historical views have different contracts. A shared read-only context/history assessment is sufficient for the scoped provider/current-card defect. Root status, persisted transcript, and existing privacy redact cascade should stay intact.
