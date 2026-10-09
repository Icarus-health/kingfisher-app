# Final code review: negative-status recheck

Reviewed commit `0911e4cac1cdd1115d2fa1b1d26f8232debfea8f` (`0911e4c`) against `8d2a971`.

**No regression found in the requested retry or per-sentence change.** The retry follows only a successfully parsed original-mode `nichts_vorliegend` with no resolved selections; ordinary-mode abstentions do not retry. It reuses the same user payload and selection IDs with the same schema and one additional system clarification, then parses through `_original_lesen` and `_urteilen`. Provider/parser errors fail closed to quotes. Selected text still passes the regular gates, including the second verifier; the reopen/render test confirms a saved answer is withdrawn after its source is ignored while the original episode remains intact.

`_gegenstatus` splits only the answer into existing punctuation-delimited sentences, then independently applies the same strongest-overlap comparison over the sentence's cited source set. The regression pair checks the complete rule-plus-negative-status paragraph, both orders of unrelated but correctly sourced statuses, mismatched statuses, and omitted conditional terms. Focused verification: `test_negative_answer_recheck.py` and `test_answer_status_sentence_scope.py` passed, 15 tests total; `git diff --check` was clean. No model, UI, or private-data operation was performed.

**Residual cross-subject status acceptance (pre-existing, outside this patch):** the tests do not cover a status word donated by an unrelated subject when the matching subject’s source clause has no recognized status. I reproduced a false pass: answer `Die Lieferung Z-204 wurde bezahlt.` citing `Die Rechnung R-719 wurde bezahlt.` and `Die Lieferung Z-204 wurde vorbereitet.` returns `bestanden=True`. The aggregate status-presence check at `satzpruefung.py:1278` sees `bezahlt` anywhere in the cited pool; `_gegenstatus` matches the shipment clause, which has no status to contradict it. This reproduces for a single sentence, where the new recursion does not run, so it is not introduced by this commit. The new status controls catch a conflicting unrelated status, but not this status-donation case; consider a separate focused regression/fix before relying on status validation across mixed-subject citations.

Reviewed commit/tree: `0911e4cac1cdd1115d2fa1b1d26f8232debfea8f` / `e046e4487e8325b5bf4f3c9446f4fac5efd28ff9`.

SHA-256:

- `sidecar/icarus_memory/satzantwort.py`: `4871fc90c41caf8e23c4291c64ecbebcb04f08c8447a1bcd9bc478e6e2cc57cd`
- `sidecar/icarus_memory/satzpruefung.py`: `7cac27a14f62ae296d06f120c030048c78a9ad85e1fd5597a5d19f2b589bed97`
- `sidecar/tests/test_negative_answer_recheck.py`: `1cf29d9272d61883a2c5e9b4c123690ce9ed53f6aaea1764a56ee9b881060b43`
- `sidecar/tests/test_answer_status_sentence_scope.py`: `63835792f46df711a0f9d0a326d44828eef5fd90f18d18193fe42a752a8445eb`
