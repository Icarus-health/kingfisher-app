# Reale zweite Satzprüfung – einmalige Diagnose

Beim lokalen Modell `qwen3.5:4b` bleiben **zwei sachlich falsche Aussagen durch beide Prüfungen freigegeben**. Das Prüfmodell fängt drei der fünf bereits bekannten lexikalischen Fehlfreigaben ab.

| Fall | Zentrale Prüfung | Echtes Prüfmodell | Kombiniert |
|---|---|---|---|
| N01 | bestanden | nein | abgelehnt |
| N02 | bestanden | ja | freigegeben |
| N03 | abgelehnt | nein | abgelehnt |
| N04 | abgelehnt | ja | abgelehnt |
| N05 | bestanden | nein | abgelehnt |
| N06 | bestanden | ja | freigegeben |
| N07 | bestanden | nein | abgelehnt |
| N08 | abgelehnt | ja | abgelehnt |
| P01 | bestanden | ja | freigegeben |
| P02 | bestanden | ja | freigegeben |
| P03 | bestanden | ja | freigegeben |

**N02:** Die Quelle erlaubt das Öffnen des Rückschlagventils, nachdem der Leitungsdruck **gemessen** wurde. Der Kandidat ersetzt das durch **eingestellt**. Beide Prüfungen akzeptieren ihn.

**N06:** Die Quelle erlaubt nach dem Abkühlen das Öffnen der **Ofentür** und verlangt für den **Glasrohling** vor dem Wiegen, abgedeckt zu bleiben. Der Kandidat überträgt die Erlaubnis auf das Aufdecken des Glasrohlings. Beide Prüfungen akzeptieren ihn.

Die drei wörtlich belegten Positivkontrollen bestehen. Das Modell allein akzeptiert außerdem N04 und N08 fälschlich; dort verhindert die zentrale Prüfung die kombinierte Freigabe.

11 einmalige Modellaufrufe, 11 gültige Antworten, keine Fehler, keine Zeitüberschreitungen und keine Wiederholungen. Ein leerer Vorladeaufruf ist separat protokolliert. Die unveränderte Standardgrenze beträgt zwei Sekunden pro Satz. Der eigene Server wurde sauber gestoppt.

Produktstand: `3ff842fe2db6be5b6fb9d31654759bbc9d3fa44a`. Verifiziertes Modell: `qwen3.5:4b`, Digest `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.

Diese Diagnose prüft ausschließlich das reale zweite Tor mit direkten synthetischen Kandidaten und vollständigen Quellen. Sie belegt keinen vollständigen Aufnahme-, Such-, Antwort- oder UI-Ablauf und keine allgemeine Modellgenauigkeit. Quellen, Kandidaten, Modellantworten und Transportdaten stehen in `report.json`; eingefrorene Eingaben und Skripte bleiben unverändert erhalten.
