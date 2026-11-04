# Bereichsablage mit 10.000 und 50.000 künstlichen Quellen

Ausgeführt gegen den Code von `aad77114aebf375681022057cf120f4bcaf1c754` mit
`scripts/probe_memory_area_scale.py --sizes 10000,50000 --body-chars 2048`.
Alle Daten liegen in einem getrennten temporären Bestand; keine Modelle, Cloud
oder persönlichen Quellen. `areas.json` enthält die vollständigen Messwerte.

Bei 50.000 Quellen: Median der Bereichsseiten 11 ms (Alle), 15 ms (Arbeit),
288 ms (Gesundheit), 278 ms (leere Finanzansicht), 223 ms (begrenzte Sonstige-Suche).
Die Sonstige-Suche meldet ihre Grenze und einen Folgecursor; sie täuscht kein
vollständig leeres Ergebnis vor. Die ältesten gezielt zugeordneten Quellen und
der Quellenentzug wurden geprüft. Prozess-RSS maximal 47.857.664 Bytes,
Datenbankgröße 630.202.368 Bytes; gesamter Test etwa 51,6 Sekunden.

Dies prüft feste künstliche Zuordnungen und Bereichsseiten, keine Modellqualität,
vollständige Suche, normale Mailimportgeschwindigkeit oder flüssige Mac-Gesamtlast.
Der Versuch, die Prozesspriorität mit `nice` zu senken, wurde vom System abgewiesen;
der begrenzte Test lief trotzdem regulär zu Ende. Das wird nicht als erfolgreich
abgesenkte Priorität berichtet.
