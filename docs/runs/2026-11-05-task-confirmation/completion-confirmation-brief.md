# Completion confirmation and truthful provenance

Read this first. BASE b906d43956abee9caf33fee5a0602eb60fa0d3d9. Bounded prerequisite of P0/P1/P3, not full task-recall acceptance.

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

## Exact problem and authorized design
Read task-completion-recall-report.md in this ledger (initial observations and section A; appendix is executable). In real create_app wiring a synthetic model can call aufgabe_erledigt after user text "Sag nur Hallo."; the task is completed with no approval, and history cannot distinguish it from the direct user done route. Strict recall also lacks task evidence, but that second gap remains outside this patch.

Implement A only, with existing stores and approval flow:
1. Default completion by the model tool requires explicit approval; direct user done action remains one click. Keep WRITE_LOCAL classification and unrelated tool defaults. Preserve actual explicit per-tool overrides/named user rules, denies and taint escalation; such delegated completions must NOT be called explicit confirmations. Apply the safe default in normal Policy construction, not just one server startup path, unless existing architecture strongly requires otherwise (explain).
2. Local approval must identify the current task intelligibly (title and ID). MCP/external caller must not receive a new private title or history solely from a dry-run; preserve or tighten current disclosure. Capture only bounded task identity/state in the existing ephemeral approval lifecycle. Pending approval cannot complete a task after a relevant edit, completion/reopen/drop or replacement. Refuse stale requests clearly. Comparison and mutation must be atomic in TaskStore; protect ABA changes using event sequence as appropriate. Existing tool schema must not let a model forge a trusted snapshot or explicit-confirmation marker.
3. Record actual new explicit completion confirmation in existing append-only task_events, without a new database or changing old rows. A distinct event kind such as user_confirmed_completion is allowed; actor_id remains unknown (no invented authenticated person). Direct authenticated user done action and a granted, state-bound local approval may record it. Generic tool calls under standing permission, legacy completed, and source-derived post_completed stay at their known provenance. Explicit confirmation on an already-done but unconfirmed active completion can add one confirmation event, retaining original done_at and separate confirmation recorded_at. Repeated same done click is idempotent; reopen then new completion is a new incarnation. Existing completion status API fields remain compatible; user-visible history label should be understandable if its renderer uses a closed kind list.
4. A model cannot gain permission by supplying extra undocumented kwargs. Existing source/profile/procedure guards must still apply. No claims/episodes created from these events, no task-state recap put into model context in this patch.

Minimum regression evidence: actual ordinary create_app chat reproducer now pending and task still open; reject leaves open; grant completes exactly once; direct done still one click; stale pending after edit and complete/reopen is refused (including an execution-time concurrency counterexample); model-fabricated snapshot/confirmed flags ineffective; explicit standing-rule execution remains distinct; direct repeat confirmation idempotent and old generic history unmodified; taint and DENY retained; MCP preview no new private title. Run focused tests while iterating, affected tests once at end; no entire backend. A tiny extension to Tool/Agent approval snapshot hooks is authorized if it is needed for this exact tool; keep optional/default behavior unchanged for other tools and justify ownership.

## Scope and limits
Likely files policy.py, tools.py, agent.py, tasks.py, direct done routes in server.py, existing task-history label map if needed, and meaningful tests. No general approval refactor, semantic router, EvidenceAnswer expansion, fixture changes, model run, network, personal data, GUI, release or push. Do not create new agents or commit. Root has one unrelated documentation-only Mistral addendum dirty; leave it untouched.

Worktree /Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/kingfisher-product-readiness-20261105. Python /private/tmp/kf-core-20261104-env/bin/python; PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:. . Synthetic stores only.

Report .superpowers/sdd/2026-11-04-kingfisher-product-completion/completion-confirmation-report.md: commands and RED/GREEN results, exact design and provenance semantics, changed files/hashes, limitations. Return status and short summary only. No speculative fixes; first trace/reproduce the known defect. Escalate concrete contract conflicts before broadening.
