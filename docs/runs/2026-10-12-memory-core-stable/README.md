# Gedächtniskern 1.0.7: Abnahme und Auslieferung

Der Nutzer hat ausschließlich die Fertigstellung des vorhandenen Gedächtniskerns und dessen geprüfte Auslieferung auf GitHub und seinem Mac freigegeben. Keine neue Funktion, neue Modellarchitektur oder Cloudverarbeitung ist Teil dieses Laufs.

Geprüfter Runtime-Commit: `e9a968f53d2c77a49dd410665c785f77bc3b59b0`, Paketversion 1.0.7. Die hier hinzugefügten Dokumentationscommits verändern diese Runtime-Bindung nicht. `data/final-e9a968f-evidence-manifest.json` bindet die synthetischen Rohbelege, die portablen Prüfläufe und die abschließenden Testprotokolle mit SHA-256 an diesen Stand.

## Was abgesichert wird

- Gefundene mögliche Änderungen dürfen bei aktuellen Fragen nicht durch die Auswahl des Modells verschwinden. Bei ungeklärter Zugehörigkeit bleiben Originale und eine neutrale Rückfrage erhalten; es wird keine Absagebeziehung erfunden.
- Eine Satzantwort darf bereits ausgewählte Originalquellen nicht still verlieren. Bei unvollständiger Abdeckung oder fälschlicher Satzabstention fällt die Darstellung auf Originalzitate zurück.
- Negative und historische Zeitfragen dürfen keinen falschen heutigen Quellenbereich erhalten. Auch gespeicherte Altantworten werden erneut geprüft.
- Eine separate Aufgabe im selben Projekt darf keine andere Zusage aufheben. Gegenstand, Teilsatz und Negation werden berücksichtigt; die korrigierten Akten werden neu berechnet.
- Automatische Beziehungen bleiben Vermutungen. Das Programm erzeugt aus ihnen keine kategorischen Ersetzungssätze. Originale, bestätigte Aussagen und Aufgaben werden nicht verändert.

## Getrennte Prüfungen

### Dauerhafte Aufnahme: 10.000 Quellen

`data/lifecycle-10000-v2.json` dokumentiert echte Store-/Intake-/Worker-/Vektorindexmechanik mit deterministischem Testanbieter und Testvektoren. Das ist kein Nachweis der Sprachmodellqualität und kein vollständiger Import des persönlichen Mailarchivs.

Alle 10.000 Originaltexte einschließlich Titel, Quellentyp, Quelldatum, Sender sowie unabhängiger Konto-/Anbieterkennung wurden gegen den Sollbestand geprüft. Ein zusätzlicher vollständiger Hashbestand blieb über Aufnahme, Labelwiederholung, Indexneustart, Nachlieferungen, neue Quellenversion und Quellenentzug erhalten. Eine kohärente Veränderung eines Originaltexts bei unveränderten Zählerständen wird durch die Sabotageprobe erkannt.

Laufzeit: 107,367 Sekunden. 1.000 Labelwiederholungen erzeugten keine neuen Originale und keine neue Einordnung. Nach dem Indexneustart wurden nur die 10 neuen Quellen und die eine neue Fassung zusätzlich eingebettet. Am Ende: 10.011 erhaltene Originale, 10.009 zulässige fertig eingeordnete Quellen, keine verbleibende Aufnahme. Auch ausgeschlossene und ersetzte Originale blieben erhalten.

Inventar-SHA-256: `c8e9d5445c2ddcd65411195e988710cb47055ba27e56f4768385b22be63b0cbb`.

### Tatsächliche lokale Modellarbeit

Der vor dem Lauf eingefrorene Katalog enthält 20 künstliche Originale und 15 Fragen. SHA-256: `7768438e8fd27fabdab0e1210b001dc474001e03f9b76025202776082e105e52`.

Einordnung: vorhandenes `kingfisher-qwen3.5:9b-32k`; lokale Bedeutungssuche: vorhandenes `bge-m3`. Transport ausschließlich zu Ollama auf Loopback. Die Aufnahme verwendet die tatsächliche `/episodes`-Route und den echten Worker; Antworten gehen durch die authentifizierte Gesprächsroute mit Frageverstehen, Auswahl und Satzprüfung. Diese Originalquellen sind synthetische Dokumente, keine persönlichen E-Mails.

Die Erstläufe bleiben erhalten: `answers-sentences-before-fix.jsonl` zeigt, dass das Satzmodell trotz richtig ausgewählter Quelle fälschlich keine Information behauptete. `answers-*-before-original-time-fix.jsonl` zeigt den zusätzlich falschen Heute-Rahmen einer historischen Bezugsfrage. Diese Fehler wurden unabhängig inhaltlich erkannt und durch rote Regressionen abgesichert; eine Trefferquote anhand von Quellen-IDs hätte sie übersehen.

Die älteren `lifecycle-results.jsonl` und `incremental-real-results.jsonl` bleiben als frühere Laufnachweise erhalten. Die endgültigen Laufdaten heißen ausdrücklich `final-e9a968f-*`.

Auf `e9a968f` wurden alle 20 Originale mit dem tatsächlichen lokalen Qwen aufgenommen und vollständig eingeordnet; die Originaltexte blieben erhalten (`final-e9a968f-intake-*`). Die 15 tatsächlichen Gesprächsantworten sind in `final-e9a968f-answers-sentences.jsonl` gespeichert. Die ID-Auswertung in `final-e9a968f-evaluation.json` hält alle 15 geforderten Belegmengen sichtbar und weist die Klinik-Statusabweichung weiterhin aus. Die unabhängige inhaltliche Prüfung fand keine erfundenen Angaben, keine Nord-/Süd-Übertragung und keine als aktive Pflicht ausgegebene widerrufene Zusage. Das ist ein begrenzter Prüfkatalog, keine allgemeine Genauigkeitsgarantie.

Der tatsächliche Satzmodus liefert drei geprüfte Satzantworten und acht Berichte mit Originalzitaten; fünf davon sind Rückfälle nach Satzabstention, drei nach sonstiger Satzunsicherheit. Drei Fälle verlangen Klärung und ein fehlender Fakt bleibt unbekannt. Bei Alex Winter stehen in der allgemeinen Frage beide ausdrücklich getrennten Originale mit Personenrückfrage, in der Einkaufsfrage nur die Einkaufsadresse. `final-e9a968f-lowercase-api-results.jsonl` belegt dieselben beiden Antworten bei vollständig kleingeschriebenen Fragen. Der historische Heute-Bezug zeigt die Notiz vom 02.09.2026 ohne falschen heutigen Quellenrahmen.

`final-e9a968f-lifecycle-results.jsonl` belegt Wiederöffnung und echten Quellenentzug: Der künstliche Code war zunächst sichtbar, verschwand nach Entzug aus altem und neuem Gespräch, und das Original blieb erhalten. `final-e9a968f-incremental-real-results.jsonl` belegt danach vier weitere Phasen: Entzug nach Store-Neustart, Antwort vor Nachlieferung, Sperre des alten Gesprächs nach neuer Fristquelle und frischer Abruf der neuen Frist bei erhaltenen alten und neuen Originalen.

Der erste inkrementelle Versuch scheiterte beim Aufwärmen der Bedeutungssuche nach 30 Sekunden mit `httpx.ReadTimeout`. Nach einer erfolgreichen Bereitschaftsprüfung des lokalen Embedding-Endpunkts in 1,57 Sekunden bestand die Wiederholung ohne Runtime-Änderung. Das ursprüngliche Konsolenereignis ist im Manifest als Meldung des Koordinators gekennzeichnet; ein überschriebenes Fehlerlog wurde nicht nachträglich rekonstruiert. `final-e9a968f-incremental-rerun.log` enthält den erfolgreichen Wiederholungslauf.

Grenze des festen Katalogs: Die unspezifische Klinikfrage zeigte beide konkreten Nord-/Süd-Originale, ohne die rubric-seitig geforderte Klinik-Rückfrage. Das ist keine Identitätsverschmelzung oder Übertragung der Absage, aber keine vollständig erfüllte Rückfrage-Rubrik. Originalzitate sind ein sicherer Rückfall, keine perfekte automatische Zusammenfassung.

### Regression und unabhängige Prüfung

Der erste vollständige Backend-Lauf ergab 6.329 bestandene, sieben fehlgeschlagene und einen übersprungenen Test sowie 26 bestandene Subtests. Die Fehler wurden nicht als bestanden umgedeutet: ältere Satztests erwarteten verlorene ausgewählte Originale, zwei relative Fristfixtures hingen vom aktuellen Datum ab, und ein Architekturscan erfasste lokale untracked iCloud-Duplikate.

Die abschließende Backend-Prüfung auf dem kanonischen unveränderlichen Export von `e9a968f` bestand mit 6.414 Tests, einem übersprungenen Test und 26 bestandenen Subtests in 999,98 Sekunden; zwei Warnungen bleiben ausgewiesen. Die weiteren Testbereiche bestanden mit 575 Tests und einem übersprungenen Test in 80,59 Sekunden. Die unveränderten UI-Quellen haben 573 bestandene Tests und einen erfolgreichen Build; die UI-Protokolle werden als Nachweis der unveränderten UI geführt, nicht als neu behaupteter Backend-Lauf. Build-Hinweise zu Chunkgröße und Plugin-Laufzeit bleiben erhalten. `final-e9a968f-full-test-proof.json` und die vier komprimierten Testlogs halten Zahlen und Log-Hashes fest. Der separate native Logiktest sowie Asset- und Anführungszeichenprüfung auf kanonischen Quellen bestanden.

Der unabhängige Review reproduzierte zusätzlich falsche Aufgabenabsagen, Negationen, Kontraste und gemeinsame allgemeine Kategorien. Die endgültige Gegenstandsprüfung hat positive Kontrollen für tatsächlich gleiche Aufgaben und komplette Veranstaltungsabsagen. Die Abnahme verlangt sichere Quellenanzeige statt stiller kategorischer Schlussfolgerungen.

## Weitere Freigabegegenfälle

Der eingefrorene Kandidat `5007716` wurde trotz vieler bestandener Prüfungen nicht ausgeliefert: Im tatsächlichen Qwen-Lauf wählte das Modell bei einer allgemeinen Alex-Winter-Adressfrage nur eines der zwei ausdrücklich verschiedenen Dokumentenoriginale. Die zweite Quelle war im Kandidatenpool vorhanden. 14 von 15 erforderlichen Belegmengen blieben sichtbar; das war kein akzeptierter Gesamterfolg. Die Rohantwort und die negative Bewertung bleiben als `candidate-5007716-*` erhalten.

Die enge Korrektur hält ausdrücklich getrennte gleiche Namen auch ohne Mail-Absenderdaten sichtbar und verlangt Klärung vor der Satzbildung. Sie erzeugt keine Personen oder bestätigten Identitäten. Konkrete Kontextfragen, Adresswechsel, negierte Personentrennung, ausgeschlossene Quellen und Kleinschreibung sind Gegenkontrollen; gespeicherte alte eindeutige Antworten werden erneut geprüft.

Der saubere vollständige Lauf von `5007716` hatte 6.398 bestandene, vier fehlgeschlagene und einen übersprungenen Test sowie 26 bestandene Subtests. Die verbliebene echte Unterlagenzusagen-Regression wurde korrigiert, ohne allgemeine Kategorien als Gegenstand gelten zu lassen. Ein Regex-Zeichen löste die Typografieprüfung aus und wurde semantisch identisch Unicode-escaped. Zwei positive Satzübernahme-/Prüftests wurden an den abgesicherten Originalbelegvertrag angepasst. Auch gleiche Aufgaben an ausdrücklich verschiedenen Veranstaltungen bleiben getrennt.

## Stand der Auslieferung

Der Koordinator meldet die lokale Installation von 1.0.7 mit Runtime `e9a968f` nach kalter Sicherung: 168 Dateien und 17 Datenbanken gesichert; Hash-/Schema-/Konfigurationsvergleich der 14 maßgeblichen Tabellen beziehungsweise Konfigurationsbestände unverändert. Diese technische Erhaltungsprüfung ist keine Bewertung der Qualität sämtlicher persönlicher Daten. Private Installationsbelege und persönliche Datenbanken sind nicht Teil dieses Repository-Nachweises.

Die neue native App wurde geöffnet; die vier Modellrollen verwenden lokal das vorhandene 9B-Modell und die Bedeutungssuche `bge-m3`. Der abschließende tatsächliche Fragen-/Antwortnachweis im persönlichen Appfenster und die Veröffentlichung auf GitHub bleiben zum Zeitpunkt dieses Dokumentationsstands offen. Ein lokaler Commit oder eine gemeldete Installation werden nicht als abgeschlossene Veröffentlichung beziehungsweise Fensterabnahme bezeichnet.

## Reproduktion

`probe_memory_core_lifecycle.py` liegt im Repository unter `scripts/`. Für die realen Modellproben in diesem Ordner muss `KINGFISHER_CORE_REPO` auf den Runtime-Checkout `e9a968f` und `KINGFISHER_CORE_PROBE_DIR` auf einen neuen getrennten temporären Ordner zeigen. `data/catalog.json` dort als `catalog.json` kopieren, anschließend `scripts/probe.py intake` und `scripts/probe.py queries` ausführen; `--quotes` prüft den Zitatmodus. Niemals das persönliche Datenverzeichnis als Probeordner verwenden. Die Begleitproben `scripts/lowercase.py queries`, `scripts/lifecycle.py queries` und danach `scripts/incremental.py queries` erwarten den bereits abgeschlossenen ersten synthetischen Antwortlauf und dieselben erzeugten IDs/Stores; auch sie benötigen das Argument `queries`. Diese Skripte führen bei Ausführung echte lokale Modellaufrufe aus; die Dokumentationsprüfung hat sie nicht erneut ausgeführt.
