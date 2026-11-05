# Confirmed task responsibility — development evidence

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

## Packaging follow-up

The seven earlier unresolved font/landscape warnings were caused by the disposable build tree omitting `design-source`, which Vite declares as its public directory. The real Dockerfile already copies that directory. A new isolated build of the unchanged UI production code at `ed9b190` included the correct layout: TypeScript and Vite passed without any unresolved-asset warning. All seven emitted font/image files match their source bytes, and the canonical asset check passes (11 referenced files, 14 icons). The cached dependency versions matched all 28 installed lockfile entries; no install or download was needed. The existing JavaScript chunk-size warning remains. These checks establish packaging, not native rendering or interaction performance.

## Task 3: current responsibility in conversation

Supported owner questions using an exact task ID or full title now resolve locally to the current confirmed decision or an explicit clarification. Saved responses contain neutral, versioned task/event references; reopening checks them again. Reset stays unknown, and a removed or recreated task cannot revive an old answer. Responsibility, requester and waiting dependency remain distinct.

The actual working-source, literal-source and knowledge-evidence paths also bind linked task decisions. Current decisions are displayed separately from historical source reports; unrelated, unselected tasks do not appear. Multiple linked tasks remain distinguishable. Source change, withdrawal or archive removes the historical rendering; the user's independent decision remains answerable for a visible task. General reads are bounded to 32 sources and eight linked task occurrences; an incomplete check withholds rather than asserting absence. New task-decision text is not sent through the approved-cloud source-selection path. Existing cloud cost/egress receipts remain visible if a later change invalidates its answer. No actual provider call was made in this work.

Initial failing tests reproduced the missing typed/general integration and selection context. Later tests exposed source archive disclosure, unselected-source leakage, lost continuation proof and a change during final rendering. Five existing clarification/disclosure regressions were corrected without changing their assertions. The grouped run passed 265 affected Python tests; subsequent receipt-only validation passed 42. Two additional actual error-retry cases and two UI history-link/escaping tests passed; TypeScript passed. These overlapping runs are not a combined test total.

Independent review found a remaining title-lookup race: renaming or recreating a task between lookup and snapshot could answer the old title with the new task. Both cases failed before the fix; preserving the lookup revision now returns protected clarification. The final affected responsibility/status suite passed 55 tests. Scoped independent re-review approved the correction with no new findings. The upstream TestClient warning remains.

This is technical integration evidence. It does not establish arbitrary semantic paraphrase accuracy, an actual Qwen/Mistral result, native interaction, installation or usage-week acceptance. The complete responsibility subplan still receives a separate integration review before grouped publication. Original sources and the frozen acceptance corpus remain unchanged; large import remains paused.

## Final integration review and source replay correction

The combined review found one remaining technical blocker: a reworded title with an expanded, shortened or partially overlapping citation could create a second personally actionable task after the original responsibility was corrected. The final fix compares exact quotation spans in the already validated source, without semantic matching. Plausible overlap or unprovable evidence requires review; genuinely disjoint and adjacent spans remain eligible. Existing exact accepted-candidate proof is still required for a rebind. All three production paths (automatic processing, candidate acceptance and direct mail action) use the rule; the final transaction rechecks corrections before creating a project. Source text is transient, never stored in the task or event as new proof material.

The source/quote cap is 256,000 characters, the occurrence walk is bounded to 128 advances, and the final corrected-source query allows 64 rows plus an exhaustion sentinel under the SQL budget. Exhaustion does not authorize a duplicate. This is an exact-evidence guard: semantically equivalent tasks in disjoint passages still need the separate quality assessment. The personal project tile/board label now reads “Meine Aufgaben”; the overview explains the independent waiting count.

Actual automatic RED tests reproduced four bypasses while the disjoint control passed. A manual race also reproduced unwanted task/project creation. The final affected run passed 81 Python tests; three further focused race/rebind cases passed. Fourteen UI checks and TypeScript/Vite passed. The full design layout emitted all seven checked assets byte for byte; only the existing chunk-size and TestClient warnings remain. No full-suite or native result is implied by these focused runs.

The one scoped final re-review approved I1 and M1 with no new Critical/Important finding. The completed technical subplan now joins storage, UI/classification, automation and actual conversation projection. Real-model semantic quality, native interaction, exact-head CI, personal installation and usage-week acceptance remain separate open gates. No bulk import, private-source upload or model-provider call occurred.

## Published-head CI follow-up

At `bb1ecec`, CI run 41965994776 completed the Python 3.10 and 3.12 backend
suites with the same single failure: the sent-mail integration test still
expected the old “vermutlich noch offen” opening. Each run passed 10,361
other tests and 26 subtests, with two skips. Later steps did not run after
that failure. UI, Mac build and Container passed; this is not an all-green
CI result or a native acceptance.

The local reproduction reached that exact assertion using the real synthetic
TLS IMAP fixture. The test now requires the intended source-qualified own
commitment and the explicit statement that its open state is not established.
Existing source quotation, role, proposal and model-free checks are unchanged.
The only production-file edit corrects the module docstring; executable AST
is unchanged. Both affected test files passed (37 tests), and an independent
scoped review confirmed the contract and unchanged semantics. The default
all-socket guard initially blocked fixture setup; the successful runs used
a temporary exception limited to that fake listener's live loopback port,
while external destinations remained blocked. The existing TestClient
deprecation warning remains. CI for the resulting correction is a separate
pending check, not inferred from the local result.
