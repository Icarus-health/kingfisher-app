# Bestätigte Aufgabenzuständigkeit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. This is a P1 subplan; the parent P0–P6 goal and its release gates remain active.

**Goal:** Eine ausdrücklich korrigierte Zuständigkeit bleibt erhalten, wird verständlich bedient und schlägt die alte Quellenangabe im Abruf.
**Architecture:** Additive Task JSON state and existing append-only events. Source reports, waiting dependencies and user decisions stay distinct. Reuse identity address anchors and conversation proof projection, with no competing memory.
**Tech Stack:** Python/FastAPI/SQLite, existing React/TypeScript UI and pytest/node tests.
**Spec:** `docs/superpowers/specs/2026-11-05-task-responsibility.md`, binding controller decisions at end; parent `2026-11-04-kingfisher-product-completion.md`.

## Global Constraints

- Originale, stabile Identitäten, bestätigte Nutzerkorrekturen, Konten und Quellenhistorie erhalten; keine Neuinstallation mit Datenverlust.
- Gedächtnis ist die maßgebliche Wissensbasis; kein zweites konkurrierendes Agentengedächtnis.
- Quelle berichtet, Modell vermutet und Nutzer bestätigt bleiben unterscheidbar.
- Großimport erst nach bestandener Qualitätsprobe und innerhalb einer tatsächlich freigegebenen Daten-/Kostenregel; dieser Plan aktiviert nichts.
- Qwen9B und BGE-M3 bleiben Standard. Mistral und bestehende weitere Cloudzugänge sind optionale, ausdrücklich erlaubte Wege. Keine automatische Cloudweitergabe wegen lokaler Langsamkeit.
- Keine persönlichen Quellen, Schlüssel oder privaten Prüfberichte in GitHub. Öffentliche Nachweise mit künstlichen Daten; private Nachweise geschützt lokal.
- Keine Nachricht versenden, Buchung auslösen oder fremde Daten löschen, ohne passende tatsächliche Nutzerfreigabe. Wiederholte Ausführung darf keine Dubletten erzeugen.
- Keine Modellarbeit beim bloßen Blättern; Hintergrundarbeit begrenzt, unterbrechbar und mit verständlichem Fortschritt.
- App, Backend, Schema, Modulversion und getesteter Modellstand werden getrennt dokumentiert. Veröffentlicht, installiert und im Alltag bestanden sind unterschiedliche Zustände.


## Review Focus

1. Response lost, request replayed after another edit: no duplicate event and response gives current state, with original receipt. Task1.
2. Explicit unknown and first-decision undo survive restart/source replay: no return to inferred self. Tasks1/2.
3. Same display name with different addresses; later merge/split or own-address drift: never silently transfer. Tasks1/2.
4. Mail decision races with owner correction: final mutation cannot complete another person's task as the user's. Task2.
5. Original source changes/vanishes while conversation stays open: no stale owner revival, no copied withdrawn text. Task3.

### Task 1: Durable responsibility decisions and authenticated API

**Files:** Create `sidecar/icarus_memory/task_responsibility.py`, `task_responsibility_routes.py`, `sidecar/tests/test_task_responsibility.py`; modify `tasks.py` and narrow route registration in `server.py`. Existing history/recall tests are neighbours, no unrelated refactor.
**Interfaces:**
- `Task.responsibility: dict | None` uses the exact spec shape. `to_dict`/`_from_row` preserve it, `_HISTORY_FIELDS` records bounded decision. Old missing fields stay valid; no inferred backfill.
- `TaskStore.responsibility_snapshot(task_id) -> dict` returns `{task: Task, revision: int, responsibility_event_sequence: int|null}` from one read snapshot.
- `TaskStore.change_responsibility(task_id, *, request_id, expected_revision, operation, decision=None, target_event_sequence=None) -> dict` returns snapshot plus `{applied_event_sequence:int, replayed:bool}`. Operation `set|reset|undo`; set accepts validated self/person decision, reset creates unknown. Compare-and-write in existing SQLite transaction. Store only bounded request ID/digest/undo target in the matching event, no raw payload.
- `GET /api/v1/tasks/{id}/responsibility` returns serializable snapshot. `POST` accepts strict `{request_id, expected_revision, confirmed:true, operation, owner?, target_event_sequence?}`. owner is `{decision:'self'|'person', address?, label?}`; reject extraneous/invalid combinations, blank/name-only address, confirmed false, malformed revision/ID. Use existing address normalization; label maximum120 chars/address254/request_id100. Existing authentication guard. No registered model tool/automatic permission.
- Prior matching receipt is checked before current revision, after canonical command validation; another request body with same ID409. Bound history lookup via existing SQL progress budget; exhausted lookup503, never pretend not found. First undo -> durable unknown. Later undo restores previous explicit state; target must be latest responsibility transition. Every successful fresh explicit request has a receipt. Responses reflect current task even on replay.
- Pure ownership input validation/helpers live in new module; use TaskStore for transaction ownership, do not duplicate connection locks or schema.

- [ ] Reproduce absent durable owner API/state on fresh synthetic tasks (different from frozen acceptance examples); add meaningful failing storage/API tests.
- [ ] Implement state/event/receipt transaction and route. No live DB migration; existing task schema unchanged. Old history/current-state proof remains compatible with absent responsibility.
- [ ] Test self/person/unknown, reset/restart, exact same-name distinct addresses, old task and status proof, two-connection CAS, same request/different body, replay after later changes/beyond100events, stale and repeated undo, rollback, missing task, guard and output actor/provenance boundaries. Source/waiting/title/date fields preserved by all operations.
- [ ] Run new tests plus existing `test_task_history.py`, `test_task_status_recall.py` (locate exact filename if different) and completion tests once. Retain RED and GREEN logs; new concrete failures justify only scoped reruns.
- [ ] Independent task review then controller commit. No publish/merge/native update before dependent Tasks2/3 are complete.

### Task 2: Visible correction and consistent lists/automation

**Files:** `app/kingfisher/src/{TaskDetail,TaskRow,TaskHistory,TodayTaskRow}.tsx`, `api.ts`, task workspace/pager helpers; add focused `TaskResponsibility.tsx` if needed. Python `tasks.py`, `task_pages.py`, `aufgaben_post.py` and actual ownership readers in briefing, kommendes, offene_punkte, graph/personen/akten/mappe. Keep waiting-only consumers unchanged.
**Consumes:** Task1 snapshot/change routes and exact responsibility record.
**Produces:** Central `effective_responsibility(task)` and matching SQL predicates; derived user-actionable/view fields in Task response, views `mine|waiting|done|others|unassigned`.
- [ ] Demonstrate confirmed-other and explicit unknown currently appear as own work; pin list/page/counter/briefing/automation cases before change.
- [ ] Add compact detail control for Ich / Person / Ungeklärt, explicit address and optional reviewed name, lazy existing contact suggestions, confirmation, reset and undo. Keep request ID/draft on ambiguous save;409 asks refresh/review without dropping inputs. Empty unchanged submit disabled; own-account overlap shown for correction, never silently rewritten. Available also on done/dropped detail. History shows decision and timestamp and unknown actor.
- [ ] Add two small filters `Bei anderen`/`Zu klären`; requester and waiting remain separately labelled. Preserve existing navigation/filter state and load/error handling. Task1 snapshot revision refreshes on change and drives history.
- [ ] Centralize actionability without turning dependency into owner; explicit other/unknown are not own overdue. Self waiting remains self with waiting dependency. Update observed readers intentionally; no automatic bulk conversion of legacy tasks.
- [ ] Guard automatic completion at proposal and commit with revision/actionability; mail release/reopen/undo cannot assign ownership. Replay/reanalysis for same source cannot create a duplicate bypass task. Original correction and source preserved.
- [ ] Test endpoint pagination/counters, all relevant readers, race at final automation commit, restart, unchanged source retry, UI editing/409/retry/reset/undo and narrow/wide rendering. No real GUI without pending permission. Independent review and commit; UI build/typecheck after actual UI edits.

### Task 3: Correction-aware conversation retrieval

**Files:** `task_status_answers.py` or focused `task_responsibility_answers.py`, `server.py` narrow conversation hooks; actual working/source/knowledge projection modules; TaskStatusAnswer/history link UI and tests. Inspect concrete source-task linkage before coding: `TaskStore.mit_quelle('episode:<id>')` is current authoritative link.
**Consumes:** Task1 current snapshot/proof and Task2 classification. No source-inferred owner as confirmation.
**Produces:** Versioned neutral owner-answer proof, current projection, bounded local ambiguity clarification, correction-aware source/task context.
- [ ] Reproduce a changed owner still missed by ordinary conversation with an invented source/task and explicit correction. Use actual authenticated request/retry/readback; no gold facts supplied as model predictions.
- [ ] Extend supported owner intent route using exact task ID/full title; ambiguous/abbreviated tasks get bounded local choices or clarification, not an old-source answer. Proof binds task revision and responsibility event; neutral persisted content; user/answer protected from model history.
- [ ] General selected source context resolves linked tasks and exposes current explicit responsibility separately from historical source report. If association is ambiguous, ask rather than asserting current owner. Bound SQL/workload. No unrestricted semantic reliability claim from regex. This integration is required, not optional after exact-title success.
- [ ] Source withdrawal removes source-dependent rendering and links without deleting explicit user decision; hidden task withholds. Later corrections invalidate old responses and retry resolves latest; original source text preserved on disk.
- [ ] Test initial/retry/reopen, reset/undo, duplicate names/titles, unrelated tasks, source changes/withdraw/archive, event-history link, old metadata, model-history isolation and changed task during response. Independently review, then grouped affected tests.
- [ ] Fresh semantic acceptance through authorized real model remains separate. Mark full P1 incomplete if unavailable; do not use exposed S05 as blind evidence. Final subplan review before grouped publication; no user installation or goal completion from technical tests.

## Execution and acceptance

Use existing isolated recovery branch, no force pushes. Implementation is already authorized by parent plan and user's autonomous continuation; no extra design-approval loop for this bounded P1 repair. Author reports hashes/logs, controller freezes reviewed revisions, independent review for each task. This subplan does not grant missing cloud/native permissions. All original sources/frozen fixtures remain unchanged. Retain the parent goal's release and usage-week gates.
