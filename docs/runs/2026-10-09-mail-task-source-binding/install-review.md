# Read-only Review: schema-20 image-only update

## Result

No concrete data-loss blocker found in the prepared control flow. Review scope was static only; the installer was not run.

- `install.py` pins new image `c6bc20a…` and requires the running prior image `72837…`. It calls the inherited `prepare()` for package/image/config/storage/signature checks, stops only the named Kingfisher container, and never invokes the schema-19 migration preflight. The preflight is only hash-checked as an inherited prerequisite. The new path requires the baseline episode schema to be exactly 20 and reports `migration_performed=false`.
- It copies `/data` to a unique pre-existing-missing backup destination before opening SQLite. A read-only tree helper compares every copied entry against the original volume, including WAL/SHM/journal bytes; it seals a private file manifest and makes a second working copy. Read-only SQLite proofs compare all logical rows, original body digests, all 17 DB names, settings, pause state, and schema 20 before publication. The sealed raw copy is checked again afterward.
- The update stages the env file with mode 0600, fsyncs it, and atomically replaces the old env. Compose uses the exact verified app compose file with `--pull never` and `--no-build`. Failures after env/image publication become `forward_repair_required`; there is no historical image/data rollback path.
- After health/version checks and confirmation of the same named volume/image, it rechecks originals, settings, pause state and database set. `self.bundle()` runs after health and invokes the hash-pinned native storage probe; it does not run while the service is stopped. The result accurately leaves `native_ui_verified=false`: the probe is storage verification, not a UI/browser session.

## Verification boundary

The post-publish proof calls `preserved(..., all_rows=False)`. Full logical-row equality is proved repeatedly before publication, including against the copied data; after normal startup only original bodies/digests, settings, pause state, schema and database set are compared. Thus startup-time changes to non-original rows would not be detected by the final proof. This is a bounded verification limitation rather than evidence of a destructive path in this image-only update; the pre-publish raw byte-for-byte archive remains the recovery copy.

The backup app directory is copied before stop and the source bundle is hash/signature-checked before and after the stop. The copy itself is not independently re-hashed in this script; `copytree` errors abort before stop. No concrete loss path was established from that boundary.

## Files reviewed

- Installer: SHA-256 `c2bd0e5404b60c1359d1134199cb47b239d30e1ebd83e4ce147e73da23657ef3`
- `proof.py`: `60255487ccb49804d66867e4b9e864f8758cf1ae89431f6674b58393be2286fb`
- `tree.py`: `71e767c970f84596dadce06cb7d4b235a2a92dcc2545a698f4a70e0e0e5bfa21`
- Reused frozen orchestrator: `019197e4203f6ee83d5b8d8e5dc9a8741f7340eac38f51a90b72cdfb3b49b50d`
- Reused data proof: `1316a92cf90edb21c89c59a1ea31a3f6b57f3437cff6994c62ab00ac5a56ce71`

No Docker, network, live data, model, or installer action was used.
