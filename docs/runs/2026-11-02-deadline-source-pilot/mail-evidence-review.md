# Independent delta review: wrapped mail entities and category guidance

Final reviewed head: `edfb4d84cc306655c36fce1eda1f61bdb7e31049`. The public addition was reviewed at `1a98289` against `ac80875`; final re-review was restricted to `1a98289..edfb4d8`, containing the two boundary fixes and four synthetic negative cases. No private artifacts, services, models or network accessed. No repository edits.

## Final assessment

**No remaining actionable findings in the scoped change. Both earlier findings are fixed. The delta is ready for the planned full regression run.**

- A second whitespace/wrap group is rejected once `wrapped` is true. Counting `re.findall(r'\r\n|[\r\n]', whitespace)` treats a CRLF pair as one separator and detects additional bare CR/LF separators. The two-wrap and both mixed-line-ending blank-paragraph countercases are now explicit rejection tests.
- `len(chars) < 40` permits appending at most the fortieth token character, including the terminating semicolon, so the former 41-character zero-padded numeric entity is rejected. The raw 256-character scan bound is unchanged.

These fixes retain exact original-span mapping, proved quote-prefix masking, one decoding pass, ambiguity rejection and word/multi-character-entity boundaries. The existing negative tests for changed negation, numbers, dates, case, omitted operators, unknown/recursive entities, ambiguous canonical matches and non-mail normalization continue to pass. No new non-mail strict-evidence bypass was found in the scoped addition.

The two category-analysis paths retain identical generic guidance: a product/app/subscription name alone is not a project; project classification needs an explicitly named undertaking, and an unsuitable entity type should be omitted. That addition is unchanged by the final repair. No hardcoded brand, entity type, validator or storage behavior is introduced. Actual prompt compliance is outside this synthetic review.

## Independent verification

At exact final head, ran only `test_mail_quote_alignment.py`: **55 passed in 0.15s**. The four new negatives reproduce the previously accepted inputs and now require `ProviderError` through the normal mail-analysis path. The intended wrapped-entity positives also continue to pass. `git diff --check 1a98289..edfb4d8` is clean and exact HEAD was verified.

The already-reviewed deadline change and any private pilot or broader regression suite are outside this final delta review. No empirical model-equivalence or private-source acceptance claim is made.
