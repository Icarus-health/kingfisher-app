# M1c: validity of a SelfModel statement's supporting basis

Use superpowers:subagent-driven-development after M2b, before model answer tuning.
Immutable audit: `../../evaluations/memory-quality/audits/2026-09-14/selfmodel-dependencies-audit.md`,
including actual-provider reproductions at ed39aa0. This is an amendment driven by
confirmed failures, not an assertion that all derived_from links have one meaning.

## Confirmed failures and invariant

A selected inferred child remains unqualified current after its unselected parent is
retracted; the old assistant answer also survives reload. A decision projection marks
the same changed basis as needing review while chat omits the qualification. An
inference from an ignored episode also remains fresh context. Fix both fresh context
and history; resetting history alone reintroduces the same invalid derivation.

Do not retract or delete descendants automatically. A historical decision still
happened even when a premise changes. Goal finish/reopen deliberately use both
supersedes and derived_from and must keep their existing historical meaning.

## First bounded implementation: SelfModel parents

Add one shared read-only basis assessment for selected SelfModel objects and history
validation. Traverse derived_from with a distinct-node budget, cycle detection and
shared-ancestor memoization. Preserve exact selected-object snapshots, not a later
root lookup. A versioned dependency signature includes parent fingerprints, effective
time/status and sensitivity; changes invalidate old unqualified assistant history.
Do not persist additional ancestor plaintext or treat hash matching as authorization.

Interpretation rules:

- Inferred current claims whose live basis is withdrawn, disputed, superseded,
  expired, future, missing or structurally incomplete must not enter unqualified
  current knowledge. Prefer omission with a neutral coverage explanation.
- Historical decisions may remain visible with an explicit basis-review qualifier.
  Unchanged qualified context must remain usable across subsequent turns rather than
  repeatedly resetting. Qualification is not a new fact or commitment.
- For other legacy ambiguous links, qualify uncertainty without declaring the child
  false. Do not silently apply a generic active-parent rule to all history edges.
- Preserve the exact goal finish/reopen pattern using documented typed state and
  reciprocal supersession relationships; do not grant a broad exemption merely
  because two arbitrary records contain a supersedes link or a source-ref string.
- Privacy takes precedence across every edge: redaction, missing protected basis or
  sensitivity above the current provider ceiling cannot be laundered into a less
  protected descendant. A review qualifier does not permit otherwise withheld text.
- Missing nodes, cycles and budget exhaustion cannot yield fully supported current
  knowledge. Diagnostics must not reveal hidden parent text.

Use the same assessment in actual prompt rendering, current API context cards and
persisted history revalidation. Preserve the visible transcript, existing approvals,
root status semantics, redaction cascade and legitimate goal workflows. No new store,
model, download, private data migration or cloud access.

## Binding preimplementation refinements

Independent review: `../../evaluations/memory-quality/audits/2026-09-14/selfmodel-basis-plan-review.md`.

1. Incomplete traversal withholds the whole candidate, including decisions and goal
   history. Unknown ancestry may contain protected data. Review qualification is
   permitted only after a complete privacy-safe walk; no hidden IDs in diagnostics.
2. Rule priority: completeness/privacy, then historical decision/exact lifecycle,
   then ordinary inference, then ambiguous legacy links. Carry basis as a separate
   explicit machine-readable qualifier in prompt/cards and a versioned history
   schema; do not overload current/outdated/disputed silently. Root-only legacy
   lineage cannot certify previously untracked dependencies. Stable withdrawn
   parents can support an unchanged review-qualified decision's history; never
   require every ancestor to be ACTIVE during that revalidation.
3. Goal recognition is edge-local. Finish is typed STATE + goal_outcome + goal_id
   referencing GOAL, matching supersedes/derived_from and reciprocal superseded_by.
   Reopen is GOAL linked reciprocally to that typed completion and original goal;
   existing reopen records have no new structured marker. Exempt only the deliberate
   SUPERSEDED status on that edge, never other ancestry/privacy or arbitrary extra
   edges. Test the real finish/reopen APIs and malformed near-matches.
4. Freeze copies of root and parents once per build with one clock and bounded
   resolver; mutable MemoryBackend references alone are insufficient. Derive both
   rendering and dependency signature from those copies. Test deterministic parent
   mutation between capture and metadata creation and during provider completion;
   never replace captured fingerprints with later values to make validation pass.

These choices keep unknown ancestry withheld, with the acknowledged cost that some
legacy ambiguous records require review rather than automatic current use. They do
not change global SelfModelStore.usable() or historical business views.

Implementation design `../../evaluations/memory-quality/audits/2026-09-14/m1c-design.md` is accepted with
these explicit choices: 128 distinct assessment nodes for the whole build/validation,
not per root; parent age alone is not withdrawal (currency still affects signature);
hide changed old current cards rather than inventing a qualification the model never
saw. Review-qualified constraints must be grouped as review data, never binding user
instructions. Wire the explicit basis-review label into the existing frontend card
with minimal change; no redesign. Preserve root eligibility and existing historical
views. The snapshot is optimistic with pre/post validation, not a claimed atomic
cross-store snapshot or protection against arbitrary ABA writes.

## Separate immediate follow-up: recognized episode evidence

The episode failure is not solved by parent assessment. Keep it explicitly open until
the next bounded patch resolves known exact local source links (including secondary
evidence). Arbitrary source_ref values remain opaque: no network fetch, no guessing
an identity namespace. Future accepted consolidations should preserve all evidence
IDs/version/quotes; existing authoritative proposal/produced links require a bounded
legacy resolution strategy. Inspect that strategy before implementing, since scanning
only the newest episodes would reproduce the old retrieval defect.

## Acceptance

Actual provider input with only child selected, then parent/grandparent withdrawal;
same-agent and persisted reload; fresh query after invalidation; supersession,
dispute, clock-only expiry/future dates, changed fingerprint and sensitivity;
historical decision with explicit review basis; goal finish and reopen positive
controls; missing parent, cycle, diamond, traversal cap; ordinary stale-age control;
unchanged qualified follow-up preserving history; current API cards consistent with
actual model input. Tests use synthetic records and a recording provider.

Review independently, run affected suites and full supported backend checks. Do not
claim complete source deletion/restore or SelfModel evidence coverage from this patch.
