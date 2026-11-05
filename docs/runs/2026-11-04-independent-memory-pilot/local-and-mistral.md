# Arbeitsaufteilung: lokal bleiben, Modelllast gezielt auslagern

Stand 04.11.2026. Diese Einordnung setzt die freigegebene Hybrid-Richtung um;
sie aktiviert keinen Cloudanbieter und bestätigt noch keine Modellqualität.

| Arbeit | Zuständigkeit | Warum |
|---|---|---|
| Originale, Konten, Akten, Beziehungen, Quellenstände, Entzug und Nutzerkorrekturen | Kingfisher lokal | Eine gemeinsame verlässliche Datenhaltung; Modellwechsel verändert keine bestätigten Fakten. |
| Mailabruf, Dubletten, bekannte Absenderregeln, Fortschritt und Wiederaufnahme | Lokaler Programmcode | Keine Modellkosten für bereits eindeutige technische Arbeit. Automatische Absender bleiben prüfbar, weil auch Rechnungen und Fristen automatisch versendet werden. |
| Volltextsuche, Filter, Datums-/Belegprüfung und Rechte | Lokal | Eindeutige Regeln und überprüfbare Ergebnisse. Fehlende Belege dürfen weder ein großes noch ein kleines Modell ersetzen. |
| Semantische Suche | BGE-M3 lokal | Vorhandenen Index weiterverwenden; keine neue Cloudkopie des gesamten Gedächtnisses. Betrieb unter begrenzter Last prüfen. |
| Kleine sprachliche Aufgaben bei ausreichender Speicherreserve | Qwen9B lokal | Vorhandenes Modell weiterverwenden. Der aktuelle Lastabbruch ist keine Qualitätsbewertung; ohne Reserve warten statt Schleifen oder stiller Cloudumschaltung. |
| Erstordnung größerer freigegebener Quellenpakete, schwierige Rollen-/Fristinterpretation, sprachliche Zusammenfassungen | Optional Mistral | Rechenarbeit entlastet den Mac. Nur ausgewählte Quellen und benötigte Ausschnitte weitergeben; lokal gegen Beleg, Schema, Quelle und Budget prüfen. Eignung erst am selben Pilot messen. |
| Skill-Auswahl aus bestätigtem Katalog | Lokaler Router und begrenzter Kontext | Keine erneute Modellarbeit beim bloßen Öffnen einer Ansicht. Neue Verfahren bleiben geprüfte, zunächst inaktive Vorschläge. |
| Aktionen wie Versand oder Terminänderung | Kingfisher mit aktueller Berechtigung | Ein Modell liefert einen Vorschlag, keine zusätzliche Befugnis. |

Die vorhandene Mistral-Aufnahme ist auf `mistral-small-2603` und den EU-Endpunkt
begrenzt. Mistral dokumentiert dieses Modell als **Small 4** mit strukturierten
Ausgaben und Werkzeugaufrufen. Das ist eine passende technische Voraussetzung
für Extraktion, kein Nachweis korrekter Personen oder Fristen. Für den ersten
Vergleich bleibt das vorhandene Modell fest; kein Wechsel auf `latest` während
der Messung. [Offizielle Modellkarte](https://docs.mistral.ai/models/mistral-small-4-0-26-03)

Die veröffentlichten Standardpreise betragen 0,15 USD/Million Eingabetokens und
0,60 USD/Million Ausgabetokens. Mit dem dokumentierten regionalen Zuschlag von
10 % ergeben sich 0,165/0,66 USD, passend zum bestehenden Preismanifest. Das
sind Tokenpreise, keine Schätzung des Gesamtimports. Wiederholte Einordnung,
Gegenprüfung und Kontext erhöhen den Verbrauch; die kleine Probe misst diese
Kosten mit. [Modellpreise](https://docs.mistral.ai/models/mistral-small-4-0-26-03),
[regionaler Zuschlag](https://mistral.ai/cloud/inference/)

Mistral-Hosting in Europa allein ist keine pauschale Datenschutzfreigabe. Vor
persönlichen Daten werden die tatsächliche regionale Route und die Studio-
Datennutzungseinstellungen geprüft. Der Help Center beschreibt einen eigenen
API-Trainings-Opt-out; er ist vom Vibe-Schalter getrennt. Zero Data Retention
muss gesondert genehmigt werden und gilt nicht für zustandsbehaftete Dienste
wie Dateien, Libraries oder Agents. Deshalb verwendet dieser Quellenweg die
begrenzte Chat-Completion-API und keinen zweiten gehosteten Gedächtnisbestand.
[API-Einstellungen](https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training),
[ZDR-Geltungsbereich](https://help.mistral.ai/en/articles/347612-can-i-activate-zero-data-retention-zdr)

## Nächste überprüfbare Lieferung

1. Dieselben zehn künstlichen Pilotmails mit belegter Personen-, Aufgaben- und
   Fristprüfung; Vorschau ohne Netz, tatsächlicher Mistral-Aufruf erst nach
   Schlüssel und konkretem Budget. Keine persönlichen Mails in diesem Pilot.
2. Rohvorschläge gegen die vorher eingefrorenen semantischen Erwartungen prüfen.
   Gegenprüfung durch dasselbe Modell ersetzt keinen unabhängigen Review.
3. Tatsächlichen Abruf separat messen. Erst danach den unbenutzten größeren
   Prüfungssatz, Quelleänderungen und Entzug prüfen. Erfolge bei bekannter
   Entwicklungsstichprobe gelten nicht als unabhängige Abnahme.
4. Persönliche Stichprobe, native Bedienung und Nutzungswoche schließen die
   Produktabnahme ab. Großimport benötigt weiterhin die passende Freigabe.

Mistral kann bei Rechenlast helfen; Identitätsverwechslungen, veraltete Quellen
und falsche Fristen müssen weiterhin durch den gesamten Kingfisher-Ablauf
verhindert beziehungsweise als unklar ausgewiesen werden.

## Aktualisierung der Anbieterprüfung am 05.11.2026

Die offizielle Modellkarte führt Small 4 (`mistral-small-2603`) weiterhin als
GA mit 0,15/0,60 USD je Million Eingabe-/Ausgabetokens. Der vorhandene feste
Modell- und Preisstand braucht deshalb derzeit keinen Austausch. Ob dieses
Modell für das konkrete Konto am regionalen Endpunkt verfügbar ist, muss nach
Einrichtung des Schlüssels über dessen Modellliste geprüft werden. Heute gab
es keinen authentifizierten Anbieteraufruf und keinen Qualitätsvergleich.
[Small 4](https://docs.mistral.ai/models/mistral-small-4-0-26-03)

Der regionale EU-Endpunkt kostet weiterhin 10 % zusätzlich. Die Dokumentation
nennt EU-/EFTA-Rechenzentren und nimmt Verwaltungs-/Abrechnungsmetadaten von der
regionalen Verarbeitungsgarantie aus. Agents, Files und Batch sind dort nicht
verfügbar. Kingfishers begrenztes Quellenpaket bleibt daher eine lokale
Warteschlange einzelner Chat-Anfragen; es darf nicht mit dem günstigeren
Anbieter-Batchdienst gleichgesetzt werden.
[Regionale Verarbeitung](https://docs.mistral.ai/inference/regional-inference)

Medium 3.5 ist seit 31.10.2026 als abgekündigt markiert. Der dort genannte
Nachfolger Large 4 befindet sich in Public Preview. Daraus folgt keine
automatische Umstellung: Ein stärkeres Modell wäre erst nach einer gemessenen
Small-Lücke, bestätigter EU-Verfügbarkeit und passendem Budget ein eigener
Vergleich. [Medium 3.5](https://docs.mistral.ai/models/mistral-medium-3-5-26-04),
[Large 4](https://docs.mistral.ai/models/mistral-large-4-0)

ZDR und Trainings-Opt-out bleiben getrennte Einstellungen. Auch bei aktiviertem
ZDR werden ausdrücklich an Studio Observability gesendete Traces nicht dadurch
geschützt. Kingfisher muss deshalb seinen tatsächlichen Anfragepfad prüfen;
eine europäische Anbieteradresse allein belegt keine vollständige Freigabe für
persönliche oder besondere Daten.
[ZDR und ausgeschlossene Dienste](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention)
