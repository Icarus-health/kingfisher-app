# Quellenkorrektur: eigenständige vollständige Fassung

## Problem und Verhalten

Ein Nutzer muss eine automatisch eingeordnete Quelle inhaltlich berichtigen können, ohne die importierte Originalquelle zu überschreiben oder eine Korrektur als bestätigte Aussage auszugeben. Die Korrektur wird als vollständige, eigene `manual_correction`-Quelle gespeichert; das Original bleibt erhalten und wird aus dem Arbeitsstand ausgeschlossen. Quelle und Korrektur behalten ihre eigene Herkunft. Die sichtbare Fassung bleibt eine Quellenmeldung, keine bestätigte Aussage.

Die Test- und Laufdaten sind vollständig synthetisch und enthalten keine privaten Inhalte. [Eingefrorene Erwartung](expected.json), [sanitisierte Resultate beider Modellversuche](results.json) und [Bewertung samt Grenzen](assessment.md) stehen neben diesem Bericht.

## Ergebnis

Der erste Lauf stieß auf zwei getrennt dokumentierte Probleme: Das lokale Auswahlmodell gab `time` zurück, und das damalige Harness erwartete `source_report` statt des tatsächlichen `working_reports`-Vertrags. Dieser Versuch endete vor der Korrekturphase und blieb unverändert archiviert.

Der einmalige Vergleichslauf mit denselben eingefrorenen Texten und Fragen bestand die Hauptkette: automatische Einordnung, Originalbericht, vollständige Berichtigung, zwei Folgefragen mit der neuen Fassung, kein Claim oder Vorschlag, und Entzug ohne Wiederaufleben des Originals. Das alte Gespräch wurde nach Berichtigung und Entzug neutral als `working_unavailable` neu geladen. Die frische Frage nach Entzug lief in den Chatpfad und antwortete „das weiß ich nicht“, ohne Quelle oder Datum.

Im Ergebnis bleibt die enge Harnessabweichung erhalten: Das Harness erwartete für die frische Frage `unknown`; tatsächlich gab der Chatpfad keinen Antwortvertragsstatus aus. Der spätere Harness-Stand akzeptiert solche neutralen No-Source-Verläufe nur dann, wenn keine Quelle, kein Datum, keine ID und kein Link erscheint. Dieser geänderte Stand ist nicht exakt die beim archivierten Modelllauf ausgeführte Skriptfassung. Es wurde kein zweiter Lauf durchgeführt.

Zwischenstand laut Integrationslauf: 19 Korrekturtests sowie 60 betroffene fokussierte Tests bestanden. Die finale Browserabnahme ist mit synthetischem Fake-Modell grün: unveränderte Vorlage zunächst deaktiviert, vollständige Berichtigung auf den 28. September mit Bedingung, Vorschau und Speichern, genau ein Erfolgshinweis, dessen Verschwinden nach der nächsten Frage, neue Fassung, historische Sperre der abhängigen Berichtigung ohne Aktionen sowie neutrales Neuladen beider alter Antworten ohne Text/Datum. Browserkonsole: keine Warnungen oder Fehler. Diese UI-Prüfung ist von der lokalen Modellprüfung oben getrennt. Die abschließende Vollregression einschließlich Clean-Tree-Probes bestand auf `6c5bb08`: **2347 Tests und 4 Untertests**, 204,18 s, zwei bekannte Bibliothekswarnungen. UI-Build, Assetvertrag (14 Dateien/17 Icons) und Schema/Beispiel ebenfalls bestanden.

## Schutz bei persönlichen Rückfragen ohne Treffer

Die Modellprobe nach Entzug fiel bei ihrer konkreten Frage in allgemeinen Chat zurück und antwortete neutral. Das ist kein genereller Schutz gegen erfundene private Fakten. Der Code-Review fand einen konkreten weiteren Trigger: „Was hast du über meine Lieblingsfarbe gesagt?“ wurde ohne Treffer ebenfalls frei beantwortet. Erkennbare persönliche Recall-Fragen gehen nun unabhängig vom Suchtreffer in den vorhandenen beleggebundenen Antwortpfad; ohne Beleg ergibt sich `unknown`. Es wird kein weiteres Modell aufgerufen.

49 Routing-/HTTP-Tests bestanden. Der adversarielle Fake-Provider würde „Deine Lieblingsfarbe ist blau.“ liefern; der HTTP-Test verlangt `unknown`, keinen Farbwert und keinen Provider-Aufruf. Neue Angaben wie „Anna hat mir gesagt …“, allgemeine Erklärungen und explizite Aktionen behalten ihren bisherigen Ablauf. Eine zunächst zu breite Regel wurde vor dem Commit durch diese Gegenbeispiele korrigiert. Das ist ein begrenzter deutscher Intent-Schutz und keine universelle semantische Absichtserkennung.

## Grenzen

Der lokale Lauf belegt ein synthetisches Beispiel auf `qwen3.5:4b`; er beweist keine allgemeine semantische Zuverlässigkeit. Die finale Browserabnahme ist grün; Vollregression einschließlich Clean-Tree-Probes sowie größere Neustart-, Bestandswachstums- und Wiederherstellungsszenarien stehen noch aus. CoS V1 insgesamt bleibt offen.

## Prüfumgebung und CI

Ein erster Gesamtversuch in der eingeschränkten Sandbox endete mit 2317 bestandenen Tests, 13 Fehlern und drei Setupfehlern: lokale Ports und die DNS-Prüfung waren gesperrt. Der oben genannte finale Lauf mit den erforderlichen lokalen Netzwerkrechten bestand vollständig; zusätzlich enthält er die 14 neuen Routingfälle. Der frühere Lauf bleibt als lokales Diagnoseartefakt erhalten.

GitHub-Prüfungen für `6c5bb08` starteten laut ihren tatsächlichen Anmerkungen wegen fehlgeschlagener Kontozahlung bzw. Ausgabenlimit nicht (CI-Lauf 35857040697, Container-Lauf 35857040667). Keine Wiederholung angestoßen. Die lokale Python-3.12-/UI-/Schema-Prüfung ersetzt keine hier nicht ausgeführte Linux-Tauri- oder Python-3.10-Prüfung.
