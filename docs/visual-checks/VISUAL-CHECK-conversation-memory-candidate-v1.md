# VISUAL-CHECK — conversation memory candidate v1

- Status: `functional-pass; browser-visual-check-pending`
- Reference: section 04 of
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Approved difference:
  `docs/screen-deviations/SDR-005-approved-conversation-memory-candidate.md`
- Date: 2026-09-03

## Functional verification

- A normal user message creates neither an episode, a knowledge candidate nor
  a claim.
- A model draft becomes a candidate only after an explicit `Merke dir: …`
  request in that same user message; the server independently enforces this.
- The explicit conversation-candidate route records a local `chat` episode
  with the exact source message, its source reference and digest-backed quote.
- The card remains associated with the assistant message after a conversation
  reload and reports its current candidate state.
- `Bestätigen` produces one append-only claim. `Nicht speichern` rejects the
  proposal without writing a claim.
- A contradicting active claim blocks acceptance until the explicit
  `Bestehenden Stand ersetzen` action is used.

Targeted backend tests: 32 passed. The frontend production build and the asset
manifest check both passed.

## Remaining visual gate

The isolated test instance could not be opened by the in-app browser on its
separate local port because the browser client blocked that URL. No visual or
pixel result is claimed from that attempt. Compare the real card at the
canonical desktop viewport after the next local Docker rebuild, then replace
this status with `pass` only if differences are none or separately approved.
