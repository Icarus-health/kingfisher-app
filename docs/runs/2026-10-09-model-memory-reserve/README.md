# Arbeitsspeicher für den Arbeitsalltag freihalten

Die Gerätehilfe plante bereits 40 % RAM (mindestens 6 GB) für System und andere Programme ein. Empfehlung, Laden und Parallelplanung verwendeten dagegen 85 % des gesamten RAM als Modellbudget. Auf einem 32-GB-Mac erschienen damit rund 27 GB als akzeptabel, obwohl die Hilfe nur 19,2 GB für Modelle vorsah.

Alle diese Wege verwenden jetzt dieselbe Planungsreserve. Separates GPU-VRAM unter Windows/Linux behält sein getrenntes 85-%-Budget. Auf 32 GB teilen sich Frage und Antwort in der Vorauswahl dasselbe katalogbekannte 9B-Modell: 18 GB einschließlich Satzprüfung und Einbettung am Tag, 12 GB für Hintergrund und Einbettung, innerhalb 19,2 GB. Das ist eine reine Kapazitätsschätzung, kein Qualitäts- oder Laufzeitnachweis.

Bekannte zu große Modelle werden vor Download oder Auswahl abgelehnt: Einzeleinrichtung, Gesamtpaket, Expertenrolle (rollenübergreifend) und Standardmodell-Einrichtung einschließlich ihrer alten Route. Die Ablehnung erfolgt vor Einstellungsänderungen. Die Standardmodell-Prüfung spiegelt den Vorrang externer Umgebungsvorgaben; alte aus Einstellungen abgeleitete Werte werden dabei ersetzt. Lokale kompatible Endpunkte unterliegen ebenfalls der Reserve, entfernte Cloud-Endpunkte nicht. Die Oberfläche sperrt nicht passende Einrichtungsknöpfe und die Gesamteinrichtung vor der ersten Teilanfrage; Standardmodell-Verbindungsfehler zeigen die konkrete Erklärung des Servers.

Gezielte rot/grün Regressionen belegen die ursprünglichen Reserveabweichungen, gemeinsame Modellnutzung, Experten- und Standardmodell-Bypässe. Die bisherigen Goldenerwartungen wurden auf die neue Reserve aktualisiert; ein Test der priorisierten Prüfmodell-Verkleinerung verwendet bewusst separates 24-GB-GPU-VRAM, wo dieser Fall weiterhin gilt. Keine Modellnamen oder Größen wurden im Katalog geändert.

## Grenzen

Keine harte Betriebssystem-RAM-Grenze und keine Messung des aktuell freien RAM. Bestehende Auswahl wird nicht still geändert; unbekannte eigene Modelle erhalten keine erfundene Größe. Die Speicherplanung allein beweist weder Antwortqualität noch Gedächtnisqualität. Keine Modelle wurden geladen oder aktiviert und keine Cloud-/Privatdaten verarbeitet. Dieser Stand ist noch nicht auf dem Mac installiert; der Nutzer hat den Fenstertest verschoben. Kalender-PR #37 bleibt unabhängig offen.

## Schlussprüfung

Codecommit: `9b78e157e34a9b1a15a9b2c306419e09126811bf`, unabhängig auf `e7033f55635bddc7439c127decc092ae4d8bb789` aufgebaut. Nur die 14 Dateien der Speicherplanung und ihrer Tests wurden übernommen; Kalenderänderungen gehören weiterhin zu PR #37.

- 24 neue Testfälle für Reserve, gemeinsame Modellnutzung, Auswahlwege und effektive Umgebung. Drei neu aufgefundene Umgehungen scheiterten vor dem finalen Guard (externer Anbieter, externes Modell, lokaler kompatibler Endpunkt); sie bestehen danach. Kontrollen für ersetzte Einstellungswerte und einen künstlichen entfernten Endpunkt bestehen ebenfalls.
- Auf dem eingefrorenen Codecommit: 231 betroffene Backend-Tests bestanden, 1 erwarteter Skip; Geräteprofil, Empfehlung, Modellpaket, Rollenwahl, Hintergrund und beide Einrichtungswege abgedeckt.
- 434 UI-Tests bestanden; TypeScript-Prüfung und Vite-Build erfolgreich. Der UI-Quellstand blieb beim Umsetzen auf den Main-Commit bytegleich. Die übliche Warnung zur Bundlegröße bleibt.
- Unabhängige begrenzte Codeprüfung: nach der Korrektur kein weiterer konkreter Blocker; der Prüfer hat keine Tests oder privaten Daten gelesen.
- `git diff --check` sauber. Kein vollständiger Backend-Gesamtlauf, keine CI-Wiederholung, kein Abonnement oder Check-in. Native Bedienprüfung und Installation bleiben offen.
