# VISUAL-CHECK — Einstellungen und Integrationen v1

- Status: `pass-with-approved-deviations`
- Reference: Screen 14 in
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1521 × 1034`
- Browser: local Chromium screenshot against the Docker runtime
- Date: 2026-09-04

## Nachweis

- `/settings` is served by the local Docker app on `127.0.0.1:8890`; direct
  loading and browser reload reach the React view rather than a 404 response.
- The overview retains the canonical desktop hierarchy: existing dark sidebar,
  light working canvas, integrations on the left and a restrained data and
  synchronisation panel on the right.
- Only manifest assets are used: the approved settings, mail, calendar and
  plus icons. No provider logos, avatars, illustrations or substitute media
  were added.
- Empty sources use the approved quiet text-in-place state and an existing
  add action. The local source API returns no passwords or source URLs.

## Unterschiede

The unreferenced add/remove interaction is limited to the approved inline
form and confirmation described in
`docs/screen-deviations/SDR-007-approved-inline-integration-setup.md`.

The overview itself has no other observed visual differences from the selected
reference structure.
