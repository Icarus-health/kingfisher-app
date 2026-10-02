# Einstieg in den begleiteten Alltagspilot

Dieser Bestand ist für echte Eingaben gedacht. Eingaben, Korrekturen, Aufgaben und Gespräche bleiben gespeichert. Der Pilot ist kein Wegwerf-Test: Beim normalen Start oder Update wird kein neuer Datenbestand angelegt und nichts zurückgesetzt.

**Lokaler Start:** Mac-App `Kingfisher.app` oder http://127.0.0.1:8892. Der dauerhafte Datenbestand heißt `kingfisher-pilot-data`. Der vorherige Testbestand wurde gesichert und separat behalten.

## Zum Einstieg

1. Kingfisher über die Mac-App öffnen. Mit einer kleinen Auswahl eigener Notizen und Dokumente unter **Gedächtnis** beginnen. Die lokale automatische Einordnung muss als aktiv angezeigt werden; noch ausstehende oder fehlgeschlagene Quellen sind keine bereits durchsuchten Erinnerungen.
2. Einige Fragen stellen, deren Antworten bekannt sind. Die Originalquelle öffnen und Person, Projekt, Datum und Bedingungen prüfen. Eine Quellenangabe ist noch keine Garantie, dass die Aussage wahr oder aktuell ist.
3. Aufgaben zunächst ausdrücklich anlegen beziehungsweise einen Quellenvorschlag prüfen und übernehmen. Vorschläge können falsch formuliert oder unvollständig sein. Über **Bearbeiten** lassen sich Titel, Termin und Notiz korrigieren. Ein erledigter Eintrag lässt sich wieder öffnen; übernommene Angaben behalten ihren Quellenbezug.
4. Unter **Einstellungen** erst ein Mailkonto verbinden und einen begrenzten Bestand einlesen. Danach die weiteren Konten einzeln ergänzen. Passwörter nur in der App eingeben, nicht im Chat oder in Git. Die derzeitige Anbindung ist IMAP/SMTP; ein Google-OAuth-Anmeldeknopf ist noch nicht vorhanden. Ob ein Google-Konto die angebotene Anmeldemethode erlaubt, ist beim Verbinden zu prüfen.
5. Gewünschte Kalender ausdrücklich auswählen. Die Kalenderansicht und Vorbereitung sind lesend nutzbar. Eine gelesene Terminnotiz ist keine ausgeführte Buchung; automatische Terminänderungen sind nicht Bestandteil dieser ersten Freigabe.
6. In den ersten Arbeitstagen Mail-/Kalender-/Aufgabenprogramme parallel weiterführen. Externe Nachrichten nur nach sichtbarer Prüfung/Freigabe. Eine echte SMTP-Zustellung ist gesondert an einem festgelegten Testempfänger zu prüfen.

## Größere Bestände

Mailimport arbeitet kontoweise in fortsetzbaren Paketen, mit Entdopplung und gespeichertem Fortschritt. Ein einzelner Abruf importiert standardmäßig bis zu 50 Nachrichten (bei zusätzlicher KI-Filterung weniger). Die automatische Einordnung läuft anschließend lokal; das kann deutlich länger als die eigentliche Aufnahme dauern. Im Gedächtnis die Abdeckung kontrollieren, nicht nur die Zahl gespeicherter Quellen.

Der technische Lasttest mit 10.000 synthetischen Nachrichten prüft Aufnahme, Index und Auffindbarkeit. Er verwendet für die Einordnung keinen Sprachmodelllauf und beweist weder vollständige Verarbeitung beliebiger Archive noch allgemeine Antwortgenauigkeit. Lange Einzelquellen über 12.000 Zeichen werden derzeit nicht automatisch vollständig eingeordnet; ihr Status muss sichtbar bleiben. Deshalb zuerst kleine reale Pakete prüfen und erst danach schrittweise erweitern.

## Daten und Sicherung

- Der Pilot verwendet einen dauerhaft benannten Docker-Datenbestand. Bei Updates muss genau dieser Bestand weiterverwendet werden.
- Der frühere Testbestand bleibt getrennt erhalten. Er wird nicht mit späteren echten Pilotdaten vermischt.
- Regelmäßige lokale Sicherungen und Sicherungen vor Datenbankmigrationen sind vorhanden. Eine zusätzliche exportierte Sicherung über die Einstellungen schützt auch außerhalb des Docker-Volumes; das Sicherungspasswort muss der Nutzer sicher aufbewahren.
- Eine wiederhergestellte Sicherung öffnet zunächst als historische, lesende Ansicht. Alte Modell-, Konto- und Aktionsfreigaben werden nicht automatisch reaktiviert; sie ist kein nahtlos weiterlaufender Arbeitsbestand. Geprüfte Originale können gezielt neu aufgenommen werden.
- Docker-Volumes und die private Startkonfiguration nicht löschen. Ein Image oder die Mac-Start-App allein enthält die Nutzerdaten nicht.
- Der Start aus dem Mac-Symbol öffnet vorerst den Browser. Ein eigenes Fenster ohne Browserleisten folgt später.

## Was noch tatsächlich erprobt werden muss

Die persönlichen Konten, reale Nachrichten- und Kalenderänderungen und mehrere echte Arbeitstage sind eine offene Abnahme. Synthetische Prüftage und bestandene Softwaretests ersetzen sie nicht. Fehlerfälle mit Frage, erwarteter Antwort und zugehöriger Quelle festhalten; Zugangsdaten dabei weglassen.
