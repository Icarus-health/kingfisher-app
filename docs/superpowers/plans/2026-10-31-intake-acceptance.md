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

## Task 4: Normalen lokalen Betrieb begrenzen

Nach vollständigem Lauf E wurde die normale 32K-Verbindung an einer privaten,
getrennten Sechs-Quellen-Kopie geprüft. Zwei unvollständige Quellen wurden vor
jedem Modellaufruf gehalten. Der Lastwächter brach später bei 24 Prozent Reserve
ab; kein vollständiger Aufgaben-/Abrufnachweis. Das ist kein kontrollierter
Vergleich nur der Kontextgröße, zeigt aber einen ungeeigneten Betriebszustand.

Gezielte Ergänzung: optionales, exakt gewähltes 8K-Profil auf denselben vorhandenen
Gewichten; altes Profil unverändert. Alle nicht gewählten Anbieter behalten ihren
Transport. Nur das positiv geprüfte Profil erhält den nativen Ollama-Transport
mit `truncate:false`, `shift:false` und vollständigem Eingabebudget. Vorwärmen und
Retention müssen dieselbe Profilvorgabe respektieren. Keine globalen
Ollama-Einstellungen, kein Dienstneustart, keine neue Modellfamilie.

Die installierte Ollama-Version 0.40.13 unterstützt diese beiden Schalter:
[versionierter API-Vertrag](https://github.com/ollama/ollama/blob/v0.40.13/api/types.go),
[versionierte Verarbeitung](https://github.com/ollama/ollama/blob/v0.40.13/server/routes.go).
Die OpenAI-kompatible Schnittstelle bietet sie nicht an. Daher ist für den
gewählten kleinen Modus ein eng begrenzter nativer Adapter erforderlich; eine
Bytegrenze und Usage allein wären kein Nachweis gegen Eingabekürzung.

- [ ] Gegenproben vor Umsetzung: volles Schema/Tools/History, erwartetes Profil,
  unveränderte Fremdanbieter, gültiger Tool-Rundlauf und Überlauf vor Generierung.
- [ ] Optionalen Profilmodus und alle modellladenden Lifecycle-Wege absichern;
  Frist, Proxy-/Redirect-, Gewichts-, Quellen- und Berechtigungsprüfungen erhalten.
- [ ] Unabhängiges Review und passende Regressionen; anschließend den ganzen
  unveränderten synthetischen Katalog durch den tatsächlichen Produktanbieter.
- [ ] Dieselbe private Stichprobe erneut, fehlende Originalteile weiterhin halten;
  Ergebnisse bleiben privat. Erst dann Veröffentlichung/Mac-Prüfung bewerten.

## Task 5: Zwei beobachtete Antwortlücken aus G schließen

Keine neue Funktion und keine erneute Eingangsmodellierung: derselbe frisch
aufgenommene G-Bestand mit unveränderten Originalen und Einordnungen bleibt die
Grundlage. G belegt den nativen Transport, aber keine bestandene Antwortabnahme.

- [x] q09-Rohsätze und alte gespeicherte Restantwort zunächst rot reproduzieren.
- [x] Teilverwerfung führt im bestehenden gemeinsamen Prüfpfad zu frisch
  geprüften Originalberichten; keine Lockerung der Einzelbelege.
- [x] q08: bei einfacher eindeutig eigener Zusagefrage fremde direkte Ich-Zusage
  mit belegten strukturierten Mailrollen aus Auswahl und zusätzlichem
  Satz-Aktenkontext ausschließen. Keine positive Urheberannahme aus dem Kopf.
- [x] Berichte, Zitate, Weiterleitungen, unklare Rollen und Mehrteilfragen erhalten;
  nach unabhängig gefundenem P2 den Frageumfang enger schließen und echte
  Store-/Render-Gegenfälle erneut prüfen. Alte fehlerhafte Auswahl sperren.
- [x] Diagnose-Pflichtwörter nicht allein aus dem gerenderten Belegfuß zählen;
  Gegenprobe vorher rot. Semantische Einzelprüfung bleibt erforderlich.
- [x] Unabhängiges Review beider Reparaturen und gezielte Gegenprüfungen ohne
  Modelle/Privatdaten. Originalanzeige ist keine modellseitige Schwärzung.
- [ ] Alle 16 Fragen über den tatsächlichen nativen Anbieter auf einer Kopie
  desselben G-Bestands erneut stellen. Eingangsdateihashes und ursprüngliche
  G-Datenbankdateien nachprüfen; keine Neu-Klassifikation behaupten.
- [ ] Vollsuite des eingefrorenen Stands, echte Stichprobe, sichere Auslieferung.
