# Mailaufnahme und Abruf: Qualitätsprobe

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Der Nutzer hat die drei Schritte im vorigen Gespräch freigegeben; native Umsetzung, einmaliges unabhängiges Schlussreview.

**Goal:** Eine neue synthetische Mailmenge durch reale Aufnahme, frische Einordnung, Aufgabenprüfung und Abruf messen; Fehler und offene Semantik sichtbar machen.
**Architecture:** Vorhandene Messlatte-Instanz und deren RFC-822/IMAP-Attrappe wiederverwenden. Separater versionierter Katalog mit Sollwerten, die nie in Modellprompts gelangen. Isolierter Qwen9B-Lauf, keine Produkt-/Konfigurationsänderung.
**Tech Stack:** Bestehendes Python/pytest/FastAPI/SQLite, vorhandenes Ollama.
**Spec:** Nutzerfreigabe „Gut dann weiter“ zu den drei Schritten: schwierige Mails, Soll-Ergebnisse, gemeinsame Aufnahme-/Abrufprüfung; `docs/00-produktvision.md`, `docs/65-ziellinie.md`.

## Global Constraints

- Nur erfundene Quellen mit `.example`-Adressen. Keine privaten Daten, Schlüssel, Postfächer oder Produktionsdatenbanken lesen.
- Großimport bleibt pausiert; keine Quellen-/Aufgabenannahme im persönlichen Bestand.
- Vorhandenes `kingfisher-qwen3.5:9b-32k`, keine Downloads/Cloud. 8K Kontext pro Diagnoseaufruf; ausdrücklich keine unveränderte Produktionslatenzmessung.
- Eigene temporäre Messinstanz, unveränderte Originale, keine Sollwerte/Prüfnotizen an Modelle. Keine Wiedergabe früherer Einordnung.
- Technische Schutzprüfungen sind keine automatische semantische Abnahme; die Probe erteilt nie eine Großimportfreigabe.
- Ein eigener Unterprozess mit begrenzter Laufzeit/Modellaufrufen; nur dieser wird bei Ressourcenabbruch beendet. Keine fremden Programme/Modelle stoppen.

## Review Focus

- Sollwerte könnten in Modellprompts gelangen: Test auf markierte Orakelnotiz und explizites Daten-Mapping.
- Falsche Person trotz richtiger Worte: Quellen-IDs und getrennte Adressrahmen prüfen.
- Historische oder spätere Friständerung: Zeitpunkt, aktueller Vorschlagsstatus und Originalbelege separat ausweisen.
- Technische Unterbrechung als Erfolg: unvollständige Läufe und fehlende Prüfungen bleiben gesperrt.
- Attrappen-Mechanik und echte Modellqualität: Modus und Grenzen im Ergebnis zwingend getrennt.

### Task 1: Katalog und auswertbare Aufnahme-/Abrufprobe

Files: `docs/evaluations/memory-quality/intake/catalog.json`, `scripts/mail_intake_quality.py`, `scripts/probe_mail_intake_quality.py`, `scripts/test_mail_intake_quality.py`. Instrument und Lastwächter werden wegen gemeinsamer Verhaltenstests zusammen geliefert.
Interfaces: `load_catalog(path)`, `run_pipeline(catalog, provider, directory, save)`; Ergebnis enthält source-map, frische Einordnung, geprüfte Aufgaben-Vorschläge, Profile, Gesprächsantworten und komponentenweise Sollprüfungen.

- [ ] Tests zuerst: ungültige Quelle/Sollreferenz verworfen, Sollwerte nicht im Mailobjekt/Modellinput, falsche Quelle trotz passender Wörter fällt durch, ausgelassene erwartete Aufgabe ist Fehler, technische Ausfälle bleiben unvollständig.
- [ ] Minimaler Katalog mit 24 Mails und eindeutigen Gegenfällen. Keine neue Produktarchitektur.
- [ ] Pipeline nutzt `messlatte.aufnahme.aufnehmen`, echte `TaskDetector.run`, `Durchlauf.vorbefuellt`, Gesprächs-API und unveränderte Originale. Keine Modellantworten vorgeben.
- [ ] Betroffene Katalog-/Messlatten-/Skripttests und Sabotageprobe; Commit.

### Task 2: Lokaler begrenzter Lauf und Schlussprüfung

Files: `docs/runs/2026-10-30-mail-intake-quality/README.md` und ausschließlich synthetische Ergebnisdateien. Native Adapter und Grenzen sind bereits Teil des Instruments aus Task 1.
Interfaces: Pipeline aus Task 1; nativer Diagnoseanbieter mit direktem lokalen Transport, positiv bestätigten vorhandenen Gewichten und 8K/1200-Tokengrenze. CLI reserviert neuen Ergebnisordner; Elternprozess überwacht nur eigenen Worker.

- [ ] Tests zuerst für Endpunkt-/Proxygrenze, leere/abgeschnittene Antworten, fehlende Gewichte, Aufruflimit und unvollständigen Ressourcenabbruch.
- [ ] Reale Qwen/BGE-Probe; vorhandenen semantischen Produktindex nach der Einordnung frisch vorbereiten, vor Fragen vollständige Abdeckung prüfen. Keine semantische Ersatzantwort aus Konstanten.
- [ ] Reale Qwen-Probe; protokollierte Messgrenzen. Bei Speicherdruck kritischer Stufe oder niedriger Reserve eigenen Worker abbrechen; keine fremden Modelle entladen.
- [ ] Modellantworten und Fehler einzeln gegen festgehaltene Sollwerte lesen; keine günstigen Wiederholungen auswählen.
- [ ] Ein unabhängiges Schlussreview. Fehler im Messinstrument korrigieren; Produktbefunde getrennt dokumentieren und nur mit reproduzierbarem Nachweis behandeln.
- [ ] Prüfbarkeit auf GitHub herstellen. Keine neue Mac-Fassung allein für Messdaten; persönlicher Fenstertest bleibt vertagt.
