# Unabhängiges Schlussreview der Wiederholungskorrektur

**Begrenzt freigegeben: kein verbliebener Blocker in den vereinbarten Gegenproben.** Geprüft wurde der eingefrorene Commit `e8cfc26d5aee8ef42a6206da4ffa02a3bbced966`; ausschließlich die Korrektur seit `da38` und die zuvor berichteten Absatzfälle. Keine Änderung an Produktdateien, keine privaten Daten, echten Modelle oder Netzwerkaufrufe.

Der neue Abschluss verlangt nicht nur irgendeinen vollständigen Lauf: Jedes ausgegebene Vorkommen eines Bestandteils des betroffenen Regelabsatzes muss zu einem vollständigen, geordneten Lauf gehören. Damit sind die zuvor bestätigten Fälle `R O Q R Q`, `R Q O R`, `R Q O Q` und `R Q R O Q` jetzt Zitatfallback, trotz aktivem synthetischem Immer-Ja-Prüftor. Hier steht R für die Erlaubnis zur Klappe, Q für ihre schriftliche Freigabebedingung und O für die fremde Schalterregel.

Die Prüfung wurde mit echten synthetischen EpisodeStore-/WorkingMemoryStore-Quellen und `working_memory_answers.prepare` wiederholt. Alle vier Negativfälle fallen auf Zitate; vollständiger Absatz, vollständig wiederholter Absatz und zwei vollständige Wiederholungen mit einer unabhängigen Regel dazwischen bleiben positiv und wiederherstellbar.

Für die historische Gegenprobe erzeugte die unverändert erhaltene alte Fassung (`satzantwort.py` SHA `272d406b20af8d1b185f1394fb118ef1b751ae57f80da85b34c378e0c3ac195b`) die früher fälschlich akzeptierte Antwort `R O Q R Q` selbst. Nach Schließen beider Stores wurde genau diese gespeicherte Antwort mit der neuen Fassung gelesen: **`wiederherstellen` liefert None**. Keine Manipulation des erzeugten Payloads. Ignore sperrt weiterhin; der Originaltext bleibt gespeichert.

**151 fokussierte Tests bestanden** über Absatzbindung, Originalauswahl, normative Quellenbindung und Before/After-Erlaubnisse. Der ergänzte dauerhafte AFTER-allein-Negativtest ist darin enthalten. Die zuvor bestätigten Header-, all-normative-, Sichtbarkeits-, Reihenfolge- und Längenproben gelten mit dem Schlussreview zusammen; diese Korrektur verändert nur die Abdeckung wiederholter ausgegebener Positionen.

Unveränderte Grenzen: strukturelle Quellenbindung ist kein Beweis semantischer Wahrheit oder Dokumentautorität. Ein historischer Status in einem eigenen abgeschlossenen Absatz bleibt die bereits dokumentierte Grenze. Vollständige erkannte Regelabsätze können Antworten verlängern oder wegen Länge/fehlender Sichtbarkeit auf Quellenzitate zurückfallen. Keine Vollsuite oder reale Modellgüteprüfung durch diesen Reviewer.

Fingerprints:

- `sidecar/icarus_memory/satzantwort.py`: `8d1c545c5127951535d50e32913035754eab9d4d6fa689100cdc46a3246e22d0`
- `sidecar/icarus_memory/satzpruefung.py`: `3ab77753104be77fe2285130d5dccfd3d0ced31891d42871c0cc226bb58d042b`

Evidenz und reproduzierbarer Zwei-Fassungen-Runner: `/private/tmp/kingfisher-paragraph-repetition-final-review-20261009.json` und `.py`. Vorbefund und breitere gebundene Gegenproben: `/private/tmp/kingfisher-rule-paragraph-corrected-review-20261009.md`.
