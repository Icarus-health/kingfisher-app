# Kingfisher UI/UX-Fokus – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Hinweise direkt erreichbar, Gedächtnisfragen kompakt und die Skill-Bibliothek schnell erfassbar machen.
**Architecture:** Vorhandene React-Komponenten, Routen und Farbtokens. Keine neuen APIs oder Abhängigkeiten. Nachweise und Entscheidungen bleiben beieinander.
**Tech Stack:** React/TypeScript/Vite, Node-Tests, synthetische Sidecar-Laufzeit und CUA.
**Spec:** `../16-gestaltung.md`, Produktvision §5.1, freigegebene Gestaltung und Nutzerauftrag vom 31.10.2026.

## Global Constraints
- Großimport pausiert, persönliche Daten unverändert.
- Keine neue Designrichtung, Produktbereiche oder Modelle.
- Quellenstand, Entzug, Versionen, menschliche Übernahme bleiben verbindlich.
- 390/900/1280 px, Tastatur, helle/dunkle Rollen, keine Modellarbeit beim Blättern.

## Review Focus
- Unbekannte Eingangstypen dürfen keine falschen Ziele erhalten.
- Eingeklappte Belege dürfen keine direkt erreichbare Sachentscheidung übrig lassen.
- Direkte Skill-Prüflinks müssen Filter und Lesesperre weiterhin überstehen.
- Suchtreffer in mitgelieferten Skills müssen sichtbar sein, ohne falschen Leerhinweis.
- Lange Titel/Kategorien müssen in schmalen Fenstern umbrechen.

### Task 1: Hinweise und Gedächtnisfragen
**Files:** `TodayOverview.tsx`, `BefundeAnsicht.tsx`, `MemoryQuestions.tsx`, `Befunde.css`; Tests `heute-ruhe.test.mjs`.
- [ ] Tests für bekannte/unbekannte Eingangstypen und Offenlegung schreiben, rot prüfen.
- [ ] Bekannte Eingangstypen zur vorhandenen Aufnahme/Prüfung verlinken. Kompakte Belege samt Entscheidung gemeinsam aufklappen; Vollansicht unverändert.
- [ ] Tests grün und echte Interaktion prüfen.

### Task 2: Skill-Bibliothek
**Files:** `ProcedureSettings.tsx`, `ProcedureSettings.css`; Tests `procedure-review.test.mjs`.
- [ ] Suchtreffer, Leerzustände und Filterrückweg rot prüfen.
- [ ] Titel/Metadaten trennen; mitgelieferte Suchtreffer direkt zeigen, nichtleere Gruppen, Filter zurücksetzen.
- [ ] Grüne Tests samt bisherigen Review-/Versions-/Quellenprüfungen.

### Task 3: Abnahme
- [ ] Ganze UI-Suite, TypeScript/Build, Assetvertrag.
- [ ] Synthetische Laufzeit: Heute→Aufnahme/Prüfung, Frage→Belege/Entscheidung, Bibliothek→Suche→Filter→Prüflink, 390/900/1280 px und Tastatur.
- [ ] Ein unabhängiges Review, Befunde gezielt beheben.
- [ ] GitHub- und Mac-Fassung getrennt prüfen; vor Update Sicherung und Importpause.
