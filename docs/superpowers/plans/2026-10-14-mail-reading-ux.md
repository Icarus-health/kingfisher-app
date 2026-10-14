# Mail lesen und den nächsten Schritt erkennen

Grundlage: freigegebener Bedienplan und erneute Rückmeldung vom 14.10.: Maildarstellung, Schrift, Übersicht und zu viele Klicks. Die frische synthetische Bedienprüfung zeigt, dass Metadaten, technische Erläuterungen und doppelte Zitate die Mail verdrängen. Allgemeine CSS-Regeln überschreiben Teile der kompakten Aufgabenansicht.

## Verbindlicher Umfang

- Postfachwahl kompakt über der Liste; Lesetext erhält die frei werdende Spalte.
- Absender und Datum unmittelbar am Betreff. Speicherung, Antwortadresse und Quellenverwaltung bleiben unter Details erreichbar. „Gespeichert · aktueller Postfachstand unbekannt“ bleibt sichtbar.
- Originalmail ohne zusätzlichen Öffnungsklick lesbar. Originalstellen, Aufgabenfelder und Speicherung unterscheiden sich sichtbar; lange Belege erscheinen auf Wunsch. Historische/ungeprüfte Quellen, Fehler und unvollständige Auswertung bleiben ausdrücklich sichtbar.
- Vorbereitete Aufgabe und Projekt bleiben unmittelbar änderbar und mit einem Klick bestätigbar. Keine Modellarbeit oder Providerabfrage beim Blättern; keine ungeprüfte Frist, Zuständigkeit oder automatische Faktenübernahme.
- Einheitliche Schriftstufen: 16 px Lesetext, 14 px Bedienung, 13 px ergänzende Angaben, 26 px Seitenüberschrift. Kompakte Seitenköpfe und geschlossene Aufgabenfläche. Aktive Auswahl muss in beiden Farbschemata lesbar sein.
- Sammelzuordnung in Bereichen erscheint erst nach einer Auswahl. Originale und bisherige Bestätigungsprüfung bleiben unverändert.
- Großimport bleibt pausiert. Keine Änderungen an Produktionsdaten, Zugängen oder Modellen; Mac-Abnahme erfolgt danach.

## Umsetzung und Prüfung

1. Regressionen für direkten Originaltext, kompakte Quelldetails, unveränderte Quellenprüfung und Postfachfilter zuerst prüfen; Mailansicht und Aufgabenbelege vereinfachen.
2. Bestehende Arbeitsflächen und Schriftstufen konsolidieren; keine neuen UI-Funktionen oder zweites Designsystem. Kompakte Aufgabenstile nach allgemeinen Materialregeln laden.
3. Betroffene UI-Tests und gesamten UI-Lauf ausführen, Build prüfen. Frische Browserprüfung bei 1280 und 900 px: Lesen, Aufgabe/Projekt, Rückweg, Such- und Kontofilter. Zusätzlich schmalen Reflow, Fokus, Fehler und Farbschemata prüfen, soweit die Browsersteuerung sie unterstützt.
4. Unabhängiges Review. Draft-PR mit überprüfbaren Nachweisen; Mac-Installation und Alltagsabnahme ausdrücklich offen lassen.

Keine vollständige WCAG-Abnahme oder Qualitätsaussage über echte Modellauswertung aus den künstlichen Daten ableiten.
