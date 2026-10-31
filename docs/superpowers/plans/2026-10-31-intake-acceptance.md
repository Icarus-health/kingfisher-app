# Aufnahme- und Abrufkorrekturen: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Unabhängige Fehlerdomänen dürfen nach `dispatching-parallel-agents` getrennt bearbeitet werden.

**Goal:** Die drei belegten Fehler des ersten vollständigen lokalen Kataloglaufs beheben und die Diagnosepfade ohne gelockerte Last- oder Beleggrenzen prüfbar machen.

**Architecture:** Bestehende Kandidaten-, Satzprüfungs- und Abrufpfade gezielt absichern. Originale, Belegbindung, Nutzerbestätigung und Quellenentzug bleiben maßgeblich; kein neues Gedächtnis und keine zusätzliche Modellrolle.

**Tech Stack:** Python, pytest, SQLite, vorhandenes Qwen9B und BGE-M3.

**Spec:** `docs/68-gedaechtnis-abschluss.md`; eingefrorener Katalog `docs/evaluations/memory-quality/intake/catalog.json`.

## Global Constraints

- Großimport bleibt pausiert. Keine persönlichen Laufzeitdaten in Commits oder Cloudagenten.
- Katalog SHA-256 `ba46791a16c41f45dad04540918cd7f384ae73d85108fe10849050ebe250eeda` unverändert erhalten.
- Kein Quellenkopf als Beweis für eine Sprecherrolle; keine erfundene Uhrzeit.
- Kein stilles Übernehmen von Aufgaben; keine Aufweichung harter Belegdetails.
- Modellprobe weiterhin 8K-Diagnose, 16.000 Eingabebyte, 1.200 Ausgabetoken; Lastwächter unverändert.
- Kein neues Modell, keine Cloudkosten, keine fremden Programme schließen.

## Review Focus

1. Bitten, eigene Zusagen und zitierte/weitergeleitete Aussagen dürfen den Handelnden nicht vertauschen.
2. Ein erfundener Titelzusatz darf keine erfundene Rechnungskennung erzeugen und keine klare Aufgabe verschlucken.
3. Zwei mögliche Uhrzeiten bleiben offen, während die Handlung sichtbar zur Prüfung erhalten bleibt.
4. Quellenänderung/-entzug muss dieselben Schutzregeln auch beim erneuten Anzeigen durchsetzen.
5. Ein Diagnoseadapter darf technische Ausfälle weder als fehlendes Wissen noch als bestanden ausgeben.

## Task 1: Aufgabenkandidaten erhalten

**Files:** `memory_analysis.py`, `task_review.py`, ggf. `task_detection.py`, passende Tests.
**Interfaces:** Bestehende `interpret`-Kandidaten und Review-Ergebnisse; keine neue API. Unsicherheit über vorhandene Prüfmarkierung transportieren.

- [ ] Regressionsfälle zuerst: Rechnung mit Nummer ausschließlich im Betreff; erfundene Nummer ohne Quelle; klare Handlung mit 18 oder 19 Uhr; tatsächlich unklare Zuständigkeit.
- [ ] Rotlauf dokumentieren.
- [ ] Minimal beheben: belegte Handlung behalten, ungestützte Titelangabe entfernen oder prüfbar kennzeichnen; keine konkrete Uhrzeit wählen.
- [ ] Betroffene Aufnahme-/Aufgabenprüfungen grün, Quellenwechsel und wiederholte Erkennung mitprüfen.

## Task 2: Zuständigkeit beim Antwortabruf

**Files:** `satzpruefung.py`, `satzantwort.py`, Tests `test_satzpruefung.py` und `test_satzantwort.py`.
**Interfaces:** `satz_pruefen(Satz, Mapping[str, Beleg]) -> Urteil`; vorhandener Zitat-/Originalmodus bei verworfener Formulierung.

- [ ] Rotfall: Mailabsender bittet Empfänger, Antwort erklärt Absender zum Handelnden. Gegenfälle mit neutraler Frist, Originalwortlaut und eindeutigem Handelnden.
- [ ] Bestehende Schutzmuster vergleichen und begrenzte, konservative Rollenbindung umsetzen; keine vermeintlich allgemeine Grammatiklösung.
- [ ] Rücklesen gespeicherter Antworten und erhaltene eindeutige Fristauskunft testen.

## Task 3: Diagnosegrenzen und vollständige Abnahme

**Files:** `scripts/probe_mail_intake_quality.py`, ggf. `scripts/mail_intake_quality.py`, Script-Tests. Abrufpackung in `working_memory_answers.py` nur nach Abstimmung mit Task 2.
**Interfaces:** Vorhandener Providervertrag, feste sichere Grenzen, Bericht trennt Modellfehler von Adapterfehler.

- [ ] Überlange Auswahl und normale Quellenfrage mit Werkzeugdefinitionen offline reproduzieren.
- [ ] Quellengetreu kompakte Auswahl bzw. begrenzte lesende Diagnose ermöglichen; keine stillen Kürzungen oder Seiteneffekte.
- [ ] Unveränderten vollständigen Katalog nach Offlineprüfungen einmal erneut ausführen, alle Antworten/fehlenden Aufgaben semantisch prüfen.
- [ ] Frisches unabhängiges Gesamtreview und betroffene Suite; verbleibende Grenzen offen protokollieren.
- [ ] Erst nach bestandener Qualität veröffentlichen, Mac aktualisieren und gemischte echte Stichprobe prüfen. Alltagswoche bleibt separate Nutzerabnahme.
