# Bounded recheck: same-source `Später` status gate

**Verdict: no blocker found in the reviewed change.** The assertion gate closes the prior conditional, tentative, and question bypasses. All three earlier repros now reject the definite “paid” answer while retaining the plain finite assertion `Später: Die Rechnung wurde bezahlt.` as an accepted later status.

The eight new negative cases all pass in the focused test file: conditional, `vermutlich`, `wohl`, `kann`, `angeblich`, question, `soll`, and quoted status. I also rechecked wrong invoice ID and wrong named subject; neither donates the later paid status to the earlier subject. The subject-anchor and source-level safeguards remain intact in the diff: supersession is local to one source and requires matching identifier/name/sachword signatures; question/quote/rule/uncertainty markers suppress supersession; the later predicate must match the finite-verb-plus-status-vocabulary whitelist.

Focused validation: `tests/test_status_subject_binding.py` and `tests/test_pruefbefunde_0929.py` — **72 passed** (one existing Starlette deprecation warning). Seven direct synthetic checks also matched expected outcomes (three old modality failures rejected, asserted later status accepted, wrong ID/name and `soll` rejected).

Working-tree SHA-256:
- `sidecar/icarus_memory/satzpruefung.py`: `00292917e711652c2bed04bd1b5df693fb0e5dfc6eadc972266ab7cd9f6bbfd1`
- `sidecar/tests/test_status_subject_binding.py`: `1258fa32f3477329ac3191a38a635c9dfae74dd487f8283e90021ec08d03a53f`

Review is bounded to the source-status supersession change and its subject binding; no production edits made.
