# Keep optional workers outside the main UI trust boundary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Close two measured integration gaps before connecting the experimental worker to personal data.

**Architecture:** A worker-only internal network reaches a narrow proxy, never the ordinary UI/API. The proxy bridges to a separate controller network using fixed read-only capability routes. Worker service credentials enter parent memory after startup, never the initial process environment accessible to a same-UID SDK child.

**Tech Stack:** Existing Node HTTP service/tests, Python stdlib proxy/tests, Docker isolation probe and existing canonical FastAPI capability broker.

**Spec:** docs/superpowers/specs/2026-11-02-modular-chief-of-staff-design.md, C/E; docs/superpowers/plans/2026-11-02-harness-process-isolation.md.

## Measured reasons

With entirely artificial data, a peer that can reach the ordinary main UI obtains its intentionally local browser session and can then read an unscoped note. A future worker must therefore not share that network. The current experimental service also starts with a service key in its environment: despite a clean child environment, a same-UID child reads the parent's initial environment through `/proc`. Deleting `process.env` after startup does not remove those initial bytes. No personal integration has been enabled and no real credential was tested or disclosed.

## Fixed constraints

- No personal stores, tokens, native changes, paid calls, import or main-app registration in this package.
- Keep all capability/currentness/tool/model-call/timeout/output limits. No root or capability increase; keep read-only root, tmpfs noexec, resource limits and verified own-resource cleanup.
- Worker entry starts without a service credential in its initial environment. It accepts one bounded controller initialization before any SDK child/job. Subsequent initialization conflicts; uninitialized `/run` fails; status exposes no credential. The same key is never passed to an SDK child.
- Controller initialization is safe only within the proven network: before initialization there is no untrusted SDK child and the only other network member is the trusted proxy. No host port or ordinary main peer is reachable.
- Worker-facing proxy port8890 permits only exact `POST /worker/mcp`, `POST /worker/v1/chat/completions` and fixed local health. No UI, ordinary API, cookies, redirects, arbitrary upstream or request-driven host/path/model/config.
- Separate proxy controller port8891 requires a different controller credential for fixed initialization/run/health operations. Worker-side knowledge of a source grant is never a controller credential.
- Proxy holds no personal store or master application token; forward only the scoped bearer grant on fixed capability routes. Strip cookie and upstream Set-Cookie, use bounded bodies/responses/headers/concurrency/timeouts, no proxy environment or retries.
- Proxy upstreams fixed: controller=`http://kingfisher-controller:8892`; worker=`http://kingfisher-worker:3001`. The worker-only broker has a separate listener/event loop; synchronous local inference must not block ordinary UI/API8890 or its cancellation handler. Test-only dependency injection is local constructor configuration, never an HTTP request parameter.

### Task1 — One-time in-memory service initialization

Files: scripts/harness_service.mjs, scripts/test_harness_service.mjs.

- [x] Write RED for uninitialized run, bounded exact initialization, repeat/conflicting initialization, no leaked key in health/errors and same-UID child initial-environment check.
- [x] Implement initialization and entry without credential environment. Preserve current constructor injection for isolated unit tests; reject accidental initial service-key environment at production entry.
- [x] Run Node service tests; keep old busy/cancel/output/cleanup/quarantine guarantees.

### Task2 — Narrow two-sided proxy

Files: scripts/harness_gateway.py, scripts/test_harness_gateway.py.

- [x] Write RED for root/UI/API denial, cookie stripping, exact path/method/body/header constraints, controller credential separation, fixed upstreams/no redirect, response bounds, service busy/error/timeout and bounded handlers.
- [x] Implement Python stdlib fixed-route proxy without private stores or child execution. No global application wiring.
- [x] Run tests and inspect fail-closed paths.

### Task3 — Actual synthetic network readback

Files: new scripts/probe_harness_production_boundary.py and tests; existing synthetic probe updated for service initialization if needed.

- [x] Use three synthetic roles (main with ordinary UI, narrow proxy, worker). Main is absent from worker network. Separate controller and worker-only internal networks; only artificial main may have inference access for an optional local semantic proof.
- [x] Verify actual config, worker cannot obtain main UI cookie or access direct main/control network/host/external DNS/IP; proxy UI/API requests never expose Set-Cookie. Verify child has no initial parent key; controller can initialize/run once; originals/skill sources unchanged, currentness/cancellation still hold and own resources are removed.
- [x] Independent review and one reproduction/fix wave; record measured gates without claiming production activation. Native packaging remains the next bounded delivery, preserving existing update/backup/TCC behavior and host storage reserve.
