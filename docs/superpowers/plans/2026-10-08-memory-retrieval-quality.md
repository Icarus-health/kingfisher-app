# Gedächtnisabruf: Ursachen getrennt messen

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Die acht ausgelassenen Umschreibungen nach tatsächlicher Fehlerstufe unterscheiden und daraus eine allgemeine, kontrolliert prüfbare Verbesserung ableiten.

**Architecture:** Vorhandenen echten Agentenweg und unveränderten Katalog verwenden. Diagnose darf weder Quellenwahl noch Antwort verändern; fehlende Abrufspur wird nicht als gemessener Nulltreffer ausgegeben. Modellantworten nur im synthetischen Werkzeug und begrenzt festhalten.

**Tech Stack:** Python, vorhandene lokale Ollama-Gewichte, bestehende SQLite-Testquellen.

**Spec:** `docs/63-cos-produktabschluss.md` und `docs/runs/2026-10-08-cos-delivery/README.md`.

## Global Constraints

- Keine privaten Quellen, Cloudkosten, Downloads oder neue Datenfreigaben.
- Katalog und alte Berichte unverändert lassen; keine Testwortliste als Suchkorrektur.
- Keine unbekannte Uhrzeit, Frist, Identität oder Bedeutung als Fakt ergänzen.
- Mac hält den geprüften installierten Stand, bis eine spätere Produktkorrektur geprüft ist.
- GitHub-CI nicht wiederholen; `[skip ci]` bei Veröffentlichung.

## Review Focus

- Fehlende Messspur ist unbekannt, nicht beobachtete leere Kandidatenmenge.
- Kandidatenfund, Auswahl und Anzeige dürfen nicht dieselbe Kennzahl erhalten.
- Modellfehler und noch laufende Modellaufrufe sind kein erfolgreicher Negativfall.
- Rohantworten begrenzen und nur aus künstlichen Quellen protokollieren.
- Verbesserte Trefferquote darf keine falschen Personen, Freigaben oder unbekannten Daten erzeugen.

### Task 1: Diagnose der Stufen

**Files:** `scripts/probe_working_memory_end_to_end.py`, `scripts/test_probe_working_memory_end_to_end.py`.

- [x] Regression für Kandidat gefunden/ungewählt, ausgewählt/ungezeigt, fehlende Spur und beobachtete leere Kandidaten; RED bestätigt.
- [x] Getrennte Felder und erste fehlende Stufe hinzufügen; altes `retrieved_expected` ausdrücklich als Anzeige-Kompatibilitätsfeld kennzeichnen.
- [x] Begrenzte synthetische Modellantworten samt Fehler-/Pendingzustand erhalten, RED dann GREEN.
- [ ] Einen echten begrenzten lokalen Diagnoselauf mit gespeicherten Rohantworten ausführen und unabhängig prüfen.

### Task 2: Kandidatenursachen prüfen

**Files:** Scratch-Auswertung in `/private/tmp`, abschließender Bericht in `docs/runs/`.

- [x] Bge-m3-Scores auf unverändertem Katalog und unabhängigen Ablenkern messen. Linux-CPU-Nachweis siehe docs/runs/2026-10-08-cpu-retrieval; echter Antwortlauf dort an RAM/Timeouts gescheitert.
- [ ] Fehlende Suchspur anhand tatsächlichem Suchaufruf klären; Modellwahl und Satz-Abstention gesondert prüfen.
- [ ] Erst danach engste allgemeine Korrektur mit unabhängigen Kontrollen festlegen. Keine blinde Schwellenabsenkung.

### Task 3: Verbesserung und Lieferung

- [ ] Beobachteten allgemeinen Defekt reproduzieren und mit einem unabhängigen Kontrollsatz absichern.
- [ ] Betroffene Prüfungen und echten eingefrorenen Vergleich ausführen, Grenzen offen dokumentieren.
- [ ] Nach Review geprüften Stand auf GitHub und bei Produktänderung datenerhaltend am Mac aktualisieren.

### Task 4: Beobachtete Uhrzeitbedingung bewahren

**Files:** `sidecar/icarus_memory/satzpruefung.py`, `sidecar/tests/test_satzpruefung.py`, `sidecar/tests/test_satzantwort.py`.

**Ruling:** Der echte Bericht enthält unabhängig vom Kandidatenabruf eine nachweisbare Bedeutungsänderung „erst nach 10 Uhr“ → „ab 10 Uhr“. Dieser konkrete Fehler wird parallel begrenzt korrigiert; ein blockierter neuer Modellstart ist dafür keine Voraussetzung. Zuständige Quellen und alte Antworten dürfen nicht verändert werden. Die gemeinsame Satzprüfung soll die Änderung verwerfen, der bestehende Renderweg auf das Originalzitat zurückfallen. Das ist eine begrenzte Prüfung von Uhrzeitgrenzen, keine allgemeine semantische Wahrheitsgarantie.

- [x] Echte Fehlformulierung sowie unabhängige Zeit-/Themenfälle als RED reproduzieren.
- [x] Allgemeine Prüfung lokaler Uhrzeitbedingungen implementieren; Quellenkopf ist kein zusätzlicher Bedingungsbeleg.
- [x] Unveränderte Zeiten, unterstützte Schreibweisen und Zeitbereiche erhalten; gespeicherte alte Satzantwort beim Rendern erneut prüfen.
- [x] Relevante Satz-/Antwort-/Zeitprüfungen und unabhängiges Diff-Review abschließen.


### Task 5: Unvollständige Bedeutungssuche sichtbar halten

**Befund:** Synthetischer echter Antwortweg mit zwei Quellen und Inventarlimit 1: Bedeutungssuche meldet `partial`, `prepare()` und `render()` melden aber weder begrenzten Bestand noch fehlende Suchabdeckung. Bei leerem Ergebnis kann der Rückfall fälschlich suggerieren, es gebe keine Information.

**Vertrag:** Treffer und Suchstatus werden pro tatsächlich ausgeführtem Suchaufruf gebunden, nicht nachträglich aus einem zwischen Threads veränderlichen globalen Status gelesen. Die alte Listen-Schnittstelle bleibt nutzbar. Teilbestand, Ausfall und unbeobachtete Adapter bleiben unterscheidbar. Gespeicherte Antworten brauchen beim erneuten Anzeigen keinen Embedder. Lexikalische und bestätigte Angaben bleiben nutzbar; unvollständige Suche wird dadurch nicht vollständig.

- [x] RED für begrenzte Quellenantwort, leeren Rückfall, Modellauswahl ohne passenden Treffer und Satz-Abstention.
- [x] Per-call-Status samt sichtbarer Kennzeichnung und Frischeprüfung implementieren; bestätigten Rückfall erhalten.
- [x] Diagnosewrapper auf echte statusgebundene Schnittstelle erweitern (RED/GREEN); unvollständige eingeschaltete Suche erhält keinen vollen Erfolgsscore.
- [ ] Betroffene Tests, unabhängiges Review und datenerhaltende Lieferung abschließen.

### Noch erforderlicher Nachweis für große Bestände

Die derzeitige semantische Suche ist weiterhin auf 2048 aktuelle Abschnitte begrenzt und hält ihre Vektoren nur flüchtig. Ein sichtbarer Begrenzungshinweis schließt diesen Funktionsabstand zum Ziel eines großen, langfristigen Gedächtnisses nicht. Vor Abnahme am vollständigen Mailbestand braucht es einen dauerhaft und inkrementell aufgebauten Suchindex über alle freigegebenen, eingeordneten Abschnitte mit Modell-/Quellenfingerabdruck, nachvollziehbarem Fortschritt, Entzug und Korrektur. Vorhandene Originalquellen und Arbeitsstand bleiben maßgeblich; ein solcher Index wäre lediglich abgeleiteter, wiederaufbaubarer Zustand. Keine blinde Erhöhung der Speichermenge, keine neue Wahrheitsdatenbank. Umsetzung und große Nutzbarkeitsmessung stehen noch aus.
