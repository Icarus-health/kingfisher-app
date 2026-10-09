# Status-binding prototype review

Compared `/private/tmp/kingfisher-status-binding-prototype-20261009/satzpruefung.py` with product `0911e4cac1cdd1115d2fa1b1d26f8232debfea8f`. I inspected the expanded scratch cases and ran four bounded synthetic calls against the prototype; no source changes or suites were run.

## Concrete remaining false accepts

1. **Unqualified answer plus competing IDs is accepted.** With `Die Rechnung ist bezahlt.` and cited units `Die Rechnung R-719 wurde bezahlt.` / `Die Rechnung R-720 ist noch offen.`, prototype returns `bestanden=True`. Since the answer has no `_KENNUNG`, neither unit is filtered; their status groups are unioned and the matching `bezahlt` causes the loop to skip the opposing `offen`. Same-kind records with different IDs remain ambiguous unless the answer carries an ID/name. Conservatively reject when the strongest lexical candidates carry distinct explicit IDs/names and their statuses disagree or one lacks a status.

2. **An ID in a neighboring body clause does not bind the status clause.** With sources `Z-205: Die Zustimmung liegt noch nicht vor.` and `Z-204: Die Zustimmung liegt bereits vor.`, the exact answer `Z-204: Die Zustimmung liegt noch nicht vor.` returns `bestanden=True`. `_abschnitte(..., True)` splits the `Z-204:` label away from the status clause; the latter has no ID, so the `if kennungen` mismatch filter does not run and the Z-205 negative status donates `offen`. Source-title IDs in `Beleg.kopf` are used, but inline/body labels are not carried across the split. Preserve a unique explicit ID/name across its clearly scoped following clause; if multiple identities make attachment ambiguous, fail closed instead of pooling statuses.

3. **Distinct named subjects can donate when the answer omits the name.** `Die Lieferung ist bezahlt.` citing `Anna Keller: Die Lieferung Z-204 wurde bezahlt.` and `Mira Sander: Die Lieferung Z-205 wurde vorbereitet.` returns `bestanden=True`. `_status_namen_belegt` only filters when the answer has names; a generic answer can take the status from any best-overlap named unit. When equally relevant units have distinct names and conflicting or absent statuses, reject the unqualified claim.

## Concrete positive regression

Identifier comparison uses raw `_KENNUNG.findall` values. `Die Lieferung z-204 wurde bezahlt.` against `Die Lieferung Z-204 wurde bezahlt.` returns `bestanden=False` (“kein Beleg zur selben Sache”). Existing token validation normalizes identifiers with `casefold`; status binding should use the same normalization so case-only differences do not make an exact source match disappear.

The prototype does correctly reject the tested explicit mismatched-ID case when the ID appears in the same status clause, and its rule-plus-negative-status original positive passed in the expanded fixture. The main gap is metadata split from the status clause and identities omitted from an otherwise ambiguous answer; this is bounded context propagation/ambiguity handling, not a need for general NLP.

Exact reviewed product commit: `0911e4cac1cdd1115d2fa1b1d26f8232debfea8f`.
