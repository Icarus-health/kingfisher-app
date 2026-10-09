# Kingfisher single-snapshot relocation review

Scope: static review of the prepared helper and supplied synthetic tests only. No Docker commands, live-container scans, host archive reads, or real apply were run.

Helper SHA-256: `145e7e32c02ebc889dd1f9e83f341c520dd53dca3395617ef294eee755865827`
Test SHA-256: `5df079caf9b33d27bca2069e13b8aa2e9472a18e711f040616f1859a774e406a`
Synthetic result: 7 tests passed.

The helper is tightly scoped to the fixed leaf `vor-update-20261009T022544Z`; it rejects symlinks and special entries, compares the leaf's relative paths, sizes, and regular-file SHA-256 values, checks a plan SHA and resolved live-root path, and keeps sibling snapshots outside the deletion traversal. The supplied tests cover matching copies, byte mismatch, pre-removal change, symlinks, special files, plan/root/target binding, and a symlink root.

Review limits to carry into the caller's apply decision:

- **Concurrent mutation remains a narrow TOCTOU risk.** In `relocate_snapshot.py` lines 112–125, a file is hashed from an open descriptor, but the later checks compare inode/device only; they do not re-check content or size/mtime/ctime after hashing and immediately before unlink. A same-inode write after the hash can therefore be unlinked. The leaf should be known quiescent for the apply window; the synthetic boundary-change test changes data before `remove_exact` starts and does not cover this window.
- **An error can leave a partially removed leaf.** `_remove_contents` unlinks each entry as it walks (lines 86–125). If a later entry changes, permissions fail, or `rmdir` finds a concurrent addition, earlier entries are already gone. The retained host copy is the recovery source; the helper has no rollback. This is bounded to the target leaf, but the caller should treat any apply error as requiring a fresh full manifest comparison before retry.
- **The manifest proves byte content and path shape, not full filesystem fidelity.** It excludes mode bits, ownership, timestamps, ACLs, extended attributes, sparse layout, and hard-link topology. It is adequate only if the preservation criterion is the requested regular-file byte-manifest equality and retained host tree, not restoration of those metadata properties.

No helper/test defect was found that redirects deletion to another leaf under the reviewed fixed-root, non-hostile local filesystem assumptions. The review does not establish that the real Docker scan matches the host copy, that the supplied live root is the intended container mount, or that the host copy remains unchanged; those remain caller-side gates.

## Bounded caller review (2026-10-09)

Reviewed `/private/tmp/kingfisher-last-snapshot-relocation-20261009/execute_verified.py` plus the pinned installer/data-proof helpers by file inspection only. Caller SHA-256: `eee8373df3aecc07c48c4266c4fbfdfceb8155a0a969513a46254660d8379ead`. No Docker, host archive, or live container operation was run. All 7 supplied synthetic relocation tests pass; Python AST parsing passed for the caller and frozen helper files.

**Blocking sequence mismatch:** before stopping the service and taking the cold `/data` copy, the caller invokes `task.sys.health(token, version=...)` (line 30). The frozen health check calls `/api/v1/world` and `/api/v1/mail/intake` (`orchestrator.py` lines 127–147), so this performs application data reads before the promised cold raw copy. If “cold RAW full/datahostcopy before SQL (no SQL at all)” is strict, remove/defer this API health probe until after the cold copy; the caller already checks running state, image ID, volume mount, and host port separately before stopping.

**Audit-state issue after successful deletion:** `result['active_data_changed']` is initialized to `False` and never updated (caller line 23). Once `outcome` confirms `one_verified_duplicate_removed` (line 52), the active file tree has intentionally changed. Any later quiet/tree/host proof failure enters the exception path but can still write `active_data_changed: false`, which is inaccurate. Set it true immediately after confirmed removal (or use a more precise field such as `target_snapshot_removed`).

**Restart failure status issue:** after `docker start` returns, the caller sets `stopped=False` before health and native storage checks (lines 60–63). If either check fails, the exception status becomes `prepare_failed`, although the snapshot was removed and the service has been restarted into an unverified state. Preserve a distinct post-apply/post-start review state through those checks; do not report this as preparation failure.

The expected-tree filter is correct for the pinned `data_proof.tree_manifest` rows `[relative_path, kind, ...]`: filtering `e[0]` against `sicherungen/<TARGET>` and its slash-delimited descendants removes exactly that subtree. The cold-copy equality compares the whole `/data` tree manifest before any SQLite proof, and both the host snapshot and new cold-copy snapshot are compared against the same fixed-leaf manifest. The one-shot writable probe uses the plan file staged under `/tmp`, with network disabled and the exact volume mounted writable, and checks quiet state during execution. Remaining caller-side limits: the maintenance/process/port/volume-writer checks are observations rather than a lock against a new writer arriving between checks; and a same-inode write in the helper's hash-to-unlink interval remains the prior noted TOCTOU limitation. Treat these as requiring the authorized exclusive maintenance window and a quiescent snapshot.

## Corrected caller rereview (2026-10-09)

Reread the corrected caller and fake-system control-flow tests. Caller SHA-256: `74d384db769f17a8005f476c978146c49a6e5c132080bdc611c14707fca4c711`; caller-test SHA-256: `7ae037ffcb555490584e6c05d6174c620571e6d3d21392d87e62e2be9210d8f`. All 10 synthetic tests pass (7 helper + 3 caller); Python AST parsing passes. No Docker, host archive, or live-container operation was run.

The prior caller findings are corrected: no API health call occurs before the stopped-container `/data` copy and full tree comparison; the pause flag is checked from the copied `hintergrund.json`; `active_data_changed` remains `null` until the exhaustive expected-difference comparison succeeds, then is set false; `archive_mutation_attempted` is set before the writable apply; and failures after a successful start are reported as `post_archive_runtime_verification_failed`. The caller tests cover successful ordering/resume, post-restart health failure reporting, and unexpected active-tree difference without restart. No new blocking caller-flow issue found. Earlier helper TOCTOU and partial-removal caveats still apply; the caller still depends on the operator's exclusive maintenance window because process/port/volume checks do not create an OS-level lock.

## V2 dependency fix rereview and V1 stop context (2026-10-09)

Narrow V2 diff reviewed. V2 SHA-256: `3d65d0260573d9c400e181d58992a15d68bba1fb70f6d54e923ec6d1e1e2f10b`; V2 test SHA-256: `54fcbf47ec691f72dada3e6573febbdeda673c82f70e57bf10ce8eb172d8ac29`. Changes are limited to a unique `...vor-archivverlagerung-geprueft` backup path and passing `data_proof.py` alongside `tree.py` to the read-only one-shot probe. The updated fake task asserts this dependency. All 10 synthetic tests pass and AST parsing passes; no Docker or live data was touched.

The retained V1 execution record (`execution.log`) says `stopped_review_required`, `archive_mutation_attempted: false`, error `invalid_json_result`, so V1 stopped before apply. The retained resume record (`resume-result.json`) says `unchanged_old_image_resumed`, `cold_copy_all_bytes_equal: true`, `archive_not_removed: true`, with the original image ID and health/background-pause checks reported successful. This note records the supplied artifacts; it is not a new live verification. The V2 backup path is distinct, and the caller still checks that its configured backup path does not exist before creating it. No new issue found in this narrow diff.
