# Answer validity audit — 2026-09-21

Nachtrag 2026-09-23: A6 und die aktuelle Anzeige quellgebundener alter Antworten wurden weiter abgesichert; siehe [geprüfter Änderungsstand](../../runs/2026-09-23-pending-conflicts/README.md). Die folgenden Befunde dokumentieren weiterhin den ursprünglichen Auditstand.

Basis: `Icarus-health/Kingfisher`, main `7e397db87103539cdb93a986e0e15d9e81d26bfd`, checkout `../memory-audit-20260921`. Source review plus bounded synthetic SQLite/API tests; no private data, external requests, real model, downloads, or commit. Initial audit was read-only. Root subsequently authorized the minimal display-label fix described below; other findings remain open.

## Assessment

The current evidence-answer path establishes the availability and continuity of stored claims and their sources. It does **not** establish that the chosen statement answers the question, accurately interprets the original, resolves an open conflict, or is objectively true. The implementation itself sets `semantic_validation: False`. The ordinary conversation route additionally accepts unvalidated model prose for many ordinary factual questions. These are material limits for reliable Chief-of-Staff use, not evidence of a measured real-model error rate.

| Contract / behavior | State | Evidence |
|---|---|---|
| I-04: explicit evidence-path negative answer limited to retrieved evidence | Implemented in this path | Fixed unknown text, no global absence claim; A5 reproduction. Ordinary chat has only prompt guidance. |
| COV-01/03: processing states and input-limit visibility | Partial | `memory_routes.py:14-45` records bounded source-processing counts, scope and `semantic_completeness=False`. `agent.py:535-536` adds retrieval-limit warning. |
| COV-02/04: answer contains scope/coverage/gaps as well as sources | Partial | Evidence answer stores search metadata, but does not attach processing coverage or explain pending sources; A5. No complete account/channel/attachment snapshot demonstrated. |
| T-KNOW-01: preserve negation/conditions/attribution without false commitment | Partial | Source quotes/digests checked and unconfirmed candidates excluded from knowledge context. Renderer copies a stored claim; it cannot validate its interpretation because projection omits source quote. Existing negation tests use claim text identical to original. |
| Answer reference/schema integrity | Implemented | Closed JSON evidence IDs, at most five, tool requests and malformed outputs fail to deterministic fallback; 184 focused tests green after label fix. |
| Question relevance and semantic truth | Missing as deterministic guarantee; not statistically evaluated | `agent.py:442-445,452-453`, `evidence_answer.py:1-5`; ordinary factual routing and conflict reproductions A2/A6. |
| T-DEL-01: withdrawn sources in new selection/model input | Implemented in exercised paths | Revalidation before/after selection; withdrawal, expiry, generation tests green. A3 confirms source marker absent from next real Agent/provider-double input. |
| T-DEL-01: historical answer remains distinguishable from current valid knowledge | Partial | Current sidebar context is filtered, but old message text and context metadata remain unchanged with `status=evidence`; A3. |
| T-DEL-01: real deletion across content stores/export/restore | Not established by this bounded sub-audit | Ignore is a withdrawal, not a deletion. No claim that retention after Ignore violates deletion policy. Root/other audit covers broader deletion/restore. |
| docs/23 conflict handling before recommendations | Partial / open failure | Conflict exists in protected clarification interface but evidence answer does not expose it; A6. |
| Clear overview without forced clarification | Partial / open failure | Distinct reference tuples force an exclusive-choice clarification even for a clear project overview; A4. |

## Findings

### A6 — P1: Known open contradiction is omitted from the answer

**Trigger:** An accepted claim says the Aurora deadline is 22 September. A second source and pending candidate say 26 September, using the same subject, predicate and context. `KnowledgeService.clarifications()` correctly returns the open conflict.

**Observed:** `answer_memory('Welche Frist gilt für Aurora?')` returns the 22 September claim with `status=evidence`; neither the competing deadline nor any conflict warning appears. This remains true after the label fix. The response may encourage reliance on a disputed deadline despite the system already knowing that a decision is required.

**Source:** `sidecar/icarus_memory/claims.py:291-299,692-720` constructs conflict semantics/list. `sidecar/icarus_memory/knowledge_context.py:33-45` checks status, validity and quote availability, not pending contradictory candidates. `sidecar/icarus_memory/agent.py:318-341,467-479,496-530` retrieves accepted claims and renders them without consulting clarification state. `docs/23-vernetztes-gedaechtnis.md:18-33` requires unresolved alternatives not to be used unmarked.

**Reproduction:** `test_answer_validity_audit.py::test_open_conflict_does_not_mark_old_answer`; observed pass confirms current faulty behavior. `answer-conflict-observation.json`, `answer-conflict.log`.

**Remedy direction:** Carry relevant unresolved-conflict state into the same answer/input validity contract; show both claims/context and the required decision without silently selecting the old accepted assertion. Do not erase accepted history or make all unrelated pending candidates invalidate everything. No production fix performed here.

### A2 — P1: Common factual questions bypass the restricted answer contract

**Trigger:** Default conversation asks `Wer ist für Aurora verantwortlich?` when the stored claim explicitly says Mira is responsible. A provider double deliberately returns Jan plus an unsupported 30 September deadline.

**Observed:** The real conversation API delivers that entire wrong response unchanged, with no `answer_contract`, despite the correct claim reaching the model input. Routing is controlled by narrow leading-word regular expressions:

| User phrase | Default route |
|---|---|
| Wer ist für Aurora verantwortlich? | chat |
| Bis wann muss Aurora fertig sein? | chat |
| Welche Aufgaben habe ich noch offen? | chat |
| Habe ich Mira etwas zugesagt? | chat |
| Welche Frist gilt für Aurora? | memory_evidence |
| Kannst du mir sagen, welche Frist für Aurora gilt? | chat |

**Source:** `sidecar/icarus_memory/memory_routing.py:8-33`, `server.py:2666-2685`, `agent.py:806-809` copies `reply.text`. The same semantic request has a different truthfulness boundary based on wording. `agent.py:773-775` only instructs the ordinary model not to infer global absence.

**Reproduction:** `test_common_factual_question_uses_unvalidated_chat_prose`; `answer-validity-observations.json` A2. This is a deliberately wrong provider result to measure enforcement, **not** proof that a natural model produced this error or an estimated frequency.

**Remedy direction:** One consistent factual-answer contract across natural wording, including safe handling of lack of evidence and critical structured fields. Do not try to solve the entire issue with isolated regex additions. Open; no routing change performed.

### A1 — P2, display bug fixed: Stored interpretation was labelled as original source content

**Trigger:** A real original says `Mira: Wenn die Freigabe kommt, prüfe ich Aurora am Freitag; bis dahin gibt es keine feste Zusage.` A separately supplied, explicitly accepted faithful paraphrase says `Mira prüft Aurora am Freitag nur nach Freigabe; eine feste Zusage liegt noch nicht vor.` Its stored value is `bedingt, keine feste Zusage`.

**Before:** The reply began `In den ausgewählten Belegen steht:`, placed the paraphrase in quotation marks and labelled the value `Wert laut Quelle`. The source reference existed, but neither this paraphrase nor the stored value were quotations from it. The selection model never received the original quote. This reproduction does not require a false user confirmation or automatic promotion of wrong content.

**Source:** `knowledge_render.py:29-41` copies `claim.statement`, `claim.value` and source metadata, but not `Evidence.quote`; `claims.py:651-686,778-788` permits separate claim and quote while checking actual quote presence. At baseline, `evidence_answer.py:212-225` mislabelled the resulting claim. Existing `test_action_states_and_attribution_are_original_evidence_not_new_facts` passed because its fixture set claim text equal to source text.

**Implemented minimal fix:** `evidence_answer.py` now says `Gespeicherte Aussagen mit Quellenbezug`, `Gespeicherte Aussage`, `Gespeicherter Wert`, and does not add quotation marks around statement/value. Escaped line breaks are retained. Fallback and clarification entries get the same truthful labels; source IDs and timestamps stay available. Technical rendering calls them stored statements. No `knowledge-context-v3` schema, provider-selection, history, or source-lifecycle change.

**Validation:** Three mode-specific regression cases and one real accepted-paraphrase integration test failed on the original renderer (four expected failures in `answer-label-red.log`), then passed after the fix. `answer-label-green.log`: **184 passed**, two dependency deprecation warnings. This fixes the label, not semantic selection or verification of the accepted interpretation.

### A3 — P2: Retained old answer has no withdrawal/current-validity marking

**Trigger:** Generate an evidence answer containing a unique synthetic source marker; call the real `/episodes/{id}/ignore` endpoint; reopen the conversation.

**Observed:** Top-level current context contains zero items. The old assistant message content and metadata are byte-for-byte unchanged and its old answer contract still says `status=evidence`. UI prints `message.content` and has no current-validity marking for such ordinary assistant answers. A future ordinary chat request correctly excludes the marker from the model input.

**Source:** `server.py:2517-2554` filters the separate current context but returns all `message.to_dict()` unchanged. `app/kingfisher/src/App.tsx:474-485` renders the content. The status labels at `478-481,494-496` are attached to memory-candidate cards, not general historical answers. `agent.py:685-709,1213-1271` validates/excludes model history.

**Reproduction:** `test_withdrawal_keeps_historical_answer_unlabelled_but_blocks_next_input`, observations A3. The historic text is not alleged to be a new model-input leak. Ignore does not mean deletion, and historical retention itself is allowed. The defect is that the visible old claim's current usability is not distinguished from its historical status.

**Remedy direction:** Preserve history while adding server-computed per-answer validity/withdrawal context in the owner UI. True deletion requires its own explicit scope and lifecycle. No production fix performed here.

### A4 — P2: Multi-person project overview is treated as exclusive identity selection

**Trigger:** Two accepted claims: `Mira prüft Aurora am Freitag` and `Jan liefert Aurora am Donnerstag`, both linked to `project:aurora`; ask `Was wissen wir über Aurora?`.

**Observed:** Both relevant rows are found, but the response is `Welchen Eintrag meinst du?`, `status=clarify`, `model_called=False`. An overview naturally needs both records; distinct people are not ambiguity in which project the user asked about.

**Source:** `evidence_answer.py:60-64` treats any difference in `(subject_ref,target_ref,scope_ref)` as ambiguity; `agent.py:496-499` asks before model relevance selection. `continue_memory` chooses within that fixed set, so it does not perform a project synthesis. This is an avoidable burden/absence-of-answer under I-12 and RET-02, while conservatively preventing identity conflation.

**Reproduction:** `test_multi_person_project_overview_forces_choice_without_ambiguity_in_question`, observations A4.

**Remedy direction:** Distinguish an actual ambiguous identity/reference from a query that requests several related records; preserve canonical IDs in either case. Open.

### A5 — P2: Bounded unknown omits an actionable processing gap

**Trigger:** Import a source containing the Aurora deadline, leave it unprocessed/unaccepted, ask `Welche Frist gilt für Aurora?` through the explicit evidence path.

**Observed:** Honest but generic `Das kann ich mit den gefundenen Belegen nicht beantworten.` No `coverage` field or processing-gap explanation is attached to that answer. The real coverage endpoint simultaneously reports one pending source. It is correct that an unconfirmed source is not automatically promoted to accepted knowledge; the missing information is what was searched and why the answer is absent.

**Source:** `agent.py:467-479,535-536` attaches search metadata/limit warning but never calls its coverage callback in `answer_memory`; ordinary `send` does so at `770-775`. `memory_routes.py:14-45` contains the available source-processing coverage. `App.tsx:465-467` only shows current selected context.

**Reproduction:** `test_pending_source_returns_unknown_without_processing_gap`, observations A5.

**Remedy direction:** Document the selected searchable corpus and applicable processing/scope gaps in the response; if useful, offer a bounded permitted source search without presenting unreviewed extraction as confirmed fact. Open.

## Verification and files

- `answer-validity-observations.json`: five baseline synthetic observations before the label change.
- `answer-validity-focused.log`: **185 passed** (five audit reproductions + 180 existing targeted tests), before production fix.
- `answer-label-red.log`: **4 failed** on expected missing truthful labels; no fixture/setup error.
- `answer-label-green.log`: **184 passed** (180 existing + four new regression cases), after the fix.
- `answer-conflict-observation.json`, `answer-conflict.log`: one additional open-conflict reproduction, after the label fix.
- `answer-validity-repro.log`: initial scratch run had one test-harness TypeError from treating `ProposalStore` as a context manager; harness corrected to `try/finally`, superseded by the successful focused run. This was not a production defect.
- `test_answer_validity_audit.py`: scratch-only reproduction script; tests intentionally assert observed gaps, so green does not mean these gaps are acceptable. Baseline JSON is retained as baseline evidence and was not rewritten after the fix.

Command environment: `PYTHONPATH=sidecar:scripts python -m pytest ... -q -p no:cacheprovider --basetemp=docs/evaluations/memory-quality/audits/2026-09-21/<unique-test-directory>`.

Focused existing files: `test_evidence_answer.py`, `test_memory_evidence_answers.py`, `test_readable_memory_answers.py`, `test_memory_clarification.py`, `test_memory_routing.py`, `test_source_exclusion.py`, `test_knowledge_time.py`, `test_memory_routes.py`. No full suite or browser flow run by this sub-agent. API tests use in-process ASGI clients and synthetic local provider doubles.

Owned production edits: `sidecar/icarus_memory/evidence_answer.py`, `sidecar/tests/test_memory_evidence_answers.py`, `sidecar/tests/test_readable_memory_answers.py`. Other shared-worktree edits belong to root/other agents. No commit made.
