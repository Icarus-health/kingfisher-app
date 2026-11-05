# Durable Conversation Drafts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Track independently reviewable outcomes.

**Goal:** Ungesendeten Gesprächs- und Starttext nach Neustart wiederfinden, ohne neuere Eingabe, andere Instanzen oder Sendestatus zu verwechseln.

**Architecture:** Versionierte Draftzeilen in bestehender ConversationStore-Datenbank; authentifizierte getrennte API; serialisierter UI-Cache und begrenzte native Flush-Anfrage. Entwürfe sind keine Fakten oder Modellhistorie.

**Tech Stack:** Bestehendes SQLite/Python3.10+, FastAPI, TypeScript/React, AppKit/WebKit macOS11.3+.

**Spec:** ../specs/2026-11-04-durable-conversation-drafts-design.md

## Global Constraints

20.000 Zeichen; 250 ms UI-Schreibpause; keine Modellarbeit; bestehende Sicherungswege; Großimport pausiert. Native Fensterzugriff weiterhin gesondert freizugeben. Delegierte technische Umsetzung unter dem freigegebenen Gesamtplan.

## Review Focus

- Antwortverlust beim Speichern oder Leeren darf keinen neueren Text löschen.
- Andere Instanz oder Neustart am gleichen Port darf keine alten Schreibaufträge übernehmen.
- Erste Nachricht mit Folgetext während des Sendens darf weder doppelte Gespräche noch verlorenen Text erzeugen.
- Schließen während Fehler/Konflikt darf keinen falschen Speichererfolg melden.
- Migration/Sicherung erhalten Nachrichten und schließen Entwürfe aus Such-/Modellhistorie aus.

## 1. Persistenz und API

Files: `sidecar/icarus_memory/conversations.py`, neues `conversation_draft_routes.py`, passende Store-/Routentests; Root integriert `server.py`.

- [x] RED: v1-Datenbank migrieren, bestehende Nachrichten bytegleich; Draft über Neustart, CAS-Konflikt, Retry, Leeren und neue Instanz prüfen.
- [x] Migration2 und `draft_get`/`draft_put` implementieren; GET liefert text/revision/instance_id, PUT erwartet text/expected_revision/instance_id.
- [x] Authentifizierung, geschlossene Felder, unbekannte IDs und fehlende Rechte vor jedem Zugriff; Store-Lock nicht über Modellarbeit halten.
- [x] Betroffene Tests und vorhandenen Sicherungs-/Wiederherstellungsweg prüfen.

## 2. Bestehende Gespräche

Files: `conversationDrafts.ts`, `CommandBar.tsx`, `api.ts`, Eingabe-/Workspace-Tests und schmale Statusgestaltung.

- [x] RED: frischer JS-Kontext, stale GET/PUT, Weitertippen, verlorene Antwort, Serverneustart und Fehlerstatus.
- [x] Serialisierte Savequeue, getrennte Revisionen, explizite Altentwurfsübernahme und Konfliktbehandlung.
- [x] Vor Submit sichern; danach nur passende Fassung leeren; kein Resend wegen Clearfehler.
- [x] Exportierte PrepareToLeave-Promise und Browserwarnung prüfen.

## 3. Startgespräch und Übergang

Files: `App.tsx` ConversationHistory, Draftkoordinator und abgestimmter atomarer Backendvertrag.

- [x] Bestehende Create/Send-Pfade gegen Entwurfsbindung prüfen und genauen Übergangsvertrag festhalten.
- [x] RED: Erstsendefehler, Neustart vor Retry, Folgetext während Erstsendens, konkurrierendes Fenster und verlorene Übergangsantwort.
- [x] Bindung/Übergang implementieren, ohne beim bloßen Öffnen leere Gespräche zu erzeugen.
- [x] Inhalt im neuen Gespräch wiederfinden und gesendeten Text nicht als neuen Entwurf wiederbeleben.

## 4. Native Lebensdauer und Abschluss

Files: `macos/Shared/WebSurface.swift`, `macos/App/AppDelegate.swift`, `RecoveryWindowController.swift`, passende Logiktests.

- [x] Begrenztes PrepareToLeave an eigene geladene Seite, kein Fallback auf fremde Instanz.
- [x] Schließen, Beenden und Reload sichern oder verständlich warnen; Cancel erhält Text/Fenster.
- [x] Unabhängiger Review, gezielte Backend-/UI-/native Prüfungen, Build und synthetischer API-Neustart.
- [ ] Nachweise und PR aktualisieren; echte Fensterabnahme nicht aus Logiktests ableiten.
- [ ] Native Bedienprüfung, persönliches Update und Alltagsabnahme nach der ausstehenden Fensterfreigabe.

Technische Nachweise und Grenzen: [Prüfbericht](../../runs/2026-11-04-conversation-drafts/README.md).
