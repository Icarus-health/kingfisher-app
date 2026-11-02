# Scoped Harness bridge — Implementation Plan

> Use superpowers:executing-plans. The accepted modular CoS spec remains the authority. Native implementation, one independent whole-package review and one final fix pass.

**Goal:** Turn the successful artificial SDK protocol spike into a reusable, bounded read-only Kingfisher bridge. No production activation while process isolation is unverified.

**Spec:** `docs/superpowers/specs/2026-11-02-modular-chief-of-staff-design.md`, phases B/C.

## Constraints and measured decisions

- Reuse EpisodeStore support snapshots and ProcedureStore selection; never add a competing memory or copy skills into per-person execution code.
- Controller issues random, short-lived, in-memory capability grants. Worker never receives the application master token, credentials, store paths or general shell/filesystem tools.
- First bridge supports at most 20 controller-selected sources, literal discovery, excerpts of discovered sources and a fixed skill selection based on the original user request. It does not claim complete semantic retrieval or expose a full personal corpus.
- Every operation rechecks all scoped original fingerprints and the selected skill signature/conflicts. Model results are rechecked after inference. Revocation/expiry/cancellation closes the grant; bounded quotas fail closed.
- Existing 8K provider owns inference admission and output validation. Normalize only text arrays and null assistant content accompanying actual tool calls, without truncation or remote fallback.
- Official SDK 0.2.2-alpha.2; clean child environment; no default shell/file tools, telemetry/log uploads, general MCP resources or retries. SDK resource-helper discovery is explicitly handled with empty resource lists and denied reads.
- This package remains opt-in and is exercised on a standalone synthetic test app, not registered on the personal server. A subprocess is not proof of OS isolation. Production activation needs a separately verified worker isolation/packaging delivery.
- No paid requests, personal source reads, bulk-import resume, global tool-door change or permanent model-role change.

## Task 1: Capability and freshness core

Create `harness_broker.py` and tests. Red/green expiry, cancellation, strict tools/arguments, scoped discovery, undiscovered excerpt denial, source correction/withdrawal, skill revocation/new conflicts, quotas, concurrency and bounded grant retention. All outputs read-only and source-labelled; task proposals remain outside this bridge.

## Task 2: Protocol adapters

Create text-only SDK normalizer and standalone FastAPI route registration. Authenticate grants on both MCP and model routes; strict bounded JSON messages and known tools, no arbitrary model/endpoints. Controller admission is dependency-injected, never inferred from worker input. Test missing/invalid tokens, malformed JSON, deny unsupported methods/resources, content preservation and cancellation/source changes during inference.

## Task 3: Pinned SDK worker and live synthetic evidence

Create a worker script and restricted profile builder using the measured SDK seam. Launch only a fixed installed Node/runtime supplied by the trusted controller; receive transient configuration over stdin; clean environment/fresh home; bounded termination and no credential logs. Add a synthetic probe using actual EpisodeStore/ProcedureStore, with unchanged sources and clear limitations. No claim that the third-party process is production isolated.

## Task 4: Independent verification

One fresh public-code review, reproduce/fix important defects with focused tests, run affected regressions and an actual local Qwen→bridge→real synthetic source→answer. Record commit, calls, timing, cancellation and remaining unpassed production gates. Preserve the intake category failure and paused import.
