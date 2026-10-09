# Review: paragraph-scope failures in conditional-scope tests

Read-only review against `e8cfc26d5aee8ef42a6206da4ffa02a3bbced966` in the shared checkout. No product files were changed.

## Reproduction

Re-ran only the three named tests with the provided venv. Result: **3 failed** (1.03 s), matching the reported failures.

- `test_always_yes_gate_keeps_both_directly_supported_rules`: expects sentence mode, gets quote mode.
- `test_rejecting_second_gate_falls_back_when_it_drops_the_governing_rule`: safely gets quote mode, but expects a `Bedingungsregel` reason and instead gets the paragraph-completeness reason.
- `test_uploaded_http_answer_and_saved_projection_keep_post_acceptance_condition`: the HTTP answer and GET projection preserve the source-bound PRE and POST text in `working_reports`; the test then raises `KeyError: 'saetze'` when it assumes the stored fallback has a sentence-answer shape.

The synthetic source is one paragraph with three units:

1. `Die Steuerung darf bis zur formellen Abnahme nicht zurückgesetzt werden.` — recognized rule
2. `Nach der Abnahme wird das Messprotokoll archiviert.` — not itself a recognized rule
3. `Ein Zurücksetzen nach der Abnahme ist nur zulässig, wenn die diensthabende Technikerin es schriftlich anordnet.` — recognized rule

`originalregelabsatz_einheiten()` treats all three as one multi-sentence rule paragraph. `_fehlender_regelabsatzkontext()` requires the complete visible paragraph, in source order, whenever a rule unit is cited. The model output contains only units 1 and 3, so quote fallback is consistent with that contract. The test’s positive expectation treats the archival sentence as independent, which conflicts with the explicit whole-paragraph policy. The stricter repeated-fragment check in the latest commit is not the cause here: even the prior “any complete sequence” behavior cannot pass this fixture because unit 2 is missing.

## Assessment and recommendation

There is **no demonstrated unsafe answer leak** in these three failures. The first is a positive-test/contract mismatch under the current deliberately conservative paragraph policy. Do not loosen the production guard just to make it green. If the intended product contract is that clearly separate actions in one paragraph may be extracted independently, that is a product-policy change and needs its own source-backed controls; this fixture alone does not establish it.

For a focused test of conditional-rule retention, either put the archive-status sentence in its own blank-line-delimited paragraph, or make the expected safe result the complete quoted paragraph. Keep a negative control where a governing qualifier or same-paragraph status is omitted, and retain the repeated-occurrence controls from the latest patch.

The second failure is a **diagnostic precedence issue**, not a safety failure: the rejected POST rule is correctly absent from the sentence answer, and fallback is retained, but the answer-level paragraph check masks the more specific rejected-condition reason. Prefer preserving the specific lost-rule diagnostic when already present, while still returning the same safe quote fallback; alternatively, make the test accept either reason. No sentence should be admitted to satisfy the assertion.

The third failure is a **test-shape bug** after the safe fallback: quote-mode `satzantwort` has no `saetze` member. The test should branch on the actual fallback status and assert the complete source quote/projection, or construct its legacy sentence snapshot from a sentence-mode answer. The GET is a saved projection through the same app/store instance; it does not prove a process/store restart, despite the nearby comment saying “Reopening”.

## Limits

This review was limited to the three named tests, their synthetic source, the source-unit/paragraph selector, and the answer fallback path. No full suite, models, network, or private data were used. It does not judge whether whole-paragraph extraction is the ideal long-term product policy; it confirms that the observed behavior follows the current explicit contract and that these tests do not justify a safety relaxation.

## Follow-up review: revised test contract

Reviewed the current test-only diff (product code unchanged) without running tests. The edits are aligned with the contract and keep the safety bar intact:

- The former two-rule positive fixture now expects quote mode when it omits the same-paragraph archival status. A new positive case asks the model for the complete IA08 paragraph and expects the whole original source unit; this tests the positive side without weakening the omission control.
- The second-gate rejection case still requires quote fallback, confirms the checker saw both rule candidates, and now asserts that the rejected `POST_RULE` remains in `verworfen`. Expecting the paragraph-completeness reason is consistent with the later answer-level gate taking precedence; this no longer promises a more specific `Bedingungsregel` diagnostic.
- The HTTP test now supplies the full paragraph, calls the same-app GET a “Reload” rather than claiming a store reopen, and keeps a negative legacy snapshot containing only `PRE_BAN`. This is a valid stale/partial-snapshot control for revalidation. It is not a process-restart test; the comment accurately delegates that coverage elsewhere.
- The permission-applicability test now expects both the rejected broad permission and the otherwise valid same-paragraph solvent ban to be withheld from sentence output, and expects the complete R-508 source unit through server-issued original selection. That matches the shared paragraph completeness rule. It still asserts the always-yes checker only sees the candidate solvent ban and retains the relevant pass/fail behavior.

I found no reason to loosen product validation for these test corrections. One small naming/intent consideration: the HTTP test title says it “keep[s] post-acceptance condition,” while the actual positive answer is now the full paragraph; its assertions do check that both PRE and POST appear, so it remains accurate enough, though “keeps full source paragraph and post-acceptance condition” would be more explicit. These conclusions are from source/diff inspection only; the parent’s focused 69-test run remains the execution evidence.
