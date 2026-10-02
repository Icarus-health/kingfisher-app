# Approved screen deviation — conversation memory candidate

Approved by the product owner in the implementation conversation on 2026-09-03.

## Gespräch + Kontext

- The canonical `system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt), section 04, defines
  the conversation structure but does not show how a proposed memory item is
  accepted, rejected or corrected.
- Kingfisher uses the existing neutral Kingfisher assistant-message card inside
  that conversation. It shows the proposed statement, the exact quoted source
  from the user's message, and only the actions needed for its current state.
- A pending proposal offers `Bestätigen` and `Nicht speichern`. If an active
  stored claim conflicts, the card names that existing statement and changes
  the affirmative action to `Bestehenden Stand ersetzen`.
- An ordinary message never shows this card and never creates a source,
  proposal or claim. The card exists only for an actual pending, accepted,
  rejected or superseded local proposal.
- In the current conversational entry point, a user must begin the message
  with an explicit memory request such as `Merke dir: …`. The model may only
  structure that request; an independent server-side check enforces the same
  requirement before any proposal is created.
- No new imagery, avatars, icon, modal, illustration or alternate chat layout
  was introduced.

This is the smallest safe interaction that lets the user decide whether a
conversation-derived item becomes durable knowledge without presenting an
unimplemented control or silently treating a statement as true.
