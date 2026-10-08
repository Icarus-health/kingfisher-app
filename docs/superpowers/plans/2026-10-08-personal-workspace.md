# Persönlicher Arbeitsbereich – erste Umsetzung

> **For agentic workers:** Use superpowers:executing-plans. Umsetzung und Prüfung in dieser Sitzung; keine neue Cloudfreigabe.

**Goal:** Vorhandene Kingfisher-Funktionen verlässlich auffindbar und im Alltag nutzbar machen.

**Architecture:** Ein bestehender Datenbestand. Lebensbereiche wählen ihre Kandidaten serverseitig vor der Seitengrenze; jede Ausgabe prüft weiterhin Originalfassung und Kategorienfingerabdruck. Entwicklung verbindet vorhandene Ziele, Gewohnheiten und Lernvorschläge. Alltagseinstiege verweisen direkt auf diese Funktionen und bestehende Quellen-/Prüfansichten.

**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript, vorhandene Testumgebungen.

**Spec:** ../../evaluations/lifeos-2026-10-08.md; Nutzerfreigabe vom 8. Oktober, ergänzt um Pulse, Atlas, Voice und Learning.

## Global Constraints

- Keine zweite Gedächtnisablage, kein Neuimport, keine privaten Daten im Repository.
- Keine automatischen Cloudaufrufe oder neuen Hintergrunddienste.
- Geprüfte Originale und manuelle Korrekturen bleiben maßgeblich.
- Pro Bereichsanfrage höchstens 500 Kandidaten prüfen; danach explizite Fortsetzung statt behaupteter Vollständigkeit. Höchstens 100 Quellen ausgeben.
- Keine Gesundheits-/Lebensqualitätsbewertung aus Datenlücken ableiten.

## Review Focus

- Seltene ältere Gesundheitshinweise hinter mehr als 50 neueren anderen Quellen müssen erreichbar sein.
- Veraltete Themenfingerabdrücke und manuelle Übersteuerung dürfen keine falschen Bereichstreffer liefern.
- Eine leere begrenzte Seite darf keinen leeren Gesamtbestand behaupten.
- Bereichswechsel und Ladefehler dürfen keine Quellen unter falscher Überschrift zeigen.
- Fehlende Gewohnheitseinträge sind kein Nachweis von Untätigkeit.

## Task 1: Bereichsauswahl vor der Seitengrenze

Files: `memory_areas.py`, `mail_intake_routes.py`, `test_memory_areas.py`.
Interface: `MemoryAreas.page(limit=50, cursor=None, area=None)`; area ist work/personal/health/finance/other. Bestehender Aufruf ohne area bleibt kompatibel. Neue Felder `area`, `selection_scope`, `scan_limited` erklären den Suchraum.

- [x] HTTP-Regressionen für ältere Quellen, Korrekturen, Entzug, ungültige Filter und begrenzte Fortsetzung zuerst rot prüfen.
- [x] SQL-Kandidatenauswahl ergänzen, aktuelle Projektion vor Ausgabe prüfen; keine Modellarbeit.
- [x] Bestehende Kategorien-/Bereichstests ausführen.

## Task 2: Richtige Bereiche und direkte Alltagseinstiege

Files: `MemoryAreas.tsx`, `MemoryAreaModel.ts`, `api.ts`, UI-Tests.
Interface: `api.memoryAreas(limit, cursor, area)`; direkte Auswahl über `/memory?area=health`.

- [x] Filtervertrag und Navigations-/Leerezustände prüfen.
- [x] Beim Bereichswechsel erste Seite laden und alte Ergebnisse entfernen; Ladezustand schützen.
- [x] Keine clientseitige Filterung einer fremden Quellenseite; begrenzte Suche verständlich zeigen.

## Task 3: Entwicklung und bestehende Fähigkeiten verbinden

Files: neue `DevelopmentPage.tsx`, `App.tsx`, `TodayOverview.tsx`, vorhandene Styles.
Interface: `/development` verwendet `GoalControls` und `HabitControls`; Gesundheit und Pflege erhalten direkte Einstiegspunkte.

- [x] Vorhandene Ziele, Abschlüsse, Gewohnheiten, Lernvorschläge und Rücknahmefunktionen erhalten.
- [x] Direkte Tages-Einstiege ergänzen; keine neue Hauptnavigation und keine erfundenen Fortschrittszahlen.
- [x] Frontend-Typprüfung, Tests und Build ausführen.

## Task 4: Abrufnachweis und erweiterte LifeOS-Zuordnung

- [x] Bestehenden synthetischen Abrufkatalog offline erneut ausführen, Ergebnis und Grenzen speichern.
- [x] Pulse/Atlas/Voice/Learning anhand des vorhandenen LifeOS-Quellstands konkret zuordnen. Vorhanden, erste Umsetzung und offen getrennt dokumentieren.
- [x] Keine Qualität des vollständigen Antwortmodells ohne dessen tatsächliche Ausführung behaupten.

## Task 5: Review und Bedienprüfung

- [x] Diff und relevante Backend-/Frontendprüfungen abschließen.
- [x] Ein unabhängiges Review des fertigen Patches; konkrete Fehler korrigieren.
- [x] Getrennte lokale Vorschau mit künstlichen Daten bedienen; persönliche Installation nur mit gesichertem, geprüftem Austausch aktualisieren.
- [x] Umgesetzt, geprüft, installiert und weitere Ausbaustufen getrennt berichten.

## Abschlussgrenzen

Alle fünf Aufgaben dieser ersten Ausbaustufe ausgeführt; Nachweis in `docs/runs/2026-10-08-personal-workspace/README.md`. Aufgabe 4 ist eine wiederholte Offline-Baseline und Zuordnung der Ideen, keine Freigabe des vollständigen Antwortmodells. Persönliche Mac-Installation unverändert. Unabhängige Reviewbefunde korrigiert; Browserprobe fand zusätzlich den bei leeren Tagen versteckten Einstieg, ebenfalls korrigiert. Die größeren Ausbaustufen bleiben im Vergleichsdokument offen.
