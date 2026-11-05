# P1 confirmed task completion in memory recall

Read this first. BASE b906d43956abee9caf33fee5a0602eb60fa0d3d9. This is one bounded product repair, not overall memory acceptance.

## Exact plan text
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

## Observed gap / task
The source-state audit in docs/runs/2026-11-05-memory-source-acceptance/state-contract-at-ff2f075.md (S04) found that real task completion/history are not ordinary evidence-recall inputs. Older mails can remain the only evidence even after a user confirms completion. Inspect and reproduce this against the current real app wiring before editing. Use new synthetic examples, not a renamed frozen heldout expectation.

Bounded desired behavior: an unambiguous question about a task that the user has explicitly completed in Kingfisher must have access to that current saved decision, with truthful status, timestamp, task identity and a directly inspectable task/history link. Older source reports remain historical source reports and must not silently override the saved user decision. Reopening/dropping and confirmed-source withdrawal must not leave a stale completion claim in a saved conversation or subsequent model history. Dropped is not completed; model-suggested completion is not user confirmation. Two tasks with similar titles must not transfer status or identity. The repair is read-only for retrieval; it must not complete/reopen tasks or create extracted facts to make an answer appear supported.

Trace ordinary strict evidence mode and existing special task routes before choosing a change. Prefer the existing evidence/refresh/status mechanisms. Do not broaden external model/MCP access, send task data remotely, or expose all task history by default. Keep working set bounded. If a correct fix requires a new evidence contract, broad parser/query heuristics, or changes beyond the current source/task/answer/readback interfaces, stop with NEEDS_CONTEXT and a concrete narrow proposal before writing production code. Do not route all task-like words to a shallow canned answer; no alternate memory store and no force-seeded gold task to pretend a heldout phase passed.

If reproducible and the existing contracts support a small repair, implement it with meaningful failing regression + counterexamples. Tests should cover actual create_app/routes or actual server wiring, user completion vs older mail, reopen and old-answer/history freshness, ambiguous similar tasks and dropped vs done, and no external/MCP data leak. Run affected tests once after focused iteration. Do not rerun the entire backend or any real model. Record what the deterministic tests prove and what still requires model quality. If no safe bounded fix is possible, a reproducible failure and design decision is a useful deliverable; do not guess.

## Environment and limits
Worktree: /Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/kingfisher-product-readiness-20261105
Python: /private/tmp/kf-core-20261104-env/bin/python with PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. . Synthetic temp dirs only. No GUI, loopback browser, personal databases, models, key access, provider requests, downloads, import resumption, network, push, merge or release. Frozen fixtures immutable. No subagents. No broad refactor. Do not commit yet; controller will freeze/review and group delivery.

Report at .superpowers/sdd/2026-11-04-kingfisher-product-completion/task-completion-recall-report.md. Include exact reproduction, actual interfaces, design decision/limits, commands/results, files and hashes if changed. Return only DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED, short result and report path.
