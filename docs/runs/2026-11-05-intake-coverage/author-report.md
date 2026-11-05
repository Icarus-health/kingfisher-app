# Intake coverage in conversation recall — bounded P1 author report

Base: `9e17e2b33922526869c0ec3ea1341b6f9492121c`. Scope: authenticated application conversations; no frozen acceptance fixture was opened or changed. This is a synthetic technical regression, not an acceptance of P1 as a whole.

## Baseline reproduction and result

The independent fixture used the app's own migrated EpisodeStore, a deterministic three-item mailbox transport, the real `Intake.start/step`, an ordinary current WorkingMemoryStore classification marker on the captured source, and the real conversation route. The connector inventoried three UIDs in the current generation. A two-item intake batch captured UID 3, failed to fetch UID 2 (synthetic OSError), and left UID 1 pending without requesting its body. An unauthenticated GET of intake returned 401. Authenticated `GET /api/v1/mail/intake` showed completed inventory of three items: **one captured, one pending, one failed**. No connector was contacted during conversation recall.

Authenticated `POST /api/v1/conversations/{id}/messages` used `memory_evidence`, asking “Bis wann muss der Probelauf der Bogenpresse BP-726 stattfinden?” The real pipeline with one deterministic local selection returned `working_reports` and the eligible original: “Bogenpresse BP-726: Der Probelauf ist nur nach der Freigabe möglich.” The baseline was already source-qualified: it did not say there was no deadline and did not explicitly say all sources had been checked. It did omit known incomplete intake from both the answer text and its context; the user would have had to consult another screen. The stored answer used the neutral persisted reference text, “Arbeitsstand gespeichert. Die Quellen werden beim Öffnen erneut geprüft.” Authenticated conversation GET reproduced the same missing disclosure. The failing test, response body, context, stored record, intake counts and connector/model call counts are in `/private/tmp/kf-intake-coverage-20261105/repro-red.log`; no production code had changed for this run.

## Repair and contract

- Existing Intake tables supply current folder generation and pending/failed queue evidence; existing versioned WorkingMemoryStore analysis markers distinguish already captured but not yet classified mail. A request uses capped account IDs and a SQLite instruction budget. Reads return only a reason or no observed gap; no identifiers, counts of supposedly relevant mail, raw text, or provider errors. It does not invoke Intake.status, walk the full progress projection, consult connectors, run maintenance, or start analysis.
- A current pending/failed uncaptured item supports “Mailaufnahme: Noch nicht alle gefundenen Mails sind eingelesen.” Already captured mail lacking current analysis supports a distinct sentence. Disabled/not-started accounts, an unresolved folder generation or incomplete inventory, and an interrupted or unavailable local read are treated as unverified. No branch asserts completeness. The notice makes no claim that any omitted mail relates to the question or contains a deadline.
- Normal conversation POST, retry POST and GET share the existing authenticated `_conversation_payload` view. It projects the current note with substantive general memory evidence, using the normal original/source and claim checks first. The intake check runs at most once per payload; recent substantive answers use the same note for the current view, within a limit of 20. It leaves explicit literal source answers, typed saved-task status, clarification/choice, procedure, and unrelated chat or calendar paths alone. ConversationStore retains the neutral turn content and its existing metadata. The note appears only in the conversation projection and stays out of sources, claims, and provider or MCP input. When the user explicitly submits local feedback, the separate feedback store can retain the projected answer snapshot, including the note. It adds no migration or provider/MCP interface.
- The app displays the same short status line once alongside the answer, outside either collapsed originals or the structured sentence renderer. It uses existing answer status styling; the plain HTTP answer (including the existing voice text path) retains the notice. There is no navigation change.
- The tests verify the answer and source link survive the addition, and an injected assistant storage failure retries the same question with one user row. Once capture completes, the reopened answer changes from capture to analysis disclosure, then drops the notice when no gap is found while preserving the original. Disabling the account and the real synthetic generation reset produce unverified coverage. An actual SQLite budget interruption retains the grounded answer and the following normal GET recovers. Tests keep the existing enabled MCP list/context surface free of this information. Readback asserts the episode DB change counter is unchanged, fails if the dashboard or connector is touched, and shows no extra model calls. Existing local selection may carry the admitted source's ordinary provenance; the new coverage reason and unread/failed queue details are not part of it.

## Verification

The test transport is in-process. The existing `kf_completion_confirmation_refused_socket` plugin disabled socket connect/connect_ex for pytest; its synthetic tests also prevent access to real keychain, connector, provider, or personal storage. Runtime flags and test stores were temporary; the UI ran against an isolated copy with existing node_modules. No GUI, deployment, import, model-quality or native click acceptance was performed.

Executed from the checkout (stdout/stderr retained under `/private/tmp/kf-intake-coverage-20261105/`):

```sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp
/private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q -s sidecar/tests/test_intake_coverage_recall.py
/private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q sidecar/tests/test_intake_coverage_recall.py
/private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q sidecar/tests/test_intake_coverage_recall.py sidecar/tests/test_mail_intake.py sidecar/tests/test_mail_intake_routes.py sidecar/tests/test_mail_intake_lane_progress.py sidecar/tests/test_mail_intake_wait.py sidecar/tests/test_source_answers_http.py sidecar/tests/test_working_memory_flow.py sidecar/tests/test_working_memory_choices.py sidecar/tests/test_memory_evidence_answers.py sidecar/tests/test_task_status_recall.py sidecar/tests/test_conversation_draft_server.py sidecar/tests/test_conversation_retraction.py
git diff --check
```

The pre-change focused cases failed for the missing projection (`focused-red.log`), and the pre-change UI case failed because the notice was not rendered as a visible paragraph (`ui-red.log`). The intermediate `focused-green.log` includes one overly broad assertion against a **local** selector's preexisting admitted-source provenance (account ID on the eligible source); it was narrowed to the new notice and missing transport rows, and the final affected command exercises the same scope. Final affected suite: **176 passed** in `affected-green.log` (46.59 s), with only the existing Starlette TestClient deprecation warning.

From `/private/tmp/kf-intake-coverage-20261105/ui`:

```sh
node --experimental-strip-types --test --test-name-pattern='intake notice' tests/conversation-workspace.test.mjs
node --experimental-strip-types --test tests/conversation-workspace.test.mjs
npm run typecheck
```

UI: 14/14 passed in `ui-final.log`; typecheck exit 0 in `ui-typecheck.log`; `git diff --check` exit 0.

## Product and test files at initial freeze (SHA-256)

```
e978aa5703ab0f6baeca29cb07f49b6b2ef3b3f98ad65eb7c8b00062b560c038  sidecar/icarus_memory/mail_intake.py
52786b5be764f465d6b00963e4631c1b736e9196c5eb3e6131af706c93bda5b2  sidecar/icarus_memory/server.py
6d11ab0c03a4c17f7d06a2c02c25227e6e322fe13aa03a142c57e76874aff4a5  sidecar/tests/test_intake_coverage_recall.py
ba20ebbeaacf84e6d6891036501f72b626d1b632b2a6dd37b546b6a0ac27e179  app/kingfisher/src/App.tsx
92ba71e68be2199dd607a2b205a1f0e5af41cbc5a9aa9dc23fbd0dfb15d38c85  app/kingfisher/src/api.ts
12c58b8ddc0fdf921758a4fdca81b42ec2d457d6b9314d2d4635c807d5c2be05  app/kingfisher/tests/conversation-workspace.test.mjs
```

This is an intake snapshot for the active local mail inventory, not a measure of semantic search recall, attachment extraction, external mail freshness, or source relevance. Intentional filtering remains distinct from an unprocessed queue item; the existing Intake view retains its own detailed status. An empty queue or absence of a notice cannot establish complete coverage. The remainder of P1, real model quality, independent review, and real use acceptance remain separate.

## Review 01 correction and second freeze

The new authenticated POST/GET regression reproduced I1 with both an uninventoried Archive and a disabled second account. Each case had three captured messages in the active Inbox, of which one was classified. Both variants returned the generic unverified notice before the correction. The read now prioritizes an observed capture gap, then an observed analysis gap, then an unverified inventory state. It retains the same generation and source-head constraints and SQLite budget. The POST/GET tests verify that the admitted original and its source link remain visible. They forbid connector and Intake dashboard or processing calls, check for one selector call across POST and GET, and verify that GET writes nothing to the episode database. Feedback snapshot behavior and the existing dependency warning remain the two deferred review items.

```sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp
/private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q sidecar/tests/test_intake_coverage_recall.py -k known_analysis_gap
/private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q sidecar/tests/test_intake_coverage_recall.py sidecar/tests/test_mail_intake.py sidecar/tests/test_mail_intake_routes.py sidecar/tests/test_mail_intake_lane_progress.py sidecar/tests/test_mail_intake_wait.py
git diff HEAD --check
```

`/private/tmp/kf-intake-coverage-20261105/fix01-red.log` records both expected failures. `/private/tmp/kf-intake-coverage-20261105/fix01-green.log` records **70 passed** (11.14 seconds) and the existing Starlette TestClient deprecation warning. The working-tree diff against HEAD passed its whitespace check. The UI files and conversation projection code match the initial freeze above. Verification for this correction was limited to the focused backend suite.

```
28958f93d5cbd688a68c6b3273636ae40e88eff7193476891c18d89d29706a9d  sidecar/icarus_memory/mail_intake.py
ac20706230617d8c405a4a07623af09aac33b945c7ecddd7a641b49787b7f5c7  sidecar/tests/test_intake_coverage_recall.py
```
