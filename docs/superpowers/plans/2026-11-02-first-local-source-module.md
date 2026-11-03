# First local source module — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. User already authorized implementation and independent agents; do not request repeated design approval.

**Goal:** One explicit local source-reading action in the existing Kingfisher source view, using the isolated Harness and current confirmed skills, with original evidence and an honest draft result.

**Architecture:** Keep the canonical stores and ordinary conversation pipeline. Reuse the scoped Broker/Protocol, the reviewed threaded controller and the three-role OS boundary. Enable a fixed controlled mode only after managed native setup verifies its runtime and isolation; missing setup leaves the normal app usable. There is no cloud fallback or write capability.

**Tech Stack:** Existing Python/FastAPI, fixed Node/SDK runtime, native Swift/Docker lifecycle and React source pane.

**Spec:** `docs/superpowers/specs/2026-11-02-modular-chief-of-staff-design.md`, Phase C/E. Public implementation evidence: `docs/runs/2026-11-02-worker-production-boundaries/README.md`, `docs/runs/2026-11-02-native-main-service/README.md`; reviewed controller scratch handoff `/private/tmp/kf-first-local-module-controller-20261102/HANDOFF.md`.

## Global constraints

- Exactly one explicitly selected current original in this first action; no direct database, filesystem, shell, master application token or inherited cloud credentials in the worker.
- Fixed local `kingfisher-qwen3.5:9b-8k`; no model chosen by the request or cloud fallback. Reuse the actual application's local-provider verification and shared capacity gate. At most one physical inference at once, including cancellation cleanup.
- Existing limits: 120 seconds, 8 tool calls, 3 model calls, 40 protocol requests. Metadata/status/prepare do not start inference.
- Results remain unverified drafts. Evidence is actual exact Broker receipts. Changed/withdrawn sources, skills, local provider or runtime pairing withhold old text, including later polls. Never write proposed interpretations into canonical memory automatically.
- Keep local roles, originals, confirmed choices, paused bulk import and the explicit Mistral budget unchanged.
- Preserve the original synthetic mode and its truthful flags. A new controlled mode and pairing identity require explicit managed setup and renewed OS proof; relabelling the existing synthetic worker is insufficient.
- Native startup/update/backup/restore must revoke and quiesce module work first. A cancelling thread is not stopped computation. Failure or rollback leaves modules unavailable until a compatible separately verified reconciliation.

## Review focus

- Generic questions must reach the explicitly selected original even when their words do not occur literally; no widening to other originals.
- Cancellation cannot release admission while transport or inference callbacks still occupy compute.
- Late source/skill/provider changes and runtime replacement must remove even previously completed results.
- A restarted controller cannot adopt an old worker/pairing or replay an old grant automatically.
- Runtime setup must not execute third-party package lifecycle scripts on the host or pass private settings into a worker.

### Task 1 — Selected-original discovery

**Files:** `sidecar/icarus_memory/harness_broker.py`, `harness_protocol.py`; respective existing tests.

- [x] RED: generic question has no literal hit; selected-original read must return only the single authorized original's bounded exact first excerpt and metadata. Multi-source grant, extra arguments, hidden/changed source and the ninth tool call refuse. Existing literal search/excerpt behavior remains.
- [x] Add `selected_original` with exact empty arguments; require exactly one grant source, return metadata plus at most 400 original characters, mark only that original discovered for existing bounded excerpt reads. Include source length/partial-coverage metadata; empty originals must not manufacture evidence. Preserve the same quota and pre/post freshness checks.
- [x] Add the exact MCP schema and function alias; run Broker/Protocol and gateway oracle suites. Independent review before activation.

### Task 2 — Reviewed controller and application boundary

**Files:** new `local_module_controller.py`, `local_module_gateway.py`, tests; new `local_module_routes.py`; narrow registration/lifespan in `server.py`.

- [x] Replay the four reviewed scratch files after checking their hashes. Retain explicit review binding/source fingerprint/consent/idempotency, bounded in-memory jobs, exact evidence and single-flight through detached inference cleanup.
- [x] Connect the existing source/procedure stores and real source dependency resolver. Authenticate with the normal app guard. Expose status, prepare, start, poll and cancel before the UI catch-all; block restore/inspection/update states.
- [x] Pin verified local provider identity and use the existing shared model gate nonblockingly for every inference. Reject overlapping calls without starting another model; no unbounded waiting queue.
- [x] Tests: no model on opening/status, stale view, repeated/different confirmation, cancelled transport with live inference, changed runtime and provider, no secret in output, no canonical writes.

### Task 3 — Explicit controlled runtime and isolation

**Files:** fixed scripts `harness_run.mjs`, `harness_service.mjs`, `harness_gateway.py`, their tests and OS probes; managed public runtime manifest/setup helpers.

- [x] Preserve synthetic contracts; add only fixed `controlled-local-readonly-v1` mode with fixed local model and paired opaque runtime generation. Worker cannot select mode, endpoint, command or credentials.
- [x] Managed runtime uses exact pinned public packages/lock and verified Node binaries; no host execution of dependency lifecycle scripts. Public cache only, read-only worker mount, no private volume or master keys.
- [x] Retain three-role isolation, direct-main/UI-bootstrap denial, outbound denial, nonroot/no capabilities/read-only/noexec/resource bounds. Prove current code in real Linux containers and separately with actual Qwen; label injected replies distinctly.
- [x] Review all mode/pairing/restart/cancellation paths before enabling in the app. Unsupported or unavailable runtime remains disabled.

### Task 4 — Source-side action and native lifecycle

**Files:** compact source work component/API definitions, `ProfileSource.tsx`, optional settings card, fixed native setup bridge/lifecycle, packaging/Compose contracts.

- [x] Expose one optional action beside an open original. Show the question, selected source, local model, waiting/cancel state, draft and actual evidence. Keep source navigation and previous selection. No work on merely opening the pane.
- [x] Native setup/reconcile is a fixed operation with progress/cancel and verified public paths; no arbitrary command/path/URL. Normal app startup and offline rollback work while modules are absent.
- [x] Revoke/stop/wait before backup/update/restore; prevent new admissions throughout. Do not replace native identity or assume TCC continuity from bundle ID alone.
- [ ] Rendered synthetic tests at 900/1280px, keyboard/focus/errors/draft retention, independent review, relevant backend/native regression and actual normal update/readback. Native window/permissions and actual mixed quality gate remain explicit acceptance tasks.
