# SelfModel dependency audit — immutable ed39aa0

Audit scope: `sidecar` extracted with `git archive ed39aa0` into `/tmp/kingfisher-memory-work/dependencies-ed39aa0`. No repository edits, real model, production records, or network calls. Synthetic actual-provider-input capture executed with the existing workspace Python environment. Reproduction: `/tmp/kingfisher-memory-work/selfmodel-dependencies-repro.py`; observed payloads: `/tmp/kingfisher-memory-work/selfmodel-dependencies-repro.json`.

## Findings

### 1. Retracted basis leaves an inferred current statement and its prior answer eligible

Locations at ed39aa0: `store.py:169-186` changes only the requested assertion; `context.py:182-196` checks each candidate itself; `self_model_history.py:81-93` validates only selected root IDs and their own serialization/state.

Synthetic sequence: record parent P (`Budget authorization.`), then child C (`ORION ist finanziert.`, STATE, INFERENCE, derived_from=[P]); query ORION; assert that ONLY C is in the first provider input; retract P; reload persisted first-turn metadata; query ORION again. Actual second provider input still contains:

> Was du über den Nutzer weißt:
> - [state] ORION ist finanziert. (inference:synthetic, selbst gefolgert; Auswahl: Passt zum Gespräch: orion)

Observed: P=retracted, C=active, item.state=current, self_model_history_reset=false, old synthetic assistant derivation retained. `selbst gefolgert` qualifies provenance but does not disclose that the entire stated basis was withdrawn. This is a current-validity bug, not merely old information shown with its historical date. Parent not being selected is essential: if P was selected too, M1b can correctly invalidate that root and obscure the missing dependency check. Fix must cover fresh context as well as history; resetting history alone reintroduces C immediately.

### 2. Decision projection already knows the basis fell, but chat does not carry that qualification

Same sequence using DECISION produces item.state=current and retains the old answer. Independently, `entscheidungen.alle(store)[0].erschuettert` is true. Existing decision projection (`entscheidungen.py:241-279`) explicitly treats a failed basis as a review reason and preserves the historical decision. Its contract is correct: a decision's occurrence is not erased or proven false by loss of a premise. The defect is the missing basis qualification in the chat rendering, not the decision remaining active/stored. The synthetic decision wording is a compact financing statement; the same metadata path applies to an explicitly historical sentence such as “Ich habe ORION beschlossen.”

### 3. Ignoring a recognized episode does not withdraw SelfModel-derived current knowledge

Locations: legacy accepted consolidation writes first evidence ID to `provenance.source_ref` at `consolidation.py:417-437`, and records all produced assertion IDs on episodes. `episodes.py:513-517` changes episode state only. Actual server ignore handler (`server.py:3426-3437`) invalidates KnowledgeService claims and ignores the episode, with no SelfModel assertion invalidation. `source_ref` is otherwise only a label in context; M1b explicitly excludes it.

Synthetic sequence mirrors that stored contract: create episode E, record INFERENCE C with source_ref=E.id, mark E consolidated with produced=[C.id], send VEGA, ignore E, send VEGA. Actual provider context still describes C (`VEGA ist finanziert.`) as current knowledge. Source is ignored; C is active; history_reset=false in the direct Agent path. This probe did NOT invoke the HTTP ignore endpoint: its claim revision update may independently clear history, but cannot fix fresh SelfModel context reintroducing C. The fresh-context bug is confirmed; HTTP-specific history retention is not claimed.

## Existing behavior that is not a finding

- Control: a STATE captured 400 days ago is item.state=outdated and actually rendered under “Alte Angaben — nicht als aktuell behaupten, im Zweifel nachfragen”. Its presence in payload is correctly qualified; do not count mere string presence as a defect.
- `redact()` already traverses derived_from transitively and removes descendant content (`store.py:188-236,399-416`). Do not conflate privacy erasure with premise retraction.
- DECISION history must remain accessible; existing “erschüttert” behavior deliberately does not mutate it.
- `derived_from` is also historical linkage, not exclusively a live premise dependency: `goals.py:16-21` creates a goal completion that both supersedes AND derives from the original goal, and `goals.py:47-53` does the same for reopening. Requiring every parent to remain ACTIVE would break these normal workflows immediately.

## Smallest correct next contract

Implement a bounded read-only **basis assessment** shared by current-context selection/rendering and persisted-history validation. Do not introduce automatic retract cascades, data deletion, a second truth store, or blanket “all parents active” semantics.

1. Distinguish the truth of the stored statement/event from validity of its supporting basis. Assess live inference premises vs historical linkage explicitly. For legacy ambiguous derived_from edges, conservatively qualify “basis changed/needs review” rather than deleting the child or falsely asserting invalidity. Exempt documented self-superseding goal lifecycle linkage from a live-parent requirement; cover with tests before rollout. DECISION should remain a historical decision with an explicit basis-review qualifier.
2. Persist a versioned dependency signature for the exact selected rendering, encompassing bounded transitive SelfModel parent state/identity and recognized authoritative episode source identity/state/version. Fresh selection and later history checks must use the same effective assessment. A changed basis invalidates the prior unqualified answer; the next turn may include a newly qualified historical item. Do not synthesize a signature from later reads that did not produce the supplied context.
3. For inference assertions whose required premise is retracted, superseded, disputed, expired/not-yet-valid, missing, or source unavailable: never place the unqualified claim in the current-knowledge section. Either omit it from ordinary current context or render it explicitly as unsupported/requiring review, consistent with the assessment. Descendant sensitivity must not permit a protected premise to be laundered through a less-protected inference.
4. Treat arbitrary `source_ref` as opaque provenance, never a URL to fetch or an assertion/episode namespace to guess. Recognize verified local episode relations (canonical typed IDs; legacy exact episode ID backed by existing consolidation/proposal/produced evidence). For future accepted consolidations persist all required evidence episode IDs, not just the first source_ref; existing episode.produced can help conservatively recover known legacy linkage. Unknown free-form refs are not proof of a missing local dependency. Missing a known typed source is fail-closed.
5. Use bounded cycle-safe traversal with memoized shared ancestors. Missing nodes, cycles, budget exhaustion, or malformed required links must not yield “current/fully supported”. Keep omission/review diagnostics free of hidden premise plaintext. Existing source revision/reopen policy must not automatically reinstate previously unsupported conclusions without reassessment.

This requires a small explicit dependency-assessment contract, not merely adding recursion to `usable()`: current APIs mix historic linkage and evidentiary support. A narrow first patch could add non-destructive basis qualification plus history signature for derived_from, followed by recognized episode support; both fresh rendering and history must be covered in each patch.

## Acceptance cases

- Actual Agent provider capture: only child selected, parent later retracts; child no longer unqualified current, old assistant derivative absent. Repeat with grandparent -> parent -> child, shared ancestor, persisted reload, and a follow-up after the reset that retains the newly qualified answer rather than resetting forever.
- Fresh first turn AFTER parent invalidation gives the same safe qualification/omission; no dependency on prior history for safety.
- Supersede, dispute, expires_at crossing, future valid_from, parent fingerprint change, missing parent, sensitivity escalation; clock change must work without materializing parent status through a separate read.
- Decision remains stored and historical occurrence visible; failing basis is explicitly marked in actual provider input, matching the existing decision view. No automatic retraction/deletion.
- Goal finish/reopen remains usable despite deliberate supersedes+derived_from; privacy redact cascade remains unchanged.
- Legacy consolidated SelfModel inference with known episode evidence: HTTP ignore endpoint, source version replacement, missing typed source, and reopen/reassessment; actual fresh provider payload must not reintroduce unqualified current inference. Exercise secondary evidence, not only first source_ref.
- Arbitrary refs (`chat:...`, URL, `ui:...`) do not trigger network access or spurious missing-source invalidation; typed unknown source fails closed.
- Cycle, diamond, bounded traversal failure; no partial “current” acceptance and no ancestor plaintext leak to a model above the effective sensitivity ceiling.
- Age-only outdated control still renders historical qualification; unchanged valid basis preserves multi-turn history.

Limitations: this was a bounded source/provider-payload audit, not broad integration or UI testing. Only direct parent retraction, ignored episode, decision projection discrepancy, and age-only control were executed; other matrix cases are proposed acceptance tests, not claimed verified defects. Parent is coordinating active implementation; this report refers solely to ed39aa0.
