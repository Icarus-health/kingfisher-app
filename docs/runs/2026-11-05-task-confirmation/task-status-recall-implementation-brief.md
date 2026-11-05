# P1 typed task status in local conversation recall

Read this first. BASE c6903f931670de4f232334da0a79b4612a3097a1. Prior completion-confirmation A is committed/reviewed; do not redo it. This task implements B from the approved design, within the existing stores and UI.

## Exact P1 plan
### P1 — Gedächtnisaufnahme, Pflege und Abruf alltagstauglich abnehmen

**Anknüpfung:** `sidecar/icarus_memory/{ingest,mail_filter,working_memory_worker,task_review,claim_index,evidence_answer,memory_questions}.py`; `scripts/{probe_mail_intake_quality,probe_memory_core_lifecycle,probe_working_memory_end_to_end}.py`.

- [ ] Eingangsweg und Rückweg für Personen, Projekte, Aufgaben, Fristen und Anhänge gemeinsam prüfen; nicht nur einzelne extrahierte JSON-Felder.
- [ ] Bestehende Fehlzuordnungen als überprüfbare Korrekturliste behandeln. Zusammenführen und Rücknahme müssen Originale, Beziehungen und Suchergebnisse konsistent halten.
- [ ] Zeit, Eigentümerschaft, Bitte/Zusage, optionaler Wunsch, Termin/Frist und historische Nachricht in getrennten Prüffällen abdecken.
- [ ] Kostenarme Vorauswahl gegen wichtige automatische Mails und gewählte Newsletter testen. Aussortierte Quellen auffindbar halten; Fehlfilter korrigierbar machen.
- [ ] Geänderte Quellen gezielt nacharbeiten; abhängige Aktenübersichten und Abrufantworten entwerten, ohne bestätigte Nutzerfakten still zu ersetzen.
- [ ] Kleine gemischte Stichprobe und danach einen zuvor nicht zur Fehleroptimierung genutzten Satz prüfen. Cloud nur innerhalb tatsächlicher Freigaben.

**Abnahme:** Qualitätsmatrix aus Abschnitt 9 bestanden. Ein kleines freigegebenes Paket kann end-to-end einsortiert, korrigiert und wiedergefunden werden; jede ausgelassene/fehlgeschlagene Quelle bleibt sichtbar.

## Binding constraints

- Originale, stabile Identitäten, bestätigte Nutzerkorrekturen, Konten und Quellenhistorie erhalten; keine Neuinstallation mit Datenverlust.
- Gedächtnis ist die maßgebliche Wissensbasis; kein zweites konkurrierendes Agentengedächtnis.
- Quelle berichtet, Modell vermutet und Nutzer bestätigt bleiben unterscheidbar.
- Großimport erst nach bestandener Qualitätsprobe und innerhalb einer tatsächlich freigegebenen Daten-/Kostenregel; dieser Plan aktiviert nichts.
- Qwen9B und BGE-M3 bleiben Standard. Mistral und bestehende weitere Cloudzugänge sind optionale, ausdrücklich erlaubte Wege. Keine automatische Cloudweitergabe wegen lokaler Langsamkeit.
- Keine persönlichen Quellen, Schlüssel oder privaten Prüfberichte in GitHub. Öffentliche Nachweise mit künstlichen Daten; private Nachweise geschützt lokal.
- Keine Nachricht versenden, Buchung auslösen oder fremde Daten löschen, ohne passende tatsächliche Nutzerfreigabe. Wiederholte Ausführung darf keine Dubletten erzeugen.
- Keine Modellarbeit beim bloßen Blättern; Hintergrundarbeit begrenzt, unterbrechbar und mit verständlichem Fortschritt.
- App, Backend, Schema, Modulversion und getesteter Modellstand werden getrennt dokumentiert. Veröffentlicht, installiert und im Alltag bestanden sind unterschiedliche Zustände.

## Design and controller rulings
Read docs/runs/2026-11-05-task-confirmation/task-status-recall-design.md; it is the implementation design. The adjacent task-completion-recall-report.md has the original actual HTTP reproduction; completion-confirmation-report.md describes the reviewed A event contract. Follow design's store, source proof, neutral persistence, history, external/MCP boundaries and actual API/UI tests. Implement a coherent bounded end-to-end path, not just a helper or a new chat-only parallel memory.

Rulings/exact caps:
- This first path supports explicit task IDs and literal complete titles, including the ordinary unquoted status-question forms in the design. Preserve punctuation/numbers/accents. Do not invent fuzzy identity resolution or add a query model. Paraphrases and mixed source/task narratives remain explicit broader P1 gaps, not silently scored passes. Original/choice/procedure commands retain priority. Unsupported constructions must not be normalized into a different user's request.
- Lookup across all states including dropped, not all_tasks(500). A title scan stops after two distinct candidate IDs, with a 250000 SQLite-opcode budget (callback each1000) and a finally-restored handler. Reference operand max256 Unicode characters; ID point lookup can handle long titles. An interrupted scan with one result is not unique. Unknown/ambiguous/withheld responses never leak candidate titles/IDs or claim that work was never done. Literal title extensions are ambiguous as defined in design.
- Task proof uses latest per-task sequence plus active completion and explicit confirmation receipt. Current done, direct explicit confirmation, delegated/legacy unknown origin and mail-derived completion stay different. Do not invent an actor. More than100 non-state edits must not lose the real active receipt; use a bounded indexed query and visible incomplete-history result when needed. Follow A's actual event names/transaction boundaries.
- Up to two applicable source stamps: task creation and an active source-derived completion. Episode-based title/provenance requires current eligible nonarchived source/parent; ignore, replace, archive or invalid parent withholds it. Unknown nonmanual lineage cannot be silently treated as independent user text. An independently saved task remains in TaskStore after a source withdrawal; only recall projection is withheld. No creation of episodes/claims.
- Read and proof validation are local/read-only. Store selection and history come from one snapshot; reread revision around cross-store source checking. Persist only strict versioned IDs/sequences/stamps and neutral text; no title/date/source quote/duplicated user query in the assistant record, previews or search. Render at most the latest20 typed replies per conversation GET; older refs remain neutral. Old ref must not revive after reopen/recompletion, source re-admission or ID replacement. Include current top-level context in sanitization.
- Local typed lookup occurs before query-model work only when command/choice priority permits. Omit typed assistant output AND associated lookup-only user turn from subsequent normal/retry/model history. User's original question remains visible in local conversation. No new MCP or provider schema/tool and no exposure of task state to external callers. Test enabled synthetic MCP, not only the closed door.
- Add one source-like task/history action using existing taskHref and TaskDetail. Label `Aufgabe und Verlauf ansehen` only if cited receipt really opens there, including receipts beyond latest100 history entries; a bounded task-scoped sequence query on existing history endpoint is authorized. Preserve back/navigation state. For dropped tasks expose existing history component rather than inventing a second viewer. No restyling.
- Meaningful independent synthetic cases only. Frozen acceptance fixtures unchanged and no reclassification of their gates as passed. No additional model, provider, UI browser, key, personal store, real calendar, import or cloud authorization. No installs/downloads, commits/pushes/releases or subagents. No broad refactor. If a precise design inconsistency is found, stop with the smallest decision needed rather than silently relaxing a requirement.

Tests: use the design's four-step sequence, focused failing regressions before code; actual TaskStore and authenticated create_app routes with synthetic provider and no-network hooks. Cover title ambiguity beyond500 including dropped, ID disambiguation, scan-interrupted recovery, events beyond100, exact current confirmation, unknown actor, stale/re-admitted/reopened data, immutable originals, provider/history/retry/MCP non-egress, read-only behavior, and the actual UI link+history route. Reuse working targeted suites; no full backend. UI may use copied source + existing node_modules for typecheck/unit tests; no GUI/localhost browser or protected running draft.

Repo /Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/kingfisher-product-readiness-20261105. Python /private/tmp/kf-core-20261104-env/bin/python with PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. . Synthetic temporary stores only. Working tree clean at dispatch.

Report .superpowers/sdd/2026-11-04-kingfisher-product-completion/task-status-recall-implementation-report.md: exact commands/results, changed files/hashes, privacy/readback contracts, explicit scope boundaries and actual supported questions. Return status and one-line results only. No subagents or self-appointed independent review.

Controller ruling during implementation: literal-title normalization must preserve German spelling distinctions such as Masse vs Maße. Broad Unicode casefold merges them and can falsely resolve the only present task. Use NFC with conservative case normalization (lower preserves ß vs ss) or explicit ambiguity rather than silently assigning identity; test uppercase ẞ as well. This supersedes the design's casefold suggestion, not the bounded lookup scope.

Controller ruling on lookup capture: preserve the original question in ConversationStore with server-owned strict typed/lookup-only flags, but skip conversation_memory.capture and source_capture_expected on this path, including retry. No new episode or claim is created by a pure task lookup. Ordinary capture remains unchanged; model and client must not forge the flags. Test source counters, pending/error readback and model history.

Controller ruling on shared source support: an opt-in require_unarchived snapshot mode may reject archived parent sources and incorporate parent support generation for this task projection. The existing default mode must preserve its behavior and fingerprint bytes. No source migration, backfill or implicit claim invalidation. Test unchanged legacy support alongside withdrawal/re-admission of the parent. This is an explicit shared-contract risk for the independent task review.

Ruling fix01 I2: allow EpisodeStore migration 27 with one private recall_archive_generation column (default0) and a verified trigger that advances it when entering archived. The task-only fingerprint includes it (including zero) for direct source and recursively its parent; legacy support_generation, Episode serialization and default fingerprint bytes remain unchanged. This supersedes the original no-migration restriction only for this marker: no suitable existing marker records archive/re-admission, and without one stale answers can revive. Cost if wrong is schema/update compatibility, so require actual v26 upgrade preservation, migration rollback/schema-verification coverage, strict direct/parent cycles and existing default-source support tests. Only isolated synthetic stores now; personal migration still needs normal backup/update. I1 restore provenance remains bounded and must fail closed when history cannot establish origin; old confirmations must not be promoted.
