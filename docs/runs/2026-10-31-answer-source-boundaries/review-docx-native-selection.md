# Independent read-only review: native original selection and deduplication

Reviewed frozen commit: **`8d065d1ddd3ca3bef115a9786338a720e081d435`**, directly based on `7789d7e9881f9a71fac1d5f910fd9b56ce3e17af`.
Checkout: `/private/tmp/kf-answer-source-boundaries-20261031`; HEAD matched and working tree was clean before and after review.

**Verdict: approved within the requested narrow scope. No important/critical finding.** The reviewer changed no repository files. All probes use synthetic MIME, disposable stores and canned local providers; no private data, real models/provider calls, network, root edits or full suite.

## Product and old-test review

The product diff is confined to the original-selection hint, existing once-only empty-answer recheck and source-aware native dedupe in `satzantwort.py`.

- The new hint is appended only when proof-validated native rows are actually available to the original-unit prompt. It permits whole literal scalar datasets without requiring grammatical sentences, explicitly keeps label/date-role matching and rejects missing/unmatched fields. It does not force an ID or fabricate an answer.
- A native first empty `nichts_vorliegend` result can now use the existing **one** recheck. That recheck uses the same complete user payload, source units, IDs and schema; it retains the native hint and adds the existing recheck instruction. There is no loop or budget/schema expansion.
- A native result still empty after that recheck returns `zitate`, not global absence. Invalid output and unsupported IDs still fail closed. No judge runs without an actual candidate.
- Same text with the same evidence set still deduplicates. Different evidence sets remain distinct if **either** candidate is native, so a prior normal candidate cannot swallow a later native candidate or vice versa. Each reaches its own existing gate with its own raw source and, only for native candidates, the separate user question.
- Both-normal dedupe retains its former behavior. Successful ordinary sentences, normal original prompts/recheck prompts and the normal judge payload are unchanged.
- The changed old native absence assertion correctly changes only one selector call to two, while still requiring `zitate`. It does not relax absence, native proof, question, role, source or judge checks.

## Selected repository tests — 133 passed

Personally executed:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_docx_native_selection.py sidecar/tests/test_docx_native_rows.py sidecar/tests/test_original_sentence_selection.py sidecar/tests/test_negative_answer_recheck.py sidecar/tests/test_satzpruefung_modell.py
```

**133 passed in 8.10 seconds**, one existing Starlette/httpx deprecation warning. Includes all 11 new controls, the exact normal prompt/recheck/judge contract, native provenance and question gate, persistent empty/missing fields, separate source judging, same-set dedupe, and existing original/recheck boundaries. The owner's 698-test run was not independently repeated.

## Independent counterprobes

Reusable external script and observed results:

- `/private/tmp/kf-docx-native-selection-independent-probes-20261031.py`
- `/private/tmp/kf-docx-native-selection-independent-probes-20261031.json`

Executed the script on the frozen checkout with the same Python/PYTHONPATH as above. Six recorded probes passed:

1. Two different current MIME DOCX attachment sources contain the same literal row but distinct additional form content. Both selected; one answer call and two distinct raw-source question-judge calls. Rejecting one produces total `zitate` and no sentence structure. Each raw source appears in exactly its own judge request; no trust merge.
2. A current native source and a normal document source contain the same text. Reject the normal candidate: both gates run separately; the normal gate retains only `satz`/`belege`, native gets `frage` too; result is total `zitate`.
3. Same mixed-source case, reject the native candidate instead: still two separate gates and total `zitate`. This exercises the `or(native)` condition in both directions rather than only two-native pairs.
4. A permanently empty native selector: exactly two calls with identical source/ID payloads, zero judge calls, `zitate`.
5. An unoffered/wrong field requested by the selector: exactly two calls, no forced choice or judge call, `zitate`.
6. Normal-only dedupe through the real sentence checks: identical text with different normal evidence sets keeps its old one-judge-call/completeness-fallback behavior. Repeating an already-valid ordinary sentence with the same source still yields one unchanged valid sentence and one normal judge call.

Key observations:

```json
{"probe":"two-current-native-sources-one-rejected","selected_sources":2,"answer_calls":1,"separate_judge_calls":2,"status":"zitate"}
{"probe":"mixed-native-normal-same-text","rejected":"normal","separate_judge_calls":2,"normal_payload_unchanged":true,"status":"zitate"}
{"probe":"mixed-native-normal-same-text","rejected":"native","separate_judge_calls":2,"normal_payload_unchanged":true,"status":"zitate"}
{"probe":"missing-or-false-empty-native","missing_field":false,"answer_calls":2,"judge_calls":0,"status":"zitate","same_ids_and_sources":true}
{"probe":"missing-or-false-empty-native","missing_field":true,"answer_calls":2,"judge_calls":0,"status":"zitate","same_ids_and_sources":true}
{"probe":"normal-only-dedupe","different_sources_keep_old_fallback":true,"normal_dedupe_judge_calls":1,"same_source_valid_sentence_unchanged":true}
```

## Frozen-state evidence and limits

`git diff --check 7789d7e 8d065d1ddd3ca3bef115a9786338a720e081d435` passed.

```text
3a87a125b10f09fb9c1c78ece5966e80ec988093cb9f08480970722e263f81a5  sidecar/icarus_memory/satzantwort.py
27b1c9454d2fb61e627ba2a61ba08bf8be6fd6477a11a63d8938d3548dfa3c78  sidecar/tests/test_docx_native_selection.py
```

The added hint and recheck improve opportunity to select a real offered row; they do not prove real model relevance or field-role comprehension. Existing proof/current-parent, visibility, row/raw/question limits, normative context, mandatory active native gate and restore/withdrawal mechanisms are unchanged by this patch. Root integration and the planned real-source/model repeat remain separate.
