# Retrieval precision correction — 4 November 2026

This is a bounded P0/P1 repair, not complete memory or Mac acceptance.
All examples and model inputs are artificial. No private store, cloud API,
import, app setting or installed application was changed.

## Outcome

The same frozen ten-case development set as the [previous run](../2026-11-04-source-roles/retrieval-results.json)
was run with the same actual installed BGE-M3 weights. The dataset hash is
unchanged. Hybrid exact evidence sets improve **8/10 → 9/10**; lexical
**4/10 → 5/10**. Expected hybrid evidence remains present in all cases;
withdrawn and expired sources remain excluded.

`Wurde die Nachricht abgeschickt?` now delivers only the original note that
says the draft was prepared and sending is not established. Unrelated grant
and presentation notes no longer enter via the shared auxiliary `wurde`.

The Alex Winter purchasing question still retrieves both S5 and S6. S5 is
preferred, but a different qualifier is not enough evidence to establish a
different person: employer, city and department can all describe one person.
The frozen fixture uses `topic:record-*` identifiers, not established person
identities. Its expected IDs have NOT been changed. This one precision case
remains open; positive ranking is not a complete identity repair.

[Results and tested source hashes](results.json) distinguish input delivery
from answer quality, which this capture-only probe does **not** evaluate.
No chat model calls occurred. Embeddings had a 30-second keep-alive, a
300-second test limit and pre/post-call resource checks. Memory pressure
peaked at level 2; free memory stayed at least 35%. This does not prove native
UI responsiveness or normal workload endurance.

## Implementation

- Query-only removal of passive auxiliaries `wurde`, `wurden`, `worden` in
  claim candidate search and matching. Stored lexical-v1 remains unchanged;
  no migration or re-embedding is required.
- Meaningful single-term nouns/names remain, including `Bitte`, `Los`, `Will`,
  furniture nouns `Liege`/`Liegen` and domain nouns such as `Zugangskarte`.
- A complete literal contact request can positively prefer matching named
  context; it cannot exclude other evidence or merge identities. Unsupported
  or ambiguous syntax uses existing ordering.
- Current explicit focus comes from the latest user message. The broader
  three-message query remains available for candidate retrieval. Earlier
  validated evidence/history and its source revalidation are retained.

## Independent review and rejected approaches

A fresh reviewer reproduced four important flaws before this candidate:
(1) blind omission of compatible employer/location contexts; (2) disputed
premises and alternative contexts wrongly treated as identity selections;
(3) previous messages preventing current qualification; (4) homographs lost
by copying the broad source-search function-word list. Ten regression cases
failed before the review corrections and 73 focused cases passed afterward.

The hard exclusion was removed. The broad list was replaced by the narrow
passive-auxiliary rule; premise/alternative questions keep all evidence.
Latest-message focus is explicit. These decisions favor correct source
coverage over a misleading 10/10 development score. The remaining identity
work needs the actual source/person route and representative answer tests.

The expanded regression run initially found three test instrumentation
wrappers that did not forward the new optional focus keyword. Their wrappers
now forward it; all original source-race assertions remain. Equivalent
profile-history wrappers were also updated. No invalidation requirement was
removed. Final affected-suite result is recorded below after completion.

## Acceptance still outstanding

- Source-grounded person choice and actual answers for the remaining case,
  including compatible identities, ambiguous names and user clarification.
- Held-out representative private/source acceptance within actual permission.
- Updated native Mac installation and end-to-end interaction acceptance.
- Full product P0–P6, controlled import and the user's real usage week.

The large import remains paused. No blanket reliability or full-suite claim.

## Final affected regressions

**522 passed** in 66.21 seconds, covering the agent/context, claim index/store,
knowledge/hybrid search, person lookup, source index, evidence answers,
source/time/profile revalidation, claim corrections and hybrid-probe contract.
One existing Starlette deprecation warning; no full-backend-suite claim.
See [test record](tests.json) for the exact file set.
