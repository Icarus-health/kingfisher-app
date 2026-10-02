### Finding Verdicts

- **[P2] Rejected stale approvals persisted/displayed as approved — ADDRESSED.** `Turn.approval_outcome` is now an explicit typed field separate from model context (`sidecar/icarus_memory/agent.py:109`). User refusal and stale-input refusal assign `rejected` only after successful Policy rejection (`agent.py:813`, `:829`); a grant assigns `approved` only after successful `Policy.grant` (`agent.py:840`). Wrong confirmation therefore still throws before an approved outcome can be created. The conversation route persists the actual outcome and conservatively uses `unknown` for a missing outcome, instead of deriving approval from the user's requested grant (`sidecar/icarus_memory/server.py:2598`).
- **Required distinction between pre-action rejection and post-action follow-up invalidation — ADDRESSED.** The actual approval decision lives outside `turn.context`; replacing context with the follow-up's invalidated context does not replace the approval outcome. The new parameterized real HTTP test explicitly covers both zero-action/rejected and one-action/approved outcomes while both responses carry `context.invalidated=True` (`sidecar/tests/test_knowledge_time.py:340`). It verifies POST, subsequent GET, SQLite metadata, suppressed stale follow-up text, and that repeated resolution returns 409 without another execution (`test_knowledge_time.py:377–391`).

### New Breakage in the Fix Diff

None. No new Critical or Important issue found in the four-file fix diff `f52b910aa232928f012a57dca792307af2ffbf50..ccb47b1f8a60ee8fe57665dd7b557516ad45e4fb`.

- The public Turn serializer exposes the outcome only when one exists (`sidecar/icarus_memory/agent.py:127`); ordinary conversation turns retain their prior response shape.
- The existing ActionAgent test double now explicitly implements the same approval result contract rather than encouraging a fallback to request intent (`sidecar/tests/test_conversation_actions.py:29`, `:34`).
- Existing server exception handling still records `unknown`; the fix does not silently turn uncertain execution into success (`sidecar/icarus_memory/server.py:2593`).

### Checks Reviewed

- Read the complete immutable fix package and appended implementation report. Reused the unchanged task brief and prior full integration review; no broader code re-review or repeated suites.
- Retained RED log identifies the exact stale-grant mismatch: **1 failed, 1 passed, 37 deselected**, 0.70 seconds (`checks/approval-outcome-red.log`). The post-action positive control already passed before the fix and remains meaningful.
- Retained focused GREEN log: **149 passed**, 15.80 seconds, covering knowledge, mail, Agent, conversation actions, routing, evidence validity and profile history (`checks/approval-outcome-focused-green.log`).
- Retained full GREEN log: **1,757 passed**, 116.95 seconds, two pre-existing dependency warnings (`checks/approval-outcome-full-green.log`). The report correctly divides these as 1,589 backend tests plus 168 probe tests.
- No test rerun was necessary: the exact uncovered HTTP contract now has two direct regression cases and the retained execution evidence covers the changed shared return contract. No code/index/branch changes; only this requested report was written.

### Out-of-Scope Observations

- None newly discovered outside the fix scope. The initially stale release copies were refreshed during this re-review and then re-read: native **17/17**, rebuilt container **6/6**, image `sha256:1d75ffb0a4ef18df0e5e3a9be7f7b9f024dfcb4c7dc06f2d147a5ca2c0a4e845`. All **14** file hashes in refreshed `reviewed-source-sha256.json` match local files at `ccb47b1f8a60ee8fe57665dd7b557516ad45e4fb`. The updated README identifies the final 1,757-test run and explicitly labels the actual Python 3.10 run as predating the last narrow approval-status fix.
- The prior review's two dependency warnings remain nonblocking. The prior explicit exclusions—restore antirollback, general raw-tool/SelfModel redesign, atomic model execution, private deployment and parent-PR integration—remain unchanged and are not reopened by this fix.

### Verdict

**Fix round: All findings addressed, no new Critical/Important breakage.**

**Ready to merge? Yes, from code review, at `ccb47b1f8a60ee8fe57665dd7b557516ad45e4fb`.**

**Reasoning:** The actual Policy decision is now preserved independently of request intent and subsequent model validity, and both sides of the reported integration defect are exercised through real HTTP and durable read-back. Complete normal published-head CI/stacked-PR gates before integration; this verdict is not a deployment or restore-authority approval.
