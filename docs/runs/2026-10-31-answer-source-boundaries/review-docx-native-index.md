# Independent read-only review: retain native rows as uncertain original refs

Reviewed frozen commit: **`7789d7e9881f9a71fac1d5f910fd9b56ce3e17af`**, directly based on `b8d0a2ab7da92062d636ecf568f126e69d85cce4`.
Checkout: `/private/tmp/kf-answer-source-boundaries-20261031`. HEAD matched the requested SHA; the working tree was clean before and after the probes.

**Verdict: approved in the requested narrow scope. No important/critical finding.** Only the 11 added production lines in `WorkingMemoryStore.commit`, their existing validation/transaction context, the new tests and the owner evidence were reviewed. No repository edit, private data, real model/provider, network, root-checkout change or whole-suite run by the reviewer.

## Code checks

- Native retention runs inside the existing commit transaction, after the normal current-snapshot, eligibility, fingerprint, dismissed-source and explicit-recheck checks. It uses the current snapshot and existing `docx_native_rows.read` validator.
- Only tagged, currently valid native DOCX rows in a raw body of at most 4,000 characters can be added. The existing validator still enforces source kind/type, current mail parent, complete unique raw row, source/region digests and all native exclusions.
- Each addition is a full literal original span with kind `uncertain`. No fact/person/date/deadline/task object or inferred field role is created. The source body and caller's input list remain unchanged.
- Every existing normalized relevant overlap takes precedence, including a partial overlap or wider historical/conditional context. The strict interval intersection correctly permits merely adjacent items while forbidding a second isolated row overlapping an existing interpretation.
- The existing `MAX_ITEMS` cap is checked before and during addition. Normal input validation and duplicate rejection still run first. Native rows are already unique in the raw body, and each appended range participates in the next overlap check.
- Existing delete/insert, stable item-ID generation, source fingerprint, revision/signature advancement, cache/ref resolution and withdrawal paths remain unchanged. A complete old empty index is not silently reprocessed; only explicit recheck can apply the new retention to it.
- The previously reviewed answer contract is unchanged: a retained uncertain ref is not a factual answer. Whole-row literal output still requires the active full-raw question/qualification gate from b8d0a2a.

## Selected repository run — 49 passed

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_docx_native_index.py
```

**49 passed in 3.99 seconds.** Personally executed. These tests include real MIME/classification composition, all existing kinds with exact/wider/partial/adjacent overlap, idempotence and unchanged input lists, invalid/missing/duplicate proofs, unsupported/draft/quoted/truncated/large sources, item limits, stale/withdrawn/dismissed sources, proof reading under the commit transaction, explicit old-empty recheck, source answers, and transient/durable synthetic search-cache behavior.

The owner's larger 425-test run was read as owner evidence and was not independently repeated.

## Independent external cases — 4 passed

External file, with no repository test modification:

`/private/tmp/kf-docx-native-index-independent-probes-20261031.py`

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -s -p no:cacheprovider /private/tmp/kf-docx-native-index-independent-probes-20261031.py
```

**4 passed in 0.50 seconds.** These deliberately use smaller partial overlaps than the owner's near-full-row partial case:

1. A `historical` item covers 40 preceding context characters and only the first five row characters. It remains the sole stored ref; the row is not separately rescued. Three explicit rechecks preserve kind, bounds, input list and exact ref IDs.
2. A `conditional` item covers only the last five row characters and 40 following context characters. It likewise keeps priority and identical IDs across three explicit rechecks.
3. A synthetic prior empty-index state is created with native read temporarily disabled in-process. Normal commit still refuses to rewrite this complete state. Explicit recheck using exactly the same empty `[]` items, with zero classifier calls, adds one full `uncertain` row ref. Three more rechecks with that same empty input keep exactly the same ref ID; normal search resolves it, and parent withdrawal makes resolver/search empty. No claims or source changes occur.
4. A normal non-native document containing `Prüfdatum\n18.11.2026` remains completely empty after an empty commit and an explicit empty recheck. No generic scalar/prose rescue occurs.

Observed outputs:

```json
{"probe":"overlap-priority","kind":"historical","overlap_chars":5,"refs":1,"rechecks":3,"same_ids":true}
{"probe":"overlap-priority","kind":"conditional","overlap_chars":5,"refs":1,"rechecks":3,"same_ids":true}
{"probe":"empty-explicit-recheck","kind":"uncertain","refs":1,"same_empty_input_rechecks":3,"classification_calls":0,"parent_withdrawal":"unresolvable"}
{"probe":"ordinary-non-native-ignore","refs":0,"explicit_recheck_refs":0}
```

## Frozen-state evidence and limits

`git diff --check b8d0a2a 7789d7e9881f9a71fac1d5f910fd9b56ce3e17af` passed.

```text
b5ee02d2b8052e55a32b7fe1f4f7d02ae518ced5f352f1b6144855ed646ccff7  sidecar/icarus_memory/working_memory_store.py
cf2f21290031495bb84e088a36a8d20a96476f0d6da0987c019d0c7484b4f0aa  sidecar/tests/test_docx_native_index.py
```

The 49 repository controls and four external probes are reported separately. This review establishes bounded original-reference preservation and existing guard behavior, not real classification, embedding or question-answer quality. No global analysis-version bump, automatic backfill or extra classification call was introduced. Root integration and any real/private repeat probe remain separate work.
