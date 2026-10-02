# Gedächtniskern: Umsetzung und Abnahme

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Fortschritt wird unten protokolliert.

**Goal:** Den bestehenden Gedächtnispfad um nachweisbare Verarbeitung, historische Kenntnis und dauerhaft begrenzten Modelleinsatz erweitern und die verbleibenden Freigabegrenzen offenhalten.

**Architecture:** Episoden, Vorschläge und bestätigte Aussagen bleiben in ihren vorhandenen Stores. Neue Verarbeitungszustände liegen transaktional neben Vorschlägen; Historie und Abdeckungsansicht werden aus dem Kern abgeleitet. Keine zweite Faktenablage, keine automatische Annahme.

**Tech Stack:** Python >=3.10, SQLite, FastAPI, bestehendes React-Frontend, lokaler Provider.

**Spec:** `docs/architecture/kingfisher-memory-sicherheitsvertrag-v0.1.md` zusammen mit `docs/architecture/memory-core-review-2026-09-12.md`.

## Global Constraints

- Fremder Inhalt ist keine Befugnis; Schemaerfolg ist kein Bedeutungsnachweis.
- Bestehende lokale Nutzerdaten bleiben außerhalb der Entwicklungs- und Testläufe.
- Ausschließlich additive Migrationen mit bestehender Migrationsprüfung; bestehende Entscheidungen nicht umdeuten.
- Kein autonomer Versand, kein Cloudfallback, keine Installation von OpenViking.
- Eine Teilverarbeitung darf niemals vollständig heißen; ein altes Checkpoint ohne Umfang wird nicht nachträglich zertifiziert.
- Unbekannte historische Zeitpunkte bleiben unbekannt. Entzogene Quellen sind kein historischer Zugriffsfreibrief.

## Task 1: Herkunft und Werkzeuggrenze

**Files:** `sidecar/icarus_memory/agent.py`, `policy.py`, neue Tests `test_memory_agent_boundary.py`.

- [x] Mehr-Runden-/Neustart-Gegenprobe mit bösartigem Provider schreiben und rot prüfen.
- [x] Herkunftseinfluss konservativ erhalten; Kontextdaten getrennt von Systemregeln zuführen.
- [x] Modellgesteuerte übertragende READ-Operationen nach Fremdeinfluss auf konkrete Freigabe begrenzen, lokale geprüfte Reads erhalten.
- [x] Testdouble beobachtet tatsächliche Aufrufe; legitime Gegenfälle ausführen.

## Task 2: Abdeckung und fortsetzbare Interpretation

**Files:** neues `memory_analysis.py`, `proposals.py`, `task_detection.py`, neue Tests `test_memory_analysis.py`.

**Interfaces:** `ProposalStore.memory_analysis` verwaltet Jobs in derselben Datenbank; `TaskDetector.run` behält seine Schnittstelle. `snapshot(episode_id)` liefert Zustand, verarbeitete Zeichen, Schema-/Modellstand; Nutzeraussagen werden daraus nicht abgeleitet.

- [x] Gegenfälle für vierte Bitte, Inhalt hinter 20.000 Zeichen, Neustart, Leasingkonkurrenz, Quellenentzug und unbekannte JSON-Felder schreiben.
- [x] Additives versioniertes Job-Schema einführen; Lease-Token und Eingabefingerprint begrenzen Ergebnisannahme.
- [x] Kleine Abschnitte auswerten; Kandidaten und Fortschritt atomar schreiben; keine Höherstufung zu bestätigtem Wissen.
- [x] Modellfehler und volle Ergebnisbudgets als Lücke führen; Quellen hinter Fehlern weiter bearbeiten.
- [x] Migration aus dem echten vorherigen Schema sowie Transaktionsabbruch prüfen.

## Task 3: Zeitlich korrekte Kernabfrage

**Files:** `claims.py`, neues `memory_history.py`, `test_memory_history.py`.

**Interfaces:** Historische Kenntnis und fachliche Gültigkeit getrennt abfragen; Timeline aus `knowledge_changes`, keine Kopie der Wahrheit. Exakte Signaturen und historische Lücken im Implementierungsbericht dokumentieren.

- [x] Späte Erkenntnis, rückwirkende Korrektur, halboffene Intervalle und Neustart als rote Tests abbilden.
- [x] Historischen Stand aus unveränderlichen Claims und Zustandsereignissen ableiten.
- [x] Rücknahme und Abhängigkeitsentzug auch beim Abruf berücksichtigen; unbekannte Altzustände kenntlich machen.
- [ ] Zeitbereich, Referenzfilter und stabile Pagination prüfen.

## Task 4: Nutzbarer Abruf und sichtbarer Verarbeitungsstand

**Files:** neues `memory_routes.py`, `server.py`, neue UI-Komponente `MemoryStatus.tsx`, bestehender Gedächtniseinstieg und API-Typen.

- [x] Authentifizierte GET-Endpunkte für Abdeckung und Timeline mit begrenzten Parametern testen.
- [x] Bestätigte Aussagen, ursprüngliche Quellen und Verarbeitungslücken im Abruf unterscheidbar zurückgeben.
- [x] Kompakte Anzeige in vorhandener Gedächtnisansicht; keine neuen Einrichtungsfragen.
- [x] Isolierter Browserlauf mit synthetischen Daten, Fehlerzustand, leerem Bestand und Neustart.

## Task 5: Review und Freigabegrenzen

- [ ] Gesamte Backend-Suite, Frontend-Build und gezielte Sabotageproben.
- [x] Neue Fähigkeiten gegen den Vertrag abgleichen; fehlende Freigaben konkret dokumentieren.
- [ ] Erst nach Review und grüner CI zur Übernahme bereitstellen. Laufzeitwechsel nur mit gesicherter Rückkehrmöglichkeit.

## Weiter geltende Abnahmen des Gesamtvertrags

Der gesamte Memory Core ist mit diesen Bausteinen noch nicht automatisch abgenommen: echte Löschung über alle Stores/Chats/Backups und späteren Restore, getrennte Zweckrechte, vollständiger Vorgangsautomat, profilspezifische Verdichtung, Evaluationsbestand (300 Quellen, 90 fachliche Fälle, 40 adversarielle Abläufe), Wachstums- und lokale Modellmessung sowie tatsächliche Entlastung müssen jeweils nachgewiesen werden. Diese Grenzen dürfen weder eine Prozentsteigerung noch eine Fertigmeldung auslösen. Folgepakete bleiben Teil des Nutzerauftrags.

## Arbeitsprotokoll

- Ausgangspunkt `9556c8e`, getrennte Arbeitskopie `Kingfisher-memory-core`, keine Nutzerdaten kopiert.
- Befund: `suggest_text` kürzt bei 20.000 Zeichen und drei Items, bisheriger `task_analysis`-Checkpoint enthält keinen Umfang. Dies wird zuerst behoben.

- Verifikation: Gesamtstand 1.246 Tests bestanden (212,08 s); danach Archivierungsrennen gezielt ergänzt und geprüft. Aktueller Frontend-Build erfolgreich. Reale Modellproben zeigen weiter Bedeutungsfehler; beide geprüften lokalen Modelle bestehen 8/10 Entwicklungsfälle, keine Qualifikation. Details und verbleibende Arbeiten: `docs/release/MEMORY-CORE-IMPLEMENTATION-2026-09-12.md`.
