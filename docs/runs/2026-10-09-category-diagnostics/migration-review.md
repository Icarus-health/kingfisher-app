# Independent review: synthetic offline category schema-20 preflight

Reviewed the isolated preflight and test contract only. No product files, live data, Docker, or services were accessed; I did not run the preflight or tests. Review snapshot hashes:

- `preflight.py`: `19bc7ff195e760f277fcad4e80dd64f4dddc5ec36221243e613d1917194c54c8`
- `test_preflight.py`: `882d1ac77a10e391bb5b89b70778f8191c49890dcc70ceede0f3b49443959030`
- Writer's `GREEN.log`: `56f7d1dbcd79541c3215cf8163c82b9d24ab7f6b31acbd6e3224aa0d0cf8e766` (`22 passed`)

## Assessment

The test design now exercises the narrow v19→v20 contract with meaningful before/after comparisons. It creates a real synthetic schema-19 `EpisodeStore`, uses the actual `EpisodeStore` migration to 20, and checks unchanged episode IDs, stored digests, bodies, documents, category rows (new field null), mail-intake rows, settings/key-file hashes, current schema, no outstanding migrations, and no inspection marker. A stale body/digest pair is rejected before snapshot; the accompanying RED showed it otherwise would have been accepted. Failure tests verify that an invalid/incomplete snapshot prevents migration, a postcheck failure restores only a verified v19 snapshot and enters inspection mode, and a corrupt recovery snapshot does not claim successful restore or allow publish.

The previously uncovered operational 17th database now has a targeted synthetic control: `recovery-status.sqlite3` remains byte-identical through both migration and restore while staying out of the product snapshot manifest. A separately checksummed but incomplete manifest is refused. Existing snapshot collision retention, unknown active database, symlink, WAL/journal, prior inspection marker, and schema precondition tests cover the relevant failure boundaries. Logging-context suppression and restoration are tested, as are one `EpisodeStore` open, no socket connection, and no background thread.

Within that bounded contract, I found no remaining blocker in the current reviewed snapshot. The RED/GREEN sequence is evidence for specific integration risks, not merely fixture expansion: operational state exclusion, stale original digest, incomplete-but-validly-checksummed snapshots, raw dependency log context, and preflight flags outside the exception boundary all received explicit controls.

## Required boundary for the eventual installer

The preflight itself is not the release orchestrator. `service_stopped` and `unpublished` are attestations, not process detection; the caller must actually stop every writer and keep the candidate unpublished for the whole run. It must create and verify the separate cold copy of all 17 databases and root artifacts before invoking preflight, and reserve sufficient free space for that cold copy, the allowlisted product snapshot, restore staging, and displaced database files. The preflight snapshot intentionally uses `BACKUP_DATA_FILES`; it excludes `recovery-status.sqlite3` and other operational/root artifacts. The synthetic tests prove the one-shot handles that boundary correctly, not that an external wrapper implements it.

The preflight performs no app/network/model start and contains no publish operation. It is not a post-publish rollback mechanism. On an exception after migration it restores only after re-verifying the snapshot, then requires the inspection marker; on recovery failure it refuses publish and marks inspection if possible. An interrupted process (for example, forced termination) is outside these Python exception tests, so the wrapper must treat any missing successful result as a hard stop and keep the candidate unpublished.

## Limits

This review did not inspect or approve the external stop/cold-copy/disk-space/publish orchestration, run the synthetic suite, validate the real product data layout, or authorize a schema-20 installation. Use only for the isolated category diagnostics patch SHA `25244a13586375dc9366aaad8d68adf4cd4867174bd9a2b207afacb44ad907b8`; do not use it for the schema-free paragraph package or another migration.
