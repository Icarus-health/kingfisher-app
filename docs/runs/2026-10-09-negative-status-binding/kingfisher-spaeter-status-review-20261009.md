# Bounded review: same-source `Später` status supersession

**Verdict: blocker.** The change correctly retains the nominal `Zusage`/`Bestätigung` subject anchors and only supersedes matching subject signatures within the same source. However, supersession currently treats any later text containing a status form as an asserted status. That can turn a conditional, tentative, or interrogative statement into definite current-status evidence and erase the earlier explicit state.

Reproduced against the working tree with synthetic inputs. In all three cases below, `satz_pruefen(Satz("Die Rechnung wurde bezahlt.", ("1",)), {"1": Beleg("1", source)})` returns `bestanden=True` with no reasons:

- `Die Rechnung ist offen. Später: Wenn die Rechnung bezahlt wurde, ist sie erledigt.`
- `Die Rechnung ist offen. Später: Vermutlich wurde die Rechnung bezahlt.`
- `Die Rechnung ist offen. Später: Wurde die Rechnung bezahlt?`

The plain assertion `Die Rechnung ist offen. Später: Die Rechnung wurde bezahlt.` also passes, as desired. The issue is that `_status_quellenabschnitte` removes the older same-subject state based on status words plus subject signature, without asserting the later clause is factual. `_abschnitte` drops question punctuation, and the subject signature omits modality qualifiers such as `wenn` and `vermutlich`, so the status matcher sees the tentative/query text as an ordinary state.

A safe bounded fix should preserve the old conflicting state unless the later same-subject unit is clearly assertive. Add controls for conditional, tentative, and question forms, alongside asserted positive and explicitly negated later states. Do not weaken the existing ID/name/source binding or the rule-vs-actual-status gate.

Focused validation: `tests/test_status_subject_binding.py` and `tests/test_pruefbefunde_0929.py` — **64 passed** (one existing Starlette deprecation warning). These tests do not cover the three modality cases above.

Reviewed working-tree SHA-256:
- `sidecar/icarus_memory/satzpruefung.py`: `82e8e13d07801fe46f90f37f9867255d428bd14117d86df08c37a9b2d87d2db7`
- `sidecar/tests/test_status_subject_binding.py`: `f6beea6980b60a48a2046a3447bc87826abdb39b964c31ada5284175c7eb3c46`
