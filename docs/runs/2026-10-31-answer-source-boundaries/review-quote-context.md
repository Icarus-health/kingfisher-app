# Independent read-only quote-context review

Reviewed immutable commit: **`b0527fdb64097e13becea3d0b871fba99be9e385`**, `Keep unrelated footer quotes outside original-unit binding`.
Checkout: `/private/tmp/kf-answer-source-boundaries-20261031`; HEAD matched this commit and the working tree was clean. The commit only changes `satzpruefung.py`, its 21-case test file, and the two quote-context evidence documents.

**Conclusion: approved within the requested narrow review; no important/critical finding.** This is not release, deployment or real-model acceptance. No repository mutation, private data, real provider/model, network or app was used by the reviewer.

## Independent evidence

Read the actual commit diff and `docs/runs/2026-10-31-answer-source-boundaries/quote-context.md`; then reran:

```text
pytest -q -p no:cacheprovider sidecar/tests/test_original_quote_context.py
21 passed in 0.31s

pytest -q -p no:cacheprovider sidecar/tests/test_answer_source_boundaries.py sidecar/tests/test_original_sentence_selection.py sidecar/tests/test_normative_paragraph_context.py sidecar/tests/test_absatzauswahl_saetze.py
72 passed in 3.65s
```

Environment: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:.`; interpreter `/private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python`.

The reviewer additionally exercised the real source stores → `prepare` → sentence pipeline → `render` with a synthetic PayPal-titled rate source, the exact provided rate statement `Ihre Rate wird automatisch abgebucht. Sie müssen nichts weiter tun.`, and the distant ASCII footer `Hilfe unter "Kontakt".`. Source length 2,885 characters; result `saetze`, one sentence call, 201 rendered characters, entire source not dumped, source body identical. The footer was present in full verification text and absent from the selected answer excerpt. The 201 rather than the implementer's 192 rendered characters comes from the longer synthetic title `PayPal · Nächste Rate`.

Saved independent stage results: `/private/tmp/kf-quote-context-independent-review-20261031.log`.

## Boundary checks

- Both `originalbindung` and `rollenbindung` use the same full-source `_unzitierte_originalabschnitte` filter. A quote-free selected middle sentence does not override a containing full-source quoted span.
- Zero quote delimiters retain prior behavior. Exactly one suitably oriented unescaped ASCII double-quote pair permits only complete source units wholly outside that span. A unit intersecting the pair or lying inside the quoted region remains excluded, even for a multi-sentence/multi-paragraph quote.
- A hidden unquoted occurrence and a visible quoted copy with identical raw wording remain blocked in both bindings. Independently repeated for the rate rule and a named person's duty; `formulieren` returned `zitate` for both.
- Independent malformed-orientation, escaped, single-quote, German-quote and multiple-pair controls remain blocked in the applicable rule and named-actor gates. The no-rule/no-actor early returns retain their prior scope; this is not a new global guard for every ordinary factual sentence.
- Raw visibility is still checked per matching source. Normalized equivalence or another source's text is not substituted for complete visible raw wording. The conservative duplicate-wording exclusion prevents the visible quoted copy from satisfying the hidden outside occurrence's raw substring check.
- The existing original-unit/atomic-paragraph, qualifier, actor, negation and source withdrawal checks remain in force. No original source body, offset, version, budget, sentence limit or second-gate behavior was changed by this commit.

`git diff --check b0527fdb64097e13becea3d0b871fba99be9e385^ b0527fdb64097e13becea3d0b871fba99be9e385` passed.

Reviewed file SHA-256:

```text
49169aecd905fbd23f75caf8eb34d6a525900b9773d7673290643ebc2b70caa3  sidecar/icarus_memory/satzpruefung.py
28c65ff4cb97a12cb681026ad3bf887014fece2e12aa22375876613da955a631  sidecar/tests/test_original_quote_context.py
```

## Limits

This deliberately recognizes no general nested-quotation grammar. Unsupported, escaped, multiple or ambiguous quote forms can still force honest quotation fallback. The independent probes use synthetic canned external responses and do not establish what any real model answered on a private source. No claim about the separate root checkout, cherry-pick, app state, whole backend suite or deployment is included.
