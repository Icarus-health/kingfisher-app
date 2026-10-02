# Merge-Reihenfolge

Laufend gepflegt. Jeder neue PR trägt sich hier ein: Basis, Inhalt, geprüft
womit, und an welcher Stelle er zusammengeführt wird. Für das Review am Mac
gilt: von oben nach unten, jeder Schritt nur, wenn der vorige grün ist.

GitHub-Actions ist wegen des Minutenkontingents rot; die Jobs brechen ab,
bevor ein Test läuft. Maßgeblich ist die lokale CI (`scripts/ci_lokal.sh`),
deren Ergebnis im jeweiligen PR steht.

## Integrationsprüfung vom 27. September 2026

Die folgende Tabelle dokumentiert die ursprünglichen Abhängigkeiten. Für den
jetzigen Merge werden #109 (gesamte Codekette) und #103 (separate Dokumentation)
zusammengeführt und die Korrekturen aus der Gegenprüfung ergänzt. Damit müssen
die Zwischenstände nicht einzeln auf `main` landen. Nachweise und verbleibende
Mac-Prüfungen: [INTEGRATION-2026-09-27.md](INTEGRATION-2026-09-27.md).

## Ursprünglicher Stand 26. September 2026

| Schritt | PR | Basis | Inhalt | Geprüft |
| --- | --- | --- | --- | --- |
| 1 | #102 | `main` | Gesamtstand #71–#101: Gedächtnis, Oberfläche, Sicherung vor dem Update, Aufgabenvorschläge im Briefing, Erststart | lokale CI grün auf `11ea5d7`, Docker-Rauchtests (Erststart, Update von `main`, Modellkette) |
| 2 | #103 | #102 | `docs/24-weg-zum-jarvis.md`, `docs/25-gedaechtnis-konzeptpruefung.md`, diese Datei, Verweis in `CLAUDE.md` | nur Dokumentation; Konzeptprüfung von zweitem Durchgang gegen den Code geprüft |

Nach Schritt 1 lassen sich #71–#101 schließen; ihr Inhalt ist in `main`.
Nach jedem Zusammenführen wird die Basis des nächsten PRs auf `main`
umgestellt, falls GitHub das nicht selbst tut.

## Neue Batches

Neue Arbeit baut auf dem jeweils letzten Schritt auf und wird hier unten
angehängt, sobald der PR steht.

| Schritt | PR | Basis | Inhalt | Geprüft |
| --- | --- | --- | --- | --- |
| 3 | #104 | #102 | Keine stillen Grenzen: Graph, Akten, Personenverzeichnis und Urteil lesen den ganzen Bestand statt der neuesten 5000 Quellen | lokale CI grün auf `2218069`; Test mit 5002 Quellen, Messung bei 20.000 |
| 4 | #105 | #104 | Offene Fragen („Was ist mit Mainz los?“) klären erst die Bedeutung, mit einem Klick; danach Suche nur in deren Quellen | lokale CI, Browserprüfung, zwei Gegenprüfungen durch einen zweiten Agenten, Sabotageproben |

| 5 | #106 | #105 | Mappe Ebene 2 und 3: „Stand der Dinge“ (Aufgaben, Termine, Bitten und Zusagen, Entwicklungen) und Chronik in Projekt- und Personenprofil, ohne Modell | lokale CI, Browserprüfung, Gegenprüfung durch einen zweiten Agenten, Sabotageproben |

| 6 | #107 | #106 | Gesprächsweg: „Was ist mit Mainz los?“ antwortet bei gemeintem Projekt sofort aus der Mappe, ohne Modell; Nachfragen bleiben im Projekt | lokale CI, Browserprüfung, Gegenprüfung durch einen zweiten Agenten, Sabotageproben |

| 7 | #108 | #107 | Etappe 2: Termine von selbst vorbereiten (Teilnehmer per Adresse, Projektvorschlag mit Grund, dauerhafte Berichtigung, Briefing „Vorbereitet“); Arbeitsbereich v2; Ortszeit im Briefing | lokale CI, Browserprüfung, Gegenprüfung durch einen zweiten Agenten, Sabotageproben |

| 8 | #109 | #108 | Etappe 2: Termine nachbereiten („Was ist herausgekommen?“ im Briefing, Text oder SRT/VTT-Mitschrift als Quelle mit Teilnehmern, Projekt und Terminende; „Nichts festzuhalten“; je Vorkommen einer Serie); Arbeitsbereich v3 | lokale CI, Browserprüfung, Gegenprüfung durch einen zweiten Agenten (Befunde in `0353712` behoben), Sabotageproben |

Schritt 3 bis 8 sind unabhängig von #103 (nur Dokumentation) und können auch
vor ihm zusammengeführt werden.

