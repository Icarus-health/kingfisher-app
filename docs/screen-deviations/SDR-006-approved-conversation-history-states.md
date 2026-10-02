# Approved screen deviation — conversation history states

Approved by the product owner in the implementation conversation on 2026-09-04.

## Gespräche – Historie

- Screen 03 in `system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt) shows the tabs
  `Alle`, `Offen`, `Warte auf mich` and `Abgeschlossen`, but it does not
  specify the data meaning or lifecycle behind those states.
- Kingfisher does not yet persist a completion or waiting state for a
  conversation. Assigning existing conversations to one of these tabs would
  therefore fabricate product data.
- The implemented safe slice is a local, persistent list of all conversations
  with a search field, newest-message preview, timestamp, message count and a
  functional new-conversation action.
- The state tabs are deliberately omitted until their semantics and lifecycle
  are defined. No substitute status, badge, avatar, imagery or filter control
  was introduced.
- Avatar omissions continue to follow
  `docs/screen-deviations/SDR-001-approved-first-slice.md`.

This keeps the visible history honest: every listed item and preview is backed
by the local SQLite conversation store.
