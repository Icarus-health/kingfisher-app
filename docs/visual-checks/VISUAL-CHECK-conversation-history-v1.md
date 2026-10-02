# VISUAL-CHECK — Gesprächshistorie v1

- Status: `pass-with-approved-deviations`
- Reference: Screen 03 in
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1536 × 1024`
- Browser: local Chromium screenshot against the Docker runtime
- Date: 2026-09-04

## Nachweis

- `/conversations` is served by the local Docker app on `127.0.0.1:8890` and
  directly loads the React screen; a browser reload no longer produces a 404.
- The screen lists only persisted SQLite conversations, ordered by the latest
  activity. Search, opening a listed conversation and creating a conversation
  are wired to the local conversation APIs.
- The visual structure uses the existing canonical sidebar, the manifest
  search and plus assets, a real search field, and list rows with title,
  preview, timestamp and message count.

## Unterschiede

Only documented, approved deviations are present:

- `docs/screen-deviations/SDR-001-approved-first-slice.md`: no avatar areas.
- `docs/screen-deviations/SDR-006-approved-conversation-history-states.md`:
  no undefined conversation-state filter tabs.

No new assets, icons, placeholder people, state badges or alternate screen
structure were added.
