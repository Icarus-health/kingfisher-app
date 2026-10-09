# `_gegenstatus` per-sentence precondition review

**Verdict: the proposed narrow fix is sound.** `_gegenstatus` currently gathers all status groups and subject words from the full answer string, then compares that combined set against the single strongest-overlap source unit. For a complete original paragraph containing both a conditional delivery rule and a later explicit “Zustimmung liegt noch nicht vor,” the rule sentence can dominate the overlap while the answer’s `offen` status comes from the next sentence. The resulting `geliefert`/`offen` counterfire is a false rejection of source-faithful text.

Split only the answer with existing `_abschnitte(satz, False)` and run the current strongest-source matching logic independently for each nonempty sentence. Return the first conflict. Keep the current source-unit splitting, status vocabulary, negation logic, lexical overlap, and IDs unchanged. Do not fall back to comparing the combined answer if per-sentence checks find no conflict: that would reintroduce cross-sentence status donation. This changes the scope of comparison, not its strictness within each sentence.

The regression should assert the full two-sentence paragraph passes. Pair it with controls showing that a delivery/paid status contradicted by its own matching source sentence still fails, and that two unrelated subjects with opposite statuses do not cross-donate either way. Also retain the conditional-permission tests: a rule alone must not turn the explicit missing approval into a shipment-completed assertion, and an unsupported or flipped status must not pass. The source is untrusted; no exemption should be based on exact-copy status or original-selection mode.

One bounded limitation: `_abschnitte(..., False)` is the repository’s existing punctuation splitter, not a German sentence parser. Reusing it is appropriate for this localized fix, but the regression should use ordinary sentence boundaries and should not imply robust handling of abbreviations or sentence fragments.

Read-only source/test review only; no code, test execution, models, UI, or live data used.
