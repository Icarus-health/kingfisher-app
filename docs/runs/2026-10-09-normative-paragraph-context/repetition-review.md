# Unabhängiges Re-Review der korrigierten Absatzbindung

Geprüft: `/private/tmp/kingfisher-rule-paragraph-context-20261009/repo`, Basis `fda6dc213a2c9183e92531940c137afc162b69a5`. Eingefrorener Patch SHA256 **`f5a68a5e60e2e13b0944f7cc8abe0f40ada31c8f6a364d259cdccaffd2cff6c9`**.

**Ergebnis: Die drei ursprünglichen Minimalgegenbeispiele sind geschlossen. Ein weiterer bestätigter P2-Fall bleibt in der Abschlussprüfung und beim Wiederherstellen: Eine korrekte Wiederholung heilt eine zuvor falsch zusammengesetzte Ausgabe. Diese Fassung sollte vor der Korrektur nicht als vollständig geordnet gebunden freigegeben werden.** Root hat den Befund übernommen; dieser Bericht bewertet ausschließlich die hier eingefrorene Fassung.

## P2: Ein vollständiger Lauf legitimiert zusätzliche ungebundene Vorkommen

`sidecar/icarus_memory/satzantwort.py:737–743`, `_fehlender_regelabsatzkontext`: `any(...)` verlangt nur einen vollständigen, korrekt geordneten Lauf. Weitere Vorkommen derselben Regel oder ihres Begleitsatzes müssen nicht selbst einem solchen Lauf angehören. `_absatzduplikate` entfernt dies nicht, wenn der Legacy-Provider alles in einem einzigen Textfeld liefert.

Reproduktion mit zwei synthetischen Quellen:

- Quelle 1: **„Die Klappe darf geöffnet werden. Dies gilt ausschließlich nach schriftlicher Freigabe.“** (`R Q`)
- Quelle 2: **„Der Schalter darf umgelegt werden.“** (`O`)
- Ein einziges Legacy-Satzfeld mit beiden Quellen: **`R O Q R Q`**. Der erste Begleitsatz steht beim fremden Schalter; erst die spätere Wiederholung ist korrekt. Auch `R Q O R` und `R Q R O Q` werden angenommen.

Alle drei Direktproben liefern **`status=saetze`**, auch mit aktivem synthetischem Immer-Ja-Prüftor. Beim Fall `R O Q R Q` wurde zusätzlich der echte Weg geprüft: zwei `EpisodeStore`-Quellen anlegen, `WorkingMemoryStore.commit`, `working_memory_answers.prepare` mit Skript-Provider und aktivem Prüftor → Satzantwort; Stores schließen und erneut öffnen → `wiederherstellen` akzeptiert die unveränderte tatsächlich erzeugte Antwort. **Keine gespeicherte Payload wurde für diesen Befund manipuliert.** Ein anschließendes Ignore sperrt die Anzeige korrekt und bewahrt den Originalkörper.

Kleine Korrekturrichtung: Nach ausgelöster Absatzbindung muss jedes ausgegebene Vorkommen eines zugehörigen Originalbestandteils zu einer vollständigen, zusammenhängenden Folge in Originalreihenfolge gehören. Eine weitere korrekte Wiederholung darf eine zusätzliche isolierte oder interleavte Instanz nicht legitimieren. Diese Abschlussregel muss weiter für neue Ausgaben und gespeicherte Antworten identisch gelten. Keine neue semantische Grammatik nötig.

## Bereits geschlossene Blocker und positive Grenzen

Die früheren eigenen Gegenproben wurden gegen diese Fassung erneut ausgeführt, mit der neuen legitimen ID-Semantik für vollständige Absätze:

- Periodlose Überschrift (`Entwurf\n\n`) plus Regel/Begleitsatz: isolierter Header+Regelsatz jetzt Zitatfallback; vollständiger Header mit Absatz ist eine serverseitige Original-ID. Mehrere periodlose Überschriften und ein Doppelpunkt-Header bleiben erhalten. Unsichtbarer Header wird nicht aus dem Prüfvolltext eingefügt.
- Ausschließlich normative Begleitsätze mit **darf / muss / soll**: isolierte Regel fällt trotz Modell-Ja auf Zitate; der vollständige Absatz bleibt als ein exakter Originaltext auswählbar.
- Einfache Umkehr und Interleaving (`Q R` bzw. `R O Q`) fallen auf Zitate. Vollständige, direkt aufeinanderfolgende Legacy-Einzelsätze `R Q` bleiben zulässig; der ID-Pfad materialisiert sie als einen Absatz. Die verbliebene Wiederholungslücke steht oben ausdrücklich getrennt.
- Begleitsatz nur unter fremder Quellenziffer sowie versteckter Volltext plus zweiter sichtbarer Quelle retten die Regel nicht. Ein Nein des zweiten Tors nur zum Begleitsatz führt nach diesem Tor auf Zitate.
- Vollständiger sichtbarer Absatz, mehrere vollständige Regelabsätze, Ein-Satz-Regel und gewöhnlicher Fakt bleiben positiv. Fragezeichen im mitgeführten Originalkontext bleiben sichtbar; vorhandene Zitatzeichen führen über das bestehende Normativtor zum sicheren Zitatfallback.
- Überlange sichtbare Absätze (>400 Zeichen) lösen vor dem Provider den Zitatfallback aus, auch wenn zusätzlich ein kurzer Regelsatz vorliegt. Ein verborgenes Fragment wird nicht angeboten. Eine andere vollständig sichtbare, selbständige Regel bleibt auswählbar; das behauptet keine vollständige Antwort auf alle möglichen Fragen zur Quelle.
- Sechs unabhängige echte Close/Reopen-Gegenproben: vollständiger Absatz, Ein-Satz-Regel und gewöhnlicher Fakt positiv; isolierte gemischte Regel, Headerfragment und rein normatives Fragment negativ. Die für Altantworten hergestellten Referenz-Umhüllungen tragen explizites gespeichertes Modell-Ja, das die neue Abschlussprüfung nicht umgeht. Ignore sperrt alle sechs; Originaltexte bleiben erhalten. Diese Altantwortproben verwenden vorbereitete synthetische Payloads und sind vom oben vollständig erzeugten Wiederholungsbefund getrennt.

## Testverträge und Nutzbarkeit

Die Umstellungen der P01-, Before/After- und Original-ID-Erwartungen auf den vollständigen Absatz sind sachlich erforderlich. Die zentralen Satztests dürfen einen exakten einzelnen Satz weiterhin als wörtlich gültig einstufen; daraus folgt jetzt keine vollständige ausgabefähige Antwort. Die Abschlussprüfung muss unabhängig davon Kontext und Reihenfolge sichern.

Im Reviewarchiv wurde der bisherige gespeicherte AFTER-Positivfall durch einen vollständigen Absatz-Positivfall ersetzt. Die vom Root im gemeinsamen Checkout ergänzte Gegenkontrolle wurde gelesen: Nach echtem Store-Reopen wird eine Kopie auf `AFTER` allein verkürzt und `restore is None` verlangt; daneben bleiben der volle Absatz sowie Ignore/Originalerhalt geprüft. Das ist eine sinnvolle explizite Vertragsänderung und erhält das negative alte Payload-Szenario. Dieser zusätzliche gemeinsame Test wurde von diesem Reviewer nicht ausgeführt; der Archivteststand ist separat unten belegt.

Bewusste Kosten bleiben: Ein kurzer relevanter Regelsatz trägt seinen ganzen erkannten Mehrsatzabsatz mit; dessen Länge, Sichtbarkeit oder Ablehnung kann die Satzantwort insgesamt in Zitate überführen. Historischer Status in einem eigenen **abgeschlossenen** Absatz bleibt die bereits benannte Autoritätsgrenze. Keine allgemeine Aussage über semantische Wahrheit, unerkanntes normatives Vokabular oder Dokumentautorität.

## Unabhängige Verifikation und Fingerprints

**148 fokussierte Tests bestanden** (`test_normative_paragraph_context`, `test_original_sentence_selection`, `test_normative_source_binding`, `test_before_after_permission`) in 1,45 s. Keine Vollsuite, keine echten Modelle, Netzwerkaufrufe oder privaten Daten. Produkt und Archiv wurden nicht geändert; Python-Bytecode/pytest-Cache für diese Läufe waren deaktiviert. Keine weiteren Gegenproben laufen auf dieser Fassung.

- `satzantwort.py`: `272d406b20af8d1b185f1394fb118ef1b751ae57f80da85b34c378e0c3ac195b`
- `satzpruefung.py`: `3ab77753104be77fe2285130d5dccfd3d0ced31891d42871c0cc226bb58d042b`
- Unveränderte Goldfixture: `a53217e6a52aa5a6c55728cc5ccc6d12ba21317a53538a391adbda970db4a361`

Evidenz:

- `/private/tmp/kingfisher-rule-paragraph-corrected-review-probes-20261009.json` und Runner `/private/tmp/kingfisher-rule-paragraph-corrected-probe-20261009.py`: ursprüngliche Gegenproben, neue ID-Positiva, Grenzen und sechs Close/Reopen-Prüfungen.
- `/private/tmp/kingfisher-rule-paragraph-repetition-probe-20261009.json` und gleichnamiger `.py`: unverändert erzeugte falsche Ausgabe einschließlich zweitem Tor, echtem Speichern/Neuöffnen und Entzug.
