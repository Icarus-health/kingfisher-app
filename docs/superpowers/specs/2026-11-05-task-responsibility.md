# Bestätigte Aufgabenzuständigkeit — P1-Ergänzung

Umsetzung innerhalb des freigegebenen Produktplans vom 04.11.2026. Dies ersetzt
weder den Gesamtplan noch seine Modell-, Mac- und Alltagsabnahme. Die folgende
Bestandsaufnahme beschreibt Optionen; die verbindlichen Entscheidungen darunter
lösen ihre offenen Punkte auf. Keine neue Nutzerfreigabe ist für diese bereits
beauftragte Korrektur nötig. Cloud, echte Daten und native Freigaben bleiben separat.

# P1 task responsibility — bounded architecture evidence

Read-only reconnaissance against requested base f4be125; no product edits, tests, models, network, GUI, personal stores, or frozen-fixture changes. This report is the only added artifact. Frozen S05 is exposed contract evidence, not a new blind acceptance result.

## Diagnosis and recommendation

The existing stores can carry this contract without a second identity registry or SQL table migration. The smallest coherent implementation is an additive responsibility record in Task JSON, append-only responsibility events in the existing task_events, a visible TaskDetail correction flow, shared task classification, and a local typed ownership-answer projection in the real conversation path. Responsibility is a user decision about one task, not a person fact or an authenticated actor claim.

Two materially different fields already exist and must remain distinct:

- `Task.person` is explicitly the requester/counterparty (`tasks.py:178`, `from_suggestion(..., person=...)`), not the execution owner.
- `wartet_auf` describes a waiting dependency but currently doubles as ownership: `is_overdue`, `wartend`, task-page SQL, project counters, TaskDetail, TaskRow, briefing and mail automation all infer “mine” from its absence. Waiting for an answer must not transfer execution responsibility.

Viable alternatives: (A) additive JSON/events, recommended; (B) a dedicated responsibility table with the same UX, history and projection semantics, technically viable but needless migration/join/atomicity surface here. Reusing `person`, changing only `wartet_auf`, putting the answer into task notes, or adding an API without UI/conversation integration does not meet the contract. A general Matter model or universal semantic parser is unnecessary.

## Existing interfaces and constraints

- `sidecar/icarus_memory/tasks.py`: Task dataclass, `to_dict`, `_from_row`, `_state`/`_HISTORY_FIELDS`, `_write`, `_append_event`, `_transaction`, `history`, `history_event`; `completion_snapshot(task_id)` already returns a per-task max-event sequence. `confirm_completion(..., expected=TaskCompletionSnapshot)` demonstrates transactional revision checking. `_change` writes only if tracked state changes. `edit` deliberately excludes titles/notes from history. New JSON fields must be explicitly loaded: unknown fields currently disappear on the next serialization.
- History SQL schema is fixed and verified, with append-only UPDATE/DELETE/REPLACE protection. Extend the JSON state whitelist and event kinds, not columns/triggers. Old records lack the new field and must remain valid without rewriting their history. `actor_id` stays null. `test_task_history.py` already checks restart, noop, rollback, two-connection behavior, legacy gaps and absence of source/title/notes in history.
- `server.py:5359–5380`: exact GET task and GET history (including a selected event sequence). `5458–5470`: PATCH details and 404/409/422 mapping. Current task GET has no revision; return a revision from the same read snapshot as the document, not a separate racing completion_snapshot call.
- Identity is address-first: `personen.Person.anker` is `a:<address>` or name-only `n:<name>`; `personen.eine(...)` raises `Mehrdeutig` for ambiguous names. GET `/people` and `/people/{name}` (`server.py:6274–6316`) already pass current confirmed merges and own addresses. `person_merges.py` stores reversible confirmed groups while preserving members. Do not invent a parallel identity registry or use a group ID as the durable task anchor.
- Self-address authority currently is `server._eigene_adressen()` → `identitaet.eigene_adressen(settings)`, collecting mail/calendar account identities. A profile display name is not identity proof. No separate stable authenticated self-person ID was established by this reconnaissance; use an explicit `self` selection scoped to the local user profile, rendered “Ich”. Do not infer self from a matching name. This is a concrete architecture limitation, not a reason to create a new registry.
- `app/kingfisher/src/TaskDetail.tsx`: exact task loader, `change` mutation/lifecycle guard, reusable success/undo notices. `TaskRow.tsx` embeds TaskSource and TaskHistory; its history refresh key needs responsibility revision. `api.ts` defines Task, TaskHistoryEvent and request methods. Existing errors preserve user input but need a specific 409 refresh/review state.
- `task_status_answers.py` already offers local exact-ID/full-title resolution, neutral stored text, revision/source checks, `storage_context`, `hidden_from_history`, `project_message`, and links to a history event. Server integration is real: conversation read projection ~4365, initial lookup ~4829, neutral answer ~4939, retry ~5271, history filtering ~4686/4696/5259. Existing parser covers completion/status questions only; it is not semantic ownership retrieval.

## Proposed state and commands (new interfaces, not existing APIs)

Use `responsibility: null | {version:1, decision:'self'|'person'|'unknown', anchor:null|{kind:'address',address:string}, label:string|null}`. Null/missing means legacy unconfirmed; `decision:'unknown'` is a durable explicit reset and must never collapse to null, missing, self, or a newly extracted source owner. An explicitly confirmed address is the identity anchor; label is a bounded user-reviewed presentation value, not matching authority. `self` and `unknown` have no address. Keep requester `person`, source provenance/quote, and `wartet_auf` unchanged.

Store event kinds `responsibility_confirmed`, `responsibility_reset`, `responsibility_undone`; `_HISTORY_FIELDS` includes the bounded responsibility object plus a bounded operation marker (request ID, canonical request digest, and undo target sequence if applicable). Do not copy original source text, titles or arbitrary reasons into immutable history. Events supply confirmation time/sequence, with actor unknown. An explicit confirmation event means the local user action was recorded; it does not identify the person who clicked.

Proposed guarded route: `POST /api/v1/tasks/{id}/responsibility` with `{request_id, expected_revision, confirmed:true, operation:'set'|'reset'|'undo', owner?, target_event_sequence?}`. New `TaskStore.change_responsibility(...)` validates and writes document+event under `_transaction`. Return updated Task plus atomic revision. A reused request ID with a different canonical request is 409. Replay of an already committed identical request is acknowledged without another event, even if the original response was lost; return current state and applied-event sequence so the UI cannot display an old success payload as current. Implement receipt lookup as a task-ID-scoped SQL query over responsibility event kinds and `json_extract(after_state, '$.responsibility_operation.request_id')`, using the existing `(task_id, sequence)` index. Search the entire task history, not the 100-entry UI page; impose a SQLite progress budget and return explicit retryable 503 if the lookup cannot complete, never treat an incomplete lookup as absence. Match canonical digest before acknowledging. This needs no new table/index; consider an indexed receipt migration only if measured cost later justifies it.

Order: check prior request receipt first, then compare max task-event sequence, validate command and selected identity/source preview, then write. Revision mismatch is 409 and preserves the draft. Identical confirmation with a fresh request and matching revision is a noop, unless intentionally re-confirming after an explicit reset. Undo is a new compensating event, never event deletion; only undo the referenced responsibility transition when no later responsibility transition intervened. Require current revision even if intervening changes touched another field, so the user sees what they are confirming. Undo of the first confirmation yields durable `unknown`, not the old inferred-self state. Undo of a reset can restore the preceding explicit self/person decision. A second reset keeps the durable barrier and is a noop.

Cross-store validation: mirror `TaskCandidates.amend_title` lock order (application lock → episodes reservation → store transaction), rather than reading identity/source and later committing an unchecked task write. Capture only the chosen identity's stable address/member material in a preview token; unrelated incoming mail must not invalidate it. Re-resolve under the relevant locks immediately before commit. Existing person merge writes also need to participate in the same application coordination or be rechecked; TaskStore's SQLite lock alone does not lock knowledge/episode databases. Do not claim globally atomic cross-database proof without that integration.

## Identity selection and source semantics

TaskDetail presents “Verantwortlich: Ich / Person auswählen / Ungeklärt”, shows requester separately, and shows “Wartet auf Antwort von …” separately. The submit button says “Zuständigkeit bestätigen”. Provide reset (“Zuständigkeit ungeklärt lassen”) and a revision-bound undo notice. Compact rows show the current confirmed responsibility; history distinguishes confirmed, reset and undone. Include dropped/done task detail, rather than hiding the correction field inside the open-task branch.

Reuse `/people` for choices, always displaying an address when choosing another person. Ambiguous display names require selection; name-only contacts cannot become confirmed person anchors. For a merged person with several addresses, select the exact address being confirmed; a later merge/split changes available display/context, not that anchor or the recorded decision. If an address is later listed among own accounts, do not silently convert the stored person decision to self: show a conflict for explicit review. Unavailable contact evidence does not erase a previously confirmed address decision. Avoid fresh source-derived names in the answer when their source is unavailable; the exact user-confirmed address remains the bounded fallback.

Retain source report as source evidence: original `Task.provenance`, TaskSource and source review remain available according to source visibility. A source report is neither rewritten by correction nor promoted to the current confirmed owner. If an explicit machine source-owner field is added at intake, it must be a separate `reported_responsibility` with episode ID and support fingerprint, nullable for old tasks; never backfill it from requester or waiting. Do not invent an owner report where the existing extraction does not contain one.

Exact invalidation rules:

- New analysis, newer mail, title/date/project/status edits, waiting/release changes, unrelated identity data, and source text revisions preserve an explicit self/person/unknown decision. They can mark the source report stale or conflicting; they cannot overwrite it.
- A source-dependent report is invalid when its supporting fingerprint/body/context changes, source is excluded/withdrawn/archived/unavailable, or current evidence is outside the allowed scope. The report then becomes unavailable/stale, not current ownership. `belegbarer_snapshot(..., require_unarchived=True)` is the existing recall guard; intake also checks task context/digest/quote in `task_candidates.py`.
- A user-confirmed task decision is independent of the old source's continued truth. Source withdrawal removes source-derived rendering/links but does not secretly revoke that decision. Render “Zuständigkeit ausdrücklich bestätigt; ursprüngliche Quelle nicht verfügbar” only if task visibility itself still permits the task. This requires a distinct owner-proof branch: current status `_stamps` withholds non-manual tasks if creation source disappears, so it cannot be reused unchanged.
- Deleting/hiding the task itself withholds the answer. Only explicit new confirmation/reset/undo changes responsibility. Scope/privacy revocation can prevent rendering; it is not a reassignment. Historical source claims are shown as “damalige Angabe”, never current instructions.

## Task views and automation integration

Centralize effective responsibility and actionability in Python and export derived flags; mirror them in SQL predicates for complete pagination/counters. Confirmed-other and confirmed-unknown never count as the user's execution work or personal overdue work. Confirmed-self may still be waiting for someone else's input. Clearing waiting does not change responsibility.

Keep waiting dependency as a separate filter. Add a compact responsibility view/filter “Bei anderen” and “Zu klären” for explicit other/unknown, or a single all-open list with those filters; do not silently put confirmed-other into “Wartend” when nobody is waiting. Legacy records may keep their previous provisional classification, visibly unconfirmed; explicit unknown must remain in “Zu klären” across restarts/reanalysis. This is a necessary small UX extension, not API-only scope.

Concrete affected readers: `tasks.is_overdue`, `wartend`, `project_overview`, `task_pages.query_page`; `briefing.py` (including source `wartet`), `kommendes.py`, `offene_punkte.py`, `graph.py`, `personen.py`, `akten.py`/`akten_markdown.py`, `mappe.py`; UI TaskDetail, TaskRow, TodayTaskRow (currently synthesizes `wartet_auf:null`), taskWorkspaceModel and task pager. Classify all current `wartet_auf` consumers by waiting dependency vs ownership before editing; do not mechanically replace every waiting check.

`aufgaben_post.py` uses `open_tasks(limit=None)`, `_treffer`, then `post_erledigen`/`post_zurueckholen`; it currently decides own completion from absence of waiting and recipient return from presence. Prevent automatic own completion for confirmed-other/unknown at both proposal and final mutation time. Mail arrival may clear a waiting dependency but may not say “wieder bei dir” unless execution owner is self; do not change owner on return, reopen or post undo. Bind final automation changes to a task revision so a correction during analysis cannot be lost. Reanalysis/auto acceptance in `aufgaben_von_selbst.py` and `TaskStore.from_suggestion` must retain correction for the same task and avoid a duplicate old-source task bypassing the barrier; any replacement task must explicitly link/supersede rather than silently lose the decision.

The inspected `wiederkehrendes.py`/routes concern recurring knowledge/calendar items, not a proven recurring Task creator. Do not invent such an interface. Repeated background passes and existing intake retries are the actual observed recurrence risk here; test those. If another task-generation path is found during implementation, apply the same decision preservation rule there.

## Conversation and recall boundary

Extend the typed local path with an explicit owner question kind (e.g. “Wer ist für die Aufgabe <ID/full title> zuständig?” and “Wer kümmert sich um <full title>?”). Keep completion interpretation unchanged. Add a versioned owner proof with task revision, active responsibility-event sequence, and any actually used identity/source-support stamps; store only neutral content/reference metadata. Render from current task/event proof and link to TaskDetail's selected history event. Reopen old conversation messages only after exact revision proof; stale messages become unavailable and retry recomputes the latest decision, never resurrecting the former one. Both question and answer stay outside downstream model history through the existing flags/filter machinery.

An ownership-intent question whose task operand is ambiguous, abbreviated or semantic must first get a local clarification (“Welche gespeicherte Aufgabe meinst du?” plus bounded current task choices), not fall through to the language model with the old source note. Apply this to normal `/conversation` and retry paths, not only an isolated endpoint. Initial bounded phrases can cover everyday formulations; document them honestly. Reusing existing exact-title matching for an owner branch is useful but is not arbitrary semantic recall.

There is a residual semantic gate: arbitrary paraphrases or broader questions may still retrieve the old source via general context. The full P1 acceptance contract must require correction-aware context assembly that exposes the current task decision alongside its historical source and prevents the source report from being presented as current owner. Resolve candidates locally from linked task/source IDs where available, then route to typed rendering or clarification. Where semantic association is needed, do not certify completeness from fixtures/regex alone: evaluate fresh independent cases through the actual conversation/model route under separately authorized model conditions. This reconnaissance does not establish that an unrestricted model answer can never contradict a correction. If that general path remains enabled without verified routing/projection, report P1 recall as incomplete; an exact-title-only pass is insufficient.

## Bounded validation matrix and open implementation checks

Use newly invented examples such as “Prüfadapter nachmessen”, requester Niko, source-reported Elif, confirmed owner Mara at `mara@example.invalid`; do not adapt frozen S05.

| Area | Required evidence |
|---|---|
| Storage/history | Old JSON/history load unchanged; self/person/unknown survives edit/restart; actor null; no title/source quote in events; transactional rollback; repeated identical requests/noops; conflicting request IDs; two-connection CAS; undo target/stale undo; replay beyond 100 events. |
| Identity | Same name/two addresses forces choice; name-only rejected; exact address retained after merge/split; self uses explicit profile-local selection; own-address drift is visible; source/identity changes during confirmation conflict. |
| UX/API | Exact task detail including done/dropped; confirmation/reset/undo; 409 preserves draft; response loss retry; readback shows latest revision; compact label, requester and waiting remain separate; history deep link. |
| Classification | Self waiting for another remains execution owner; other without waiting is not mine; unknown without waiting is not mine; counters/overdue/pages/briefing/Today/graph agree; no page-size blind spots. |
| Automation | Correction during a mail decision invalidates commit; completion/release/reopen/post undo cannot transfer owner; repeated source analysis preserves reset/confirmed owner and does not create a bypass duplicate. |
| Sources | Body/context revision, withdrawal, archive, deletion and scope change invalidate source report; user decision preserved with bounded display; hidden task withholds; no original source text copied into events/conversation storage. |
| Real conversation | Initial question, retry, reopen, revision change, unavailable source, duplicate title, abbreviation clarification; no owner claims in model history; unsupported semantic requests fail closed/clarify within supported owner-intent routing. |
| Later semantic gate | Fresh cases across paraphrases and broader recall, actual allowed model configuration, current ownership beats old source or requests clarification. Report observed support honestly; exposed S05 cannot count as blind evidence. |

Before implementation, settle three concrete points: (1) exact UI/filter placement for other/unknown without conflating waiting, (2) the shared application-lock participation of identity merge/source/task mutations, and (3) the existing general-context source-to-task linkage used to intercept unsupported ownership recall. These are implementation decisions/read checks, not grounds to expand into a new identity store or universal parser. No product acceptance is claimed by this document.

## Verbindliche Entscheidungen des Controllers

1. JSON-Zuständigkeit und bestehende Ereignishistorie verwenden, keine neue
   Personen- oder Wahrheitstabelle. `responsibility` ist null (Altbestand) oder
   `{version:1, decision:'self'|'person'|'unknown', address:str|null, label:str|null}`.
   Fehlend/null bleibt unbestätigt; ausdrückliches unknown ist dauerhaft. Requester
   und Wartedependenz werden nicht umgeschrieben.
2. Eine Korrektur ist eine ausdrückliche Aussage des lokalen Nutzers über eine
   konkrete Aufgabe. Für person bestätigt er eine vollständige Adresse und optional
   einen Anzeigenamen, nicht die Wahrheit einer automatisch hergeleiteten Akte.
   Kontaktvorschläge sind lediglich Eingabehilfen. Dieselbe ausgewählte Adresse
   bleibt nach Merge/Split bestehen; kein Gruppen-ID-Anker und keine Namensheuristik.
   Name ohne Adresse wird zurückgewiesen. Der gespeicherte Anzeigename ist als vom
   Nutzer bestätigter Text zu behandeln. So ist keine neue atomare Transaktion über
   Kontaktgraph und Aufgabenbank nötig. Bei späterer Überschneidung mit eigenen
   Kontoadressen ist eine sichtbare Klärung nötig, keine stille Umwandlung in self.
3. Jede neue ausdrückliche Bestätigung/reset/undo mit eigener request_id erhält
   eine Ereignisquittung, auch bei gleichem Zustand. Dieselbe request_id mit gleichem
   kanonischem Inhalt wird ohne weiteres Ereignis bestätigt; anderer Inhalt ist409.
   Die UI verhindert unveränderte erneute Speicherung und behält die request_id bei
   unklarem Antwortausgang. Das ist eine bewusste Abweichung von der optionalen
   Noop-Empfehlung der Bestandsaufnahme: keine unquittierten erfolgreichen Requests.
   Quittungen liegen nur in bounded Event-Metadaten, nicht in einer neuen Tabelle.
4. Eine Revision bindet genau den vom Nutzer gesehenen Aufgabenstand. Undo ist ein
   neues Ereignis; es darf nur die letzte Zuständigkeitsänderung zurücknehmen und
   braucht die aktuelle Revision. Vor der ersten expliziten Zuordnung war nichts
   bestätigt: Undo führt dann zu ausdrücklich unknown, nicht zu vermutetem self.
5. Vorhandene Aufgabenansichten bleiben. Zwei kleine Filter `Bei anderen` und
   `Zu klären` machen explizite person/unknown zugänglich. `Warte auf andere`
   bleibt unabhängig davon eine Antwort-/Zuarbeitsabhängigkeit. Eigene Aufgaben,
   Überfälligkeit und Briefing dürfen person/unknown nicht als eigene Ausführung
   ausgeben. Keine neue Hauptnavigation.
6. Bestätigte Zuständigkeit gilt unabhängig von einer später veralteten Quellennotiz.
   Entzug entfernt Quellentexte/Belege aus der Antwort, nicht still die Nutzerentscheidung.
   Verborgene/entfernte Aufgabe liefert keine Antwort. API und Modell behaupten
   keinen verifizierten Akteur; actor_id bleibt null. Keine Quellenvolltexte in Events.
7. API allein ist keine Fertigstellung. Bedienung, Listen/Automatik und Gespräch
   müssen vor Freigabe zusammenpassen. Explizite Eigentümerfragen werden lokal
   beantwortet oder geklärt. Bei allgemeinem Quellenabruf müssen verknüpfte aktuelle
   Korrekturen neben der alten Quellenangabe berücksichtigt werden. Ein lediglich
   exakter Titel-/ID-Test reicht nicht als allgemeine Abrufabnahme. Neue semantische
   Fälle und echte Modellprobe bleiben erforderlich; exponiertes S05 ist kein Blindtest.
