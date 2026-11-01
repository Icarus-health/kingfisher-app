# Independent read-only review: bounded native question budgets

Reviewed frozen commit: **`7165da562e763aac9533f788d2cf0c1c2f13a29b`**, directly based on `8d47d3aaf6d4a22bf3c90e20bf64fdef5ac60a26`.
Checkout: `/private/tmp/kf-answer-source-boundaries-20261031`; HEAD matched and working tree was clean before and after review.

**Verdict: approved within the requested narrow budget scope. No important/critical finding.** No repository edits, private data, real models/providers, network, root changes or full suite by the reviewer.

## Code review

- `native_standard` is computed before inserting either default. It requires **both originally supplied budgets to be `None`**, the existing Kingfisher profile, one or two nonempty valid native questions and complete nonempty raw evidence within the existing 4,000-character cap.
- Only that branch sets 12 seconds per request and 12/24 total. The existing outer JSON deadline clamps the total for both a single request and a pair; an expired deadline returns uncertainty without calls.
- Once either budget is explicit, the old branch is preserved. In particular, an explicit per-request budget with omitted total retains the old 16-second native pair default. Explicit total with omitted per-request budget retains the old eight-second profile default.
- Ordinary, mixed, three-or-more, non-profile and invalid requests retain previous behavior. Serial execution, source/raw/wire constraints, question/qualification instruction, native proof and strict JA/timeout/whole-answer gates are unchanged.
- The changed existing budget assertions alter only the specifically approved pure-native defaults and their outer-deadline expectation. Normal and explicit-budget checks remain present.

## Personally executed repository controls — 44 passed

Environment: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:.`; interpreter `/private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python`; pytest cache disabled.

```text
pytest -q -p no:cacheprovider sidecar/tests/test_native_question_budgets.py
30 passed in 0.27s

pytest -q -p no:cacheprovider sidecar/tests/test_docx_native_candidates.py::test_native_profilpaar_hat_24_gesamt_und_12_je_satz_ohne_echte_wartezeit sidecar/tests/test_docx_native_candidates.py::test_alle_anderen_und_expliziten_budgets_bleiben_unveraendert sidecar/tests/test_docx_native_candidates.py::test_engere_aeussere_frist_wird_durch_native_paarbudget_nicht_verlaengert sidecar/tests/test_satzpruefung_modell.py::test_managed_local_profile_allows_cold_start_but_respects_explicit_budget sidecar/tests/test_satzpruefung_modell.py::test_die_vorgaben_sind_zwei_sekunden_je_satz_und_sechs_gesamt
14 passed in 0.15s
```

This includes single/pair success at a synthetic 9.2 seconds, hard per-request/total caps, outer and expired deadlines, explicit budgets, normal/mixed/three/non-profile exclusions, malformed native questions/raw evidence, negative/unclear results and a genuine source pipeline's all-or-nothing timeout control. No real waiting or model was required.

## Independent counterprobes — ten recorded cases passed

External artifacts, not repository edits:

- `/private/tmp/kf-native-question-budget-independent-probes-20261101.py`
- `/private/tmp/kf-native-question-budget-independent-probes-20261101.json`

The independent fake-clock matrix uses 9.3 seconds of simulated work per request, distinct from the owner's values:

| Case | Observed call limits | Verdicts |
|---|---|---|
| Both defaults, one native request | 12 | JA |
| Both defaults, two native requests | 12, 12 | JA, JA |
| Explicit per-request 12, omitted total | 12, 6.7 | JA, UNKLAR |
| Explicit total 24, omitted per-request | 8, 8 | UNKLAR, UNKLAR |
| Single native, outer deadline 7.5 | 7.5 | UNKLAR |
| Native pair, outer deadline 17 | 12, 7.7 | JA, UNKLAR |
| Ordinary profile pair | 8, 4 | UNKLAR, UNKLAR |
| Mixed native/normal profile pair | 8, 4 | UNKLAR, UNKLAR |
| Single native, expired outer deadline | no calls | UNKLAR |

The explicit-per case demonstrates the old 16-second total; the explicit-total case demonstrates that the new per-request default does not leak into explicit calls.

The tenth probe uses actual synthetic MIME capture, current native proof and index, two valid empty selections, candidate creation and first sentence checks. The real question/raw request constructor is exercised in both gate calls. A fake clock lets the first source return JA after 9.3 seconds; the second exceeds its 12-second allowance and returns timeout uncertainty. Actual result: **`zitate`, exactly one rejected candidate, no accepted fragments or sentence structure, no claims**. Each call contains the unchanged complete raw body of exactly its own source and the separate actual question. This proves that the first JA does not survive as a partial answer after the second timeout.

```json
{"probe":"real-source-first-JA-second-timeout-over12","call_limits":[12.0,12.0],"status":"zitate","rejected":1,"accepted_fragments":0,"unchanged_full_raws":true}
```

## Frozen evidence and limits

`git diff --check 8d47d3a 7165da562e763aac9533f788d2cf0c1c2f13a29b` passed.

```text
5384b3483c2ead0ff65f323fd197ade8cac5936b3ef6ad0addf10a9197ae7984  sidecar/icarus_memory/satzpruefung_modell.py
3303e6928d6ae0e065676d945d9839acddac72fc46458e626880c9ae1cf06e8c  sidecar/tests/test_native_question_budgets.py
```

The 44 repository controls and ten recorded independent cases are separate evidence and remain below the requested approximate 100-test scope. This establishes the exact budget/control-flow contract, not real latency, real semantic model quality, root integration or end-user acceptance. The actual unchanged-source product repeat remains the root agent's next step.
