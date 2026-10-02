# VISUAL-CHECK — Vorhaben und Aufgaben v1

- Status: `pass-with-approved-deviations`
- Reference: Screen 08 in
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1521 × 1034`
- Browser: local Chromium screenshot against the Docker runtime
- Date: 2026-09-04

## Nachweis

- `/vorhaben` is served by the local Docker app and directly loads the React
  screen rather than a 404 response.
- The screen retains the reference hierarchy: existing dark sidebar, heading,
  restrained filter row, primary add action, and a quiet light task table.
- The empty local store uses the approved text-in-place empty state with the
  one permitted follow-up action. No task row, person, project or priority is
  simulated.
- The browser route uses only approved plus, check and sidebar assets.

## Unterschiede

Only the approved, data-honest differences in
`docs/screen-deviations/SDR-008-approved-local-task-slice.md` are present:
the undefined delegation tab and unbacked project/priority columns are omitted,
and task creation remains inline in the existing surface.
