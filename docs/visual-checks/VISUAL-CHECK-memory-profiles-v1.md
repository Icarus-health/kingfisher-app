# VISUAL-CHECK — Personen- und Projektprofile v1

- Status: `approved-empty-state; populated-profile-check-pending`
- References: sections 06 and 07 in
  `design-source/06_Screens/Approved/system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt)
- Viewport: `1521 × 1034`
- Browser: local in-app Chromium against the Docker runtime
- Date: 2026-09-04

## Nachweis

- Profile are read-only projections from the existing Icarus graph and source
  stores. They do not create a person table, CRM copy, or inferred relation.
- Person and project nodes in the graph open their matching profile route. The
  direct routes also load safely when the requested entity is not present.
- Tabs are real local state and expose only fields already returned by the
  profile APIs: projects, conversations, tasks, documents, decisions, team,
  current claims and claim history.
- Empty sections remain text-in-place. No example person, project, avatar,
  image or relationship is inserted into the persistent store.

## Live verification

- `/memory/people/Dr.%20Kranz` loads the honest not-belegen state when that name
  is absent from the current local graph.
- Browser console: 0 errors, 0 warnings.
- The current local SQLite graph contains no person or project nodes, so a
  populated profile comparison has intentionally not been faked.

## Approved differences

- Avatars and profile imagery are omitted under SDR-001 and the closed asset
  manifest.
- The reference's compact statistic labels are populated only where the
  projection has a backed value; missing categories use the approved calm
  empty state rather than a fabricated count.
- Profile editing, person creation and project creation are not exposed. The
  current Icarus profile APIs are read-only projections.

## Remaining gate

After a real, user-approved source produces a person or project node, capture
both profile types at the canonical desktop viewport and compare populated
copy, metrics, tabs, evidence lists and spacing against sections 06 and 07.
