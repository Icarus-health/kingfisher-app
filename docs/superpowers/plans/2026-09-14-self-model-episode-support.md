# M1d: episode support of accepted SelfModel inferences

Execute after the parent-basis patch, using superpowers:subagent-driven-development.
Design authority is the reviewed existing contract plus
`../../evaluations/memory-quality/audits/2026-09-14/m1d-design.md`.
Read that design in full. It is a design, not an implemented capability.

## Required result

Ignoring, replacing or withdrawing a required original episode must prevent a
recognized accepted SelfModel inference from returning as current via fresh context,
old assistant text, secondary evidence or source reopening. Do not erase the original
record or falsely treat a historical decision as never having occurred. Use M1c's
shared qualifier/privacy machinery; preserve ordinary direct user assertions.

## Binding choices

1. Resolve canonical accepted proposal support through an indexed exact produced
   assertion lookup. No newest-N proposal/episode scan. Validate all evidence, not
   just provenance.source_ref or the first original. Multiple producers or incomplete
   evidence are explicit unknowns. Proposal and episode metadata are data, not rights.
2. Capture complete typed support on future accepted assertions, including proposal
   ID, original episode/version/quote and durable withdrawal generation. Maintain
   serializer/export/schema compatibility; legacy records remain present.
3. Add an episode support generation that increases on entering ignored and never
   decreases on reopen. Capture it at acceptance, never fill it from current state
   during retrieval. Validate tracked source head/metadata and all original quotes.
   Archived originals remain valid; summaries cannot replace originals.
4. Existing accepted inference records have no historical generation proof. Do not
   silently certify them with a migration baseline. Classify known legacy support as
   needing explicit reassessment while preserving content and historical views.
   No mass deletion, automatic re-approval or fabricated approval timestamp.
5. Provide a small explicit reassessment path for a user reviewing the exact existing
   assertion and its currently valid original evidence. The preview must bind the
   assertion fingerprint, producer and all evidence versions/generations; submission
   rejects stale previews. Reassessment grants use of that evidence now; it must not
   silently refresh last_confirmed_at, invent a new factual statement or alter source
   permissions. Invalid/ignored/missing sources cannot be reauthorized through this
   path. Use the existing review surface with minimal UI, no autonomous model tool.
6. Opaque source_ref values never cause network access or namespace guessing. A
   missing accepted producer cannot be replaced by a name match. Exact legacy local
   produced relationships may establish an incomplete recognized link, never complete
   support without the original proposal evidence. Parent-only inferences follow
   M1c; do not manufacture episode requirements for arbitrary direct user statements.
7. Episode-backed support remains local-only while episode sensitivity lacks an
   explicit contract. Enforce at least assertion and accepted-proposal sensitivity;
   a historical/review qualifier never authorizes otherwise withheld text.
8. Cross-database acceptance is not atomic. Capture support before assertion creation,
   require completed accepted producer linkage for usability, and revalidate at
publication/provider boundaries. Interrupted acceptance stays non-usable.

## Accepted review refinements

`../../evaluations/memory-quality/audits/2026-09-14/m1d-design-review.md` maps the concrete surfaces. The
delivered UI is app/kingfisher, not the legacy app/src proposal page. Add a compact
dedicated SelfModel statement-review subsection in the existing memory area; person
merge review and ClaimStore claims retain their separate meanings. Evidence review
must disable both ignore AND reopen actions (allowIgnore=false alone does not do so
in the current ProfileSource component). Prefer an explicit read-only viewer mode.

Use authenticated preview/submit routes, never an Agent tool. Submission accepts an
expiring server-issued preview token and explicit confirmation, not client-supplied
evidence or timestamps. Bind exact assertion content/kind/producer, all evidence and
source generations, and M1c ancestry. Validate canonical producer correspondence so
copied support cannot authenticate another assertion. Reject non-ACTIVE, expired or
future roots; an age-outdated ACTIVE root may receive support while remaining age-
outdated. Never call confirm, record, proposal.accept or source reopen for reassessment.
Preserve all original factual/provenance/status timestamps and domain structured data.
Same-token retries must be idempotent or cleanly stale, not duplicate approvals.

Typed support is not accepted through generic RecordIn. Redaction must remove its
quote-bearing fields. Missing/malformed producer/source data is fail-closed. Audit
IDs and old/new support hashes only, not original quotations. Verify actual mutation
serialization across routes and workers; a single route lock is not a transaction
across all stores. Interrupted or racing updates cannot publish a current inference.

## Implementation and verification sequence

Concrete design and independent review are preserved as `m1d-design.md` and
`m1d-design-review.md` in the same audit directory. The review's three corrections
are binding: generic imports/writes cannot issue or replace local authorization;
the producer is reserved before assertion/supersession side effects; durable
authorization and secondary audit failure have explicitly different outcomes.

Accepted implementation order: hold the exact producer transaction, then an atomic
assertion-backend batch encompassing creation and reciprocal supersession changes.
Commit producer authorization first, then the assertion batch. Failure before
producer publication rolls back both; failure after producer publication but before
assertion commit leaves a non-usable accepted producer with a missing root, while
preexisting assertions and their links remain intact. Test real two-connection races
and both failure boundaries. This is not a cross-database atomicity guarantee.

The dedicated durable producer commitment is the authorization record. Failure to
append a secondary audit event must be reported honestly as an audit limitation;
it must not falsely report a denial after usable authorization has been committed.
Commitment issuance remains restricted to the trusted acceptance/reassessment path.
Ordinary backend writes with stale support reject and require rereading; explicit
redaction clears support. Follow the reviewed evidence, cache, pagination and token
bounds, immutable identity hash allowlist and clean 409 replay behavior.

First inspect and record exact migration/API/schema/UI locations before changing
code. Independently review that concrete design, including the reassessment preview
contract. Then add synthetic red regressions and implement the smallest coherent
vertical slice. Avoid deploying the generation migration separately from acceptance
capture. Reuse shared source and parent assessment functions where their semantics
match; do not duplicate competing validity rules.

Required controls: second evidence withdrawn; source version/head/metadata changed;
same body on unrelated source; archive versus ignore; source ignored and reopened
before the next conversation; parent-supported inference versus opaque direct user
provenance; old producer behind thousands of new proposals; duplicate/missing producer;
malformed/oversized support; interrupted acceptance; unchanged support across restart;
actual provider history reset and current cards; local-to-external switch; stale and
valid user reassessment; no silent freshness change; export/import and migration of
legacy rows. Preserve old raw diagnostic attempts. Run independent review and relevant
backend/frontend/CI/runtime checks before integration.

## Explicit remaining boundary

Generation stored in an old backup cannot know later decisions that were lost with
the newer installation. This patch does not solve restore quarantine, cross-backup
deletion journals or physical erasure. Restore remains a separately blocked release
gate until its runtime boundary is implemented and tested.
