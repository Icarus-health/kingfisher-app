# Gesprächsaufnahme und gezielte Rückfragen

## Änderungen

Der Gesprächsserver nimmt die Originalzeile bereits vor der Modellantwort auf. Er gibt diesen Erfolg jetzt als internes, geprüftes Signal an den Agenten weiter, auch beim erneuten Versuch einer fehlgeschlagenen Antwort. Das Signal kommt nicht aus der HTTP-Nutzereingabe. Ohne dieses Signal wird keine erfolgte Aufnahme behauptet. Die Systemanweisung unterscheidet Aufnahme, automatische Einordnung und menschliche Faktenbestätigung; ausdrückliche Merkbitten bleiben im bestehenden Vorschlagspfad.

Der Quellenselektor entscheidet anhand eindeutiger Entscheidungsnamen statt kurzer Themenwörter wie `time`. Die neuen Modellwerte werden vor der bestehenden Prüfung auf die bisherigen internen Status abgebildet. Damit bleiben gespeicherte Antworten, Personenprüfung, Konfliktbehandlung und Quellenentzug kompatibel. Mehrere unabhängig erfragte Themen verlangen die Auswahl jeder passenden Teilquelle; sie werden nicht zu einer Aussage zusammengeführt. Es gibt keinen neuen Index und keine heuristische automatische Ergänzung vermeintlich passender Quellen.

Der Alltagslauf zeigte einen weiteren alten Schreibweg: `episode_festhalten` konnte eine Modellparaphrase als separate Episode speichern. Der beobachtete Aufruf verwendete den Typ `event`; gezielte Gegenproben reproduzierten zusätzlich die für die Quellensuche relevanten Typen `message` und `document`. Wie `merken` wird dieses Werkzeug im Modellgespräch nun weder angeboten noch ausgeführt. Ein trotzdem zurückgegebener Aufruf wird auditiert und beendet die Runde, ohne parallele Aufrufe auszuführen. Originalaufnahme, ausdrückliche Vorschläge und der direkte Werkzeugweg bleiben erhalten. Bestehende Daten werden nicht umklassifiziert oder gelöscht. `Episode.produced` bezeichnet erzeugte Assertions und ist kein KI-Ursprungsmarker.

## Nachweise

- `d6d4a2b`: 2432 Tests und 4 Kalender-Untertests bestanden. Die zwei vorhandenen Test-Client-Warnungen bleiben bestehen.
- `6c72867`, nach Schließen des zusätzlichen Schreibwegs: 131 betroffene Tests bestanden. Die neue Duplikatprobe scheiterte zuvor für beide Episodentypen; der direkte Werkzeugweg bestand vorher und nachher. Eine zusätzliche identische Gesamtsuite wurde für diesen kleinen Nachtrag nicht wiederholt.
- Die sechs neuen Statusfälle scheiterten ohne Abbildung, anschließend bestanden alle sieben Tests einschließlich Ablehnung einer erfundenen Quellen-ID.
- Unabhängige Codeprüfung der Auswahländerung und des abschließenden Schreibschutzes fand keine konkrete Regression.
- UI-Dateien und sichtbare Komponenten wurden in diesem Nachtrag nicht verändert. Die UI-Prüfung des vorherigen Pakets wird nicht als erneute Browserprüfung ausgegeben.

Die Hashes der lokalen Prüflogs stehen in `checks.json`. Der vollständige synthetische HTTP-Lauf ist lokal aufbewahrt; die kompakte Antwortspur mit seinem Hash liegt in `qwen4b-development-d6d4a2b.json`. Der Lauf begann vor dem Commit auf einem geänderten Arbeitsbaum; seine erfassten Produktionsdatei-Hashes wurden mit `d6d4a2b` abgeglichen. Er verwendet vier statt nur einer Werkzeugrunde. Der spätere Schreibschutz ist separat ausgewiesen.

## Bisherige Entwicklungsszenarien

Ein gepaarter Versuch verwendete fünf identische synthetische Auswahl-Nutzlasten jeweils mit alten und aussagekräftigen Statusnamen. Beim Anruffenster entfiel die falsche Datumsrückfrage. Das zweite unabhängige Thema blieb durch die Umbenennung allein weiterhin unvollständig; deshalb wurde der vollständige Teilfragenauftrag separat ergänzt. Die Roh-Auswahlantworten stehen in `selector-label-paired-results.json`.

Im anschließenden einmaligen Lauf der zehn schon vorliegenden Entwicklungsszenarien waren Anruffenster, beide Bedingungen, explizite Terminkorrektur, offener Widerspruch, fehlender relativer Zeitbezug, wieder geöffneter Bestand, Quellenentzug sowie Tagesübersicht/Terminvorbereitung/Antwortentwurf nachvollziehbar. Es wurde keine Nachricht versendet. Der Fall ohne Beleg blieb `working_unknown`, scheiterte jedoch weiterhin an der eingefrorenen Formulierungsprüfung; er wird nicht nachträglich als vollständig bestanden umgewertet.

Bei den gleichnamigen Projektquellen blieben beide Zitate sichtbar und es wurde gefragt. Die präzisere Projekt-Rückfrage ist dennoch offen: Die vorhandene Erwartung verlangt eine Personenfrage, obwohl der Datensatz keine belastbaren Personen-IDs oder Mailbox-Unterscheidung liefert. Seine zusätzlichen Projektlinks liegen an Aufgaben, nicht an den Episoden. Diese Metadaten werden nicht ohne eigene Aktualitätsbindung in Antworten übernommen.

## Unabhängige neue Gegenprobe

Ein anderer Agent legte vor dem Lauf vier neue Fälle fest (`holdout-cases.json`, SHA-256 `0e3f411c7c623f95c1b2774db8194a40c54b6e7da9e036e50f27a3833e462fd2`). Auf `6c72867` wurden sie einmal mit `qwen3.5:4b` ausgeführt: ein eindeutiges Anruffenster, zwei unabhängige Bedingungen mit ähnlicher unpassender Drittquelle, ein relativer Tag ohne Quellenzeit sowie gleichnamige Absender mit verschiedenen Mailadressen/Vorgängen. Es gab keine Produktanpassung an diese Fälle und keinen wiederholten Modelllauf.

Alle vier Quellenmengen stimmen, einschließlich Ausschluss der Ablenkungsquelle und Erhalt beider gleichnamiger Absender. Anruffenster und Bedingungen werden vollständig zitiert; beim relativen Tag wird kein Kalenderdatum erfunden. Personen werden nicht zusammengeführt. Die gespeicherten Antworten und unveränderten ursprünglichen Bewertungen stehen in `qwen4b-holdout-6c72867.json`.

Die eingefrorene automatische Antwortwertung ist **3/4**, weil der Bedingungsfall versehentlich das falsch geschriebene Wort `gegeneichnet` verlangte. Quelle und Antwort enthalten korrekt `gegengezeichnet`. Die fachliche Prüfung der vollständigen Originalzitate ist davon getrennt; die rein mechanische Korrektur und Neubewertung derselben Antwort stehen als Erratum daneben. Weder Originaldatensatz noch Ergebnis wurden nachträglich überschrieben. Auch diese vier Fälle sind keine repräsentative Produktgenauigkeit.

## Grenzen

Die bekannten Entwicklungsszenarien sind keine unabhängige Qualitätsquote und beweisen keine fehlerfreie V1. Eine neue Objekterzeugung ist kein Betriebssystemneustart. Freie Personen-/Projektauflösung, semantische Suche ohne Wortüberschneidung und die mehrtägige Alltagsprüfung bleiben offen. Modellantworten außerhalb des beleggebundenen Abrufs können weiterhin unpassende Formulierungen enthalten.

Private Quellenverarbeitung und Modellauswahl der vorhandenen App bleiben unverändert. Für diese Prüfung wurden nur synthetische Daten und das bereits installierte lokale Modell verwendet; keine Downloads, Cloudübertragung, Nachrichtenversendung oder CI-Neustarts.
