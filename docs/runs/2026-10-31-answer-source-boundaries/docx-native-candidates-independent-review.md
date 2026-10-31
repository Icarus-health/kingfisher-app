# Independent read-only review: bounded native literal candidates

Reviewed frozen commit: **`8d47d3aaf6d4a22bf3c90e20bf64fdef5ac60a26`**, directly based on `8d065d1ddd3ca3bef115a9786338a720e081d435`.
Checkout: `/private/tmp/kf-answer-source-boundaries-20261031`; HEAD matched the requested SHA and working tree was clean before and after review.

**Verdict: approved within the requested narrow scope. No important/critical finding.** No repository edits, private data, real model/provider, network or root-checkout changes by the reviewer. This is not a full-suite, real-model or real-product-run acceptance claim.

## Inspected boundary

The product diff adds the approved candidate branch to the existing original recheck and changes only the default budget for an exact native Kingfisher pair.

- `formulieren` keeps `native_kandidaten=False` as its direct-call default. The normal caller enables it only when selected source-ID set equals the actual offered evidence source-ID set and no evidence was omitted.
- Candidates can be formed only inside the existing single recheck branch: the first and second outputs must both parse as valid `nichts_vorliegend` with no original units. `unklar`, malformed output, foreign IDs, contradictory output or empty `antwort` do not reach candidate formation.
- There must be one or two evidence records, each with exactly one current proof-validated visible native row, and an active gate. No eligible subset is rescued when another evidence record lacks a row or coverage differs.
- Candidates are exact complete raw rows with their individual evidence numbers. They still pass the same first checks and the separate mandatory full-raw question/qualification gate. Nothing in this branch interprets a label, infers a person/date role, confirms a fact or merges trust.
- An accepted candidate remains a literal unconfirmed source report with the existing native review binding. Any first-check or semantic rejection/uncertainty/timeout prevents a partial answer through the existing answer-completeness gate. Remaining native absence still falls back rather than claiming global absence.
- Ordinary valid generator output does not enter the new branch. The changed old tests correctly distinguish an always-yes judge accepting a valid raw candidate from a negative judge keeping the empty-generator case closed; they still do not permit unchecked rows.

## Budget check

Only `gesamt_budget is None`, a Kingfisher profile and exactly two valid native questions enter the new default of at most 16 seconds. Individual default stays 8 seconds. The existing outer JSON deadline clamps that total and an expired deadline returns uncertainty without calls.

Explicit budgets retain priority. Ordinary, mixed, single, three-or-more and non-profile calls retain their old defaults. There is no parallelism, wire/raw limit change or additional model role. Unsupported native adapters and native proof/question/raw limits remain closed through existing gates.

## Selected repository tests — 95 passed

Personally executed:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_docx_native_candidates.py sidecar/tests/test_docx_native_selection.py sidecar/tests/test_satzpruefung_modell.py sidecar/tests/test_negative_answer_recheck.py
```

**95 passed in 4.86 seconds**, including all 44 new controls. This covers complete/omitted/additional sources, default-false direct calls, schema/status/ID failure in both selector stages, one/two/three sources, multiple or missing rows, invalid gate/raw limits, wrong date role, stored native review mutations, parent/source changes, legacy inference rejection, the ordered JA→NEIN/UNKLAR/timeout condition case, normal judge/recheck contracts and budget matrix. The owner's larger 742-test run was not independently repeated.

## Independent counterprobes — nine recorded cases passed

External reusable artifacts, not repository edits:

- `/private/tmp/kf-docx-native-candidates-independent-probes-20261101.py`
- `/private/tmp/kf-docx-native-candidates-independent-probes-20261101.json`

The script builds real MIME DOCX attachments, captures them with `remember`, retains their uncertain refs in the normal WMA commit and derives current proof-validated evidence with `belege_sammeln`. It copies/renumbers these validated evidence objects only to establish the requested test order; source refs, proofs and raw bodies remain unchanged.

Three mandatory condition cases: two distinct current sources contain the same row; only the second has `Die folgenden Termine gelten nur nach schriftlicher Freigabe.`. The selector returns exactly two valid empty outputs with identical source/ID payloads. The first actual raw gate returns JA. The second returns NEIN, UNKLAR or exceeds a short synthetic timeout. All three cases yield `zitate`, zero accepted fragments and exactly one rejected candidate. The result's completeness reason confirms that the first accepted row was not displayed as a partial answer. Each actual gate request contains the exact row, separate question and its own complete unchanged raw source.

```json
{"probe":"JA-first-then-qualified-failure","second":"nein","selector_calls":2,"separate_raw_gate_calls":2,"status":"zitate","accepted_fragments":0}
{"probe":"JA-first-then-qualified-failure","second":"unklar","selector_calls":2,"separate_raw_gate_calls":2,"status":"zitate","accepted_fragments":0}
{"probe":"JA-first-then-qualified-failure","second":"timeout","selector_calls":2,"separate_raw_gate_calls":2,"status":"zitate","accepted_fragments":0}
{"probe":"default-false","selector_calls":2,"judge_calls":0,"status":"zitate"}
```

Five independent fake-clock cases, with no model work or long waits:

```json
{"case":"profile-pair","call_budgets":[8.0,8.0],"verdicts":["ja","ja"]}
{"case":"explicit-smaller","call_budgets":[8.0,3.0],"verdicts":["ja","unklar"]}
{"case":"outer-smaller","call_budgets":[8.0,3.0],"verdicts":["ja","unklar"]}
{"case":"ordinary","call_budgets":[8.0,5.0],"verdicts":["ja","unklar"]}
{"case":"mixed","call_budgets":[8.0,5.0],"verdicts":["ja","unklar"]}
```

The explicit/outer total is 10 seconds in those two smaller-budget probes. Each fake successful call consumes seven seconds, making the remaining allowance and closed second verdict observable.

## Frozen-state evidence and limits

`git diff --check 8d065d1 8d47d3aaf6d4a22bf3c90e20bf64fdef5ac60a26` passed.

```text
55f5a7c125382a05175c3ef6eae06481970a67c9306d9d01ae5f7c606eab2b05  sidecar/icarus_memory/satzantwort.py
c53ca7c05c3e7710832e9fe58f6244549cfbe18de2e865cbc2f2d5f6c8464f8d  sidecar/icarus_memory/satzpruefung_modell.py
5f4907cafd1691d54ae27bc4941bf7b5ee79caa216776c9cf089306735f96300  sidecar/tests/test_docx_native_candidates.py
```

The 95 repository tests and nine recorded external cases are separate evidence. The canned semantic verdicts establish gate wiring and total failure behavior; they do not prove real question/date-role understanding. The new branch supplies a bounded original candidate, not a forced answer. Root integration and the planned unchanged-source real product run remain separate.
