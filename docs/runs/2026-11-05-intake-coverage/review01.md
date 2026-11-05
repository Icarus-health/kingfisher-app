# Intake coverage review 01

## Spec compliance

❌ **Issues found.** A known analysis gap can disappear behind an unverified inventory state. See I1.

⚠️ This review covers the bounded synthetic recall change. Real model quality, native UI interaction, and the full P1 acceptance matrix remain outside the evidence.

Reviewed the frozen staged candidate in `intake-coverage-review01.diff` against base `9e17e2b33922526869c0ec3ea1341b6f9492121c`, the brief and the author report. The retained baseline `/private/tmp/kf-intake-coverage-20261105/repro-red.log:1` shows three inventoried messages, one capture, one pending item and one fetch failure. The answer already attributed the conditional statement to its source and made no categorical deadline or mailbox-completeness assertion. The reproduced defect was the missing disclosure.

## Strengths

- Capture evidence is tied to the current generation and an actual pending or failed item without a captured episode. The review checked the unchanged generation-reset write, which clears the folder generation and inventory completion while retaining past sources. The recall path uses bound parameters, an account cap and an SQLite opcode budget. Its constructor only takes the existing connection. SQL interruption leaves a descriptive notice and the next read can recover. `sidecar/icarus_memory/mail_intake.py:149`, `:400`, `:669`, `:688`, `:713`, `sidecar/tests/test_intake_coverage_recall.py:182`
- The analysis check uses the existing structural marker, source generation and analysis version. The answer still relies on the existing eligibility and evidence projections, including lineage checks and withheld statuses. No queue detail is introduced into those projections. `sidecar/icarus_memory/mail_intake.py:702`, `sidecar/icarus_memory/working_memory_store.py:50`, `sidecar/icarus_memory/server.py:4347`, `:4376`, `:4486`, `sidecar/icarus_memory/working_memory_answers.py:1400`, `sidecar/icarus_memory/knowledge_answer_view.py:61`
- GET, normal POST and retry use the same conversation view. The provider history reads stored messages separately. The focused auth-route test retains the original and its source link, checks the stored turn and DB change counter, and prohibits connector and dashboard access. Retry leaves one user turn. The enabled MCP test covers its tool list and context call, which uses a separate context endpoint. `sidecar/icarus_memory/server.py:4492`, `:4614`, `:4679`, `:5056`, `:5305`, `sidecar/icarus_memory/mcp.py:323`, `sidecar/tests/test_intake_coverage_recall.py:89`, `:156`, `:197`
- The projected-answer gate excludes literal source answers and requires an eligible evidence status. Typed task status projects a separate context. The UI displays one compact line per eligible answer outside collapsed originals and structured sentences, using the existing status style. The SSR evidence covers all three render paths. `sidecar/icarus_memory/server.py:4492`, `sidecar/icarus_memory/source_answers.py:196`, `sidecar/icarus_memory/task_status_answers.py:229`, `app/kingfisher/src/App.tsx:545`, `:560`, `app/kingfisher/tests/conversation-workspace.test.mjs:230`

## Issues

### Critical

None.

### Important

**I1. An unknown folder or account hides independently known incomplete analysis.** `sidecar/icarus_memory/mail_intake.py:697`, `:702`; `sidecar/icarus_memory/server.py:4265`; `sidecar/tests/test_intake_coverage_recall.py:127`.

The function returns `unverified` before checking persisted analysis. An active, inventoried INBOX with two captured and unclassified messages returned only “Mailaufnahme: Den Stand konnte ich nicht verlässlich prüfen.” after either adding an unstarted Archive to the same account or adding a disabled account. Authenticated POST and GET both preserved the eligible answer and both omitted the known analysis gap. The submitted test puts account disabling and generation reset after all captured messages have been classified, so it misses the mixed state.

Keep current-generation joins and the read budget, evaluate known capture and analysis evidence before selecting the generic uncertainty fallback, and cover mixed states at the conversation route. One compact status can prefer known capture, then known analysis, then unverified. Neither known status claims anything about an omitted message's relevance.

### Minor

**M1. An answer suffix changes the literal regression expectation saved through feedback.** `sidecar/icarus_memory/server.py:4504`, `:4613`; `sidecar/icarus_memory/rueckmeldung_routes.py:95`, `:107`; `sidecar/icarus_memory/rueckmeldung_faelle.py:42`, `:64`.

The notice is absent from ConversationStore turns and their provider history. The unchanged feedback route separately persists the projected `content` when the user explicitly submits a report. For a report marked wrong or outdated with zero or multiple structured sentences, its export uses the full snapshot as the forbidden answer. A changing intake suffix can make identical underlying answer text miss that existing literal comparison. This is a static call-path finding. The review did not execute the feedback route. Keep the local feedback record and its regression comparison distinct from the transient coverage line, for example by removing the exact typed suffix before deriving the forbidden answer. The unchanged claim-adoption caller instead revalidates structured sentences, and the workflow review builds model input from the user request and correction, so the two downstream checks did not show propagation into claims or model input. `sidecar/icarus_memory/uebernehmen_routes.py:37`, `sidecar/icarus_memory/uebernehmen.py:61`, `sidecar/icarus_memory/workflow_learning.py:138`

**M2. Affected backend test output has an existing dependency warning.** `/private/tmp/kf-intake-coverage-20261105/affected-green.log:4`; `sidecar/tests/test_intake_coverage_recall.py:8`. The shared FastAPI test client emits a Starlette deprecation warning for its HTTPX integration. Existing test infrastructure owns this warning.

## Evidence

- Retained author output showed 176 backend passes, 14 UI passes and a successful typecheck in `affected-green.log`, `ui-final.log` and `ui-typecheck.log` under `/private/tmp/kf-intake-coverage-20261105/`. No broad test command was rerun.
- The only independent execution was the specific I1 doubt. The offline test reused the synthetic fixture and connector guard, then checked both POST and GET for each mixed state. Both cases failed at the specific analysis-disclosure assertion. The source text remained intact and the only selector call was for POST. The test file and output are `/private/tmp/kf-intake-review.qitgay/test_mixed_intake.py:11` and `/private/tmp/kf-intake-review.qitgay/mixed.log:1`.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp \
  /private/tmp/kf-core-20261104-env/bin/python -m pytest \
  -o cache_dir=/private/tmp/kf-intake-review.qitgay/cache \
  -p kf_completion_confirmation_refused_socket -q -s \
  /private/tmp/kf-intake-review.qitgay/test_mixed_intake.py
```

## Assessment

**Task quality: Needs fixes.** The bounded, read-only projection works for isolated states. The mixed-state early return defeats the requirement to disclose known analysis gaps.

**Counts** 0 critical, 1 important, 2 minor.
