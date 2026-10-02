# VISUAL-CHECK — Nachrichten im Kontext v1

- Status: `pass-with-approved-deviations`
- Reference: Screen 10 in
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1521 × 1034`
- Additional viewport: `1440 × 1034`
- Browser: local in-app Chromium against the Docker runtime
- Date: 2026-09-04

## Nachweis

- The screen keeps the reference's dark sidebar, quiet white content surface,
  title, restrained active view control, and message-list anatomy.
- Each row uses only actual local inbox preview data. No avatar, provider art,
  category row, or message body is fabricated.
- `/nachrichten` directly loads in the local Docker app. The active sidebar
  entry opens the screen, and navigation from Nachrichten to Gespräche and
  back was exercised without a console warning or error.
- The currently configured local runtime has no mail account. Its neutral
  text-in-place state reads `Noch kein Postfach verbunden.`; no demonstration
  messages were created merely for a screenshot.
- The deliberate differences are recorded in
  `docs/screen-deviations/SDR-009-approved-local-inbox-slice.md`.

## Vergleich

- The reference title is preserved as `Nachrichten im Kontext` in the same
  restrained serif hierarchy.
- The reference's selected `Alle` view becomes the only visible, backed
  category. It uses the existing muted active-control treatment.
- The white content plane, thin horizontal list dividers, dark sidebar, and
  approved mail icon match the established Kingfisher screen language.
- Person circles are absent under SDR-001; category controls, provider marks
  and mail details are absent under SDR-009.
- Populated message-row spacing is structurally implemented but awaits a
  user-configured local mailbox for a data-real visual capture.
