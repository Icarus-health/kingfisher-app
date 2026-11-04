# Gespeicherte Mail: vollständige Aufgabenbestätigung

Begrenztes P3-Paket des freigegebenen Produktplans; Basis main `1b5a262`.

## Vertrag

Die gespeicherte Originalmail bleibt ohne Postfach- oder Modellabruf lesbar. Ihre Aufgabenvorschläge verwenden dieselbe geprüfte Frist- und Personenanzeige wie die Aufgabenliste. Datum, Uhrzeit, Bezugsperson und Projekt sind vor der gemeinsamen Übernahme sichtbar. Der Nutzer kann den Fälligkeitstag und „Warte auf“ ändern; eine unveränderte belegte Uhrzeit bleibt erhalten. Historische, ungeprüfte oder unklare Fristen werden nicht automatisch als heutige Fälligkeit übernommen. Personenbezug und wartende Person bleiben getrennt.

Die Übernahme verwendet die aktuellen eigenen Kontoadressen, damit eine eigene Zusage dem Empfänger zugeordnet wird. Änderungen der eigenen Identität zwischen Vorschau und Bestätigung erfordern erneutes Prüfen. Entzug, Quellenänderung, Wiederholung und Speichern nach ungewissem Ausgang nutzen die bestehenden Schutzmechanismen.

## Umsetzung

- [x] Backend-Gegenproben für Fristanzeige, eigene Zusage, Identitätsänderung und Quellenentzug.
- [x] Bestehende Vorbefüllung wiederverwenden; Identität an Bestätigung binden.
- [x] Oberfläche mit kompaktem Personen-/Fristhinweis und aufklappbaren Änderungsfeldern; Änderungen und Fehler erhalten den Entwurf.
- [x] Betroffene Tests, unabhängiges Review und gerenderte künstliche Bedienprüfung.
- [ ] Auf GitHub liefern. Native Macprüfung und normaler Updateweg bleiben getrennt nachzuweisen.

## Review Focus

Eigene Nachricht wird als fremde Bitte verknüpft; historische Frist wird heute aktiv; belegte Uhrzeit geht bei Tagesauswahl verloren; unbestätigte Modellfrist überdeckt ein geprüftes leeres Ergebnis; Kontoidentität ändert sich nach Vorschau; Entwurf bleibt nach Fehler sichtbar, enthält aber unbemerkt neue Quellenwerte; Wiederholung erzeugt eine zweite Aufgabe.

## Ruling

Dieses Paket vereinheitlicht den vorhandenen Aufgabenweg, statt einen neuen Modellaufruf oder eine neue Fristerkennung einzubauen. Große Gedächtnis-/Importqualität wird damit nicht behauptet. Der Großimport bleibt pausiert.

Ergebnisse und Grenzen: [Prüfprotokoll](../../runs/2026-11-04-saved-mail-task-confirmation/README.md).
