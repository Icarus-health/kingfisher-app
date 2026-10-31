# Skill-Bibliothek: Einordnung und begrenzter Abruf

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Nutzerfreigabe vom 31.10.: die vorgeschlagene Einordnung umsetzen und bestehende Gedächtnisprüfung fortführen; kein weiterer Freigabeschritt für reversible Umsetzung.

**Goal:** Grundverfahren und bei Bedarf geladene Skills nach Zweck und bestätigtem Anwendungskontext auffindbar machen, ohne Aktenwissen zu kopieren.
**Architecture:** Die vorhandene JSON-Metadatenstruktur in procedures.sqlite3 additiv ergänzen. Kategorien ordnen; Aufgabenbereich, positive ganze Auslöser und gegebenenfalls Kontext begrenzen die Auswahl. Volltexte erst nach eindeutiger Wahl lesen. Bestehende Quellen-/Versionsprüfungen bleiben bindend.
**Tech Stack:** Python/Pydantic/SQLite, bestehende React-Einstellungsansicht, keine neue Abhängigkeit.
**Spec:** Nutzerfreigabe zum unmittelbar vorangegangenen Vorschlag: drei Merkmale (Grundverfahren/bei Bedarf; Suchen & Prüfen/Kommunikation/Planung & Arbeit/Gedächtnispflege/Sonstiges; allgemeiner oder besonderer Kontext), automatische Einordnung von Lernvorschlägen, keine Skillkopie je Akte. Verbindlicher Gesamtabschluss: docs/68-gedaechtnis-abschluss.md.

## Global Constraints

- Nur mit künstlichen Daten arbeiten. Persönliche Daten, Cloudschlüssel und Postfächer bleiben unangetastet; Großimport bleibt pausiert.
- Eigene Skills sind immer bei Bedarf; ein Lernvorschlag darf sich nicht selbst zum Grundverfahren erheben.
- Fehlende neue Metadaten erhalten abgeleitete Vorgaben, ohne gespeicherte alte Fassungen umzuschreiben oder ihre Hashes zu verändern.
- Kontextetiketten sind ausdrückliche Wortgruppen, keine aufgelösten Personen-/Projektidentitäten. Namen ersetzen keine Aktenwahl; keine automatische Skillanlage pro Akte.
- Kontextschritte aus Zitaten oder negierten Passagen dürfen keinen Skill aktivieren. Mehrere passende Skills bleiben Konflikt.
- Lernvorschläge bleiben bis menschlicher Bestätigung inaktiv; Kategorien ändern keine Berechtigungen oder Quellenprüfungen.
- Persönliche Skills bleiben lokal. Auswahl ohne zusätzlichen Modellaufruf, keine Behauptung gemessener Beschleunigung.

## Approaches

Gewählt gemäß freigegebenem Vorschlag: kleine Metadaten plus vorhandene Bibliothek. Separate Verzeichnisbäume würden Versionierung und Quellenabhängigkeiten duplizieren. Ein eigener Skill pro Akte würde Fakten/Präferenzen und Abläufe vermischen. Beides entfällt.

## Review Focus

- Alte Markdown- und Datenbankfassungen bleiben auswählbar/exportierbar, ohne still neue Versionen zu erzeugen.
- Kategorisierung allein aktiviert keinen Skill; Kontext muss positiv in der eigenen Anfrage stehen.
- Neue Einstellungsfilter dürfen den direkt aus dem Gespräch angeforderten Vorschlag nicht verstecken.
- Veraltete/widerrufene Quellen und abgewählte Fassungen bleiben auch nach Kategorisierung gesperrt.
- Ein Lese-/Speicherfehler darf Entwurf oder Freigabe nicht als erfolgreich ausgeben.

### Task 1: Metadaten und Auswahl

**Files:** sidecar/icarus_memory/procedures.py, procedure_routes.py; sidecar/tests/test_procedure_categories.py.
**Interfaces:** Spec bekommt category (optional; Vorgabe je Aufgabenbereich), contexts (0–4 ganze Wortgruppen). Listenausgabe bekommt category, contexts und tier=contextual. Grundverfahren bekommen ihre feste Kategorie. Bestehende Schnittstellen select/select_for bleiben erhalten.

- [ ] RED: Legacy-Export und Dubletten, Standardkategorien, strikte Zusatzmetadaten, Kontext/Gegenbeispiele, nicht geladene Volltexte und gesperrte Fassungen prüfen.
- [ ] GREEN: Normalisierung für neue Vorschläge, abgeleitete Metadaten beim Lesen alter Zeilen; Wiederverwendung anhand normalisierter Metadaten ohne Legacy-Umschreibung.
- [ ] Bereich vor Katalogbewertung filtern; Auswahl nach Bereich + Auslöser + optionalem Kontext. Kategorien verleihen keine Berechtigung.
- [ ] Lernprompt benennt Einordnung und begrenzte Kontextetiketten; Katalog bleibt unter acht Einträgen/2400 Bytes.
- [ ] Betroffene Backendtests; Commit.

### Task 2: Bestehende Bibliothek kompakt filtern

**Files:** app/kingfisher/src/ProcedureSettings.tsx, app/kingfisher/tests/procedure-review.test.mjs.
**Interfaces:** Kategorien/Grundverfahren/bei Bedarf und Suche im Metadatenkatalog. Neue Fassung bewahrt Einordnung; direkte Ziel-ID bleibt trotz Filter sichtbar.

- [ ] RED: Kategorie/Suche grenzen Zeilen ein, Ziel bleibt sichtbar, Formular bewahrt vorhandene Metadaten, Lese-/Speicherfehler verhindern Erfolg.
- [ ] GREEN: vorhandene Select-/Such-/Aufklappbausteine nutzen; optionale Einordnung aufklappbar, kein neuer Screen.
- [ ] UI-Tests, Typecheck/Build/Assetvertrag; Commit.

### Task 3: Gesamtprüfung und offene Abnahme

**Files:** docs/67-bewaehrte-ablaeufe.md, docs/runs/2026-10-31-skill-kategorien/README.md.
**Interfaces:** bestehender fester 24-Mail-/16-Fragen-Katalog, keine Sollwerte in Modellprompts.

- [ ] Kategorien über echten lokalen HTTP-Weg mit künstlichen Daten: Vorschlag → Übernahme → Auswahl → Kontextwechsel → Quellenentzug → Neustart.
- [ ] Gedächtnis-Gegenfälle (Personenwahl, Quellen/Fristen) und Kataloginstrument prüfen; reale Modellprobe nur bei ausreichender stabiler Speicherreserve.
- [ ] Ein unabhängiges Schlussreview, notwendige Korrekturen mit RED→GREEN. Keine Endlosschleife.
- [ ] Prüffähigen Branch/Draft-PR bereitstellen. Mac-Update/Fenstertest, echte Mailstichprobe und Alltagswoche offen ausweisen.
