# Approved screen deviation — local task slice

Approved by the product owner in the implementation conversation on 2026-09-04.

## Vorhaben / Aufgaben

- Screen 08 in `system-overview-canonical-source-v1.png` (vor der Veröffentlichung entfernt) shows four filters:
  `Meine Aufgaben`, `Delegiert`, `Wartet auf andere` and `Erledigt`.
  Kingfisher has durable local semantics for the first, third and fourth
  views, but no independent stored meaning for `Delegiert`.
- The implemented view therefore shows only `Meine Aufgaben`, `Warte auf
  andere` and `Erledigt`. No task is assigned an invented delegation status.
- The reference also displays project and priority columns. Tasks currently
  persist an optional opaque project identifier but no displayable project
  relation or priority field. The UI therefore shows the real title and due
  date only; it does not fabricate project labels, priority badges or urgency.
- The approved `+ Aufgabe` action opens a short inline form in the same task
  area with title and optional due date. A date is stored locally at the end
  of that calendar day. No modal, new scene, additional task metadata or
  placeholder row is introduced.
- Checking a task calls the local completion endpoint and moves the persistent
  task out of `Meine Aufgaben`; it does not delete its history.

This is the smallest honest task surface over the existing Icarus SQLite
lifecycles.
