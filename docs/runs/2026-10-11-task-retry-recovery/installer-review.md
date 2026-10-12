# Independent bounded installer review — b7cd321

**Result: no concrete blocking defect found in the reviewed installation path.** This is approval of the prepared script's bounded behavior, not evidence that an installation or private-data preservation check has run. The installer was not executed by this reviewer.

Scope: `install.py`, `backup.py`, `preservation_guard.py`, `qualify_copy_worker.py` in `/private/tmp/kingfisher-task-recovery-package-b7cd321`. Read local scripts and existing synthetic proof metadata; independently exercised selected actual installer AST functions with fakes and temporary synthetic SQLite databases. No personal application/configuration/volume, Docker, calendar API, UI, model or network access. No product changes.

## Reviewed behavior

- Pre-switch pins require old native `preview.f858681` manifest and image `sha256:48b1bd538de8eb14eca5f217dcefeac28f042630533310cb7cc7916ed40e0102`, and new runtime `preview.b7cd321` image `sha256:44c6f9fa0c6d0a8852ac7dfdbdad221def3e237a61acd5bb1485ca8e8f04db27`. Completed package probe is bound by its script/log hashes and image identity. Candidate native files must equal the package manifest and pass signature checks before replacing the existing bundle.
- `backup.py:12–21,71–87` compares configuration with the running container, checks the exact named volume and sole current container user, and holds an advisory recovery lock. It stops that old service, mounts its source volume read-only, creates a new complete archive, restores it into synthetic worker scratch space, and checks every file/directory entry, bytes and uid/gid/mode/mtime/xattrs before SQLite opens. Every root SQLite copy receives integrity checking. The old runtime restarts in finally before any new-code switch; no productive data migration or archive restore occurs in this phase.
- `install.py:52–54` qualifies a separate archive copy using the pinned new image, `--network none`, read-only container and read-only backup mount. The worker opens only copied EpisodeStore/TaskStore files, verifies the existing v22 header projection and complete two-way parity with original tags, and requires preservation equality. It does not mount the productive named data volume.
- Capture/verify functions are structurally identical in the standalone guard, embedded live probe and qualification worker. Capture covers the exact root DB set, all schema objects and user versions; every table in episodes/tasks/self-model is hashed as a row multiset. Equality plus expected EpisodeStore22/TaskStore3 rejects any migration, schema drift or changed selected-store rows. The seven additional core tables cover projects/notes/conversations as well. This does not claim that every runtime bookkeeping row in every other database is unchanged.
- `install.py:66–86` changes exactly one `KINGFISHER_IMAGE` assignment in original configuration bytes. Atomic replacement retains private file mode. Compose receives an explicit environment without ambient `ICARUS_*`, `KINGFISHER_*`, `COMPOSE_*` or `LLM_API_KEY`; PATH/HOME/DOCKER_HOST remain. `--no-build --pull never` prevents an unreviewed build/pull. After startup, relevant runtime environment values must equal the old state except the separately verified version. Image and named `/data` volume must match exactly.
- The final path checks health, expected version, paused background intake, storage status, file/configuration identity, all selected row fingerprints and all DB schemas/versions. It truthfully marks native process/window/calendar verification false and native restart pending.
- `install.py:93–110,139–143` never restores an old archive over new data or automatically starts the old runtime after a failed new publication. It first establishes the container state and stops an existing service, preserves failed new Contents, restores old code/configuration and writes a recovery-required marker. Failed Docker lookup, unexpected identity or failed stop raises before code/config rollback. New productive writes remain in place for manual recovery assessment.

## Independent synthetic checks

Executed `/private/tmp/kingfisher-task-recovery-installer-independent-probe.py` against the actual reviewed functions; exit 0:

- Ambient environment keys removed, required host keys retained; provider/model/key drift rejected, version-only difference accepted.
- Actual `compose_up` passes explicit cleaned environment, `--no-build`, `--pull never`.
- All three guard implementations match structurally.
- Unchanged synthetic SQLite inventory accepted; a changed original row separately in episodes/tasks/self-model and a changed task schema version rejected.
- Actual rollback function with foreign container identity or failing stop leaves synthetic new code, new configuration and new durable data untouched, with no start/compose/copy/run call.

Also read the parent's `install-preflight-tests.json` (9 SQLite, 4 staging, 3 recovery controls) and `compose-real-final.log` (synthetic-only actual Compose config). Their four reviewed source hashes match independently computed current hashes. Those additional executions belong to the parent; reviewer did not run Docker.

## Limits

The maintenance lock is advisory, not a global OS/browser exclusion guarantee. This review assumes the stated maintenance window, paused intake and no competing update; the existing locked native session is deliberately not restarted. Normal post-start runtime activity is not proven absent. A failed strict equality check stops the new path rather than silently treating it as preserved. Native WebKit/window and calendar interaction remain unverified. No live installation or personal-data assurance is claimed here.

## Frozen hashes

- install.py: `c393f93e9189d99ce6a6f4d43997f2e924bf5478a0b4e93710d27f2d19cc0e13`
- backup.py: `0ec50de484af9f31305a0e8e1b99172975aae048a556a5e9a904f0a3baa12438`
- preservation_guard.py: `f776bb3164d6c3f0c7587056b4550031cb94a4074a24464d1378725722bb71c0`
- qualify_copy_worker.py: `5d55b01f6ec30e1f572c5a4fb8557fc3577e37f9246ef56e53e409b384f0d34d`
