# Read-only Installer review: schema-free paragraph package e8cfc26

## Scope and conclusion

Static review only; neither installer nor verifier was executed, and no Docker/live data was accessed. Package `e8cfc26` is based on `ce39f71`; its Dockerfile copies only `satzantwort.py`, `satzpruefung.py`, and the version marker. Comparing the package files with commit `e8cfc26` confirms their hashes match. The commit diff against its parent changes only `satzantwort.py`; the copied `satzpruefung.py` is identical to the parent. No schema or migration is present.

The install procedure is appropriately conservative for this schema-free patch: it prepares an app copy, backs up the app/environment/container inspection, cold-stops the one app container before copying `/data`, validates SQLite and episode body digests before switching, and keeps the original data volume mounted throughout. It does not remove/replace source rows or restore a stale data snapshot during rollback. The expected install environment currently already has `KINGFISHER_DURABLE_MEMORY_SEARCH=1`; the script writes the same value, and the installed Compose file contains only the `kingfisher` service (no Ollama service). Provider/model endpoint settings remain unchanged in the environment; the script compares the persisted provider/model/calendar/mail/schedule setting groups and confirms the background pause remains on.

I found no static data-loss or schema-rollback blocker for this exact package and state. The script is an update helper, not proof of success: the native UI is explicitly not verified.

## Safeguards verified in source

- It refuses a pre-existing backup or prepared-app path and checks the expected native binary hash plus the native real probe before changing app/config files.
- It retains a mode-`0700` dated backup directory; copies the app, environment (mode `0600`), container inspect output (mode `0600`), and then the stopped container's `/data` tree.
- Before switch, `root_data_check` runs `PRAGMA quick_check` for SQLite files directly under `/data` and recomputes each episode body digest from `episodes.sqlite3`.
- It preserves the original app bundle and a separate copy of the app as exchanged. On an exception after the swap it moves the candidate app aside, copies the original app back, restores the exact previous env bytes and mode, and brings Compose back up using the original app/config. It does not roll back `/data`.
- Post-start it verifies health, version, world, memory coverage, intake pause, image ID, the same named `/data` volume, episode IDs/digests, SQLite quick checks, selected user settings, pause state, native binary hash, and code signature. It has a 45-second bounded health wait.
- The separate verifier checks the installer-produced version report; runs the package's embedded Python/UI file-hash checker inside the app container; independently recomputes original episode body digests and SQLite checks; and rechecks native binary hash and signature. Its final report contains counts/status, not episode IDs or bodies.
- The package smoke file is synthetic and states `network: none`, `private_sources_used: false`, and `real_model_test: false`; its checks exercise literal paragraph behavior and ordinary-fact controls, not a live model or user content.

## Cautions before execution

1. The `except` block attempts app/config rollback but does not perform a second `/health` and `/fassung` check after restoring the old app. If installation raises after the swap, treat rollback as attempted, then independently verify the old version is serving before declaring recovery. The shared volume is deliberately left in place, which avoids losing accepted writes during this window.
2. Several guardrails use Python `assert`. Run with ordinary Python (not `python -O`), which preserves those checks.
3. Pre-swap failures can leave the dated backup or `Kingfisher-neu-<revision>.app` in place; the script then refuses a blind rerun. That is safe against overwrite but requires inspecting/archiving the partial preparation before retrying.
4. The health loop exposes the candidate through the existing loopback port before all assertions finish. Background ingestion is required to remain paused; if a user submits data during that short window and rollback occurs, it remains in the same schema-compatible volume rather than being discarded. Do not restore the cold snapshot over the live volume.
5. The app-bundle Compose file is copied from the repository and then asserted byte-equal to the currently installed Compose file before code-sign verification. This makes the update reject an unexpected Compose change rather than silently replacing runtime wiring.

## Boundaries

This review does not prove the Docker image is available on the Mac, the native window works, a real model answers correctly, or the update has run. It does not authorize the separate category-diagnostics package/schema-20 update. The package and scripts must be used only for the stated schema-free paragraph release.

Root addendum: before execution, the helper and fresh verifier also compare the exact set of root SQLite filenames against the cold backup. No store can disappear while an equal count from other files passes. Both helper scripts compile; neither has run yet. The native read-only reserve probe returns before=ok and after=ok at the current small-update state. Approx.687MiB free is not a large-import capacity acceptance.
