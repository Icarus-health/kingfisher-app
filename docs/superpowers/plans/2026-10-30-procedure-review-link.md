# Lernvorschlag direkt öffnen

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Freigegebenes Gesamtziel; native Umsetzung, ein unabhängiges Schlussreview.

**Goal:** „Ablauf prüfen“ öffnet den betreffenden Lernvorschlag mit Schritten und Prüfung, ohne erneutes Suchen in der Bibliothek.
**Architecture:** Bestehende Gesprächskarte, Einstellungen und Detailzeilen verwenden. URL `/settings?ablauf=<kodierte ID>#ich-ablaeufe`; Auswahl reagiert auf direkte Navigation, Neuladen und Verlauf. Nur der verlangte vorhandene Eintrag wird geöffnet/fokussiert. Keine automatische Bestätigung.
**Tech Stack:** vorhandenes React/TypeScript/Vite, Node-Tests und vorhandenes Playwright/Chrome.
**Spec:** Nutzerfreigabe `docs/68-gedaechtnis-abschluss.md` und Abschnitt „Benutzen“ in `docs/67-bewaehrte-ablaeufe.md`. Basis dieses UI-Schritts: `bb94507` / PR #103; keine erneute Backendimplementierung.

## Global Constraints

- Bestehende Gestaltung und Komponenten; keine neuen Assets, Ansichten, APIs oder Modellarbeit.
- Nur künstliche Browserdaten auf 127.0.0.1:8893; kein persönlicher Bestand und keine Cloud.
- Detail frisch laden; Fehler oder geänderte Grundlage erlauben keine Übernahme.
- Kein falscher Ersatz bei fehlender ID: verständlicher Hinweis, Bibliothek bleibt nutzbar.
- Normales Öffnen ohne Ziel bleibt kompakt. Rückweg erhält Gespräch und Eingabeentwurf.
- Browser plugin not available; vorhandene Playwright-CLI aus lokalem npm-Cache verwenden, keine Installation. Wrapper benötigt fehlende Registry-Metadaten und wird daher ohne Download durch das bereits installierte CLI ersetzt.

## Review Focus

- Ähnliche Titel dürfen keinen anderen Vorschlag öffnen; ID entscheidet.
- Abwesender/fehlerhafter Eintrag darf keine andere Fassung vorauswählen.
- Navigation zwischen zwei Zielen auf derselben Einstellungsseite muss reagieren.
- Neuladen/Übernahme darf Details nicht unbemerkt schließen oder ungeprüft aktivieren.
- Fokus/Rückweg bei 900 und 1.280 Pixeln, Entwurf und Quelle bleiben erhalten.

### Task 1: Durchgängiger Gesprächsverweis und geöffnete Zielzeile

Files: `app/kingfisher/src/App.tsx`, `app/kingfisher/src/ProcedureSettings.tsx`, `app/kingfisher/tests/conversation-workspace.test.mjs`, neue `app/kingfisher/tests/procedure-review.test.mjs`, `docs/67-bewaehrte-ablaeufe.md`, `docs/runs/2026-10-30-procedure-review-link/README.md`.
Interfaces: vorhandene `procedure_proposal.id`, `navigate(path)`, GET `/api/v1/procedures` und GET `/api/v1/procedures/{id}`. Kein neuer Backendvertrag.

- [ ] Regression zuerst: tatsächlicher Gesprächsknopf transportiert kodierte ID; Zielzeile öffnet und lädt Detail, andere Zeilen bleiben geschlossen; fehlende ID zeigt Hinweis; normales Öffnen kompakt. Render-/Navigationsprüfungen im bestehenden Vite-Hook-Teststil, Browsergegenfall vor Änderung.
- [ ] Run `node --experimental-strip-types --test app/kingfisher/tests/conversation-workspace.test.mjs app/kingfisher/tests/procedure-review.test.mjs`; neue Zielprüfungen müssen rot sein.
- [ ] URL-Ziel in ProcedureSettings bei Laden und popstate neu lesen. Bestehende ProcedureRow um kontrolliertes Öffnen und Fokus auf die Zielzusammenfassung ergänzen; Detail-/Quellen-/Bestätigungsprüfungen wiederverwenden.
- [ ] Gesamte UI-Suite, Produktionsbuild und Assetvertrag. Reale Browserinteraktion bei 900/1.280 px: Gespräch→Vorschlag→Details→bestätigen→Rückweg mit Entwurf; unbekanntes Ziel, Fehler beim Detailladen und Wechsel zwischen Zielen prüfen. Keine Konsolenfehler/Überläufe.
- [ ] Ein unabhängiges Review, wichtige Befunde einmal mit Rot/Grün beheben; Nachweis und eigener PR. Backendvollsuite nicht erneut ausführen, solange kein Backendcode geändert wird.
