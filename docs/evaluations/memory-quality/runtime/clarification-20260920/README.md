# Source-bound memory clarification

This increment adds conversation continuity to the experimental evidence-answer
path. It does not enable that path in the normal chat UI or deploy the Mac app.

## API

Use the existing authenticated
`POST /api/v1/conversations/{conversation_id}/messages` route with
`{"message":"Welche Adresse hat Alex?","answer_mode":"memory_evidence"}`.
When the returned assistant has `answer_contract.status="clarify"`, send the
selection to the same route and conversation with the same `answer_mode`.
Examples: `"[1]"`, `"Nummer 1"`, or `"den Alex aus dem Einkauf"` when those words
occur in order in exactly one of the displayed reference contexts.
Set `"new_question":true` to abandon the pending selection and retrieve for a
new question. Requests without `answer_mode` retain normal chat behavior.

Only the immediately preceding complete assistant clarification is eligible.
The server obtains it from its existing SQLite conversation, never from a
client-supplied context. Reopening that store does not require in-memory Agent
state. Another conversation, an intervening turn, or a completed selection
cannot reuse the pending options. Error retries preserve the original mode;
retrying an old memory error after another turn returns HTTP 409.

## Selection and provenance boundaries

- Number selection refers to the displayed original record, not a proven person.
- Short literal clues match ordered words of original statements. Articles and
  a small set of connective words are ignored; negations and alternatives are
  conservatively rejected. Unsupported phrases ask again. This is not general
  language understanding, alias resolution, or semantic validation.
- Ambiguous matches across subject/target/scope tuples ask again. Registry labels,
  hidden identifiers and inferred relationships are not selection inputs.
- All previous options must still have the same canonical projection, memory
  revision and transitive source generations before selection and after rendering.
  Expiry, withdrawal or metadata changes invalidate the entire comparison.
- Invalidated and cloud-provider responses contain no pending originals or IDs.
  Valid selection retains only the selected records and their lineage.
- Follow-ups use zero model calls, tools, approvals or knowledge writes. The
  conversation route persists the user/assistant messages as usual. Historical
  transcript retention is unchanged; an invalidation does not delete history.
- Initial retrieval can still be incomplete, and initial unambiguous model
  selection can still fail or time out. This increment does not resolve those
  prior limitations or establish truth of imported observations.

## Verification

`sidecar/tests/test_memory_clarification.py` uses real temporary SQLite evidence,
the actual Agent and the existing FastAPI route. It covers literal and numeric
selection, ambiguous/negative/mixed input, withdrawal of selected and unselected
sources, transitive withdrawal, expiry, metadata changes, render-time changes,
malformed lineage, cloud exclusion, conversation isolation, persisted reopening,
default-chat preservation, explicit new questions, and error retry mode.

All tests use synthetic data; no private application data or inference credits.
The ordinary Mac and Linux suites remain the merge gate alongside code review.

Recorded acceptance, 2026-09-20, implementation `2cb25252ef4bc0685e91f144ac3c496e718185e5`:

- macOS / Python 3.12: `pytest -q sidecar/tests scripts` — **1,946 passed**, four
  calendar subtests passed, two existing dependency deprecation warnings.
- Linux ARM64 / `python:3.10-slim`: all `sidecar/tests` plus the six diagnostic
  script suites listed in `.github/workflows/ci.yml` — **1,923 passed**, same
  two warnings. This locally reproduces the Python test commands, not the
  GitHub-hosted Ubuntu runner or every CI job.
- Focused regression run: **79 passed**. Independent read-only review: no
  actionable blockers; reviewer separately ran all 34 clarification tests.
- Frontend build, legacy JavaScript syntax, asset manifest (14 files / 17 icons),
  self-model JSON Schema and example validation passed. Rust was unchanged and
  was not rerun locally.
- Built runtime image: `kingfisher:clarify-2cb2525`, digest
  `sha256:fb81235385b91eb8f31df7ce88cd704f1e22a3c161dffb2e5d9481f9263f0a2b`.
  Actual authenticated HTTP requests to the installed package passed initial
  clarification, unresolved clue, foreign-conversation exclusion, continuation
  after a full container process restart, single-use selection, and invalidation
  after withdrawing the unselected source. The acceptance launcher injected a
  local provider that rejects every inference call; no model or tool was used.
  The synthetic acceptance container was stopped afterward; its data was kept.

GitHub-hosted execution is not claimed: the account's exhausted Actions budget
is why the user requested local verification. Existing Mac installation and
private data were not changed by this increment.
