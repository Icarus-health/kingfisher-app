# Vollständige Regelabsätze erhalten

Vorbereiteter Liefernachweis, 9. Oktober 2026. **Die abschließende Vollsuite und Mac-Installation stehen für diese Lieferung noch aus.** Produktstand `e8cfc26d5aee8ef42a6206da4ffa02a3bbced966`, Testvertragsstand `50dea3e`. Der installierte Mac bleibt bis zur bestandenen Abnahme auf `ce39f71`.

## Problem und Verhalten

Ein wörtlicher Regelsatz allein kann eine Folgeeinschränkung oder einen historischen Entwurfsstatus verlieren. Erkannte mehrsätzige Regelabsätze werden deshalb als vollständige Originaleinheit angeboten. Alle Bestandteile müssen zusammen und in Quellreihenfolge erscheinen, auch bei älteren Textausgaben und gespeicherten Antworten. Eine korrekte Wiederholung darf kein weiteres ungebundenes Vorkommen verdecken. Der zentrale Quellenschutz und das zweite Prüftor bleiben zuständig.

Unsichtbare, abgeschnittene, überlange oder teilweise verworfene Gruppen führen zu Belegen statt einer freien Teilantwort. Gewöhnliche Fakten und Ein-Satz-Regeln behalten ihren kurzen Pfad. Die eingefrorene Goldfixture blieb unverändert. Der strukturelle Schutz ist kein Beweis semantischer Wahrheit, Dokumentautorität oder allgemeiner Vollständigkeit.

## Unabhängige Gegenprüfung

Das erste Review fand Header-/Satzeinheiten-Kollision, ausgeschlossene normative Begleitsätze sowie Umordnung/Interleaving. 12 neue Gegenproben waren vor deren Korrektur rot. Das nächste Review fand eine zusätzliche Wiederholungsumgehung, auch über tatsächlich erzeugte gespeicherte Antworten nach echtem Store-Neustart. Drei weitere negative Kontrollen waren vor der Root-Korrektur rot. Die korrigierte Fassung wurde unabhängig mit 151 fokussierten Tests geprüft; vollständige Wiederholungen bleiben positiv. Root-Gruppen: 227 betroffene Prüfungen und 69 weitere Vertragsprüfungen bestanden; nicht addiert.

Die strengeren Erwartungen in Before/After-, Originalauswahl-, Applicability- und HTTP-Tests sind ausdrücklich dokumentiert. Vollständige Originale bleiben positive Kontrollen; verlorene Begleitsätze, verworfene Bedingungen und alte unvollständige Payloads bleiben negative Kontrollen. Der HTTP-GET-Test beweist erneute Projektion in derselben App, keinen Neustart; reale Store-Neustarts werden separat geprüft.

Ein erster Volltest auf `da38e85` wurde nach dem Wiederholungsbefund abgebrochen und zählt nicht als Abschluss. Er zeigte außerdem gesperrte lokale Testserver/Prozessdiagnosen sowie alte Teilabsatz-Erwartungen. Die Vertragskorrektur lockert keinen Produktguard. Der erste abgeschlossene breite Lauf ergab 6.339 bestanden, 1 fehlgeschlagen, 3 übersprungen und 32 Subtests. Das zusätzliche Messlatten-Skript erfand aus „Bitte senden“ eine Muss-Aussage. Derselbe Fehler besteht unabhängig im unveränderten Archiv von `70cac`; er stammt nicht aus dieser Produktänderung. Der sorgfältige Test übernimmt nun den vollständigen echten Fristabsatz im normalen Textschema. Alte und erfundene Daten sowie die freie Muss-Paraphrase bleiben negative Kontrollen. 5/5 fokussiert bestanden, Szenario-Gold und Produktguards unverändert. Der Abschlusslauf auf `50dea3e` läuft; noch kein finales Grün behauptet. [Unabhängiges Review](messlatte-contract-review.md).

## Echter Modelllauf: enger Umfang

Sechs fest vorgegebene künstliche Quellen, `qwen3.5:4b`, zehn echte Aufrufe von Formulierung und zweitem Tor: vier ausreichende Satzantworten, zwei sichere Rückfälle, keine akzeptierte inhaltliche Falschaussage in diesen sechs Fällen. H01/C01 sind keine Antworterfolge: das Modell gab zwei IDs für eine atomare Originaleinheit aus. Die Belegoberfläche wurde hier nicht gerendert geprüft. Generation und Zweitprüfung nutzten dasselbe Modell; das ist keine unabhängige Wahrheitskontrolle.

Keine neue Suche, Aufnahme, Indexierung oder persönliche Einordnungsqualität gemessen. Das ersetzt den wegen des früheren eigenen BGE-Cachefehlers offenen Gesamtlauf nicht. Exakte Wiederherstellung der drei BGE-Dateien bleibt bis zur ausstehenden konkreten Downloadfreigabe offen.

Der Testserver nutzte echte getrennte APFS-Dateiklone, eigene Inodes, `OLLAMA_NOPRUNE=1`, Cloud aus, eigenen Loopback-Port, Watchdog und anschließendes Herunterfahren. Die vier nativen Qwen-Dateien sind nach SHA-256 und Metadaten unverändert. Keine persönlichen Quellen verwendet.

## Paket und verbleibende Grenzen

Das netzlos gebaute Image `1.0.6-local.e8cfc26` basiert auf dem verifizierten installierten `ce39f71`. 264 Python- und 112 UI-Dateien wurden byteweise geprüft; die künstlichen positiven und negativen Paketkontrollen bestehen. Oberfläche und nativer Wrapper bleiben unverändert. Die Mac-Installation erfolgt erst nach bestandener Vollsuite mit kalter Sicherung und frischer Original-/Datenbankprüfung.

Ein abgeschlossener historischer Header in einem eigenen Absatz wird nicht automatisch an spätere Regelabsätze gebunden. Unbekannte normative Sprache, Quellenautorität, Abrufverluste, echter persönlicher Quellenbestand, native Bedienung und Akkuqualität bleiben getrennte offene Abnahmen. Vollständige Gruppen können länger sein und häufiger auf Belege zurückfallen. Der gesamte CoS ist weiterhin nicht fertig abgenommen.
