# Wiederaufnehmbare Mailaufnahme und erweiterbare Themen

## Geliefert

- Bounded IMAP inventory over finite UID snapshots; actual message counts instead of UID-distance percentages. Gmail special-use All Mail covers Inbox, Sent and archive without traversing duplicate labels. Other providers currently fall back to INBOX, explicitly shown before start.
- Persistent inventory/capture checkpoints in episode schema11; originals and capture acknowledgement share one transaction. New-message and history lanes share work fairly. Historical capture backs off when statement analysis is behind; new messages retain capacity.
- Account-scoped provider IDs shared by automatic and manual intake; Message-ID alone never establishes cross-folder identity. Existing pre-provider sources cannot be safely reconciled across different folders solely from their headers and may require review.
- Partial wire fetch bounds raw mail to2MiB. Oversized/incomplete text is marked truncated and withheld from automatic interpretation. Attachments are not analyzed. Single failed fetches retry with backoff without blocking later messages.
- Separate versioned topic suggestions and exact original-span entity suggestions. Originals, search inclusion and confirmed claims are not rewritten. Manual topic corrections remain preserved; changed/withdrawn/dismissed evidence cannot silently regain a current automatic interpretation.
- Visible preview/start/pause/resume/retry, real inventory/capture/statement/topic counters and explicit failures. Unknown totals remain indeterminate. No guessed overall ETA. Pausing intake preserves originals; already stored sources can still be interpreted under the separate memory-automation permission.

## Evidence

- Full local sidecar suite: **2630 passed** (5m02s), with loopback permission and temporary compiler caches. Initial sandbox-only run failed at local test-server binds/Swift cache writes and at old-version fixtures; fixtures were updated to reconstruct their stated pre-v11 schemas.
- Following final integration fixes: **111 affected tests passed**, including provider wire limits, actual complete_json budget contract, generic-address protection, dismissal, scope confirmation, source changes, permission changes, retries and upload priority.
- **30 frontend controller/progress tests passed**, production build passed; asset contract passed (16 files/15 icons). Existing bundle-size warning remains.
- 10,000-message synthetic inventory: finite actual count, bounded capture with analysis backpressure, and next incoming message still captured.
- SQLite snapshot reopened successfully with capture counters and manual category correction intact.
- Browser component with actual routes/storage and synthetic mailbox: reviewed scope, started, observed4/12 captured and0/4 interpreted, paused, reloaded with same state, resumed. This verifies the component flow, not a full native-window or real-mail import.
- Actual installed local qwen3.5:4b: two invented messages processed in5.0s; both statement and topic passes complete, with work/appointments evidence. No entities were proposed in this small sample; this is an interface smoke test, not an extraction-quality benchmark.
- Independent review found and fixed unrestricted raw-wire fetch, ignored-source backpressure, account-removal race, retry cooldown mismatch, manual/automatic dedup mismatch and dismissed interpretation bypass.

## Deployment

Image `kingfisher:mail-intake-20260929`, ID `sha256:11fb171d87f78d5b8e51d930d4c94637cdc8f707e12cc4b63da56074583dc5c5`.

Test container upgraded first on its existing volume. All142 Python module hashes match the working tree. Pilot then upgraded on `kingfisher-pilot-data` after a quiescent snapshot at `/data/sicherungen/kingfisher-20260929T120433Z`. Old container retained as `kingfisher-pilot-before-mail-intake-20260929`. Do not start its older code against the migrated schema11 volume; rollback needs the saved pre-update snapshot on a separate volume.

Post-update checks: healthy server/schema11; **2 mail accounts and8 calendar sources preserved**, credentials still present; **6 initial categories**, local analysis active. Read-only preview of both actual accounts recognized `[Gmail]/Alle Nachrichten`. **No bulk real-mail import was started.** The user starts each account after reviewing its displayed scope.

## Honest remaining limits

This is an intake and interpretation workflow, not a guarantee of perfect memory. Large/truncated originals and attachments remain explicitly unresolved. Non-Gmail archive/sent discovery is not yet supported beyond the shown fallback. Entity candidates are source hints, not automatically merged people/project records. Adding categories is supported through the versioned API; the first UI exposes source-level category correction, not a full taxonomy editor. Whole-corpus throughput and answer usefulness still need observation with actual user data.
