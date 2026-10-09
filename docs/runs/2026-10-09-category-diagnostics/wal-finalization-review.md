# Bounded review: offline WAL finalizer and v2 hook

Reviewed only the WAL helper, its data proof/tests, and the v2 installer hook/tests in `/private/tmp/kingfisher-category-wal-finalization-20261009/` and `/private/tmp/kingfisher-category-install-wal-20261009/`. I did not execute the helper or tests. The writer's final logs report 24 helper tests and 38 combined v2 installer tests passing. The parent supplied a separate network-free exact-image Linux smoke at `/private/tmp/kingfisher-category-wal-linux-smoke-20261009.log`; it reports success on SQLite 3.46.1 with 17 databases.

## Result

No blocking issue found in the final bounded contract. The initial Linux smoke exposed a real defect: the read-only logical inventory created new zero-length WAL and 32 KiB SHM pairs on previously sidecar-free databases already in WAL mode. The final helper permits only these newly created pairs after checking the database header's WAL-mode bytes, requires the pair shape exactly, retains byte equality for database files, pre-existing WAL files, and auxiliary files, and checkpoints all paired WALs through SQLite. Non-empty newly appearing WAL files still fail closed. The supplied Linux smoke now passes: the committed original remains present, schema stays at 19, all 17 databases finalize, and SQLite removes the sidecars.

The regression set includes an actual schema-19 `EpisodeStore` record whose row is absent from a main-file-only immutable read, an active writer, zero-length WAL, all-17 persistent-WAL headers, and a newly appearing non-empty WAL control. The v2 hook makes a raw stopped copy and seals it before any SQLite logical read; then it runs the checkpoint-only helper inside the host watcher, proves a clean schema-19 store, and only then continues to the frozen preflight migration. The no-WAL path remains unchanged.

## Deployment contract

The standalone `finalize` CLI passes static `--service-stopped`, `--unpublished`, and `--exclusive-writer` attestations. For the v2 path, the host-side `guarded_run` checks the native process, LaunchAgent, Compose process, port, and allowed writable-volume set every 250 ms and immediately before and after the one-shot. On a lost check it waits for the checkpoint helper to finish, then refuses publication and leaves manual review. That is sufficient for this checkpoint-only stage; no helper callback/RPC framework is needed. The remaining limit is the acknowledged non-atomic interval between observations.

## Final hashes

- WAL helper: `a1cfd9ce698420f63dc9dd0f2a6111a80d960e81285613367341c79189a8d20b`
- `data_proof.py`: `1316a92cf90edb21c89c59a1ea31a3f6b57f3437cff6994c62ab00ac5a56ce71`
- WAL helper tests: `2027e273457edb620b5b1e399ed6ea0e890bdec165711ba85d52bec71fc4beec`
- v2 orchestrator: `035a6e8ec7fd8f24cf12628dbd614e97ff159072685894b11b425058d99f35af`
- v2 orchestrator tests: `53f47eacf8d426a94ec5843ccfeb968876039c31a343ccf35dc9e666379633a9`
- v2 WAL hook tests: `a288a0ec873a5dd6e5d0b2c3eb89985a2a715ee9a21a2a456a86e01304746b17`
- Prior v1 orchestrator remains frozen at `ea2924c30be4526de0308b524ea249131181399099719d73d0ccf1e524a0b73f`.

No product files or live data were changed in this review.
