# Fortlaufende Zusagenerkennung — Arbeitsstand 8. September 2026

## Implementierter Kern

`TaskDetector` prüft gespeicherte Nachrichten und Dokumente mit dem lokalen
Modell. Er verwendet denselben Extraktions- und Zitatprüfer wie die bisherigen
Mailvorschläge. Zusammenfassungen und ausgeschlossene Quellen bleiben außen vor.
Ein Lauf ist auf höchstens 20 Modellaufrufe begrenzt; Rohquellen werden in Seiten
gelesen. Der Prüfstand ist unabhängig vom Zustand der Wissensverdichtung.

Die bestehende Vorschlagsdatenbank erhält in Migration 2 eine Prüftabelle.
Vorschläge und Prüfstand werden in einer gemeinsamen SQLite-Transaktion
angelegt. Auch ein leeres Ergebnis wird gespeichert. Bereits abgelehnte
Vorschläge werden bei Wiederholung und Neustart nicht erneut vorgelegt.
Eine zweite Store-Verbindung kann dieselbe Prüfung nicht doppelt speichern.

Aufgabenkandidaten tragen Episode, Digest und Originalzitat. Der bisherige
Annahmepfad für persönliche Wissensaussagen weist sie ausdrücklich ab.
Quellenentzug und Entzug der Laufberechtigung während des Modellaufrufs
verwerfen das Ergebnis. Bereits gespeicherte offene Kandidaten aus entzogenen
Quellen werden beim nächsten Prüflauf als überholt markiert. Modellfehler
bleiben erneut prüfbar; Statusmeldungen enthalten keine fremden Fehlertexte.

## Geprüft

107 gezielte Tests bestanden, eine bestehende Starlette/httpx-Warnung:

- `test_task_detection.py`: 12 neue Prüfungen zu Neustart, Ablehnung, unabhängigen
  Quellen, lokalem Modell, Quellen-/Berechtigungsentzug, erneutem Versuch,
  ausgeschlossenen Zusammenfassungen, begrenzten Läufen, Datenbankmigration,
  gleichzeitigen Verbindungen und Transaktionsabbruch.
- `test_migrations.py`, `test_verdichtung.py`, `test_mail_conversation_flow.py`:
  bestehende Migrations-, Wissens- und Mailabläufe weiterhin erfolgreich.
- Die Sabotageprobe erzwingt einen SQLite-Abbruch beim Schreiben des Prüfstands:
  Es bleiben weder halbe Vorschläge noch ein falscher Erledigtstand zurück.

Lokales Protokoll: `outputs/task-detection-foundation-tests.txt` im Aufgabenordner.

## Noch keine Abnahme von Punkt 12

Der Kern ist noch nicht an den laufenden Zeitplan oder die Oberfläche
angeschlossen und wurde nicht auf die Nutzerinstanz ausgerollt. Offen sind:

1. Ausdrückliche, wiederholsichere Übernahme in die bestehende Aufgabenablage,
   einschließlich Projekt, Fälligkeit, Wartezustand und Originalquelle.
2. Einfache Prüfung und Ablehnung in der Aufgabenansicht sowie Zeitplananbindung
   mit aktuellem Modell und aktueller Berechtigung. Fehlerhafte Quellen müssen
   bei längerem Rückstau andere Quellen nicht dauerhaft verdrängen.
3. Echter lokaler Modelllauf, Browserprüfung, Neustart und gemeinsamer Ablauf
   mit Projekt, Aufgabe/Zusage, Entscheidung, Briefing und Aktionsfreigabe.
4. Gesamttests, lokale Auslieferung und GitHub-Review des vollständigen Ablaufs.

Die dokumentierte Abnahme bleibt unverändert bei 11 von 20 Punkten (55 %).

## Übernahmeweg ergänzt

Der Backend-Pfad `/api/v1/task-candidates` liefert offene Vorschläge und erlaubt
mit ausdrücklichen POST-Aufrufen Annahme oder Ablehnung. Bei Annahme werden
Titel, optionale Projektzuordnung, Fälligkeit und Wartezustand in die bestehende
Aufgabenablage geschrieben. Die Originalstelle bleibt an der Aufgabe lesbar.
Vor einer neuen Aufgabe werden Quellenzustand, Digest und Wortlaut erneut
geprüft. Eine bereits abgeschlossene Übernahme wird bei Wiederholung unverändert
zurückgegeben.

Eine feste, aus dem Vorschlag abgeleitete Aufgabenkennung verhindert Dubletten
auch beim Abbruch zwischen Aufgaben- und Vorschlagsspeicherung. Der nächste
Aufruf vervollständigt den Vorgang. Der Abnahmetest entzieht zusätzlich die
Quelle nach diesem Abbruch: Die zuvor ausdrücklich gespeicherte Aufgabe bleibt
erhalten und wird nicht irrtümlich als neue Übernahme behandelt.

112 gezielte Tests bestehen einschließlich vollständiger Wiederherstellung.
Protokoll: `outputs/task-candidates-tests.txt`. Der erste API-Test deckte eine
verschachtelte, nicht wiedereintrittsfähige Sperre auf; der zusätzliche äußere
Lock wurde entfernt, der anschließende Lauf besteht. Noch keine UI-Anbindung,
Zeitplanaktivierung oder neue Roadmap-Abnahme. Punkt 1 der obigen offenen Liste
ist damit im Backend umgesetzt; seine gemeinsame Browserprüfung bleibt offen.

## Zeitplan und Aufgabenoberfläche ergänzt

Der Zeitplan prüft Zusagen nach der Quellenaufnahme. Die vorhandene getrennte
Modellfreigabe bleibt Voraussetzung; ein Cloud-Modell erhält für diesen Schritt
keine Rohquellen. Bei geänderter Zeitplaneinstellung oder gewechseltem Agenten
wird ein laufendes Ergebnis verworfen. Ein Erkennungsfehler verhindert die
anschließenden Schritte einschließlich Sicherung nicht.

Migration 3 speichert die Leseposition. Ein begrenzter Lauf fährt beim nächsten
Mal hinter der zuletzt versuchten Quelle fort. Das gilt auch bei Modellfehlern
und nach einem Neustart. Nach dem Ende des Bestands beginnt die nächste Runde
wieder vorn; nicht erfolgreich geprüfte Quellen bleiben dadurch erneut prüfbar.
97 gezielte Zeitplan-, Aufgaben-, Migrations- und Wiederherstellungstests bestehen.

In den Ansichten „Meine Aufgaben“ und „Warte auf andere“ erscheint bei offenen
Vorschlägen ein kompakter Knopf „Zur Prüfung“. Aufklappen zeigt Originalzitat,
Quelleninhalt und die ausdrücklichen Aktionen Prüfen und Verwerfen. Das Formular
nutzt die bestehenden Projekt-, Datums- und Wartefelder. Die Übernahme zeigt die
Aufgabe anschließend in der passenden Aufgabenansicht. Leere Vorschlagslisten
belegen keinen eigenen Bereich. Ein fremder Antworttext bleibt reiner Text.

Browserprüfung auf dem Mac gegen eine isolierte lokale Testinstanz:

- 1440 × 1000: Aufklappen, Formular prüfen, Warteperson eingeben, ausdrückliche
  Übernahme und Anzeige in „Warte auf andere“; Neuladen erhält Aufgabe und Quelle.
- Absichtlich ausgelöstes HTTP 503: Fehlermeldung sichtbar, Eingaben erhalten,
  anschließender erneuter Versuch erfolgreich.
- Zweiten Vorschlag verwerfen; keine JavaScript-Ausnahme und kein unerwarteter
  Konsolenfehler. Der erste Test verwendete einen falschen Überschrift-Selektor;
  der korrigierte Lauf gegen frische Testdaten besteht.
- Die Screenshots `outputs/task-candidates-form.png` und
  `outputs/task-candidates-saved.png` wurden betrachtet. Formularabstände und
  Feldanordnung wurden kompakter an die vorhandene Gestaltung angeglichen.
- Browser plugin not available: reguläres vorhandenes Playwright verwendet.
  Keine neue Browser-Abhängigkeit. Die bekannte globale Mindestbreite der App
  bleibt offen; dieser Lauf behauptet keine neue mobile Gesamtabnahme.
- TypeScript/Vite und Assetmanifest (14 Dateien, 17 Icons) bestehen.

Die UI-Skill-Prüfung umfasst den hier beschriebenen Vorschlagsablauf. Der volle
CoS-Ablauf mit Entscheidung und Aktionsfreigabe, Docker-Auslieferung und
GitHub-Abgleich bleiben für Punkt 12 erforderlich. Noch keine Erhöhung auf 60 %.

### Gesamttests

Die vollständige Suite dieses Stands besteht mit **1.001 Tests** in 228,68
Sekunden, einer bekannten Starlette/httpx-Warnung und unverändert ausgeschlossenem
lokalem Dateimuster `* 2.py` (unversionierte Synchronisationskopien).
Protokoll: `outputs/task-candidates-full-tests.txt`.
Ein erster echter Ollama-Lauf mit qwen3.5:4b lieferte dagegen keinen verwertbaren
Vorschlag (`failed=1`). Er zählt nicht als Modellnachweis; die Ursache wird
getrennt untersucht. Der erfolgreiche Browserlauf verwendet synthetische,
vorgegebene Kandidaten und ersetzt diesen Nachweis ausdrücklich nicht.

Der anschließende diagnostische Ollama-Lauf nach Ende der Gesamtsuite ist
bestanden: qwen3.5:4b erkannte zwei Aufgaben aus einer synthetischen Projektmail
und lieferte zwei wörtlich vorhandene Textstellen ohne Werkzeugaufruf. Der
anschließende Wiederholungslauf analysierte null Quellen. Ergebnis:
`outputs/task-detection-ollama-result.json`. Der erste Fehler ist mangels
Detailprotokoll nicht abschließend erklärt; eine behobene Modellursache wird
nicht behauptet. Der wiederholbare Prüfstand erlaubte den erfolgreichen erneuten
Versuch, ohne die Quelle vorher fälschlich als erledigt zu markieren.
