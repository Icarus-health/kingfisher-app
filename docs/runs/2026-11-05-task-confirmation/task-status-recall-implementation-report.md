# P1 bounded typed task-status recall — implementation evidence

Base: `c6903f931670de4f232334da0a79b4612a3097a1` (reviewed Part A). Design: [Task status recall](task-status-recall-design.md). Chronological author evidence: the reviewed final code is now committed as `2e47086e8d4706e8fa6c4d21d8fe8877c6b27755`. Independent review is recorded in task-status-recall-fix01-review.md; broader P1 acceptance remains separate.

A normal authenticated conversation can resolve a saved task by full literal title or supported ID without invoking the question or answer model. Examples:

- `Ist Atlas Wartung erledigt?`
- `Wurde „LINDENBOGEN-46 Materialliste prüfen“ erledigt?`
- `Habe ich die Aufgabe Atlas Wartung schon abgeschlossen?`
- `Wie ist der Status der Aufgabe t-000000000001?` (example ID; also supports actual request and suggestion IDs)

The lookup normalizes NFC, lowercase and whitespace; it retains `Maße` vs. `Masse`, accents, punctuation and code suffixes. The unquoted path treats a literal token-boundary extension as ambiguous. Exact quoted title matching still counts same-title tasks from every state, including dropped. An interrupted title search never reports uniqueness from one seen hit. Point IDs bypass the scan, including for titles above the 256-character operand cap. A completed no-hit search for an unmarked question may continue through ordinary recall with no saved task data. Explicit IDs, explicit task forms and quoted titles use the local typed path for absence, ambiguity and withheld proof as well. Original-source requests, procedure choices and evidence choices keep their existing routes.

## Read and persistence contracts

- A read transaction selects the task and the latest per-task event sequence, current state boundary and applicable Part A confirmation. Separate SQLite progress guards bound title and history work to 250,000 opcodes each, with a callback each 1,000 and cleanup in `finally`. A history scan that cannot establish the state boundary yields an explicit incomplete-history result without a link. The history query uses the per-task sequence index and reads at most the state event and the confirmation row, without a 100-entry paging cutoff. Event sequences, rather than equal timestamps, identify each active completion.
- The local answer distinguishes open, dropped, generic/legacy done, mail-backed done and explicit confirmation. Dropped does not borrow `done_at` as completion evidence. The saved completion instant and later recorded confirmation remain separate. The explicit action does not establish a named actor. A mail proposal does not change the state until accepted; `post_completed` remains mail-derived even if later separately confirmed.
- The task's creation source and, when the active state event establishes mail-derived completion, the completion mail are eligible only under current bounded source proof. Missing, ignored, superseded, archived or invalid attachment-parent support withholds the projection. Unknown nonmanual origin is not treated as independent user text. The existing conversation lock covers cooperating mutations and task revision is checked again after the source checks. Neither original sources nor saved task/history data are altered by recall.
- The shared `belegbarer_snapshot` / `read_snapshot` change is opt-in. Only task recall passes `require_unarchived=True`; it rejects archived sources and recursively checks archived parents, and includes parent support generation in the task-specific fingerprint. For default callers the existing fingerprint representation and eligibility rules are unchanged. This is the shared evidence risk verified by the attachment lifecycle, episode support and source answer regressions, including the new direct default-fingerprint comparison across parent archive. The initial candidate had no migration; review fix 01 below adds the private archive marker. There is no claim rewrite.
- The assistant stores neutral text, minimal base context and strict v1 ID, revision, receipt sequences and at most two source stamps. The serializer drops copied content/context for typed records. The latest 20 typed replies are projected locally on GET, with the same validation on POST/retry response. Outdated, malformed and older references return neutral text with no stale ID, sequence, source stamp or link in message or top-level context. Source re-admission and task ID reuse do not revive a prior response.
- The original typed question remains a local conversation row. Server-owned flags keep it lookup-only; typed lookup and retry skip episode creation and background capture. It does not become the generated conversation title, a preview excerpt or a global conversation-search hit. Typed responses and their paired question are filtered before normal and retry model history, with a defensive Agent filter. The existing external provider and MCP schemas are unchanged. Enabled in-process MCP tests cover the real catalogue, the absent task-status tool and the existing context tool.
- The conversation draws one escaped plain-text answer and links through `taskHref` to `TaskDetail` with the selected receipt. The link label is **Aufgabe und Verlauf ansehen**. The existing History UI opens for the cited receipt, including dropped tasks and receipts older than 100 entries. The authenticated route uses an exact task/sequence point query and rejects a cross-task receipt. The UI preserves the originating message anchor when going back and offers the regular recent history inside the same viewer.

## Verification commands and retained outputs

Early RED: the new store suite initially had 4 expected failures (missing store interface/budget); the first actual HTTP cycle after the store reads had 3 expected failures (old source fallback, absent typed link and ignored exact-sequence query); the sharp-s counterexample failed on the prior casefold. The UI regression initially failed loading the missing link component. The additional quoted-title parser regression reproduced source-keyword interference in a literal title; retained RED log: `/private/tmp/kf-task-status-recall-parser-red-20261105.log`.

```sh
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
 /private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q \
 sidecar/tests/test_task_status_recall.py sidecar/tests/test_task_completion_confirmation.py \
 sidecar/tests/test_task_history.py sidecar/tests/test_task_history_api.py sidecar/tests/test_task_edit.py sidecar/tests/test_task_pages.py \
 sidecar/tests/test_task_source_generation.py sidecar/tests/test_aufgaben_post.py sidecar/tests/test_aufgaben_post_sicherheit.py \
 sidecar/tests/test_conversation_memory_capture.py sidecar/tests/test_conversation_retraction.py sidecar/tests/test_conversation_search_page.py \
 sidecar/tests/test_source_answers.py sidecar/tests/test_source_answers_http.py sidecar/tests/test_attachment_lifecycle.py sidecar/tests/test_episode_support.py \
 sidecar/tests/test_agent.py sidecar/tests/test_memory_agent_boundary.py sidecar/tests/test_mcp_tuer.py sidecar/tests/test_profile_history.py \
 sidecar/tests/test_procedure_runtime.py | tee /private/tmp/kf-task-status-recall-backend-final-20261105.log
```

The reused offline plugin replaces `socket.connect` and `connect_ex` with immediate `ConnectionRefusedError`. The focused in-process recall fixture also traps both with assertions. The test probes cover direct completion, a real mail candidate and older literal report, pending and accepted mail completion, historical receipt and restart readback, source/parent withdrawal, preview and search, local/external synthetic provider, retry and enabled MCP. This is a scoped backend suite.

```sh
set -o pipefail
ui_check=$(mktemp -d /private/tmp/kf-task-status-final-ui.XXXXXX)
cp -R app/kingfisher/. "$ui_check/"
ln -s /private/tmp/kf-skill-categories-20261031/app/kingfisher/node_modules "$ui_check/node_modules"
echo "$ui_check" | tee /private/tmp/kf-task-status-recall-ui-20261105.log
(cd "$ui_check" && npm run typecheck && node --experimental-strip-types --test \
 tests/task-status-recall-ui.test.mjs tests/task-workspace.test.mjs \
 tests/goal-task-link.test.mjs tests/conversation-workspace.test.mjs) | tee -a /private/tmp/kf-task-status-recall-ui-20261105.log
git diff --check
```

UI test uses Vite SSR in middleware mode with no listening browser/server, real React rendering of the link and history state, and the in-process HTTP regression verifies the exact linked receipt. No install, network, real model, protected store, GUI or acceptance data were used. No frozen fixture or gate classification was changed. Paraphrases that do not retain a full literal title, mixed task/source narratives, real model quality and the P1 holdout remain open.

## Initial candidate result

- Backend: **406 passed** (including 23 typed-recall cases) in 74.74 seconds; only the existing Starlette/httpx deprecation warning. Exit 0. The pre-final affected run also returned 406 passed.
- UI: **18 passed**; TypeScript check exit 0. Exit 0 for the combined check. No GUI acceptance.
- `git diff --check` passed. Worktree left uncommitted for independent review.

## File manifest

SHA-256 of the frozen production and test edits:

```text
a31f2cd822632a3f8d5d5a334a352270797efe8ef8824cdc1f4abb72f0ceb97b  app/kingfisher/src/TaskStatusAnswer.tsx
a2c53bec5a43980842fb0e639e11dd1a25cfaeb855ec55893f450c3b5a70905a  app/kingfisher/tests/task-status-recall-ui.test.mjs
4e724ba29e13833f2455c37bbdb762d9d74175e77600c8baec3c6cae1f598417  sidecar/icarus_memory/task_status_answers.py
627ecc8d3e19a8fd39458a8087af8d44e51c87f5a39ac2b0dd097e00bf121084  sidecar/tests/test_task_status_recall.py
caa4a3705eb64c37b891d5a6bb2b4e48d5f1d218fcc9ce8f458b584cda00a915  app/kingfisher/src/App.tsx
6ce479888210f988cd5c2b2fb47a03662ecdc89c2b6f87e62c9e22c1f9e1adc7  app/kingfisher/src/TaskDetail.tsx
5dbf7039bda6e2cdacd09bc9bf425d3d48394aa8806fa6b3abd5d4fd60a8edae  app/kingfisher/src/TaskHistory.tsx
dffffe04ace861fffe1e729cf236952b98686f5932312af83effe843a5a91a7d  app/kingfisher/src/TaskRow.tsx
53f256c5c5cd94e0b5b97654d028dae3b79cb53d279bd589eb3ac8a89e8c3daa  app/kingfisher/src/api.ts
d6f0a713909c547d9b969545ec931b0b55a6bea7008dc1ffd9e201dd327ca034  app/kingfisher/src/taskWorkflow.ts
41e1713b9e2b6b28cac44fb0d1e56fdafbcabed4a1e87f6165ea2d4c001e81f0  sidecar/icarus_memory/agent.py
652e03b5bec16063ed2de3d0f254ac9cdde76526e50e9fd9605c0c355c99d18b  sidecar/icarus_memory/conversations.py
72244809ff5245bf81a382ff3619995fcd2d4756de97926e2ac8b350f5b1ca6a  sidecar/icarus_memory/episodes.py
b081d955f5df084e072b8fb2a53c5d6002f279cf2dffce281b1cad105f9c5f8d  sidecar/icarus_memory/server.py
163103443eb57bc3d20d40eae8e9da44d05a6ac1663b3acf64820e96610960ca  sidecar/icarus_memory/source_snapshot.py
5a404d24339045993e817dc14c51b07b9d532c91a1b5b993bdfc575a5efd28db  sidecar/icarus_memory/tasks.py
```

## Review 01 fixes

**I1. Restored completion provenance.** A restored done task keeps the restore sequence as its current history boundary. Within the same read snapshot and SQL budget, the lookup checks up to eight prior restore and removal pairs to establish the original completion event. The checked removal snapshot must match the restored state, and the task history must identify a single creation. If that proof is incomplete or the ID has been reused, the answer withholds the status and link. An original mail completion still requires a valid stamp for the completion mail. The current confirmation search starts at the restore boundary, so an earlier explicit receipt is never presented as a new confirmation. The authenticated regression covers two successive restores, opening the exact restore event, withdrawal of the completion mail, and a same-time completion under a reused task ID.

**I2. Archived source readmission.** EpisodeStore migration 27 adds a private integer column with a default of zero. A verified SQLite trigger increments it when the source enters the archived state. The task-specific support fingerprint incorporates the value, including zero, for the direct source and recursively for attachment parents. This invalidates prior candidate source-backed task references once and prevents archived references from reappearing after reconsolidation at the same timestamp. A fresh lookup can use the source when it is eligible again. The original document, source head, existing support generation and default evidence fingerprints retain their previous values. The real v26 upgrade and parent archive tests verify the unchanged support of an active synthetic claim. Other tests verify atomic migration rollback and failure to open a v27 store missing the trigger.

The initial focused reproductions produced 3 expected failures covering restore, direct source readmission and parent readmission. The earliest migration-test attempt also exposed two test setup errors caused by treating EpisodeStore as a context manager. The fixture now closes the store explicitly. A schema-neighbor run found one older mail-header test inserting the new column into a v21 fixture. The corrected run keeps that fixture at v21 and verifies the default after upgrade.

```sh
set -o pipefail
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. /private/tmp/kf-core-20261104-env/bin/python -m pytest -q \
 sidecar/tests/test_task_status_recall.py -k 'restored_mail_completion or archive_and_readmission' \
 | tee /private/tmp/kf-task-status-recall-fix01-red-20261105.log

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. /private/tmp/kf-core-20261104-env/bin/python -m pytest -q \
 sidecar/tests/test_migrations.py -k 'episode_v26 or archive_generation' \
 | tee /private/tmp/kf-task-status-recall-fix01-migration-red-20261105.log

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
 /private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q \
 sidecar/tests/test_task_status_recall.py sidecar/tests/test_migrations.py sidecar/tests/test_episode_support.py \
 sidecar/tests/test_attachment_lifecycle.py sidecar/tests/test_aufgaben_von_selbst.py sidecar/tests/test_update_backup.py \
 | tee /private/tmp/kf-task-status-recall-fix01-core-final-20261105.log

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
 /private/tmp/kf-core-20261104-env/bin/python -m pytest -p kf_completion_confirmation_refused_socket -q \
 sidecar/tests/test_akten_vorschlaege.py sidecar/tests/test_mail_header_index.py sidecar/tests/test_mail_ingestion.py \
 sidecar/tests/test_category_diagnostics.py sidecar/tests/test_source_index.py sidecar/tests/test_compact_search_index.py \
 sidecar/tests/test_projekt_automatik.py sidecar/tests/test_task_rechecks.py sidecar/tests/test_bezuege.py \
 sidecar/tests/test_source_project_link.py sidecar/tests/test_memory_areas.py sidecar/tests/test_mail_mime_retry.py \
 -k 'migration or v2 or v18 or backup_restore or existing_v1' \
 | tee /private/tmp/kf-task-status-recall-fix01-schema-neighbors-final-20261105.log
git diff --check
```

The final core run passed all **194** selected tests in 23.75 seconds. The schema-neighbor run passed all **19** selected tests in 4.07 seconds, with 197 deselected. Each run exited 0 with the existing Starlette/httpx deprecation warning. `git diff --check` passed.

SHA-256 of the 19 files changed in fix round 01, relative to the frozen review 01 index.

```text
3d6367b3c39f660dbecada32094f6b772a6a963b4652f367aac8f58aec80cb22  sidecar/icarus_memory/episodes.py
beb397e3145955b24427c080de6ba9dee34bfd68b970beb5ca76252ab6318213  sidecar/icarus_memory/source_snapshot.py
06fe37a68f679512ec135ca3fc81cad5c0205330fc40790cadfc46142174e041  sidecar/icarus_memory/tasks.py
0651e620705f3fabdd00fad429ac8e640a15162ccd0a14ff84c0fdb387fc77ff  sidecar/tests/test_akten_vorschlaege.py
cb1acf41f1e0303abfca1a6c14a68bf0a5b3bd7d0586e113146484f7b24a8053  sidecar/tests/test_bezuege.py
a8150522084741054e0afd7c798a71f4e30b0ba19e9eb8232d9f4bc768c76e6e  sidecar/tests/test_category_diagnostics.py
1efd1bf4a4ad0a88db57dc4dfd48f6fb5517180b611d2943a57dc13b84a76f6d  sidecar/tests/test_compact_search_index.py
461cc5ebf9b9d18ad3d7ece65779365f2814ea6aee7b070e5cb54254cfa81471  sidecar/tests/test_mail_header_index.py
f78fa134ea394d6709cb1edaaa0d1cd347b52132b18c5941e91f0b4fe34da208  sidecar/tests/test_mail_ingestion.py
992215c4a89017793a914bebd388ed5c2894a2c6c52a3145bbebd15dab01f96c  sidecar/tests/test_mail_mime_retry.py
4e5167145d8b052ea78007cc8704e2ce619ce99e80c21112c463c7b8ae914b8b  sidecar/tests/test_memory_areas.py
15ec4ae3b0154384aaeb3d3d2e07d46c28e093361d554e301aa266d971ecbe13  sidecar/tests/test_migrations.py
0350b0fb3051a1974ea8697a6e4cff6e3ffcf6fd6c419029492d6280b0905a95  sidecar/tests/test_projekt_automatik.py
99c0f83a321b40c207d1d6bbac2c0d857b2b10bc5ee9985de2f7a9eb7124e78a  sidecar/tests/test_source_index.py
941a33e3649abd8eb83a64c981cc59d69bc8d41ef3f180f63035f9ee68ed0edf  sidecar/tests/test_source_project_link.py
12034c025ee17cc35b86efcc9467ddf13db61eba9f00e0de37bdc234219b71d0  sidecar/tests/test_task_rechecks.py
078372539d21b19770912a3aa5b67f65839254a2c5beaab38c7212e28a04e53c  sidecar/tests/test_task_status_recall.py
359b57c6b81a3a210c2ad2cc055ad34cf49ebb0b48816efd3ae884872414557d  sidecar/tests/test_update_backup.py
3763aac7171b88428b6b8cb955fe27a1b7ffee72ed295532a8a5d9be823cd9b9  sidecar/tests/working_memory_legacy.py
```
