# Isolated Harness wiring proof — 2026-11-02

This is a disposable **artificial-data proof**, not personal activation or a delivered Mac module. It reuses the existing immutable software image `sha256:6624c90d391bf226a4e0541df7ed96d08a3785ca0681da6b9330ab16dc1f45a0`, with a read-only public-code/runtime mount, to avoid duplicating another large image in the nearly full Colima drive. No personal volume, application token, cloud key, host Docker socket or worker host port was supplied.

The worker joins only its dedicated internal network; the separate artificial gateway owns model/source/skill authorization. Docker documents internal networks as externally isolated; private user-defined networks also separate unrelated stacks. We additionally disabled external DNS forwarding and measured the actual behavior rather than relying only on configuration. [Docker networks](https://docs.docker.com/reference/compose-file/networks/#internal), [bridge isolation](https://docs.docker.com/engine/network/drivers/bridge/#differences-between-user-defined-bridges-and-the-default-bridge).

Observed worker controls: UID `1000:1000`, read-only root, dropped `ALL` capabilities, `NoNewPrivs=1`, effective capabilities zero, 512 MiB memory, 0.75 CPU, 64 processes, only internal networking, custom loopback DNS, and bounded non-executable/non-setuid temporary filesystems. `/data` is a separate inaccessible empty tmpfs. The only host mount contains public code, the locked SDK and the verified Linux Node binary, read-only.

Negative probes returned `ENETUNREACH` for both an external IP and direct host Ollama, `ESERVFAIL` for external DNS, `EROFS` for root writes, and `EACCES` for the data directory. The authorized gateway returned HTTP 200, showing that the worker was not merely disconnected from everything.

The same scoped source/skill flow then completed using real local Qwen9B/8K: two model calls, one real scoped source search, automatic confirmed-skill selection, correct source ID and unchanged originals. The ungranted conflicting source was excluded. Final post-review elapsed time: **27.234 seconds**; observed Mac pressure peaked at **2**, below the configured abort condition (`>2`). No other application was closed. The actual answer was inspected: “Die Zugangskarte liegt in Fach A42.” with its correct source ID. Automated token/source-presence checks alone remain a smoke oracle.

All newly created containers/networks were removed and their absence verified before the passing receipt was emitted. The personal Kingfisher app, its source data, settings and paused import were unchanged. No paid call occurred.

## Reviewed repairs

A fresh independent review reproduced three P2 defects. Red/green tests now require failed or mismatched cleanup to fail the proof; attest actual tmpfs rights and limits; and clean child-created read-only directories without following symlinks. Unrecoverable job cleanup now quarantines the service instead of crashing or accepting another job. Final tests: **9 Node service tests and 91 focused Python tests passed**.

The Linux SDK originally failed because the Mac install lacked a Linux native binding. Its exact locked dependencies were installed for Linux/ARM with scripts disabled. A second failure was traced to its native loader copying a library into the correctly non-executable temporary folder. The pinned loader's `NARB_DISABLE_NATIVE_CACHE=1` setting loads the locked binary directly from the read-only runtime. Temporary execution permissions were not relaxed.

Runtime pins: SDK `0.2.2-alpha.2`; package-lock SHA-256 `b9c37928b69fc90ea9e8d1f76dabe0696f14c000e36ec54d814e278709ded294`; official Node `24.22.2` Linux/ARM archive SHA-256 `eb187837a2230d4047161ac0be008584e16b46f726e9c9490ee35dc6b17d9ba8`. Normal production packaging, authenticated user entry, source-dependent result display and native Mac acceptance remain the next delivery. The bulk import remains paused; Mistral has not been activated.
