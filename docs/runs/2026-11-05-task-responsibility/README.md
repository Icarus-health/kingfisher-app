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
