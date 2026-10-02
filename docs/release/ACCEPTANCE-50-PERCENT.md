# Abnahme des lokalen 50-Prozent-Stands

Datum: 8. September 2026. Zählweise unverändert: zehn vollständig erfüllte
Abnahmepunkte von zwanzig. Keine Aussage über halbe Entwicklungszeit oder AGI.

## Punkt 11: gemeinsames Tagesbriefing und Terminvorbereitung

Die gemeinsame Abnahme verbindet die bereits dokumentierten Einzelprüfungen
mit erneuten Docker-Browserläufen des aktuellen Images. Beide Ansichten lesen
die vorhandenen Stores; es gibt keine zweite Gedächtnisablage.

| Nutzerweg | Nachweis und Ergebnis |
| --- | --- |
| Aufgabe im Briefing öffnen und erledigen | Browser: trotz 50 Wartezuständen sichtbar, Aufgabenname und Projekt korrekt, Erledigen entfernt sie aus Briefing und Terminvorbereitung |
| Geänderte Entscheidungsgrundlage prüfen | Browser: Warnung in beiden Ansichten; vollständige Begründung im Briefing; Link öffnet passende Projektentscheidungen; Zurücknahme entfernt beide aktuellen Warnungen |
| Projekt und Person vorbereiten | Gezielte Tests und bisherige Docker-Läufe: ausschließlich gewählte IDs, getrennte Gleichnamige, aktuelle Aussagen, Aufgaben, Entscheidungen, Notizen und Quellen; kein Zuordnen anhand des Termintitels |
| Originalbeleg und Entzug | Tests und dokumentierte Docker-Läufe: Quellen öffnen, Skripttext inert, ausgeschlossene Quellen und widerrufene Aussagen nicht erneut als aktuellen Kontext verwenden; gemeinsame gezielte Claim-Auswahl mit der Personenakte |
| Ortszeit | Sommer/Winter und Tageswechsel als Regression; Docker-Browser Europe/Berlin und America/Los_Angeles in der vorangegangenen Prüfung bestanden |
| Kalender teilweise ausgefallen | Neue Regression vor Korrektur fehlgeschlagen. Aktueller Docker-Browser: Fehler im Briefing sichtbar, gesunder Termin weiterhin vorbereitbar, Wiederholung entfernt Fehler und stellt den zweiten Termin wieder bereit |
| Kalendertermin entzogen oder Quelle ausgefallen | API-Prüfung: 404 beziehungsweise 503; kein alter Vorbereitungskontext als Erfolg; Browser-Entzugsprüfung siehe CALENDAR-PREPARATION-QA.md |
| Lokaler echter Mac-Kalender | Nach Ausrollen echte Teilnehmer in der Vorbereitung lesend geprüft; keine Testdaten im Alltagsbestand |

Aktuelle gezielte Suite: 45 Tests bestanden. Browser: Chromium/Playwright,
1521 × 1034 und 1440 × 1000. Browser plugin nicht verfügbar, deshalb reguläres
Playwright. Keine JavaScript-Seitenfehler in den bestandenen Abläufen.
Die sichtbare Fehlerzeile nutzt die bestehende Darstellung; keine neuen
Einstellungen oder Einrichtungsfragen. Screenshot von Teilausfall und
Aufgabenbriefing visuell geprüft. Der vollständige Referenzvergleich aller
Desktop-Zustände bleibt eigenständig Punkt 16; mobile Abnahme bleibt ausgesetzt.

Lokale reproduzierbare Prüfeinstiege im Aufgabenordner `outputs/`:
`briefing-partial-qa.cjs`, `briefing-consistency-qa.cjs`,
`briefing-decision-context-qa.cjs`, `briefing-local-time-qa.cjs`.
Bildnachweise: `briefing-partial-failure.png`, `briefing-all-tasks.png`,
`briefing-decision-project.png` und die beiden Ortszeitbilder.

Automatische Mail-Relevanzsuche, dauerhafte automatische Terminzuordnung und
KI-Zusammenfassung sind damit nicht zugesagt. Die explizite, belegte Vorbereitung
und das gemeinsame aktuelle Gedächtnis erfüllen Punkt 11.

## Punkt 19: Update und verlustfreier Rückkehrweg

Erneuter vollständiger Lauf mit beiden korrigierten lokalen Versionen:

- Vorher: `sha256:82e4ca6bb779784497cb75148b0e6dcce379c059f3ed05394af161c1c5b67470`.
- Nachher: `sha256:7631de317d76e2366fa1f4365e66f62ebbdf76662002b13226119197e60749e2`.
- Tatsächliche Reihenfolge: vorher → nachher → vorher → nachher.
- Alle zehn SQLite-Stores fachlich befüllt; jede Stufe prüft Integrität,
  Schema-Version und sämtliche ursprünglichen Datenzeilen.
- Nach dem ersten Update eine weitere Aufgabe angelegt; auch sie bleibt bei
  Rückkehr und erneutem Update erhalten.
- Verschlüsseltes Vorher-Paket in einen neuen Ordner zurückgespielt; sämtliche
  Datenbankinhalte exakt verglichen. Die gespeicherte unveränderliche Image-ID
  startet die frühere Version als separate App. Neuere Arbeit bleibt in der
  aktualisierten Instanz erhalten.
- Beide Apps im Browser geprüft: Aufgabe, bestätigter Claim, Originalquelle,
  erhaltenes Gespräch, Modell verbinden, neue echte Ollama-Antwort und Neuladen.
- Der bereits vorhandene echte Aufgaben-Schema-Migrationstest prüft außerdem
  das Zurückspielen des alten Schemas, während der migrierte neuere Bestand
  erhalten bleibt. Pakettests prüfen zusätzlich Schlüssel und Einstellungen.

Prüfeinstiege: `outputs/acceptance-update.py`, `all-store-update-qa.cjs`,
`acceptance-return-qa.cjs`. Die Testbestände sind separate Docker-Volumes.
Die Alltagsinstanz wurde weder zum Befüllen noch zum Rücksetzen benutzt.
Anleitung: UPDATE-AND-RETURN.md; vorherige Nachweise: UPDATE-RUNTIME-QA.md.

Abgenommen ist dieser konkrete Update- und Rückkehrweg. Bei inkompatiblen
Schemaänderungen bedeutet Rückkehr die separate Wiederherstellung der passenden
Sicherung, keine verlustfreie Rückwärtsmigration beliebiger neuer Daten.
Ein automatischer Updater ist eine spätere Bedienverbesserung und gehört nicht
zum Wortlaut von Punkt 19. Die manuelle sichere Aktualisierung und die vorhandene
Wiederherstellungsbedienung sind geprüft; die Dokumentation benennt die Grenzen.

Gesamtprüfung des finalen Codes: 945 Backendtests bestanden in 176,39 Sekunden;
eine bestehende Starlette-Abkündigungswarnung. Docker-UI-Build, Assetmanifest
(14 Dateien, 17 Icons) und Diff-Prüfung bestanden. Nach Sicherung auf Port 8891
ausgerollt und echte Mac-Kalenderteilnehmer erneut im Browser geprüft.
