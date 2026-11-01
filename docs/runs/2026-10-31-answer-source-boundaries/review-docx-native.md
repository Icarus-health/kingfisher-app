# Independent read-only review: native DOCX rows and question gate

Reviewed frozen commit: **`b8d0a2ab7da92062d636ecf568f126e69d85cce4`**, based on `2cfea10fe0e3f41d87fbf56bc70ad3d5ad2332f1`.
Checkout: `/private/tmp/kf-answer-source-boundaries-20261031`; HEAD matched the requested SHA and the working tree was clean.

**Verdict: approved within the requested narrow scope. No important/critical finding.** The reviewer made no repository changes. This review uses only synthetic MIME/data, temporary stores, canned providers and local TestClient requests. It does not establish real model quality, private-source usefulness, root integration or deployment acceptance.

## Inspected contract

I read the complete product diff, `docx_native_rows.py`, the new tests, the changed `test_docx_table_context` assertion, and the owner evidence `docs/runs/2026-10-31-answer-source-boundaries/docx-native-rows.md`.

- The existing bounded DOCX reader still exposes `bytes -> str`; its additional result records complete parser-derived row spans. The normal text output is retained. Unusable/duplicate row spans do not acquire native proof; >64 parsed rows suppress span proof before repeated full-text searches.
- Capture is limited to a fully read DOCX and complete/unambiguously mapped MIME capture. An unread unrelated logo does not invalidate the DOCX's independent completeness. Partial DOCX/MIME does not get native proof.
- The internal tag binds exact body and main-region digests/ranges, source key and parent ID. Read validates exact types/schema, duplicate JSON keys/tags, ordered nonoverlapping full rows, body/region equality, current fingerprint/source head, DOCUMENT/EMAIL kind/type, valid current mail-parent binding, and one exact raw occurrence across the whole body.
- Invalid proof returns `None` and blocks the tagged native attempt. Valid proof without an eligible visible row returns `()` and does not suppress ordinary original statements. A suitable row remains an opaque, complete literal row; the label does not become a person/date-role/fact assignment.
- Maintext quote/draft restrictions, normative original contexts and row-level norm/pronoun/role/name/finite-statement restrictions remain in place. The native adapter does not treat an independent later form question's pronoun as a role assignment to a preceding row. A normative free chain remains excluded.
- Native sentences bypass only the narrowly necessary original-unit/role-boundary checks after current native proof is established. They must still be exactly the full unmodified proved row. Partial/paraphrased/foreign-name/date outputs do not receive the native exception.
- Native rows require the existing active JSON second gate. That same single call receives the separate question, exact row and full unchanged raw source. It demands both source fidelity and question/date-role fit, including omitted shared qualifications. Unsupported adapters, inactive gate, failure/timeout, question >2,000 characters or raw source >4,000 characters return uncertainty/quotations. Native raw sources are not windowed to make them fit.
- The normal sentence gate keeps its original payload without the user question. Native no-information output cannot become global absence from the restricted row subset.
- Restore rederives proof from current source/parent/index state; the saved native review key binds question, row, source refs and judge model. Text and structured display both use the source-report frame. Source version change or parent withdrawal invalidates the answer, while original body/history remain.

## Selected repository tests — 207 passed

Command personally run on the frozen checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -p no:cacheprovider sidecar/tests/test_docx_native_rows.py sidecar/tests/test_docx_table_context.py sidecar/tests/test_mail_docx_attachments.py sidecar/tests/test_original_sentence_selection.py sidecar/tests/test_normative_paragraph_context.py sidecar/tests/test_original_quote_context.py sidecar/tests/test_satzpruefung_modell.py
```

**207 passed in 8.56 seconds**, with the existing Starlette/httpx deprecation warning.

This covers the actual MIME/remember path, malformed/duplicate metadata and duplicate JSON keys, source kind/type, truncation and unsupported XML structures, row/count/text limits, ordinary prose with and without suitable rows, no false absence, raw 4,000-character boundary behavior, inactive/unsupported/timed-out gate, question/date-role/shared-condition wiring, reopen/GET/withdrawal, proof mutations and inherited original/norm/quote guards.

The changed old `test_docx_table_context` expectation is appropriate: the native ID is now offered instead of failing before the model, but without an active question gate the candidate still yields `zitate`. It checks that the long free chain is not offered as a short unit and that the genuine full row is offered. It does not replace a rejection with an accepted native sentence.

## Independent external counterprobes — 8 passed

External probe file, not a repository test edit:

`/private/tmp/kf-docx-native-independent-probes-20261031.py`

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -s -p no:cacheprovider /private/tmp/kf-docx-native-independent-probes-20261031.py
```

**8 passed in 1.58 seconds**, with the same existing warning. The 207 and 8 are reported separately; the owner's 730-test run was not independently repeated.

Independent cases:

1. Real MIME → remember → indexed attachment → prepare → active question gate → render, using `Prüfdatum\n18.11.2026\tPrüfstelle`, an unpunctuated next field and independent `Üben Sie weitere Tätigkeiten aus?`. Exactly one answer call and one judge call. The judge receives the separate real question, exact row and full unchanged raw body; both text and structure show `Quelle berichtet: „…“`. No claims are created and parent transport contacts remain transport contacts.
2. Filled Prüfdatum versus return-date question: `unklar` from the same question gate yields `zitate`; the raw source and separate question are both present in that call.
3. Shared one-sentence header `Die folgenden Termine gelten nur nach schriftlicher Freigabe.` outside the row remains in the whole raw judge payload, with an explicit qualification instruction; `unklar` yields `zitate`.
4. Exact row copied into generated subject/header and also present in maintext: `body.count(row)==2`. Native proof read is invalid and formulation stops before answer/judge calls. A quoted/header copy cannot supply visibility for the main row.
5. Normalized-only visibility and date-only visibility return no eligible raw row. Two identical main table rows acquire no native proof.
6. A normative following `Wenn … gilt diese Angabe nicht.` remains outside the native exception, even with an always-yes synthetic judge.
7. A 2,001-character question cannot enter the native judge; result remains `zitate` without a judge call.
8. Actual conversation API GET rederives the native display and structure; original GET returns the complete unchanged body. Parent withdrawal makes saved GET `working_unavailable`, removes all source links and native structure, and adds no model calls.

Selected observed outputs:

```json
{"probe":"native-question-positive","calls":1,"row_chars":31,"raw_chars":364,"same_raw":true,"framed_text_and_structure":true}
{"probe":"duplicated-header-main-row","raw_occurrences":2,"native_invalid":true,"answer_calls":0}
{"probe":"native-api-parent-withdrawal","get_model_calls":0,"source_body_unchanged":true,"after":"working_unavailable","structured_native_removed":true}
```

## Frozen-state checks

`git diff --check 2cfea10 b8d0a2ab7da92062d636ecf568f126e69d85cce4` passed. Final HEAD and clean working tree were read back after tests.

SHA-256:

```text
c594f6fad212a53ba7f6e8737db12efc1da7ab59216a6096fa52660fdf6cdf99  sidecar/icarus_memory/docx_native_rows.py
2156c0fe358e2f9a454e8ecbdf938b48895bf5866a777b61d3350050249c9eea  sidecar/icarus_memory/satzantwort.py
83d5fdcd8dd6c5eada7eb23fb0b6a6978b0b97606b4ac64ccba235b17e05bcb2  sidecar/icarus_memory/satzpruefung_modell.py
c2ddd144f4f13b37530255b374c367c961b9b5084656874df707031329fd6295  sidecar/icarus_memory/document_text.py
45371db8f01425d59c4b5cbbfbe4186d5142860e28143f31a53f18c56be500d9  sidecar/icarus_memory/anhaenge.py
```

## Limits

The canned positive/negative judgments verify wiring and fail-closed control flow, not whether a real model correctly understands every field/date role or qualification. A native label remains opaque; `Anna` is not promoted to a person assignment. Unsupported structures and large sources may conservatively remain quotation/uncertainty cases. Existing old captures do not gain native provenance without a normal fresh capture/version. No general architecture, broad audit, whole suite or private-source/model conclusion is included.
