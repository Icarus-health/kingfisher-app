# P2 bounded feedback regression repair

Base: 6731dd5. Read-only review finding M1 is not yet proven: after answer projection appends `context.mail_intake_notice`, the explicit feedback route persists displayed answer, and the exported forbidden answer for zero/multiple structured sentences contains the transient suffix. A later same wrong substantive answer may escape literal matching when coverage changes.

First reproduce via real authenticated conversation -> feedback POST -> regression export, with synthetic data only and no real model/network. Use existing intake_session fixture if useful. Test actual matching/normalization from messlatte where possible. If not reproducible, report and do not patch speculatively.

If proven, make the smallest repair. Preserve full displayed feedback snapshot and its provenance; regression assertion must track substantive answer independently of the trusted transient intake suffix. Retain existing single structured sentence behavior. Any removal must be tied to server-generated metadata and exact final suffix: do not heuristically strip source text that resembles a note or arbitrary substrings. Old feedback without new metadata keeps its current export behavior; no migration or backfill guessing. Missing/mismatched/non-string metadata must not drop answer text. Do not revive withdrawn source text or bypass authoritative projected view. Preserve workflow learning opt-in and no new active skill, no added model call or network. No changes to client feedback body contract required.

Meaningful regression tests: authenticated roundtrip showing same underlying answer still matches after intake notice changes/disappears; snapshot retains what was displayed; one-sentence behavior; multiple/plain behavior; missing/mismatched metadata and genuine note-like answer preserved. Run affected feedback and workflow-learning tests plus intake recall only; not whole backend. Record initial RED and final GREEN once per necessary change, no broad repeated runs. No model quality claims.

Allowed product area: rueckmeldung_routes.py / rueckmeldung_faelle.py plus focused existing/new tests; another product file only with explanation first. No schema migration, frozen fixture edits, UI work, cloud/API access, local app/GUI, personal sources/key, bulk import or git push/merge. Do not commit: root verifies hashes and owns grouped commit. No subagents.

Review and report: exact reproduction, root cause, final design, file hashes, commands/log paths, results, limitations, any concerns. Write report to `.superpowers/sdd/2026-11-04-kingfisher-product-completion/feedback-intake-report.md`. Return short DONE/concerns only. Test env `/private/tmp/kf-core-20261104-env/bin/python`, PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.:/private/tmp and `-p kf_completion_confirmation_refused_socket` for network-denied pytest. Test source changed only by you during implementation.

## 3. Global Constraints

- Originale, stabile Identitäten, bestätigte Nutzerkorrekturen, Konten und Quellenhistorie erhalten; keine Neuinstallation mit Datenverlust.
- Gedächtnis ist die maßgebliche Wissensbasis; kein zweites konkurrierendes Agentengedächtnis.
- Quelle berichtet, Modell vermutet und Nutzer bestätigt bleiben unterscheidbar.
- Großimport erst nach bestandener Qualitätsprobe und innerhalb einer tatsächlich freigegebenen Daten-/Kostenregel; dieser Plan aktiviert nichts.
- Qwen9B und BGE-M3 bleiben Standard. Mistral und bestehende weitere Cloudzugänge sind optionale, ausdrücklich erlaubte Wege. Keine automatische Cloudweitergabe wegen lokaler Langsamkeit.
- Keine persönlichen Quellen, Schlüssel oder privaten Prüfberichte in GitHub. Öffentliche Nachweise mit künstlichen Daten; private Nachweise geschützt lokal.
- Keine Nachricht versenden, Buchung auslösen oder fremde Daten löschen, ohne passende tatsächliche Nutzerfreigabe. Wiederholte Ausführung darf keine Dubletten erzeugen.
- Keine Modellarbeit beim bloßen Blättern; Hintergrundarbeit begrenzt, unterbrechbar und mit verständlichem Fortschritt.
- App, Backend, Schema, Modulversion und getesteter Modellstand werden getrennt dokumentiert. Veröffentlicht, installiert und im Alltag bestanden sind unterschiedliche Zustände.

### P2 — Skillbibliothek und kontrolliertes Lernen fertigstellen

**Anknüpfung:** `sidecar/icarus_memory/{procedures,procedure_model,procedure_routes,learning_patterns,learning_service}.py`, `sidecar/icarus_memory/procedure_skills/`, `app/kingfisher/src/ProcedureSettings.tsx`.

- [ ] Bestehende Kategorien und zwei unabhängige Dimensionen verwenden: essenziell/bei Bedarf sowie Suche, Kommunikation, Planung, Analyse/Arbeit. Keine unübersichtliche Ordnerhierarchie.
- [ ] Router, Geltungsbereich, Priorität bestätigter Korrekturen und mehrere gleichzeitig passende Verfahren prüfen; Konflikt zeigt Rückfrage statt stiller Auswahl.
- [ ] Wiederholte Korrektur in einen verständlichen inaktiven Lernvorschlag überführen. Neue Vorschläge auf Duplikate und notwendige Reichweite prüfen.
- [ ] Beispiel, Gegenbeispiel, Quelle, Version, Rechtebedarf und Rücknahme gemeinsam darstellen. Nach Änderung/Entzug alte Ergebnisse und Caches nicht weiter anwenden.
- [ ] „Warum dieser Ablauf?“ bei Bedarf anzeigen; der normale Nutzer muss keine Markdown-Datei bearbeiten.

**Abnahme:** Vereinsmail nutzt den passenden Ton, eine private Mail übernimmt ihn nicht; Namensdaten bleiben Fakten. Kein ungenehmigter Skill wird aktiv. Messprobe zeigt passende Auswahl ohne unnötige Lade-/Modellrunden.
