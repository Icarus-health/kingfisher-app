# Independent category-20 installer review

Read-only review of `/private/tmp/kingfisher-category-install-orchestrator-20261009/orchestrator.py`, `data_proof.py`, and `test_orchestrator.py`, plus a static review of `/private/tmp/kingfisher-category-fresh-verifier-20261009.py`. No installer, Docker, application, model, network, or private-data action was performed by this reviewer.

## Findings

- The initial package-check rejection of Docker's image-declared `/data` volume was addressed with a 1 MiB `tmpfs` override. The parent supplied an exact-image create/inspect/run probe showing `Mounts=[]`, `HostConfig.Tmpfs={'/data':'rw,noexec,nosuid,size=1048576'}`, package check 264/112 passing, and exit 0. This resolves that integration concern.
- The orchestrator has a sound fail-closed shape in the reviewed snapshot: immutable image ID and named volume checks; explicit operator maintenance attestation; stop/quiescence checks; full cold-copy proof before writable one-shot migration; schema-20 proof before changing the image env; and no historical restore after publish. It checks the app bundle again before and after publication. The fresh verifier now checks the current binary, Info.plist, compose file, exact settings JSON, schema, cold sidecars, exact one writable `/data` volume, database set, original IDs/digests, and codesign.
- The synthetic suite now covers allowed versus unexpected named-volume writers during the guarded migration. The writer's `WORKING.log` reports 30 passing tests. This is reported as the writer's test result; I did not execute the suite.

## Final corrections verified

- The orchestrator now checks the full process command for the exact app executable path as well as Compose commands. A new synthetic test covers the case where `comm` only reports `Kingfisher` while the full command contains the app path.
- The fresh verifier now selects `(id,digest,body)` from the cold backup and recomputes every backup body's `sha256:` digest before comparing original IDs and digests against the live database.
- The migration watcher deliberately lets an in-progress one-shot finish after a maintenance check fails, then prevents publication and leaves manual review. This avoids blindly interrupting a transaction, but a newly competing writer could overlap the remainder of that migration; the outcome is not automatically repaired. Keep this limitation explicit and keep the maintenance-window requirement in the run procedure.

## Final artifact hashes

- `orchestrator.py`: `ea2924c30be4526de0308b524ea249131181399099719d73d0ccf1e524a0b73f`
- `test_orchestrator.py`: `f205d977d3ce693fd829d8dfa971f0bd402087529c498206d3ad9a5a61989fa5`
- `kingfisher-category-fresh-verifier-20261009.py`: `c875794b346ef7473f375f864128b68e02d1d86a53c8df78f01e6e4afd528b21`

The writer's final log reports 30 synthetic tests passing. I did not execute the suite or either runtime script.

## Scope

I found no other blocking issue in the reviewed orchestration contract. The orchestrator/tests are isolated artifacts and do not modify the shared product checkout or product data.
