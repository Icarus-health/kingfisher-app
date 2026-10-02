# Approved screen deviation — inline integration setup

Approved by the product owner in the implementation conversation on 2026-09-04.

## Einstellungen – Integrationen

- Screen 14 in `system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt) defines the calm
  integrations overview, but does not define an add/remove flow for multiple
  personal mail accounts, CalDAV sources or HTTPS iCalendar subscriptions.
- An add action opens a reduced inline form inside the existing integrations
  area. It does not use a modal, new scene, illustration, provider logo or
  alternate layout.
- Mail passwords and CalDAV app passwords are submitted only to the local
  keychain path. They are never returned in the sources overview or rendered
  after saving.
- Removing a source requires a second, textual confirmation within the same
  row. It removes only Kingfisher's local configuration, never data at the
  provider.
- Individual Google calendars can be added as separate personal HTTPS
  iCalendar subscriptions. Kingfisher does not claim a Google Calendar OAuth
  capability that is not implemented.

This is the smallest safe setup flow for real local sources while preserving
the reference screen's hierarchy and the user's visible consent boundary.
