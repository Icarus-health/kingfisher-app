# P1 incomplete-mail coverage in memory recall

Read this first. BASE 9e17e2b33922526869c0ec3ea1341b6f9492121c. The last bounded task/status repair is committed and reviewed; do not redo it.

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


## This bounded task

Determine, using actual current app routes and synthetic stores, whether an admitted source plus an inventoried but deferred/failed mail can produce an answer that implies there is no deadline or that all relevant information was checked. Historical pointer only: docs/runs/2026-11-05-memory-source-acceptance/state-contract-at-ff2f075.md S07. Do not use or alter frozen acceptance fixtures to optimize this case; create an independent small synthetic reproduction.

Start with a real reproduction before editing production code: actual mail Intake inventory/defer/failure and actual authenticated conversation/evidence route, with deterministic synthetic model/search where needed. Capture response, context, stored conversation and intake status. A visible separate intake-status page alone does not establish answer-level disclosure. Do not assume the old diagnostic is still correct, and do not invent a false-positive defect if current answer is already appropriately qualified.

If the bug has a coherent small repair through existing stores/conversation components, implement it with regression tests. Otherwise return NEEDS_CONTEXT with concrete minimal design choices and affected interface before broader edits. The desired end state is trustworthy source scope in the user's answer, not a helper that no app path uses.

Contract/rulings:
- Tell the user the factual known scope: e.g. some inventoried mail remains unread/failed or not fully analyzed. Never claim that an unprocessed mail is relevant to this question or that it contains a deadline. Preserve useful current supported facts. A saved task-status answer is about a verified saved task and must not be silently replaced by a claim about mailbox completeness.
- No global 'memory complete' from an empty queue, a disabled account, a reset folder generation, or a single queried source. Unknown coverage is not complete. Distinguish known incomplete ingestion from analysis as necessary for the actual path; first inventory snapshot and existing data contracts, not a new competing coverage database.
- Coverage read must be read-only, local and bounded. Existing Intake.status has maintenance/projection behavior; don't automatically call work or model operations during conversation GET/browsing. No automatic inventory/network/model from this addition, no bulk resume. If a source/queue changes, don't retain a stale 'all checked' assertion. Do not turn a coverage snapshot into a source/claim or model-generated fact.
- Existing source/choice/procedure/task routing and draft/retry guarantees remain. Source-only explicit questions stay source-scoped. The unknown/deferred body is never read from the connector or passed to a model. No new MCP/provider tool/schema, no account addresses/subjects/UIDs/provider errors in external requests or lookup metadata. Tests must exercise normal/retry/local readback plus enabled synthetic MCP where the touched paths make that relevant.
- UI stays compact: reuse existing answer/source status treatment with a concise note and an existing intake/processing destination if needed. No restyle, global warning spam, navigation changes or unrelated functionality. Static/SSR UI evidence is not native click acceptance.
- No migration unless specifically returned for ruling. Preserve original sources, recognized facts, source entitlement and correction history. On uncertain store evidence fail descriptively without blocking unrelated grounded answers.
- No GUI/browser/model/provider/credential/personal store/import/install/commit/push/subagents. All work in isolated temp synthetic stores. Do not touch docs/fixtures/memory-acceptance-20261104. No duplicate broad backend runs; new focused regression plus truly affected suites, existing node_modules only for UI tests/typecheck if UI changed.

Use actual code under sidecar/icarus_memory/{mail_intake,server,conversations,evidence_answer,source_answers}.py and existing UI answer surfaces as starting pointers, not all mandatory edit targets. Inspect scope then choose minimal coherent change. Cite existing API/read-side contracts; if they cannot express factual coverage without schema work, propose concrete alternatives instead of guessing.

Repo /Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/kingfisher-product-readiness-20261105. Python /private/tmp/kf-core-20261104-env/bin/python, PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp . Existing offline pytest hook kf_completion_confirmation_refused_socket blocks connect/connect_ex without external calls; tests still must not use personal stores or apps. Existing UI node_modules in /private/tmp/kf-skill-categories-20261031/app/kingfisher/node_modules may be symlinked into a copied temporary UI; no install.

Write full report to .superpowers/sdd/2026-11-04-kingfisher-product-completion/intake-coverage-recall-report.md: actual reproduction, requirement mapping, changed files/hashes, exact commands and retained output paths, no-egress/read-only evidence, limitations. Return short status/results only. Independent review belongs to controller after freeze.

Ruling review01: a known capture gap outranks a known analysis gap, which outranks generic unverified coverage from a separate incomplete/disabled account or folder. Preserve the bounded read and current-generation restrictions; do not assert relevance or completeness. Explicit feedback snapshots may retain projected text, so distinguish that path from neutral ConversationStore persistence in reports.
