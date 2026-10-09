# Bounded post-migration resume review

Reviewed only `resume.py`, `postmigration_proof.py`, and `test_resume.py` under `/private/tmp/kingfisher-category-postmigration-resume-20261009/`. No live action was performed.

## Result

No data-preservation or publish-path blocker found for the currently verified stopped, migrated-but-unpublished state. The resume requires the externally bound migration receipt SHA and canonical schema-19 proof SHA, revalidates the cold backup, exact image/package dependencies, current volume, old stopped-container image, native bundle hashes, and saved environment. It then proves current schema 20 using WAL-aware read-only SQLite, checks the new diagnostic column remains NULL, compares all rows/original bodies/settings/pause to the schema-19 proof, and only then publishes the pinned new image. It does not stop or start the old container, migrate, checkpoint WAL, or restore a historical snapshot. Runtime probing is after healthy startup. The supplied proof records schema 20, 344 originals, 17 databases, all rows/settings preserved, pause true, inspection false, and unpublished. The writer reports 8 passing synthetic tests.

One reporting caveat: `execute()` sets `task.stopped=True` and the result to `stopped_schema20_manual_review` before `task.quiet()` proves the container is stopped. The active-container negative test therefore returns a status that says “stopped” while the fake container is running. This path still fails closed and does not publish, but the status overstates what was verified if the precondition changes. It does not block the already independently confirmed stopped state; avoid relying on that status alone as proof of stopped runtime.

## Reviewed hashes

- `resume.py`: `f36fb8c25cc984283cccbbc466e71da9cb8b463c54f1727285ee7c2bda842ab4`
- `postmigration_proof.py`: `f4dbca6039095338b956b2bfa36336a145f40717841d462a83aaba6f8ce849d3`
- `test_resume.py`: `23c0af72401a871294c25270614954dae2abe1a38933ab592c4da33de442c2f0`
