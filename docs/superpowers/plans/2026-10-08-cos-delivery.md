# Kingfisher: Alltag und vollständiger Abruf

**Goal:** Den vorhandenen persönlichen Arbeitsraum nutzbar verbinden, die reale lokale Antwortkette messen und den geprüften Stand datenerhaltend auf GitHub und dem Mac bereitstellen.

**Architecture:** Bestehende Aufgaben-, Ziel-, Quellen- und Gedächtnisdienste verwenden. Keine zweite Datenbank, kein zweiter Hintergrunddienst. Öffentliche Quellen bleiben Quellenberichte. Modelle schlagen vor; Quellengültigkeit, Identität, Zeit und Freigaben prüft Code.

**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript, bestehende native Mac-Hülle, Docker, Ollama.

**Spec:** `docs/63-cos-produktabschluss.md`, `docs/evaluations/lifeos-2026-10-08.md`, ausdrücklicher Nutzerauftrag vom 2026-10-08. Dieser Lieferplan ist ein überprüfbarer Teil des umfassenderen aktiven Produktziels, keine Behauptung vollständiger Fertigstellung.

## Global Constraints

- Originale, persönliche Daten, Zugangsdaten und bestehende Einordnungen erhalten; vor Mac-Austausch kalte Rückwegsicherung.
- Keine neuen Cloudkosten, keine privaten Daten im Modellvergleich, keine automatischen externen Schreibaktionen.
- Fremdcode nur nach Lizenz-/Herkunftsprüfung übernehmen. Bestehende Kingfisher-Bausteine vor Duplikaten bevorzugen.
- GitHub-Minuten sparen: `[skip ci]`, keine CI-Neustarts oder Statusabonnements.
- Unbelegte Aussagen bleiben unbekannt; Quelle, Quellenversion, Erfassungszeit und tatsächliche Bestätigung unterscheiden.
- Günstige Agenten für begrenzte Aufgaben; Integration und Schlussprüfung separat.

## Review Focus

Prüfe insbesondere widerrufene oder abgeschlossene Ziele bei Aufgabenanlage, Altbestände ohne goal_id, ungewollte Datenmigration, öffentliche Quellen ohne Zieltreffer, Redirect-Provenienz, fehlgeschlagene Abrufe, Quellenberichte als persönliche Fakten, Modellausfälle, falsch positiv bewertete Abrufmessungen, versteckte Cloudaufrufe und unveränderte Mac-Daten beim Update.

### Task 1: Ziel mit nächstem Schritt verbinden

**Files:** `sidecar/icarus_memory/tasks.py`, `server.py`, passende Aufgaben-/API-Tests; `app/kingfisher/src/GoalControls.tsx`, Aufgabenansicht, `api.ts`, passende Frontendtests.

**Interfaces:** Optionales strukturiertes `goal_id` in Aufgaben, rückwärtskompatibel. Neue Aufgaben dürfen nur auf ein aktuelles aktives Ziel verweisen. Historische Aufgaben behalten ihre Beziehung auch nach Zielabschluss. UI legt per ausdrücklicher Nutzeraktion einen betitelten nächsten Schritt an und zeigt die Beziehung wieder an.

1. Erst fehlende Roundtrip-/API-/UI-Verhalten testen, RED beobachten.
2. Vorhandene Task-Serialisierung/Migration und Zielprüfung erweitern; keine IDs in Freitext verstecken.
3. Form pro aktivem Ziel, sichtbare Beziehung in Aufgabe. Bestehende direkte Aufgabenanlage bleibt gültig.
4. Betroffene Backend-/Frontendtests ausführen. Expected: alle grün, Altdaten bleiben lesbar.

### Task 2: Öffentliche Quellen sichtbar und nachvollziehbar

**Files:** `world_monitor.py`, `world_routes.py`, World-Tests; `WorldControls.tsx`, neue `WorldPage.tsx`, `App.tsx`, SPA-Routen und Frontendtests.

**Interfaces:** Bestehende `/api/v1/world`-Quelle um finale Abrufadresse und Versionshash ergänzen, konfigurierte Adresse behalten. `/world` zeigt alle registrierten Quellen und manuell ausgelösten Abruf; Today verlinkt diesen Bereich auch ohne Tagesinhalt. Zielüberschneidung als Themenhinweis kennzeichnen, nicht als geprüfte Relevanz. Keine weitere automatische Quellensammlung/Annahme von Fakten.

1. Redirect-/Versionsnachweis, Altquellen, Quellen ohne Ziele und SPA-Route testen, RED beobachten.
2. Erfassungszeit, endgültige URL und SHA-256 des tatsächlich gespeicherten Textes erhalten; Fehler dürfen alte erfolgreiche Version nicht als neue ausgeben.
3. Bestehende Source-Controls in eigener Weltwissen-Seite wiederverwenden, verständliche Herkunft-/Aktualitätsanzeige.
4. Betroffene Tests ausführen. Expected: grün, kein öffentlicher Bericht wird automatisch bestätigter persönlicher Fakt.

### Task 3: Vollständigen lokalen Gedächtnisabruf messen

**Files:** neues `scripts/probe_working_memory_end_to_end.py`, zugehörige Tests, `docs/runs/2026-10-08-cos-delivery/`.

**Interfaces:** Eingefrorener synthetischer Paraphrasenkatalog; echter `Agent.answer_memory` inklusive Frageverständnis, produktiver Suche und Auswahl. Ergebnis trennt erwartete/gewählte Quellen, Status, Antwortmodus, Zeit und Modellaufrufe. Kein Fake-Ergebnis als Modellqualität ausgeben. Kein Schlüssel oder Nutzerdatenspeicher als Eingabe. Ausgabe überschreibt nichts.

1. Offline-Tests für Bewertungsfehler, Cloudverbot und Ausgabeschutz zuerst, RED beobachten.
2. Diagnostik implementieren; lokale Anbieteradresse explizit, echte Frage-/Antwortrollen verdrahten. Satzprüfung und Zitatmodus explizit kennzeichnen.
3. Mit installiertem kleinen lokalen Modell und lokalem Embedder an getrenntem Port prüfen. Keine Downloads. Cold-/Warmzeiten und Ressourcenbegrenzung dokumentieren; Ausfälle als Ausfälle zählen.
4. Expected: Diagnostiktests grün, unveränderter Kataloghash; Qualitätszahlen werden berichtet, nicht durch Anpassung des Katalogs verbessert.

### Task 4: Prüfen, veröffentlichen und Mac aktualisieren

**Files:** Run-Record, Produktabschluss-Matrix, bestehende Build-/Installationsskripte nur falls nötig.

**Interfaces:** Tasks 1–3 liefern gemeinsam den Stand; existierender Draft PR #6. Lokaler Container + native Mac-Hülle behalten Einstellungen/Volume. Separate kalte Sicherung und Wiederherstellungsweg vor Update.

1. Frische unabhängige Diff-Prüfung; wichtige Befunde reproduzieren und beheben.
2. Backend-/Frontend-Gesamtprüfungen und Build. Expected: grün oder echte externe Einschränkung ausdrücklich benannt.
3. Isolierter echter Bedienlauf mit künstlichen Daten: Ziel→Aufgabe, Weltwissen→Quelle, Gedächtnisantwort. Expected: Quellen und Beziehungen bleiben nach Neuladen sichtbar.
4. Geprüften Stand mit `[skip ci]` auf bestehenden PR übertragen, nach erfolgreicher Prüfung zusammenführen; Rückwegsicherung, Mac-Installation, Gesundheitsprüfung und echter Fenstertest.
5. Tatsächliche Abnahme und verbleibende Kernlücken dokumentieren. Aktives Gesamtziel bleibt offen, solange erforderliche Alltags-/Gedächtnisnachweise fehlen.
