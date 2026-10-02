# Mail memory intake implementation plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task. Independent connector and category modules may be delegated under the user's existing authorization.

**Goal:** Persistent bounded mail intake with honest progress, source-grounded extensible categories and continued current-mail processing.
**Architecture:** Extend the episode database with inventory jobs and topic annotations; retain existing original-source and working-memory contracts. Bounded scheduler work handles inventory, fair retrieval and local interpretation.
**Tech Stack:** Python, SQLite, IMAP, FastAPI, React/TypeScript.
**Spec:** ../specs/2026-09-29-mail-memory-intake-design.md

## Global constraints
- Preserve all pilot accounts, sources and corrections. No reset.
- Original sources remain separate from machine interpretation and confirmed knowledge.
- No cloud processing, external sends, or automatic identity merging.
- Percentage means actual enumerated items; unknown totals remain indeterminate.
- New categories require no source rewrite or mailbox redownload.

## Review focus
- IMAP UID gaps and generation reset: enumerate actual messages and retain old sources.
- Restart after capture: transaction protects duplicate counts and checkpoints.
- New mail during a large archive: reserve bounded work for both queues.
- Revoked sources and corrections: stale annotations cannot be presented as current evidence.
- Duplicate Gmail labels: account-scoped provider IDs deduplicate sources.

## Task 1: Connector inventory
Files: connectors/mail.py, tests/test_mail_inventory.py.
- [x] Fake IMAP tests for special-use folders, quoting, bounded UID windows, missing messages and UIDVALIDITY mismatch.
- [x] Implement folders(), inventory_page(folder, after_uid, before_uid, limit, uidvalidity), message_in_folder(folder, uid).
- [x] Run new and existing connector tests.

## Task 2: Persistent intake and scheduler
Files: mail_intake.py, episodes.py migration11, mail_ingestion.py, scheduler.py, server.py, tests/test_mail_intake.py.
Interfaces: Intake(episodes).start(account, folders), step(account, reader, permitted), status(account), pause(account, paused).
- [x] Test interrupted inventory, capture atomicity, fair new/history queues, retries, paused permission and changed generation.
- [x] Persist finite folder snapshots and work rows; bounded inventory/capture; account-scoped Gmail IDs.
- [x] Add authenticated status/start/pause routes, background scheduling and rollback-compatible backup verification.
- [x] Verify migration from version10 and restore roundtrip.

## Task 3: Extensible annotations
Files: memory_categories.py, tests/test_memory_categories.py.
Interfaces: migrate(conn), Categories(episodes).run(provider, limit, permitted), list_for(episode_id), correct(episode_id,categories).
- [x] Test source withdrawal, changed fingerprint, manual corrections, taxonomy revision, model output validation and generic mailbox identities.
- [x] Store independent source-grounded automatic topics and entity suggestions; never rewrite originals or confirmed claims.
- [x] Run focused tests and category review.

## Task 4: User flow
Files: MailIntake.tsx/css, api.ts, MailSyncSettings.tsx, source detail component.
- [x] Show setup vs connected vs active explicitly, selected scope, inventory/capture/analysis counts and bounded error display.
- [x] Add pause/resume, live polling with cleanup, category evidence and correction controls.
- [x] Build and test controller transitions; verify real browser when technical permission allows.

## Task 5: Acceptance
- [x] Independent diff review; address findings.
- [x] Focused and full sidecar regression tests, frontend build and asset contract.
- [x] Synthetic large inventory and restart/backup/restore test.
- [x] Document limitations and exact observed results, then back up pilot before deployment.

## Execution record and rulings

See ../../runs/mail-intake-20260929/README.md for measured results.
- Ruling: use Gmail All Mail for both history and new arrivals, avoiding duplicate label capture. INBOX fallback is explicit for unsupported providers.
- Ruling: schema11 keeps intake and annotations inside the backed-up episode DB; nested source-head transactions join the capture transaction.
- Ruling: no bulk real-mail import during deployment; preview actual scope, then user starts in the UI. Actual-account preview succeeded; real corpus quality acceptance remains open.
- Ruling: intake pause does not revoke access to already stored originals; separate memory automation controls analysis. UI states this explicitly.
- Ruling: no ETA until representative measurements; counts and stages are available now.
