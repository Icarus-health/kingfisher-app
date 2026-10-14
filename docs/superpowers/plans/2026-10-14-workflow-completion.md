# Workflow Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Die vier vom Nutzer freigegebenen Lücken schließen, damit gespeicherte Quellen direkt Arbeit abnehmen.
**Architecture:** Vorhandene Episoden, Vorschläge, Aufgaben und reversible Ablagemetadaten weiterverwenden. Neue reine Lese-/Vorschlagsdienste ergänzen die bestehenden API-/UI-Abläufe; der Gedächtniskern und die Originale bleiben bestehen.
**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript/Vite, bestehender nativer Mac-Updater.
**Spec:** docs/superpowers/specs/2026-10-14-workflow-completion.md

## Global Constraints
- Kein Fortsetzen des Großimports oder Ändern der wirksamen Hintergrundpause.
- Keine Cloudaktivierung, externen Logos/Karten oder neuen Anmelderechte.
- Nur synthetische Fixtures; keine persönlichen Inhalte/Zugänge in Agenten oder GitHub.
- Bestätigungen prüfen Quellenstand und Kontext erneut, sind idempotent; Nutzerkorrekturen haben Vorrang.
- Mac-Abnahme und Update als nächster Nutzertermin nach geprüfter Lieferung; bestehende Installation während Entwicklung erhalten.
- GitHub-Minuten schonen: keine CI-Testneustarts und keine ungeprüften Releases.

## Review Focus
- Quellenentzug/Ersetzung während Vorschlag oder Bestätigung: nichts aus veraltetem Stand speichern.
- Historische Mail, fremde Zuständigkeit oder bedingte Zusage: keine heutige eigene Frist behaupten.
- Gedoppelte Klicks, geänderte Projekte, fehlgeschlagenes Speichern: genau einmal übernehmen und Entwurf behalten.
- Gleichartige Organisationsnamen mit unterschiedlichen Rechtspersonen: nur Darstellungsvorschlag, kein Identitätsmerge.
- Treffer außerhalb Graph/2.000 Metadaten/25 Vorschauzeilen und nach Filterwechsel: vollständige korrekte Trefferzahl und Seite.

### Task 1: Gmail-Diagnose und begrenzte Korrektur
**Files:** bestehende mail_anmeldung.py, postfach_lage.py, connectors/mail.py, google_oauth.py nach belegter Ursache; gezielte sidecar/tests/. Root besitzt tatsächliche lokale Diagnose, keine Produktionsinhalte an Worker.
**Interfaces:** Bestehende GET /api/v1/mail/erreichbar und Nachrichtendienste, ohne Inhaltsausgabe; Diagnose mit Fehlerklasse/Phase/aggregierter Dauer.
- [x] Bestehende Konfiguration nur auf Typ/Modus prüfen; sichere Verbindung/Anmeldung/Zeitrahmen abgrenzen.
- [x] Ursache reproduzieren, passende Gegenprobe vor Korrektur, minimal korrigieren.
- [x] Betroffene Tests und konkrete Nutzer-/Netzgrenze dokumentieren.

### Task 2: Lokaler Mail-Arbeitsablauf
**Files:** neue local_mail_workflow.py und ggf. pure service/helper, local_mail_routes.py; MailReader.tsx plus getrennte SavedMailWorkflow.tsx/API; passende Tests. WorkspaceViews-Kinds/Validierung darf nur dieser Worker erweitern, keine neue Originalquelle/DB ohne Bedarf.
**Interfaces:** register(app,guard) in neuem Modul; lesender Quellen-/Vorbereitungsstand, bewusste Vorbereitung/Bestätigung, vorbereitete Vorschläge an Episode+digest+Kontext gebunden. Root integriert register und einen ggf. nötigen begrenzten Hintergrundhook in server.py; Worker dokumentiert genaue Signatur. Gemeinsame vorhandene Aufgaben-/Projektannahme wiederverwenden.
- [x] Tests für Offline-Original, GET ohne Modell/Provider, historisch/fremd, Quelle geändert/entzogen, gleiche Bestätigung und Sendefehler schreiben und rot nachweisen.
- [x] Quellengebundene Vorbereitung/Cache, direkte UI und gemeinsame Annahme implementieren.
- [x] Gezielte Tests/Sabotageprobe und kurze Integrationsanleitung liefern.

### Task 3: Organisationsvorschläge
**Files:** neue organisation_group_suggestions.py (register(app,guard), pure candidate generation); OrganisationGroups.tsx und eigene API/UI-Helfer; passende Tests. Nicht workspace_views.py oder server.py ändern; normale Gruppenspeicherung/undo bleibt bestehen.
**Interfaces:** Vollständige aktuelle Organisationskennungen + revisions-/quellengebundener Vorschlag, reason/name/members; Vorschau und Änderungen vor normaler bestätigter Speicherung. Ablehnung im vorhandenen Metadatenspeicher benötigt Schema-Absprache mit Root/Task2, kein zweiter Store.
- [x] Konservative positive/negative Namensfälle, vorhandene Gruppe, abgelehnt, changed-source/member, doppelte Annahme und Undo testen.
- [x] Automatische erklärbare Vorschläge und kompakte Vorschau/Bestätigung implementieren; keine Modelle auf GET.
- [x] Gezielte Tests/Sabotageprobe und API-/Schema-Integrationsangaben liefern.

### Task 4: Vollständige Dokumentordner
**Files:** neue workspace_documents.py (register(app,guard)); MemoryFolders.tsx, eigener workspaceDocumentsApi.ts und ggf. reine FolderPagination-Helfer; passende Tests. server.py/WorkspaceViews-Kinds/OrganisationGroups/MailReader sind fremdes Eigentum. Gemeinsame MemoryViewState-Felder nur nach Root-Abstimmung erweitern.
**Interfaces:** paginierter read-only GET /api/v1/workspace-documents für q/folder_id/project_id/source_area/project_area/offset/limit; items samt kanonischer episode:/note:-Kennung, total/has_more, aktuelle Filteroptionen. Keinen vollständigen Quellenkörper in Liste oder History speichern.
- [x] >2.000 Zuordnungen, >25 Quellen, verschachtelte Ordner, Unicode-Suche, Filter und aktuelle/entzogene Quellen gegen vollständigen Bestand prüfen.
- [x] Serverabfrage und echte UI-Seiten statt Graph-Vorschau implementieren, Rückwege erhalten.
- [x] Gezielte Tests und synthetischen großen Bestand messen; kein Modellaufruf.

### Integration und Abnahme
- [x] Root integriert Register/Hintergrundhaken/Schemadeltas seriell, führt unabhängige Paketreviews durch.
- [x] UI-Gesamtlauf, Produktionsbuild/TypeScript und passende Backendregression; abschließendes unabhängiges Branchreview.
- [x] Isolierte Browserabläufe bei 900/1280 Pixeln samt Fehlersituationen prüfen.
- [x] GitHub mit konkreten Nachweisen und Grenzen liefern; Mac-Update/Fenstertest als nachfolgende Abnahme kennzeichnen.

Abschlussnachweis: `docs/runs/2026-10-14-workflow-completion/README.md`. Die Checkboxen umfassen Implementierung/GitHub-Lieferung und getrennte Browserprüfung; die anschließende echte Mac-Abnahme und Produktivinstallation sind noch ausstehend.
