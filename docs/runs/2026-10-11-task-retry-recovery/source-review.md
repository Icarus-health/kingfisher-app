# Task-save recovery: independent bounded review

Reviewed the uncommitted diff against cde97a7cf86f2bfffb006c2f409757521e9664b6. No product edits, private data, browser/native UI, backend/model/network calls or Git mutations. Synthetic helper tests only.

## P2: reviewed reset can delete a different pending request after restore failed

Location: `app/kingfisher/src/taskSaveAttempt.ts:40-47` (especially the `this.id && previous` guard at line 44).

Reproduction using the actual helper with synthetic in-memory Storage:
1. Stored value is malformed; `first.restore()` rejects, leaving `first.id` null.
2. Another window resolves that old malformed entry and saves a new valid request B. Its acknowledgement is lost, so B remains pending.
3. The first window's explicit reviewed reset calls `resetAfterReview()`.
4. Because `this.id` is null, the ownership check is skipped and request B is deleted.

This violates the stated exact-own-request reset contract. After reload the other window has lost its durable replay identity; a later retry can become a new request. The checkbox authorizes abandoning the request the first window displayed, not silently deleting a different newer one. Bind reset to the storage value actually observed by that attempt and reject a changed value, including when no UUID could be restored. Read-error cases should not establish ownership of arbitrary future data.

## Separate multiwindow atomicity limitation

Cleanup at line 66 is two Storage operations (`getItem`, then `removeItem`), not one conditional operation. A deterministic interleaving of storage calls (read A, another window writes B, remove key) deletes B despite the equality check. The same type of interleaving exists in reset/read/write. The probe is a controlled synthetic schedule, not an observed native-browser race. Stable foreign B already present before cleanup is correctly preserved. Do not describe this implementation as atomic across concurrent windows or a global exactly-once guarantee; a per-form in-flight guard and server binding do not cover different freshly generated UUIDs.

## Verified controls and review scope

- Independently ran `node --experimental-strip-types --test tests/task-save-recovery.test.mjs tests/task-save-attempt.test.mjs tests/goal-task-link.test.mjs`: 14 passed, 0 failed. The two goal-link tests are static source checks, not a browser execution.
- Extra synthetic control: reset during pending save throws; success of A preserves a stable foreign B.
- Product persists only the opaque UUID before invoking send; missing/throwing/invalid storage closes the send path. Confirmed-save cleanup failure remains confirmed.
- Manual and each goal have distinct keys; changed payload retains its request UUID for existing backend 409 validation. No backend changes in this slice.
- UI reset is an explicit checkbox plus `type=button`; both handlers recheck checkbox/busy/in-flight and make no API call. Opening forms resets review consent. No new route or stale-handler defect found in this bounded review.
- Fields are not stored; reload cannot recover the previous title/date/project. Clear messaging explains this. No crash-durability or cross-window lock proof was performed.

Probe: `/private/tmp/kingfisher-task-recovery-independent-20261011.mjs`.

## Source fingerprints reviewed

- taskSaveAttempt.ts: dbe3f45a4b553bb67887bb6852b8f6e637c13897229c6965fd412d60cf6fd59a
- TaskRetryReview.tsx: 393f8065710a06733db4700d4568a46826643c9fc59ca9ae5208c33cf03874a9
- App.tsx: 1ae6224cd094cc754747d2b7140577fa708dabf3896e68b12ebf2aaf2b0f3b48
- GoalControls.tsx: aee589895f9622cdee0b2c0aeced30b3799922be36245b5e0651c4ea597caf50
- task-save-recovery.test.mjs: 54e2aead92f6513d2218459cd7dd9fa517fc6cf550ed76967bb33ab80dd362f3

## Final narrow re-review: correction verified

The P2 reset finding is closed for the reviewed revision. `restore()` records only a successfully read raw storage value (before validating its UUID); `resetAfterReview()` now requires an observed and unchanged value and still rejects a conflicting own UUID. A failed read establishes no ownership. Persisting this attempt updates its observed value. Both new permanent failure controls passed, and I independently repeated the original malformed → other lost-acknowledgement request → reset sequence: reset rejects and B remains stored. Raw synthetic browser-error sentinel is absent from restore/save preparation messages.

Fresh targeted command above: **17 passed, 0 failed** (including the 2 static goal-link checks). No broader suite or browser/native execution by this reviewer. Static UI/CSS recheck found no further concrete blocker: checkbox styles are narrowly scoped, review button remains non-submit, busy/consent guards remain, and preparation does not invoke an API. The previously documented non-atomic interleaving of separate localStorage operations remains an explicit limitation; this is not a global multiwindow guarantee or a native WebKit verification.

Final hashes:

- taskSaveAttempt.ts: 3c3a42c77d37f31dcc39ca5cc52d6f38f9a70dc841510d2b73359e85eb6c8568
- TaskRetryReview.tsx: 393f8065710a06733db4700d4568a46826643c9fc59ca9ae5208c33cf03874a9
- TaskRetryReview.css: a2264b7f6cb3fbcd0b793d395e9164df286ae5e855997c0d6126eba05a91c82f
- App.tsx: 1ae6224cd094cc754747d2b7140577fa708dabf3896e68b12ebf2aaf2b0f3b48
- GoalControls.tsx: aee589895f9622cdee0b2c0aeced30b3799922be36245b5e0651c4ea597caf50
- task-save-recovery.test.mjs: c81dcb6ad96b2ae442fe4bd30a64eebbfc376f584a0f369ddb1c2743dabf532e
