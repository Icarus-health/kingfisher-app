# Completion confirmation and truthful provenance

Base `b906d43956abee9caf33fee5a0602eb60fa0d3d9`. Bounded implementation of section A in [task-completion-recall-report.md](task-completion-recall-report.md). Section B (task status as strict recall evidence) remains open.

The synthetic `create_app` regression sends the ordinary chat text “Sag nur Hallo.” and makes the provider issue `aufgabe_erledigt`. The action now appears as a pending `write_local` request and the task stays open. Rejecting does not write a completion; a fresh grant completes the task exactly once. The direct authenticated done buttons still require one action.

## Implementation

- `Policy()` applies a minimum `confirm` for `aufgabe_erledigt` if there is no explicit tool override. Stronger class policy, configured tool overrides, source taint escalation and user constraints are preserved. A named standing rule can lower the level on a clean turn. An explicit completion denial cannot be lowered by a standing rule. Other tool defaults are unchanged.
- The tool accepts only a string task ID. Unknown fields are rejected before a standing rule can match them. Its two optional approval hooks prepare a local title/ID preview and receive a trusted execution snapshot only from an actual grant. Existing tool callbacks and adapter schemas keep their behavior. The same read obtains the display title, status and latest event sequence. Only task ID and event sequence constitute the execution snapshot. The local preview retains a bounded title (up to 4096 characters plus truncation marker), with no notes or source text. Neither the preview nor the sequence enters persisted approval metadata, audit, model input or MCP payloads.
- The authenticated conversation card overlays the live preview on a pending request. `/chat` returns the authenticated preview; `GET /approvals?local_preview=true` opts in for the local API. The default `GET /approvals` response and the initial `/tools/aufgabe_erledigt` reply show the ID-only dry run. The existing `icarus_freigaben` bridge reads the redacted default and cannot request a preview via tool arguments. No new MCP tool or UI was added.
- The existing source, profile, knowledge and procedure guards run before grant. `TaskStore.confirm_completion` compares the supplied snapshot and mutates the task within the same `BEGIN IMMEDIATE` SQLite transaction, using the append-only sequence to reject edits, edit reversal, complete/reopen, drop and identity reuse. The test interleaves a write from a second store just before entering the completion transaction, after the approval has already been consumed. A stale request is consumed as a refusal with a plain local message; it creates no completion event. Approval success and stale refusal receive a deterministic local response without asking a model to summarize; those replies are omitted from model history.
- The two authenticated direct done routes and the granted snapshot path append `user_confirmed_completion`. Generic standing execution and preexisting `completed` events do not assert explicit confirmation. Mail-derived `post_completed` events remain mail-derived. If the task is already done without an active confirmation, a fresh explicit action appends one confirmation with unchanged task state and `done_at`; its new `recorded_at` captures the confirmation time. Unrelated edits retain that active completion. A new completion after reopen, drop or task replacement is a separate incarnation. Repeated done actions add no duplicate. Existing rows, schema and task/status response fields are unchanged. `actor_id` remains null and the new UI label says “Erledigung ausdrücklich bestätigt”. No task event creates a claim or episode or changes strict recall.

## Verification

From the worktree, the RED command before production changes was:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest -q \
  sidecar/tests/test_task_completion_confirmation.py
```

The corrected RED run had **12 expected failures** and one existing Starlette/httpx warning. In the normal chat regression, the real HTTP response's `action_requests` was empty, reproducing the absence of an approval. The independent characterization in the linked report established that the task actually completed with the old `notify` execution. Intermediate GREEN after the first policy/transaction and MCP readback refinements was **13 passed**, with the same warning. The fixture uses only in-process HTTP, a synthetic model and synthetic stores; its socket methods refuse connection attempts.

The final affected suite uses a temporary pytest plugin that replaces `socket.socket.connect` and `connect_ex` with a function raising `AssertionError` at session start and restores them at finish. An initial broad affected run was stopped after discovering an existing loopback port 1 probe; it did not establish the final result. The following command attempted to deselect that probe using a path relative to the working directory; pytest's reported node path was relative to `sidecar`, so the probe was included and blocked by the plugin.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest \
  -p kf_completion_confirmation_no_socket -q \
  --deselect=sidecar/tests/test_mcp.py::test_ohne_sidecar_kommt_eine_verstaendliche_meldung \
  sidecar/tests/test_task_completion_confirmation.py sidecar/tests/test_task_history.py \
  sidecar/tests/test_task_history_api.py sidecar/tests/test_task_edit.py sidecar/tests/test_task_reminder_api.py \
  sidecar/tests/test_aufgaben_post.py sidecar/tests/test_aufgaben_post_sicherheit.py \
  sidecar/tests/test_agent.py sidecar/tests/test_regeln.py sidecar/tests/test_regeln_tuer.py \
  sidecar/tests/test_mcp.py sidecar/tests/test_mcp_tuer.py sidecar/tests/test_mcp_client.py \
  sidecar/tests/test_knowledge_time.py sidecar/tests/test_profile_history.py \
  sidecar/tests/test_procedure_runtime.py sidecar/tests/test_conversation_memory_capture.py \
  sidecar/tests/test_mail_conversation_flow.py sidecar/tests/test_memory_agent_boundary.py
```

That run had **391 passed, 2 failures** (exit 1). Both failures were the intentional socket assertion: the existing MCP unreachable endpoint test probes loopback port 1, and the procedure budget test probes loopback Ollama tags during setup, before its synthetic model response transport is used. The same two cases passed in isolation under a stub that raises the ordinary `ConnectionRefusedError` instead of `AssertionError`, still with no connection:

```sh
sed 's/raise AssertionError(/raise ConnectionRefusedError(/' \
  /private/tmp/kf_completion_confirmation_no_socket.py \
  > /private/tmp/kf_completion_confirmation_refused_socket.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest \
  -p kf_completion_confirmation_refused_socket -q \
  sidecar/tests/test_mcp.py::test_ohne_sidecar_kommt_eine_verstaendliche_meldung \
  sidecar/tests/test_procedure_runtime.py::test_learning_uses_real_json_provider_budget_contract
```

The two runs account for **393 passing affected cases**, including all 13 completion regressions. Both runs emitted only the existing Starlette/httpx deprecation warning. This is not a full backend run.

The UI TypeScript check passed with existing installed dependencies, without a package download:

```sh
ui_check=$(mktemp -d /private/tmp/kf-completion-confirmation-ui.XXXXXX)
cp -R app/kingfisher/. "$ui_check/"
ln -s /private/tmp/kf-skill-categories-20261031/app/kingfisher/node_modules "$ui_check/node_modules"
(cd "$ui_check" && npm run typecheck)
git diff --check
```

No GUI acceptance, real model, cloud, migration, release, commit or push. The local API still has the existing sidecar authentication model and does not verify a named person. An external process that can read the shared token and call private local HTTP endpoints is outside the MCP bridge boundary. Pending approvals originating only from MCP remain unbound to React conversations; the local authenticated API can read and resolve them. No MCP-only approval screen was added.

## Changed files

SHA-256 of the delivered files:

```text
508173cc1c09d4f56d7ef0e3f643274981f8430228e3fe3401f69ab46af21afb  app/kingfisher/src/TaskHistory.tsx
94df453987851589fd0d38be0b54f6f8019ec915aa224bba0de2333c5c5dd9ae  sidecar/icarus_memory/agent.py
ce41fc26092eddb0cfd5da1c93b7facaa5173556f8e2a5d51fb964e169e02c22  sidecar/icarus_memory/policy.py
7b644c0681cd7483a124ba0df3b989a2afbd30d2a7a16c64c5348f32daa19a7e  sidecar/icarus_memory/server.py
e36386dd81b9a925a25897b8da675343935f7cf309fbecdc1fb10853bccc47ad  sidecar/icarus_memory/tasks.py
076a08a6490840418bb0e8374523137cde2fc779ef88effc84b1122b43a55ce9  sidecar/icarus_memory/tools.py
245dfd9d370a1973f5e23219dd2356ff2a7234a03c8c139eeb721b5e4ca6c10b  sidecar/tests/test_task_completion_confirmation.py
```

The preexisting Mistral addendum was left untouched; its SHA-256 at readback was `e2f8a78d39f93425f1a937abac44c9fd2ab811d671a2d2c2b1f33ad04cf56792`.
