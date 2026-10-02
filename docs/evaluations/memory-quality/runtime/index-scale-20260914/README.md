# Begrenzte Suche bei wachsendem synthetischen Claim-Bestand

Immutable Produktion ed39aa02de8ee873520342531de70e97b6166bd9, lokaler Mac,
14.09.2026. Drei Stufen mit 10.001, 50.001 und 100.001 Claim-Zeilen,
je 20 tatsächliche Agent.send-Aufrufe an einen CapturingProvider. Der ältere
passende Claim erreichte bei allen 60 Aufrufen die tatsächliche Provideranfrage.
Keine privaten Daten oder Modellaufrufe.

Die zusätzlichen Zeilen wurden direkt synthetisch eingefügt. Sie haben unterschiedliche
IDs, Werte und Texte, teilen jedoch den synthetischen Ursprungsbeleg. Das prüft die
indexbasierte Kandidatenauswahl gegen viele irrelevante Zeilen, weder den Import
100.000 unabhängiger Quellen noch vollständige Graph-/Ereignislast. Jede Anfrage
startet ohne Gesprächsverlauf; nur ein fachlich passender Beleg muss geprüft werden.

Gemessene Agent-Dauern ohne Modell liegen in diesem warmen Minimalfall unter einer
Millisekunde. Die Rohwerte sind im JSON erhalten; daraus folgt keine Zusage für
Antwortzeit, Last-P95, mehrstufige Recherche oder einen realen zehnjährigen Bestand.
Der Nachweis zeigt, dass der frühere Verlust vor der Modellanfrage auch bei dieser
synthetischen Größe ausbleibt.
