# Confirmed task responsibility — core/API evidence

Scope: additive task JSON and authenticated correction API, on the existing SQLite task/event store. Requester, waiting dependency and execution responsibility are distinct. Existing missing responsibility stays unconfirmed; explicit reset or the first decision's undo stays unknown. This core is only Task 1 of the associated P1 subplan: UI/classification, automatic-action guards and real conversation retrieval remain required before user delivery.

## Verification

Two synthetic entry points initially failed because the store method and guarded API did not exist. The first implementation passed 62 targeted tests. Independent review found two blocking issues: a legitimate current-incarnation restoration after prior deterministic ID reuse lost its receipt/proof, and the event-kind query collided with the existing source-authority guard. Both were reproduced before fixing.

The final core correction passed 70 tests under Python 3.12, with outbound sockets blocked:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest -q \
  -p kf_completion_confirmation_refused_socket \
  sidecar/tests/test_task_responsibility.py \
  sidecar/tests/test_task_history.py sidecar/tests/test_task_history_api.py \
  sidecar/tests/test_task_status_recall.py \
  sidecar/tests/test_task_completion_confirmation.py \
  sidecar/tests/test_geltende_quelle.py
```

Cases cover exact-address identity, explicit unknown, restart, first/later undo, stale revisions, two SQLite writers, failed-write rollback, same-request replay after later edits and more than 100 history events, conflicting replay, exact task-ID reuse, fresh/old tombstone restoration and old status-proof compatibility. A fresh tombstone's bounded internal removal-event marker permits proof only when the latest removal and restored state match. Ambiguous legacy restoration never borrows another incarnation's receipt. No SQL schema migration or competing identity registry was introduced. The source-authority guard remains unchanged.

The existing Starlette/httpx TestClient deprecation warning is tracked separately. This evidence does not cover model interpretation, actual Mac interaction, installed-app compatibility, large-mail-import quality or usage-week acceptance. No personal mailbox, paid provider, original-source changes, app installation or bulk continuation occurred.

Independent scoped re-review approved both corrections with no new Critical/Important findings; reviewed file hashes matched the reported test revision. This approves the bounded core/API task only.

## Repeating the offline checks

The recorded command used a temporary pytest socket blocker. Its byte-identical, credential-free copy is retained here as `offline_socket_guard.py` (SHA-256 `4d3cd08dd11ea6f8a4e7b4ee9d4511db56ee6813f1421479041782058a9a5b45`). To repeat the listed tests in a configured development environment, add `docs/runs/2026-11-05-task-responsibility` to `PYTHONPATH` and use `-p offline_socket_guard` with that environment's Python interpreter. This preserves the same refused-connection behavior; it does not change the historical commands or count as an additional test run.

## Task 2: visible correction and consistent work lists

The development UI now offers Ich, Person and Ungeklärt in task details, with exact-address selection, confirmation, reset, undo and review after a concurrent edit. Person remains the requester/counterparty field; responsibility is separately confirmed. Legacy entries remain unconfirmed. Mine, other-person and unassigned views use shared classification, while waiting describes a separate dependency and may overlap those categories. Profiles, project dossiers, source promises and original messages remain available with their distinct meanings.

Briefing and personal overdue counts exclude explicit other/unknown work. Mail automation checks responsibility both when proposing an action and inside the final task write. A source retry can reuse a corrected task only through its original accepted candidate evidence and exact citation; a different action sharing a quote stays reviewable. Confirmed user title edits and provenance are preserved. No new SQL schema or identity registry.

Six initial tests reproduced incorrect personal-work classification, automatic completion and source replay behavior. The first affected Python run passed 390 cases with one obsolete waiting-copy assertion; the later affected subset passed 95. Initial UI verification passed 61 of 63 with two outdated label assertions; the final relevant subset passed 23. Results overlap and are not a summed test total.

Independent review then found three integration defects: delayed successful saves could display an older task revision; direct mail acceptance returned 500 for the new expected source conflict; and a correction racing candidate acceptance could leave an orphan new project. Captured RED runs reproduced all three. The correction uses shared UI mutation claims and monotonic snapshot generations, returns an actionable 409, and defers the deterministic project factory until after the final transactional correction check. Both correction-first and acceptance-first orderings are covered.

After those changes, 89 affected Python tests and 40 affected UI cases passed. The final strengthened editor/handler subset passed nine cases. TypeScript and Vite built successfully. Independent scoped re-review approved all three corrections with no new Critical/Important findings. Relevant tests are in `test_task_candidates.py`, `test_mail_conversation_flow.py`, `test_task_responsibility_views.py` and `tests/task-responsibility.test.mjs`, with the supporting reader/automation suites recorded in the development run. No actual provider, private source or native window was used.

Task and workspace databases still commit separately: an interruption after project commit retains the prior deterministic retry behavior. This patch does not promise distributed atomicity. Editor retry inputs remain in the open detail's memory. Real navigation-away, focus, narrow/wide WebKit layout and contact suggestions still require native acceptance. Existing asset-resolution/chunk warnings and TestClient deprecation remain tracked; no new asset/dependency references were introduced. The personal count label and independent waiting-count explanation remain a small UX review item. Task 3 conversation integration and the full semantic/native/usage-week gates remain open.
