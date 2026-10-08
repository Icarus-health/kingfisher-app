# Explizite Vorher-/Nachher-Regeln getrennt prüfen

Produktstand: `3ff842fe2db6be5b6fb9d31654759bbc9d3fa44a`; Baseline `470c09fe4cbeb2225e5e94233408278cfb376eb0` (Produktmodule identisch mit zuvor installiertem `dfd4e85`). Die native Oberfläche bleibt unverändert. Installation und vollständiger abschließender Testlauf werden nach ihrem Abschluss ergänzt.

## Verhalten und Grenzen

Eine Quelle kann eine Handlung vor einer Abnahme verbieten und dieselbe Handlung danach ausdrücklich erlauben. Die gemeinsame Satzprüfung übertrug bisher das frühere „nicht“ auf den späteren Satz. Das verursachte unnötige Zitat-Rückfälle und einen falschen Verwerfungshinweis.

Die neue Ausnahme verlangt eine vollständige wörtliche Originalstelle, einfache Modal-/Passivgrammatik, dasselbe ausdrücklich benannte Ereignis und dieselbe Handlung innerhalb derselben Originalquelle. Ein vorheriges Verbot und eine nachherige Erlaubnis behalten ihr eigenes Zeitfenster. Daraus folgt weder, dass das Ereignis eingetreten ist, noch dass weitere Voraussetzungen erfüllt sind. Andere Quellenverbote, unbefristete Verbote, abweichende Ereignisse, nicht eindeutig zugeordnete Satzteile und veränderte Bedingungen bleiben gesperrt.

Zitate im gesamten Quellentext schließen die enge Ausnahme vorsichtig aus, auch wenn die einzelne innere Stelle keine Anführungszeichen enthält. Fragezeichen und kombinierte Satzzeichen dürfen eine Frage nicht zu einer Erlaubnis machen. Die unabhängige Prüfung fand diese beiden Regressionen im ersten Kandidaten; neue rote Tests wurden vor der jeweiligen Korrektur beobachtet. Zwischenkandidaten wurden nicht installiert. Apostrophe oder ein anderes Zitat an anderer Stelle können deshalb auch eine gültige Erlaubnis in den Zitat-Rückfall führen. Dies ist kein allgemeiner deutscher Bedeutungsparser.

## Nachweise

- 38 neue gezielte Fälle; der erste unveränderte Stand scheiterte in neun der ersten 27 Fälle. Review-Regressionsläufe und 222 abschließende betroffene Prüfungen liegen bei. Diese Zahlen überlappen und werden nicht addiert.
- Unabhängiger Code-Review: 30 Gegenproben und zehn tatsächliche Speicher-Schließen/Wiederöffnen-Prüfungen, einschließlich Entzug, ohne verbleibenden Befund im Änderungsumfang.
- Ein alter Exporttest scheiterte unabhängig bereits auf der Baseline zwischen UTC-Mitternacht und Berliner Mitternacht. Nur seine Quellen-Testuhr wurde eingefroren; die korrekte Produkt-Zeitzonenanzeige bleibt unverändert.
- Der lokale Modellvergleich verwendet bytegleich 19 künstliche Quellen und 16 Fragen, vor dem Produktpatch eingefroren. Aufnahme per HTTP, echter Einordnungsworker, Kategorienvorschläge, dauerhafter Index und Gesprächsantworten laufen tatsächlich; keine persönlich verbundenen Quellen oder Cloudmodelle.
- Ursprünglicher 13-Fragen-Bestand: unabhängig **11 → 12 ausreichende Antworten**, keine unbelegte Sachantwort in diesem kleinen Lauf. IA03 beantwortet nun die Vorher-Frage direkt; W03 behält die spätere Erlaubnis ohne falschen Verwerfungshinweis. W04 zeigt weiterhin nur Regel und Vorgang nebeneinander, ohne den notwendigen Schluss ausdrücklich zu sagen.
- Drei zusätzliche deutsche Fälle bleiben vollständige Originalzitate, keine direkten Antworten. Im erweiterten Satz daher **11 → 12 ausreichende von 16**. Ihre Belegtexte enthalten die Information; sie gelten nach demselben Direktheitsmaßstab als unvollständig. Die vorgeschlagene DE02-Goldformulierung „berührt“ ist stärker als das Original „bearbeitet“ und wurde ausdrücklich nicht übernommen.
- Nach echtem Schließen und Wiederöffnen bleiben alle 16 Antworten unverändert, ohne Modellaufrufe. Quellenentzug sperrt die betroffene Anzeige ohne Inferenz, das Original bleibt erhalten.
- Antwortphasen-Aufrufe steigen von 64 auf 66, weil mehr belegte Sätze die vorhandene zweite Modellprüfung durchlaufen. Kein behaupteter Kostenspareffekt. Diagnostisches Entladen zwischen Paketen, RSS-Stichproben und eine Zeitgrenze ersetzen keine harte GPU-Begrenzung oder Akku-Alltagsabnahme.

## Weiter offene Qualität und Alltag

Fünf der acht sachlich falschen direkten Negativkontrollen bestehen unverändert auch auf der Baseline die zentrale lexikalische Prüfung. Das sind keine neuen Fehlfreigaben des Zeitpatches, aber ein bestehendes Produktrisiko. Der Code-Review selbst prüft kein reales zweites Prüfmodell. Die separate einmalige Diagnose in `real-verifier/` führt anschließend elf echte lokale Prüfaufrufe aus: Das Prüfmodell fängt drei der fünf lexikalischen Fehlfreigaben ab, **N02 und N06 werden weiterhin durch beide Tore fälschlich freigegeben**. N02 ersetzt Druckmessen durch Druckeinstellen; N06 überträgt die Erlaubnis von der Ofentür auf den Glasrohling. Alle drei wörtlich belegten Positivkontrollen bestehen; keine Fehler oder Zeitüberschreitungen. Der leere Vorladeaufruf ist getrennt protokolliert. Dies prüft direkte Kandidaten, nicht deren tatsächliche Erzeugung im ganzen Gesprächsweg. Originalbindung und eine lokal passende Wortmenge beweisen keine semantische Richtigkeit. Diese zwei Fälle sind der nächste gezielte Gedächtnisblocker; ein zweites LLM-Urteil allein schließt sie nicht.

Der persönliche Bestand ist weiterhin ausdrücklich pausiert: 304 von 122.399 inventarisierten Mails aufgenommen, 120.805 warten auf Abruf. 187 Mail-Kategorienauswertungen sind fehlgeschlagen; im gesamten Kategorienstatus sind 193 Fehler gespeichert. Die Fehlerursache wird bisher nicht gespeichert und lässt sich aus diesen Zahlen nicht erschließen. Dies ist keine vollständige Gedächtnisabdeckung. Produktives Ollama bleibt aus, Bedeutungssuche unavailable. Native Fenster-/Tages-/Akkuabnahme bleibt offen.

## Speicher und Rückwege

Drei alte, gestoppte Kingfisher-Testcontainer wurden nach Host-Archivierung, Blob- und Rootfs-Prüfsummen, exaktem Bild-Reload und einer nicht gestarteten Wiederherstellung der Prozess-/Umgebungskonfiguration mit nur lesendem Datenmount entfernt. Das gemeinsame Volume bleibt erhalten. Eine solche Konfigurationsprobe ist kein voller Laufzeit- oder Writable-Layer-Restore. Private Metadaten und Archive bleiben außerhalb des Repositories.

Die vorher geschätzten 195 MiB eigener Bildschichten wurden **nicht** als freier Platz gewonnen: tatsächlich nur 299.008 zusätzliche Bytes; ein Bild konnte wegen weiterer Referenzen nicht entfernt werden. Rund 688 MiB Docker-Freiplatz bleiben knapp. Kein globales Prune, kein Volume gelöscht, keine fremden Dienste gestoppt. Die native Update-Reserve muss vor dem Umschalten erneut bestehen; große Aufnahme braucht weiterhin eine eigene Kapazitätsentscheidung.
