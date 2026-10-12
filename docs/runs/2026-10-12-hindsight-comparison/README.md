# Hindsight gegen Kingfisher: lokaler, getrennter Vergleich

**Entscheidung: Hindsight 0.10.3 und den getesteten Reranker derzeit nicht in Kingfisher übernehmen.** Auf diesem Mac mit dem vorhandenen Qwen9B ist kein Gewinn an Verlässlichkeit oder Geschwindigkeit belegt. Der Test hat dagegen einen konkreten Auswahlfehler in Kingfisher sichtbar gemacht. Diesen gezielt beheben, statt das Gedächtnis auszutauschen.

Stand: 12.10.2026. Nur künstliche Quellen. Keine persönlichen Speicher, Cloudinferenz, API-Gebühren oder Änderungen der installierten App. Alle drei eigenen Testports sind nach Abschluss geschlossen; Kingfishers `/health` liefert weiterhin HTTP 200.

## Versuchsaufbau

- Kingfisher-Code: `f75ccadadf4de9de88c3784cea6770c98fab955f`; letzter Laufzeitcode-Commit `69409536162aa866a2610bcfbfad7255fd4f645e`.
- Hindsight: `hindsight-api-slim[embedded-db]==0.10.3`, eigener PostgreSQL-Speicher über `pg0-embedded==0.15.2`. Kein zusätzlicher Docker-Stapel; die vorhandene Docker-Platte hatte weniger als 1 GB Reserve.
- Beide verwenden dieselben vorhandenen lokalen Gewichte: `kingfisher-qwen3.5:9b-32k`, Digest `4b44ba7611d862092ee5ea1fe4fbf3c127613ea7721bf762de348d5ff9d65de3`, sowie `bge-m3:latest`, Digest `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`.
- 20 eingefrorene deutsche Originale, 15 Fragen. Katalog-SHA256: `7768438e8fd27fabdab0e1210b001dc474001e03f9b76025202776082e105e52`.
- Fester Fragezeitpunkt: 12.10.2026, 10:00 Uhr Europe/Berlin. `occurred_at` bezeichnet in diesem Dokumententest den Zeitpunkt der Originalquelle, nicht automatisch den Zeitpunkt eines darin berichteten Ereignisses. Quelle s15 wurde am 12.10. um 09:00 erstellt und berichtet über den Vortag, den 11.10. Quelle s20 hat ausdrücklich keinen bekannten Originalzeitpunkt.
- Ein Modellaufruf zur Zeit, Temperatur 0. Hindsight: `reasoning_effort=none`, nativer Kontext 32768, Retain-Ausgabegrenze 4096, automatische Konsolidierung aus. Kingfisher: bestehender Klassifizierer und JSON-Quellenauswahl; semantischer Cache nach Aufnahme einmal vorbereitet. Hindsight Recall: Budget `mid`, 2048 Tokens; Reflect: Budget `low`, angefragte Ausgabegrenze 512.
- Inferenz ausschließlich über einen fest auf `127.0.0.1:11434` gerichteten Proxy mit Modell-/Endpoint-Whitelist. Der Hindsight-Embedding-Provider heißt technisch `openai`, sein Ziel war ausschließlich die lokale kompatible Ollama-API. Keine Cloudschlüssel.
- Zusätzlich: multilingualer FlashRank-Reranker `ms-marco-MultiBERT-L-12`, etwa 100 MB Gewichte. Erst Bestandteil des Hindsight-Tests, danach isolierte Umordnung derselben unveränderten deutschen Originaltexte. Keine Produktintegration.

## Gemessene Zeiten

| Pfad | Umfang | Ergebnis |
|---|---:|---:|
| Kingfisher: Originale automatisch einordnen | 20 Quellen, 20 erfolgreich | 93,32 s gesamt; 4,61 s Median/Quelle |
| Hindsight: Fakten/Entitäten aus Originalen extrahieren | 20 Quellen, 20 erfolgreich | 257,45 s gesamt; 12,50 s Median/Quelle |
| Kingfisher: Quellenauswahl mit Qwen | 15 Fragen; eine vom geprüften Pfad nicht behandelt | 7,41 s Median/Pfad |
| Hindsight: Recall einschließlich Reranker | 15 Fragen | 1,93 s Median |
| Hindsight: native Reflect-Antwort | nur erste zwei Fragen | 189,74 s und 172,52 s |
| Kleiner Reranker auf unveränderten Originalen | 15 Fragen | 0,65 s Median |

**Die Arbeitsschritte sind unterschiedlich.** Kingfisher klassifiziert Originalstellen und zeigt ausgewählte Originalzitate. Hindsight extrahiert neue Fakten und kann mit mehreren Werkzeug-/Modellschritten freie Antworten formulieren. Die Tabelle misst diese tatsächlich ausgeführten Pfade, keine identischen Aufgaben und keine universelle Leistungsfähigkeit der Systeme. Kingfishers reine Kandidatensuche wurde separat gemessen; beispielsweise 0,088 s bei der ersten konkreten Frage, gegenüber 2,58 s für Hindsight Recall. Kalte und warme Zustände sowie Modellresidenz beeinflussen die Einzelwerte.

Die zwei nativen Reflect-Aufrufe reichten zur Abgrenzung des teuren Pfades. Die übrigen 13 Reflect-Aufrufe wurden bewusst nicht ausgeführt. Es gibt deshalb keine 15-Fragen-Genauigkeitsquote für Hindsight und keinen Beleg für dessen Antwortverhalten in allen übrigen Fällen. Der Reflect-Parameter 512 begrenzte nicht alle internen Modellschritte; die protokollierten Aufrufe enthielten teils mehr als 11.000 Eingabetokens.

## Reproduzierte Qualitätsbefunde

### 1. Kingfisher findet den Widerruf, lässt ihn aber bei der Auswahl weg

Frage `withdrawn_commitment`: Die ursprünglich zugesagte Hilfe am Herbstmarkt wird zuerst auf einen anderen Veranstaltungstag verschoben und anschließend ausdrücklich zurückgezogen.

- s04: ursprüngliche Zusage.
- s05: dieselbe Veranstaltung verschoben.
- s06: „Ich kann am 27.09.2026 doch nicht beim Herbstmarkt helfen; bitte meine Zusage streichen.“

Alle drei befinden sich im tatsächlich an Qwen übergebenen Kandidatenkontext. Dennoch liefert Qwen `{"status":"source_reports","ids":["S1","S3"]}`: s04 und s05, ohne s06. Kingfisher zeigt damit den alten Stand ohne den entscheidenden Widerruf. Eine getrennte Wiederholung reproduzierte exakt dieselbe Auswahl. Die nachgelagerten Anpassungen verursachen diesen Verlust nicht: Bereits die rohe Modellantwort lässt s06 weg.

Das ist ein **Auswahl-/Antwortkontextfehler**, kein Nachweis einer unzureichenden Suche. Eine bloße Kennzeichnung als „Quelle berichtet“ genügt hier nicht. Belege: `data/selection-diagnosis.json` und `data/answers.json`.

### 2. Hindsight erfindet schon bei der Aufnahme einen konkreten Zeitpunkt

s20 berichtet „nächsten Freitag um 17 Uhr“, sagt ausdrücklich, dass das Datum der alten Originalmail unbekannt ist, und verbietet die Ableitung aus dem späteren Erfassungsdatum. Hindsight speichert trotzdem einen abgeleiteten Fact mit `When: 2026-10-19`.

Der 19.10.2026 ist außerdem ein Montag. Parallel existiert zwar ein korrekter Unsicherheits-Fact, aber dieser verhindert die erfundene Datierung im selben Speicher nicht. Das ist ein tatsächlich gespeicherter Extraktionsfehler. **Nicht getestet** wurde, ob Hindsight diesen Fehler anschließend in einer nativen Antwort ausgeben würde. Beleg: `data/hindsight-extracted-facts.json`, Original s20 im Katalog.

### 3. Hindsight antwortet auf eine eindeutige Umformulierung unnötig mit „unknown“

s01 nennt das Gespräch mit Dr. Lena Berg im Klinikum Nord und die mitzubringende Angebotsliste. Eine andere Quelle betrifft ausdrücklich eine Absage im Klinikum Süd und nicht den Nord-Termin.

- Konkrete Frage: native Hindsight-Antwort nennt die Angebotsliste richtig und grenzt Süd/Nord ab; zusätzliche Zitation von s12 ist hier kein falscher Fakt.
- Umformulierte, weiterhin ausdrücklich auf Klinikum Nord bezogene Frage: Hindsight erkennt s01 und die Angebotsliste, erklärt die Antwort aber wegen vermeintlich ungeklärter Identität für `unknown`.

Das ist eine unnötige Enthaltung trotz passendem Beleg, keine sichere Auflösung des Problems durch ein anderes Gedächtnis. Kingfisher wählt in beiden Fällen s01. Beleg: `data/answers.json`.

### 4. Breiter Recall ist noch keine passende Antwort

Hindsight liefert bei der konkreten und der umformulierten Frage jeweils alle 20 Originalkennungen zurück. Die richtige Nord-Quelle steht in der nach Originalkennungen deduplizierten Fact-Reihenfolge erst an Position 3 beziehungsweise 5. Auch bei der Frage nach einer nicht vorhandenen Blutgruppe liefert Recall 17 Originalkennungen.

Daraus darf weder eine falsche finale Antwort noch eine gute Suchpräzision abgeleitet werden. Recall und Antwort/Enthaltung müssen getrennt bewertet werden. `summary.json` hält die tatsächliche Reihenfolge fest.

Kingfishers Blutgruppenfrage wird vom geprüften Arbeitsgedächtnispfad nicht behandelt (`prepare` liefert `None`). Ein vollständiger Agentenlauf mit verifizierter Enthaltung wurde hier nicht durchgeführt. Ebenso sind getrennte Nord-/Süd-Originalzitate bei der mehrdeutigen Terminfrage keine falsche Identitätszuordnung; die Frage nach besserer Rückfrage-/Darstellungsform bleibt separat.

### 5. Der kleine Reranker liefert keinen sicheren Übernahmegewinn

Der zusätzliche Versuch ordnet alle 20 unveränderten Originaltexte um, ohne Qwen und ohne Suchfilter. Unter den 14 Fragen mit erforderlichen historischen Belegen sind diese bei 12 Fragen vollständig unter den ersten drei/fünf Treffern. Bei der umformulierten Nord-Frage fehlt s01 jedoch in den ersten fünf; beim Zusagen-Widerruf fehlt s06 dort ebenfalls.

Damit würde eine Beschränkung auf diese ersten Treffer gerade die wichtigen Fehler verschärfen. Kein automatisches Filtern oder Ersetzen der vorhandenen Suche. Der isolierte Pythonprozess meldete rund 821 MiB RSS; das beinhaltet die Testinitialisierung mit ONNX-Sessions und ist keine gemessene Zusatzlast einer optimierten Produktintegration. Beleg: `data/original-reranker-ablation.json`.

## Tatsächlicher Quellenentzug

Die eigene künstliche Quelle s19 enthält einen fingierten Objektivcode. Vor Entzug wurde dieser über beide Systeme gefunden. Danach:

- Kingfisher: `EpisodeStore.ignore` sperrt das Original als Beleg. Eine schon gespeicherte Antwort wird beim erneuten Rendern `working_unavailable`, enthält den Code nicht mehr und verlangt eine neue Frage. Eine frische Suche liefert `unknown` ohne s19. Der Originaltext bleibt erhalten.
- Hindsight: Löschen des eigenen Testdokuments s19 liefert HTTP 200; ein neuer Recall enthält s19 nicht mehr. Eine native alte Reflect-Antwort wird dadurch nicht in einer Kingfisher-Oberfläche nachträglich geprüft; diese Verlaufsgarantie wurde für Hindsight nicht getestet.

Das ist tatsächlicher Belegentzug. Die inhaltliche Absage s06 dagegen muss als historische Quelle auffindbar bleiben und darf nicht wie eine entzogene Quelle verschwinden. Beleg: `data/withdrawal-results.json`.

## Was wir sinnvoll übernehmen

1. **Den Vergleichskatalog als feste Regression für Kingfisher.** Insbesondere Widerruf nach Datumsänderung, gleichnamige Menschen, unbekannte Originalzeit und fehlende Information.
2. **Getrennte Messung von Aufnahme, Suche und Antwort.** Ein breiter Trefferpool oder ein schneller Reranker beweist keine richtige Antwort. Original-ID, Zeitbezug und endgültige Auswahl gemeinsam prüfen.
3. **Gezielte nächste Verbesserung an Kingfishers Auswahl.** Bei aktuellen Zusagen/Fristen die eindeutig zugeordneten Änderungen und Widerrufe aus dem bereits gefundenen Kontext mitprüfen. Unsichere Personen-/Vorgangszuordnung führt zur Rückfrage. Kein pauschales „neueste Quelle gewinnt“, keine freie automatische Änderung von Fakten und kein zweiter kompletter Gedächtnisstack.

Es wurde **kein Hindsight-Laufzeitcode in das Produkt übernommen**, weil der getestete Aufbau dafür keinen Nutzenbeleg liefert. Auch die neue Auswahlabsicherung ist in diesem Bericht ein begründeter nächster Arbeitsschritt, noch keine installierte Korrektur. Die unabhängige Fallprüfung durch einen kleinen Agenten bestätigt die drei konkreten Qualitätsbefunde und die Grenzen der Übernahmeentscheidung.

## Grenzen und Nachvollziehbarkeit

Kleiner künstlicher Katalog, überwiegend kurze Originale, keine Massendaten-/Mehrtagestests, kein Batteriebenchmark, keine wiederholten unabhängigen Läufe mit statistischen Unsicherheitsintervallen. Keine Prüfung von Hindsights automatischer Konsolidierung, trainierten Dispositionen oder langfristig aufgebauten Observations. Keine Aussage darüber, ob ein größeres/Cloud-Modell andere Ergebnisse erzielen würde. Kein Anspruch auf „fehlerfreies Gedächtnis“ aus diesem Test.

`data/measured-events.jsonl.gz` bewahrt die vollständigen originalen Ereignisse einschließlich Hindsight-Responses und Traces. `data/answers.json` ist eine lesbare Projektion ohne die umfangreichen Traces. Das Modellprotokoll enthält auch Setup-/Kompatibilitätsproben; Phasenlabels wurden erst nach der Aufnahme ergänzt. Daraus nicht blind vollständige Phasenkosten aufsummieren. Keine privaten Schlüssel oder persönlichen Inhalte sind Bestandteil dieser Artefakte.

### Wiederholung, ausdrücklich nur im künstlichen Testbestand

Die exportierten Skripte verlangen separate Arbeitsverzeichnisse und verändern keine Kingfisher-Produktkonfiguration. Python 3.12, laufendes lokales Ollama und genau die vorhandenen beiden Modelle sind Voraussetzung. Die Einrichtung lädt Python-Abhängigkeiten, eine PostgreSQL-Runtime und den kleinen Reranker; sie ist nicht vollständig offline.

```sh
export KINGFISHER_REPO=/absoluter/pfad/zum/Kingfisher-Checkout
export KINGFISHER_HINDSIGHT_BENCH_DIR="$(mktemp -d /private/tmp/kf-hindsight-XXXXXX)"
# Ab diesem Punkt nur den eigenen synthetischen Testordner verwenden.
python3.12 -m venv "$KINGFISHER_HINDSIGHT_BENCH_DIR/.venv"
RUN="$KINGFISHER_REPO/docs/runs/2026-10-12-hindsight-comparison"
cp "$RUN/data/catalog.json" "$KINGFISHER_HINDSIGHT_BENCH_DIR/catalog.json"
"$KINGFISHER_HINDSIGHT_BENCH_DIR/.venv/bin/pip" install -r "$RUN/harness/requirements.txt" -e "$KINGFISHER_REPO/sidecar"
"$KINGFISHER_HINDSIGHT_BENCH_DIR/.venv/bin/python" "$RUN/harness/start_services.py"
```

In einem zweiten Terminal mit denselben Umgebungsvariablen: API-Gesundheit auf `http://127.0.0.1:18935/health` prüfen, dann `compare.py intake`, `compare.py queries`, optional `compare.py queries reflect`. Im Export ist Reflect ausdrücklich auf die ersten zwei Fälle begrenzt. Danach `rerank_originals.py` und `withdrawal_and_selection.py`; letzteres entzieht ausschließlich s19 im künstlichen Bestand. Die Dienste anschließend mit Ctrl-C beenden. Keine vorhandene Bank oder Produktdatenbank als Testpfad verwenden. Die Skripte sind opt-in Diagnosewerkzeuge, keine Tests der installierten Oberfläche.

Die Skriptexporte wurden syntaktisch geprüft; der gesamte Test lief mit den temporären Ursprungsfassungen. Der portable Export wurde nicht nochmals mit einem zweiten vollständigen Modelllauf ausgeführt.
