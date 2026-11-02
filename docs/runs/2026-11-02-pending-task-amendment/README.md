# Source-bound correction of a pending task title

Base: `0e11fe548c69259ee7bbcb835b0d17e16fc2a674` (merged through PR112). Candidate release1.0.41. Artificial test data only in public evidence.

Problem: a new extractor does not replace old pending wording because the canonical source/digest/quote/context ID remains unchanged. A manual acceptance would create a task, which is a different decision. Generic TASK proposal creation can coalesce identical titles from different sources.

The explicit `/api/v1/task-candidates/{id}/amend` operation keeps original evidence/context and creates one immutable pending successor with `task_amends` lineage. The original becomes superseded, retaining the normal detector tombstone. A caller supplies the expected old statement, source ID, digest and task context. Source reservation remains held through the proposal transaction. Unsupported hard details, stale sources, previous decisions and acceptance crash gaps fail closed. Successors carry no positive semantic-review marker and create no active task/project. Legacy unbound proposals are deliberately unsupported.

Validation:

- RED: missing route/lineage behavior reproduced before implementation (47 failing cases in the first selection).
- Final implementation selection:53 tests passed; affected candidate/review/retention/proposal/page/automatic-acceptance/source suites:416 passed in76.92s.
- Fresh independent review: no P1/P2 findings. Additional checks covered later-superseded successor retries after restart, lineage roundtrip, canonical tombstones and successor acceptance crash gaps.
- Minor review observation: the new history event was ignored by the logbook allowlist. Reproduced with one failing actual API-to-logbook test, then registered the event. Final amendment+logbook selection:101 passed in23.53s, with one existing dependency deprecation warning. Raw mail/title text is absent from this event; retries do not duplicate it.

The public feature does not claim model accuracy or full import acceptance. The root-only real-source check remains separate, and installation/native readback is pending. No paid calls, global source rewrite, role change or bulk import occurred during this patch.
