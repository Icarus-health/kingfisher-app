# Optional worker: close the UI and parent-environment boundaries first

This is a synthetic integration package, not personal-app activation. No private sources or real credential were used. The ordinary Kingfisher server, paused import, model roles and native wrapper are unchanged by these files.

## Measured gaps

A peer reaching the ordinary UI can obtain its intentionally local browser session. This works as a positive control with the real `create_app`, a temporary store and an artificial token. A future untrusted worker therefore cannot share the main UI/API network.

Separately, a clean SDK child environment does not prevent a same-UID Linux child from reading its parent's initial environment through `/proc`. The old experiment's artificial service key was recoverable. Removing `process.env` after startup did not remove the initial bytes. No real credential was involved.

## Repair and boundaries

- Worker starts without a service key in its initial environment. A one-time bounded initialization places it in parent memory before any SDK child. The production entry rejects accidental credential environment configuration.
- Three synthetic roles: ordinary UI8890 plus separate broker listener8892; a narrow proxy; and an isolated worker. The proxy joins two internal networks. Main and worker share no network. No host port is published in this proof.
- Proxy worker listener8890 permits only exact scoped capability routes. Controller listener8891 has a distinct credential. Fixed upstreams, body/header/response/thread/time bounds, no redirect/proxy environment/retry, no UI/API/cookie or arbitrary target forwarding. Proxy holds no personal store or master token.
- UI/broker use separate event loops, preserving cancellation and ordinary UI responsiveness during a blocked worker inference.
- Existing UID1000, read-only root, cap-dropALL, no-new-privileges, noexec tmpfs, resource caps, source/skill currentness and verified own-resource cleanup remain required.

## Verification

- One-time initialization and existing service tests:12 passed on macOS,1 Linux-only test skipped there. That exact same-UID parent-environment test subsequently passed inside the actual Linux worker.
- Gateway initial tests:18 passed. Independent review reproduced two additional P2s: trailing request bytes prevented disconnect cancellation; failed timer start leaked handler capacity and the accepted socket. Both regression tests failed before the fix. Both are fixed in the single review wave: trailing bytes cancel a completed single-request connection, all setup stays under cleanup, and admission is8 handlers to fit the deployed32-PID budget.
- Final affected gateway/probe/broker/protocol/worker tests:139 passed plus12 subtests in37.15s, including the28 strict receipt-oracle tests. One pre-existing dependency deprecation warning remains.
- Actual final three-role proof after the fixes:17.9seconds; source search and automatic current skill selection traverse the real SDK/MCP path. Two model replies are explicitly injected, so this is **not** live model-quality evidence. The separate earlier live Qwen proof is documented in `../2026-11-02-harness-isolation/README.md`.
- The ordinary UI cookie positive control succeeds in its own container. Worker direct main IP returnsENETUNREACH; main DNS is refused; proxy root/API/UI attempts return404 without Set-Cookie; unauthenticated controller access returns401. External IP/host model/DNS access remains denied; actual capabilities0 and NNP1 are confirmed.
- Baseline returns the artificial A42 source only. Cancellation and source withdrawal withhold results; ordinary UI replies in about6ms during the deliberately blocked separate broker call. Original bodies remain unchanged. Sampled maximum Mac pressure1. Every owned container and network is removed and absence verified.

## Deliberate unpassed gates

No production server registration, native runtime installer, public module catalog, private-data worker run, paid-provider request or full Chief-of-Staff acceptance is claimed. The next delivery must package/reconcile the optional public runtime and preserve normal backup/update/rollback and native permissions before exposing an action in the existing UI. No automatic import continuation follows from these controls.
