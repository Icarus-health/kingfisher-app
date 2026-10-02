# Offene Widersprüche bis in die Antwort prüfen — 2026-09-23

## Problem und Ergebnis

Audit A6: Eine angenommene Aurora-Frist (22. September) und ein offener widersprechender Kandidat (26. September) erzeugten bereits einen Klärungsfall. Die Gedächtnisantwort lieferte trotzdem die alte Frist ohne Hinweis. Jetzt prüft eine gemeinsame Grenze relevante offene Wissenskandidaten vor der Ausgabe und stellt die Antwort bei einem möglichen Widerspruch zurück. Sie übernimmt keinen Vorschlag und entscheidet keine Frist.

Die Prüfung gilt für ausgewählte beleggebundene Antworten, Folgeauswahlen, verwendeten Gesprächskontext, erneute Modellnutzung alter Ableitungen und gespeicherte Freigabegrundlagen. Bei freier Modellantwort gilt sie konservativ für sämtliche verwendeten Wissenseingaben, weil jeder davon die Antwort beeinflussen kann. Bei strukturierter Auswahl wird nach der Auswahl nur die tatsächlich angezeigte Aussage geprüft; eine strittige Frist blockiert deshalb keine unabhängig ausgewählte Betreuungsaussage.

Gespeicherte Antworten werden beim Öffnen gegen aktuelle Quellen und offene Widersprüche geprüft. Betroffene Texte und Kontextkarten erscheinen als Hinweis. Der ursprüngliche Audit-Datensatz bleibt unverändert. Eine abgelehnte Alternative kann die unverändert gültige alte Antwort wieder sichtbar machen; ein Quellenentzug kann das nicht. Die Gesprächsliste zeigt für Wissensantworten eine neutrale Vorschau.

## Grenze und Aufwand

- Keine neuen Abhängigkeiten, Datenmigrationen, Embeddings oder zusätzlichen Modellaufrufe. Eine eindeutige Konfliktkonstellation benötigt keinen Modellaufruf.
- Exakte Subjekt-/Kontextreferenzen; bestehende Prädikat-/Zeit-/Wertregeln; aktuelle Originale mit Digest, Zitat und Quellenstand; transitive Grundlagen.
- Höchstens 128 Claims, insgesamt 500 offene Kandidaten, 64 KiB pro Kandidatendokument, gemeinsames SQL-Budget von ungefähr zwei Millionen VM-Schritten und eine kooperativ geprüfte Sekunde je Konfliktprüfung. Bei Grenze/Ungewissheit keine unmarkierte Sachantwort.
- Die jüngsten 20 Antworten mit Wissensherkunft werden beim Öffnen aufgelöst; ältere werden neutral zurückgestellt. Originalquellen-Antworten behalten ihre getrennte bestehende Grenze.
- Anwendungsaufbau, Wiederherstellung und eingeschränkte Agenten übernehmen dieselbe Prüfung. Unabhängig konstruierte Agenten ohne die optionale Wissenskandidaten-Anbindung behalten das bisherige Verhalten.
- API-Anlegen/Ablehnen von Wissenskandidaten verwendet wie Annahme und Gesprächsantwort dieselbe Gesprächssperre.

## Prüfung

Implementierung: `b667ecf08710519acc6f917c1a6a3c059c6e192f`.

- Fünf ursprüngliche Antwort-/Folgeauswahl-/Änderungsfälle zuerst rot reproduziert, danach bestanden.
- Zusätzliche Prüfungen zu falscher Sperrung einer unbeteiligten Aussage, Kontextleiste nach einer Nachricht ohne Kontext, Herkunftsentzug, Ablehnung, abgelaufenen Kandidaten, fehlenden Grundlagen, alter Quelle, Grenzen, Kandidaten hinter einer globalen 500er-Liste und Änderungen während der Modellauswahl/dem Rendern.
- Unabhängige, begrenzte Prüfung durch günstigeren Agenten: zwei konkrete Integrationsprobleme gefunden und behoben; anschließende Prüfung ohne weiteren konkreten Befund. Das ist keine vollständige Sicherheitsprüfung.
- Paketprüfung über echtes lokales HTTP: Dokument hochladen, ausdrücklich einen Kandidaten anlegen/annehmen, Antwort, neue widersprechende Quelle/Kandidat, Neustart, alte und neue Antwort zurückstellen, Kandidat ablehnen, weiterer Neustart, gültige Antwort wieder sichtbar, erste Quelle entziehen, alte Antwort ungültig. Synthetischer Auswahl-Provider; kein tatsächliches LLM.
- Browser: ungültige frühere Antwort und zurückgestellte Konfliktantwort sichtbar; alte Frist und Kontextkarte fehlen.
- Docker-Paket gebaut; Asset-Vertrag: 14 Dateien, 17 Icons bestanden.
- Vollständiger lokaler Lauf auf dem sauberen Implementierungscommit: **2164 bestanden, vier Unterprüfungen bestanden**, zwei bestehende Abhängigkeitswarnungen, 171,56 Sekunden. Gegenüber dem vorherigen Stand 26 neue Regressionstests.

## Was damit ausdrücklich nicht bewiesen ist

Es handelt sich um einen Schutz gegen bereits strukturierte mögliche Widersprüche. Ein Zitat im Original beweist weder die Wahrheit der Quelle noch die Richtigkeit der daraus abgeleiteten Aussage. Unterschiedliche Werte eines unbekannten Prädikats können konservativ als möglicher Widerspruch gelten, obwohl sie sich inhaltlich ergänzen.

Das automatische Einlesen allgemeiner Dokumente/E-Mails erkennt noch nicht nachweislich alle Fakten, Bedingungen, Personen und Friständerungen. Die vorhandene Verarbeitung zielt auf begrenzte Kandidatentypen; ein abgeschlossener Verarbeitungslauf ist kein Vollständigkeitsnachweis. Unproponierte Informationen können diese Grenze nicht auslösen. Die Belegauswahl durch ein Modell bleibt semantisch ungeprüft. Allgemeine Frageformen, übergreifende gemeinsame Suche und repräsentative unabhängige Mehrtages-/Holdout-Qualifikation bleiben offen. Daher keine Prozentangabe zur Gesamtqualität und keine Fehlerfreiheitszusage.

Nächste Priorität: den Import einer vollständigen Korrespondenz mit Bedingung, gleichnamigen Personen, Terminänderung und späterer Korrektur bis zur belegten Antwort qualifizieren. Fehlende Extraktion und fehlender Abruf getrennt messen; keinen Abschlussstatus als vollständiges Verständnis ausgeben.
