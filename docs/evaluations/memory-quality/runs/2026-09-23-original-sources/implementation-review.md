# Independent implementation review: original-source answers

Reviewed the uncommitted `feat/raw-source-answers` change in `work/memory-audit-20260921` on 2026-09-23. This is a read-only product review; the small reproductions used temporary databases. No network, live model, or product files were changed by this review.

## Findings

### P2 — Natural quoted-source questions bypassed the deterministic path in automatic mode (fixed during review)

`source_answers.literal_query()` recognizes a quoted term with `Quellen`, `Originaltext`, or `Dokumenten` (`source_answers.py:24-33`). The UI sends `answer_mode: auto`; `server.py:2688-2693` calls `memory_routing.route()` before `Agent.answer_memory()`. The pre-existing router sends several natural source-reading requests to ordinary chat instead of `memory_evidence` (`memory_routing.py:7-36`). Reproduction in the current checkout:

| Question | `literal_query` | `route` |
|---|---|---|
| `Was steht zu "AURORA-4711" in meinen Quellen?` | `AURORA-4711` | `memory_evidence` |
| `Suche in meinen Quellen nach "AURORA-4711".` | `AURORA-4711` | `chat` |
| `Zeig mir den Originaltext zu "AURORA-4711".` | `AURORA-4711` | `chat` |
| `Was steht in meinen Dokumenten über "AURORA-4711"?` | `AURORA-4711` | `chat` |

For the latter three questions, the new source-only answer was never prepared, and normal chat could call a model. The implementation owner added a narrow explicit read-intent branch before the generic action-verb branch (`memory_routing.py:23-27`) and regression cases for these forms, while keeping send/write requests on chat. I reviewed the patch and ran `test_memory_routing.py` plus `test_source_answers_http.py`: **23 passed**. The new forms have route-level coverage; the existing HTTP test covers the `Was steht ...` auto-mode source path and zero provider calls.

### P3 — The first 20 matching IDs can all be unusable while a usable 21st source exists

`source_search.search()` selects `ORDER BY e.id LIMIT 21` and returns at most 20 IDs (`source_search.py:73-80`). Only afterward does `source_answers.prepare()` filter sources with existing or retracted Claims (`source_answers.py:98-115`). I reproduced this with 21 current DOCUMENT Episodes sharing `COMMON-TERM`, accepted Claims for the first 20 IDs, and no Claim for the last. The temporary pytest passed and showed `truncated=True`, `candidate_count=20`, `deferred_count=20`, `refs=[]`, and rendered status `no_match_in_searched_text`; the 21st current source remained unclaimed and contained the term.

The user-facing text does mark the search incomplete, so this is a bounded recall limitation rather than a silent completeness or withdrawal failure. Still, `no_match_in_searched_text` is misleading for a search that found 20 matching but deferred records. A bounded scan that continues until it has three displayable sources or its resource budget is reached would improve recall; at minimum use an unavailable/incomplete status when matches were deferred. Do not remove the query/time limits.

## Boundary checks and non-findings

- Persisted source replies use neutral content plus ID/fingerprint/range references (`conversations.py:248-258`). The conversation API projects each returned source turn afresh (`server.py:2551-2574`), and `Agent.load_history()` excludes source-answer assistant turns (`agent.py:1266-1282`). These paths do not persist the displayed quote as assistant prose or pass it to later model history.
- `source_is_unclaimed()` checks every Claim status, including retracted Claims (`claims.py:407-429`); `_snapshot()` also excludes ignored, non-current, and produced sources (`source_answers.py:36-50`). The supplied tests include retraction, ignore/reopen, metadata change, provider history, and local-only behavior.
- I tested an artificial direct-store mutation after `render()`'s final `_resolve()`: the already-captured quote could then be returned after `EpisodeStore.ignore()`. This is **not** a demonstrated normal HTTP leak: the ignore/reopen routes and conversation response projection share `conversation_lock` (`server.py:2502`, `3587`, `3598`). I therefore do not count this injection as a blocker. Background/direct store writers would need the same serialization discipline if they change source validity.
- The `read_snapshot(max_bytes=...)` predicate is part of the `WHERE` clause, despite its concatenated SQL construction (`source_snapshot.py:37-41`). It does exclude oversized documents; no size bypass was found.

The review does not establish end-to-end product usefulness. It establishes the two reproducible behaviors above and checks the key persistence, withdrawal, and model-history boundaries in the current patch.
