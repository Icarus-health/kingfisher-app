# Gedächtniskern: verlässliche Zuordnung und Abruf

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Die drei Reparaturschritte sind vom Nutzer zur Umsetzung freigegeben.

**Goal:** Falsche automatische Aufgabenänderungen verhindern, bestätigte Personenidentitäten beim Abruf berücksichtigen und den bestehenden Aufnahme-/Abrufweg gemeinsam auf dem Mac abnehmen.

**Architecture:** Bestehende Akten, Originalquellen, Bestätigungen und Rückfragen weiterverwenden. Keine zweite Wissensablage, kein neuer Skill-Router, keine neuen Modelle. Unsichere Veränderungen gehen in den vorhandenen Vorschlagsweg; dieselbe bestätigte Personenidentität gilt für Kontaktansicht und Gespräch.

**Tech Stack:** Python/SQLite/FastAPI, bestehende React-Oberfläche, Docker und native Mac-Hülle.

**Spec:** Nutzerfreigabe vom 30.10.2026: „Setze die drei Reparaturschritte um und prüfe danach den ganzen Ablauf auf dem Mac. Keine neuen Funktionen und den Großimport erst fortsetzen, wenn Zuordnung und Abruf zuverlässig funktionieren.“ Ergänzend `docs/00-produktvision.md` und `CLAUDE.md`.

## Global Constraints

- Keine neuen Funktionen; Großimport bleibt pausiert, solange die Qualitätsabnahme offen ist.
- Originalquellen, Quellenentzug, bestätigte Korrekturen und bestehende Rückgängig-Funktionen erhalten.
- Nur künstliche Daten in Tests, Agentenberichten und eingecheckten Nachweisen; keine privaten Mailtexte, Schlüssel oder Profile.
- Keine Cloudanfrage und kein Modellwechsel ohne vorhandene passende Freigabe. Bestehendes Qwen9B und BGE-M3 für die Mac-Probe verwenden.
- Keine spekulative Identitätswahl anhand bloßer Häufigkeit, Aktualität oder gemeinsamem Vornamen.
- Sicherung und Bestandsprüfung vor Installation; keine stillen Massenkorrekturen am echten Bestand.
- Änderungen auf eigenem Branch; Tests mit tatsächlichen Fehlernachweisen, unabhängiges Review, dann Mac-Probe. Keine Behauptung eines fehlerfreien Gedächtnisses.

## Review Focus

- Verneinung, Absicht oder bloßes Antworten erledigen keine Aufgabe.
- Gleicher Vorname bei anderer Mailadresse verändert keinen fremden Wartestatus.
- Bestätigte Zusammenführung gilt auch nach Neustart; widerrufene/ungeprüfte Zusammenführung nicht.
- Mehrdeutiger Kurzname fragt vor Modell- und breiter Sucharbeit; eine häufige Person verdrängt keine andere.
- Änderung/Entzug einer Quelle macht alte Antwortbelege unbrauchbar; Hintergrundpause bleibt nach Update bestehen.

### Task 1: Sichere Aufgabenänderungen aus Mail

**Files:** `sidecar/icarus_memory/aufgaben_post.py`, passende Tests in `sidecar/tests/test_aufgaben_post*.py`, dazugehörige Bestandsdokumentation.

**Interfaces:** Bestehendes `Lauf.verarbeiten`, ProposalStore, TaskStore und Rückgängig unverändert nutzbar. Keine neue API und kein neues Modell.

- [x] Regressionsfälle zuerst rot: „Druckdaten noch nicht fertig, nächste Woche schicken“ lässt Aufgabe offen; Anna Frei beantwortet keine Aufgabe von Anna Berg.
- [x] Automatische Erledigung ohne nachgewiesene Erfüllung auf bestehenden Bestätigungsvorschlag begrenzen. Wortüberschneidung beweist nur möglichen Zusammenhang. Begründungen dürfen weder Versand der Unterlagen noch Erledigung erfinden.
- [x] Wartestatus nur bei eindeutig passender bekannter Gegenseite und belastbarem Bezug automatisch ändern. Widersprechende bekannte Adresse hat Vorrang vor Namensgleichheit; bei Unsicherheit keine stille Änderung.
- [x] Gegenprüfen: idempotente Wiederholung, Quellenänderung/-entzug vor Bestätigung, Rückgängig und unveränderte Fristen. Bestehende Tests, die das falsche Verhalten festschreiben, an den korrigierten Vertrag anpassen und erklären.
- [x] Gezielte Tests und dokumentierter Rot/Grün-Nachweis; Commit nur der zugehörigen Änderungen. Vollsuite einmal nach Integration aller Reparaturen.

### Task 2: Gemeinsame Identität und frühe Rückfrage

**Files:** `personenfrage.py`, `personen.py`/`person_merges.py` nur soweit zur Wiederverwendung nötig, `frage_weg.py`, `bedeutungen.py`, `working_memory_identity.py`, `agent.py`, `server.py` und betroffene Tests unter `sidecar/tests/`.

**Interfaces:** Vorhandene bestätigte `ClaimStore.person_merges` sind maßgeblich. Bestehender Auswahlvertrag (`meaning_choice`, scope) und Quellenschutz bleiben erhalten. Wiederverwenden statt parallele neue Identitätstabelle.

- [x] Die drei Gegenproben aus `/private/tmp/kingfisher-retrieval-probe-20261030.py` als bleibende Tests zuerst rot: zwei Alex + konkrete Fristfrage, dominante häufige Person, bestätigte zwei Adressen einer Person.
- [x] Namenskandidaten durch bestätigte Identität normalisieren, alle zugehörigen Quellen/Adressen berücksichtigen. Unbestätigte oder getrennte Personen nicht zusammenziehen.
- [x] Auch bei Kurznamen und konkreter Frage vor breiter Recherche rückfragen. Häufigkeit ordnet Möglichkeiten, bestätigt aber keine Person. Explizite Auswahl und bestätigte Aliasnamen bleiben nutzbar.
- [x] Frühe Identitätsprüfung im echten Gesprächseinstieg vor Fragedeutungsmodell und semantischer Suche; nicht nur direkt in `Agent.answer_memory`.
- [x] Tests für Auswahl/Fortsetzung, Widerruf/Neustart, Einzelperson und Entzug; Rot/Grün und betroffene Regressionstests. Commit der Reparatur.

### Task 3: Gesamtablauf, Bestand und Mac-Abnahme

**Files:** Ein integrierter Regressionstest unter `sidecar/tests/`, reproduzierbare lokale Probe unter `scripts/` nur wenn vorhandene Proben nicht ausreichen; sachliches Laufprotokoll unter `docs/runs/2026-10-30-memory-core-repair/`.

**Interfaces:** Bestehende Aufnahme, WorkingMemoryStore, Gesprächs-API, Quellen-/Aufgabenbestätigung und vorhandene Updatewege.

- [x] Künstlicher Fall: zwei gleichnamige Menschen, mehrere Adressen derselben bestätigten Person, Mail mit Aufgabe und Frist, spätere Korrektur, nicht erledigte Zusage, Quellenentzug und erneutes Öffnen des Bestands.
- [x] Kette testen: Original aufgenommen → Einordnung mit Beleg → richtige Akte → Rückfrage/Auswahl → richtige Antwort mit Quelle → Änderung/Entzug berücksichtigt → Aufgabe nicht fälschlich erledigt.
- [x] Eine volle Regression, Build, Syntax und vorgeschriebene Prüfungen nach letztem Code-Stand. Unabhängiges Review und relevante Reviewkorrekturen.
- [x] Bestehende echte automatische Aufgabenänderungen zunächst nur lesend nach Umfang und Belegen prüfen. Unsichere Altänderungen nicht still zurücksetzen; konkrete Liste/Reviewweg erhalten.
- [ ] Sicherung und Bestandsfingerabdruck vor Mac-Update, installierte Version/Commit prüfen. Aktive Konten und Kalender erhalten; Großimportpause nachlesen.
- [x] Im Mac-Fenster synthetische Aufnahme, Personenwahl, Quellensprung und Aufgabenstatus prüfen. Qwen9B/BGE-M3 in begrenzter Last und ohne ungewollte Parallelverarbeitung prüfen; Kosten/Antwortzeiten/Last und offene Grenzen nennen.
- [x] Großimport nur bei bestandener repräsentativer Qualitätsprüfung fortsetzen; andernfalls pausiert lassen und den konkreten Grund benennen.
