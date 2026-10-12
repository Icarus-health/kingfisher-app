# Independent package review — b7cd321

Scope: read-only artifact/source binding and synthetic package-probe code/results. No personal data, Docker calls, UI/native app launch, model/network calls, product changes, or Git mutation. Only this review report was written. Native signature and architecture verification commands are read-only on the packaged artifact.

## Artifact binding: no mismatch found

- `source.tar` SHA-256 `54985d265894c0db73f2eea596421e803aa07478394cf8e48dbc087c7d7b2438` equals an independently streamed `git archive --format=tar b7cd321dd2c081b48c5fcb42fd3ae37184554326`. The archive PAX comment names the same full commit.
- Compared every archived regular file with staging: no missing files; only `.dockerignore`, `Dockerfile`, and `VERSION` differ. Those are the declared staging overrides. Original/archive and packaged VERSION hashes agree with the override record (`1.0.6` -> `1.0.6-preview.b7cd321`).
- Dockerfile pins base `sha256:48b1bd538de8eb14eca5f217dcefeac28f042630533310cb7cc7916ed40e0102`, replaces both Python package and UI before copying frozen content, sets exact version and full revision, and returns to `USER kingfisher`. Build context is restricted to those runtime directories/VERSION; the host dependency symlink is not copied by this allowlist. Recorded result image: `sha256:44c6f9fa0c6d0a8852ac7dfdbdad221def3e237a61acd5bb1485ca8e8f04db27` (read from image-id/build log, no live Docker inspection by reviewer).
- `package-freeze.json` exactly equals the probe's literal expected manifest. All 272 runtime-package files (including the sqlite-vec licence file) and all 112 UI files match by exact path set and SHA-256, not just counts.
- New UI is present: `app/dist/index.html` points to `assets/index-BlbjYsOl.js`, SHA `c78d8c9417a37d7ca6d635ff8ebaab357b5e0ce61052365b7a96cab01ed20131`. That served asset contains both opaque storage scopes, the reviewed-reset controls, and the corrected `observedValue` check. The referenced CSS contains `.task-retry-review`. Vite config outputs directly to `app/dist`; absence of `app/kingfisher/dist` is expected. No browser rendering was performed in this review.
- Native bundle's exact six-file manifest matches current package bytes. Info.plist says `1.0.6-preview.b7cd321`. Independently ran `codesign --verify --strict --deep` successfully and `lipo -archs` returned `arm64`. This proves local signature validity, not notarization.
- Current DMG bytes hash to `dd82c485c719a760b7a06bbec786175a9b78f8a88ebda35bd15e407d37d4d2f3`, matching `dmg-verification.json`. Inspected `verify_native.py`: it mounts read-only, compares the mounted complete six-file manifest to the staged bundle, verifies signature and detaches in finally. That successful mount proof is the build operator's recorded evidence; reviewer did not mount the DMG.

## Package probe: bounded review findings

The probe checks the installed import path, exact runtime/UI sets and hashes, version file/environment, empty data directory, and absent provider configuration before its synthetic workflows. The new manual block covers both `/api/v1/tasks` and `/tasks`, one task for repeated request, fields/goal/project preservation, equivalent timezone instants, changed payload 409, edit+completion preservation after restart, schema versions and rejection after goal completion.

Two observed probe failures must not be called package success:

1. Initial log stopped with `IndexError` at the older live-intake fixture's `analysis_batch()[0]` before reaching new manual cases. This was reported immediately; it is not evidence of a source/UI binding defect.
2. The new manual block creates the goal in `SelfModelStore(MemoryBackend())` then recreates a fresh empty MemoryBackend during restart. The task persists, but the goal does not exist in that new synthetic store, so `_validate_task_goal()` returns 409 before replay. Static prediction was confirmed by the subsequent log (`Das Ziel ist nicht mehr offen`). This fixture needs a persistent synthetic self-model store for a genuine goal+restart check; weakening product validation would be wrong.

Several copied earlier probe sections emit `final_package_status: passed` before the new manual block. Those markers alone are insufficient. Require overall exit 0 plus the last `packaged_manual_task_retry_both_routes_restart_current_status_payload_conflict_goal_link` result. At this interim review point the full new probe has not passed. Product/image/native artifact content has not been changed by this reviewer.

## Stable fingerprints read

- package-freeze.json: `69086280176dea5bf2415c9966039a170392e0160fba9a046555d34283d33662`
- Dockerfile: `61ae785cdb062c380ff84df871a826c89f0044a61e781ba1369c94e8d6d47da1`
- .dockerignore: `00d3c5cfd0dc6da1b6b676e58b9328fe6801eaad41683f6b932ded8e38847768`
- staging-overrides.json: `b40451e4e3acdb9c30b1991dff98c6f3485dbc207dd433609c527576513901ae`
- verify_native.py: `57fb171af96a6f4c59c93550ca11c1ccc3e831493dd5557d387a0072a333249f`
- mac-app-manifest.json: `a902e6a4c0320027b75de1e95a4d64c0ffec1232d907124239f2ddb94746a670`
- dmg-verification.json: `ab8179f6eff70bd6073999d4c4ea82158366de2361b14a7576dd2f582adf8f49`

The probe is being corrected by its owner; final probe/result hashes and status will be appended after its completion.

## Final completion of the package review

The fixture now uses `persistent_manual_store()` with a synthetic `SqliteBackend` for both initial and restarted application instances. The old failing logs remain separately preserved (`package-probe-insufficient-test-tmpfs.log`, `package-probe-first-manual-assertion.log`, `package-probe-ephemeral-goal-fixture.log`). The initial storage-budget failure was resolved by raising only the synthetic container tmpfs to 1 GiB; no production minimum-reserve change is involved.

I read the completed `package-probe-final.log`: no traceback, and its actual final line confirms the manual both-route replay, restart/current-status, conflict, and goal-link cases, with TaskStore 3 and EpisodeStore 22. The executing parent confirmed actual process session 41760 finished with exit 0; I did not execute or inspect Docker myself. The embedded expected manifest remains exactly equal to package-freeze.json.

`recovery-proof.json` records four successful synthetic full-App browser cases (manual reload/replay, changed-field conflict and explicit reset without automatic submission, goal reload/replay, and unavailable storage with no send); no page errors. Those browser runs belong to the parent, who reports serving this built UI locally. The proof JSON alone does not include served-asset hashes; independent artifact inspection above verifies that the newly built served assets contain the reviewed change. No native window/WebKit rendering is claimed by this review.

**Final result: no remaining artifact/source-binding blocker in this bounded review.** The two probe setup failures are corrected, and the full package probe is complete. This is not an installation or personal-data acceptance result; native-window verification remains open and the package is not installed.

Final fingerprints:

- package_probe.py: `a72a6abefedeb4a0b7820072cff178b44c622522e0c4551592e3f3c7da10cc61`
- package-probe-final.log: `a2023c55e3fe103e9c1d0e41ef2c60cfe9ca0f538a4fe03243a7485bcc160a1a`
- recovery-proof.json: `4666ef647f0d12da44470319ebef0cd82c0647fbe9fee74f8833c960fd33ad6b`
- package-freeze.json: `69086280176dea5bf2415c9966039a170392e0160fba9a046555d34283d33662`
- image-id.txt: `c54c5bd2f98b353a234d05b479977114b4f83fc046173121257f62479c003dec`
- source.tar: `54985d265894c0db73f2eea596421e803aa07478394cf8e48dbc087c7d7b2438`
- mac-app-manifest.json: `a902e6a4c0320027b75de1e95a4d64c0ffec1232d907124239f2ddb94746a670`
- dmg-verification.json: `ab8179f6eff70bd6073999d4c4ea82158366de2361b14a7576dd2f582adf8f49`
