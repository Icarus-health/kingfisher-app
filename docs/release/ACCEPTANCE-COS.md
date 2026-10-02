# Abnahme: gemeinsamer Stabschef-Ablauf

8. September 2026. Abnahmepunkt 12 bleibt unverändert:

> Projekte, Aufgaben, Zusagen, Entscheidungen und Aktionsfreigaben gemeinsam bedienen

Ergebnis: **erfüllt**. Damit sind 12 von 20 bestehenden Punkten erfüllt (60 %).
Keine Teilpunkte und keine Umdefinition der Zählweise.

## Gemeinsamer Lauf

Der Ablauf wurde im gebauten Image `kingfisher:task-candidates` (Image-ID
`bad18e55c9f2`) auf dem Mac mit einem ausschließlich synthetischen, separaten
Datenvolume durchgeführt. Kalender und Mail stammen aus kontrollierten lokalen
Testadaptern; keine Nachricht wurde an einen externen Empfänger versendet.

| Anforderung | Konkreter Nachweis |
| --- | --- |
| Projekt und Aufgabe gemeinsam bedienen | Projekt in der UI angelegt; erkannte Zusage mit expliziter Projektwahl übernommen; Aufgabenansicht behält die Zuordnung |
| Zusage prüfen und verfolgen | Zeitplan erzeugt belegten Kandidaten; UI zeigt Originalzitat; Übernahme als Warteaufgabe für Alex, Quelle öffnen, ausdrücklich zurück zu mir holen |
| Tagesüberblick und Terminvorbereitung | Überfällige Aufgabe führt vom Tagesüberblick in dieselbe Projektaufgabe; Terminvorbereitung enthält genau diese Aufgabe und die zugehörige Entscheidung |
| Entscheidung begründen und prüfen | Entscheidung im Projekt mit explizit gewählter Budgetgrundlage gespeichert; späterer Widerruf zeigt Prüfbedarf sowohl bei der Entscheidung als auch in der Terminvorbereitung |
| Aktionsfreigabe und Ergebnis | Antwort auf die ursprüngliche Projektmail entworfen; falsche Bestätigungsphrase hält Ausführung gesperrt; korrekte Phrase führt im lokalen Mailadapter genau einmal aus; Freigabe und Ergebnis stehen im Gespräch |
| Neustart und Wiederholung | Container neu gestartet: Aufgabe, Quellenzitat, Projekt, erschütterte Entscheidung und Freigabeverlauf erhalten; kein erneuter Kandidat, kein erneuter Versand; Aufgabe erledigen und wieder öffnen funktioniert |
| Lokale Modellauswertung | Tatsächliches Ollama-Modell qwen3.5:4b erkennt aus synthetischer Projektmail zwei Aufgaben mit Originalzitaten; Wiederholung analysiert dieselbe Quelle nicht erneut. Details und erster fehlgeschlagener Versuch stehen in TASK-DETECTION-QA.md |
| Fehler und Entzug | Gezielte Tests prüfen Quellen-/Modellentzug, atomaren Prüfstand, doppelte Speicheraufrufe und unterbrochene Übernahme. Browser-503-Test erhält Eingaben und erlaubt erneutes Speichern |
| Einfache UI | Bestehende Aufgabenansicht mit zugeklappter Prüfgruppe; Sichtprüfung und begrenzte delegierte Umsetzungsfreigabe in SDR-012 |

## Technische und lokale Nachweise

- Vollständige Backend-Suite: **1.001 bestanden**, bekannte Starlette/httpx-Warnung,
  228,68 Sekunden. Lokale unversionierte Synchronisationskopien `* 2.py` wurden
  wie bisher nicht als Teil der versionierten Tests ausgeführt.
- TypeScript/Vite, Assetmanifest mit 14 Dateien und 17 Icons sowie Docker-Build
  bestehen. GitHub-CI für den Code-Commit `69af485` ist erfolgreich.
- Playwright im echten Chromium-Browser, 1440 × 1000, kein Framework-Overlay,
  keine unerwarteten Konsolen- oder Seitenfehler. Browser plugin nicht verfügbar;
  vorhandenes reguläres Playwright verwendet.
- Gemeinsame Skripte im lokalen Aufgabenordner: `outputs/common-cos-qa.cjs`,
  `outputs/common-cos-restart.cjs`; Testfixture `outputs/common-cos-server.py`.
  Screenshots `common-cos-preparation.png`, `common-cos-changed-basis.png` und
  `common-cos-restart.png` wurden betrachtet. Der erste Projektselektor wurde
  auf die tatsächliche Combobox korrigiert. Beim Neustart begann der erste
  Browseraufruf vor Erreichbarkeit; nach positiver Health-Prüfung bestand der Lauf.
- Nutzerinstanz auf **127.0.0.1:8891** aktualisiert; vorhandenes Datenvolume
  `kingfisher-review-20260907` erhalten. Vorherige Sicherung:
  `/data/sicherungen/kingfisher-20260908T082147Z`.
- Nach Auslieferung: Health erfolgreich, Vorschlagsdatenbank auf Schema 3 mit
  `integrity_check = ok`; tatsächliche Mac-Kalenderteilnehmer in der
  Terminvorbereitung erneut im Browser geprüft, ohne private Details auszugeben.

## Grenzen bleiben sichtbar

Die Modellerkennung ist ein Vorschlag, keine Garantie vollständiger oder richtig
interpretierter Zusagen. Originalzitat, ausdrückliche Annahme und Bearbeitung
bleiben erforderlich. Der Zeitplan und seine Modellprüfung sind opt-in.
Ein offener Wartezustand wird ausdrücklich bedient; eine automatische Bewertung,
ob eine spätere Antwort eine Zusage erfüllt, wird nicht behauptet.

Diese Abnahme erweitert den ursprünglichen Punkt 12 nicht zu einer vollständigen
Umsetzung aller langfristigen Produktvisionskapitel. Insbesondere sind echter
Mailanbieter und fortlaufende Quelleneinrichtung (09), alle Profilbeziehungen (07),
Agentenübergaben (13), Ziele/Gewohnheiten/Außenwelt (14), Automationen/Browser/Sprache
(15), vollständige Referenzabnahme (16), Docker-Desktop-Neuinstallation (17) und
vollständiger persönlicher Alltagstest (20) weiterhin offen. Kein AGI-Nachweis.
