# Live processing pause and stale progress — 2026-10-09

Base: `3667e4e18b9e255780c755889370b46368cf0a6d`.
Tested code: `7ef15d30c2686b54a36f1c8ae18e7cf31940aaab`.

An enabled sorting setting previously appeared to be running even while the background controller was globally paused or blocked by power policy. A failed refresh could also leave old completion, retry and duration statements looking current. The memory status now reads the live execution blocker independently of cached model readiness, shows the reason for waiting, labels retained counts as the last known state after a refresh failure, and removes current completion/ETA/retry claims until a successful refresh. Failed follow-up reads after changing automation use the same stale-state handling. Unconfirmed controls stay disabled until the user refreshes successfully.

This does not change scheduling permissions, resume background work, probe a model during coverage polling, or modify original sources. It adds the optional `execution_pause_reason` response field; older servers remain compatible with the frontend.

## Verification

- Affected backend files: **76 passed, 1 skipped** (Linux thread priority on macOS).
- Full UI suite: **439 passed**; TypeScript and Vite build passed. Existing bundle-size warning remains.
- Clean Git archive of the code commit: **4 new HTTP tests and 13 focused component/helper tests passed**, and TypeScript/Vite build passed. Existing node dependencies were shared; no dependencies were downloaded.
- Initial tests reproduced missing live pause information and stale UI claims before the fix.
- Independent read-only review found two additional issues: sorting switched off still suggested that resuming an independent pause would start it, and failed post-toggle refreshes silently left old claims visible. Both were reproduced as failing tests and corrected in one pass, including neutral retry wording. No final independent runtime re-review was performed.

`verification.json` pins outcomes, log hashes and clean build hashes. The compressed logs preserve the failing reproductions and passing checks. `freeze.json` pins the archive; the archive itself is local and is not committed.

## Boundaries

These are isolated HTTP, server-rendered component, helper and controlled event-handler tests. The event-handler test substitutes deterministic hooks and does not validate the React runtime or a rendered DOM. The user explicitly deferred the real Mac window test, including the selected calendars and corrected event display. No browser fallback was used. No full backend suite was repeated. No model inference, cloud request, productive mail/calendar reading or installed Mac app replacement occurred.

This branch is based on main and does not include the separate calendar, RAM or health draft branches. The existing combined Mac preview package has not been changed. This is an incremental status correction, not an Atlas inventory or proof of end-to-end personal memory quality. The broader acceptance gaps remain recorded in `docs/64-cos-abnahme-status-2026-10-09.md`.
