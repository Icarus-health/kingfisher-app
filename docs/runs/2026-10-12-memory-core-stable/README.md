# Gedächtniskern 1.0.7: Abnahme und Auslieferung

Der Nutzer hat ausschließlich die Fertigstellung des vorhandenen Gedächtniskerns und dessen geprüfte Auslieferung auf GitHub und seinem Mac freigegeben. Keine neue Funktion, neue Modellarchitektur oder Cloudverarbeitung ist Teil dieses Laufs.

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

`lifecycle-results.jsonl` belegt echten Quellenentzug: Ein künstlicher Code war zunächst sichtbar, verschwand nach Entzug aus altem und neuem Gespräch, und das Original blieb erhalten. `incremental-real-results.jsonl` belegt Wiederöffnung nach Entzug sowie eine tatsächliche neue Fristquelle: alte Antwort ungültig, neue Quelle sichtbar, beide Originale erhalten.

Grenze des festen Katalogs: Die unspezifische Klinikfrage zeigte beide konkreten Nord-/Süd-Originale, ohne die rubric-seitig geforderte Klinik-Rückfrage. Das ist keine Identitätsverschmelzung oder Übertragung der Absage, aber keine vollständig erfüllte Rückfrage-Rubrik. Originalzitate sind ein sicherer Rückfall, keine perfekte automatische Zusammenfassung.

### Regression und unabhängige Prüfung

Der erste vollständige Backend-Lauf ergab 6.329 bestandene, sieben fehlgeschlagene und einen übersprungenen Test sowie 26 bestandene Subtests. Die Fehler wurden nicht als bestanden umgedeutet: ältere Satztests erwarteten verlorene ausgewählte Originale, zwei relative Fristfixtures hingen vom aktuellen Datum ab, und ein Architekturscan erfasste lokale untracked iCloud-Duplikate. Die neue Gesamtprüfung läuft auf einem kanonischen, unveränderlichen Git-Export. Der separate native Logiktest auf kanonischen Quellen bestand; die unveränderte UI hat 573 bestandene Tests und einen erfolgreichen Build, Asset- und Anführungszeichenprüfung sind bestanden.

Der unabhängige Review reproduzierte zusätzlich falsche Aufgabenabsagen, Negationen, Kontraste und gemeinsame allgemeine Kategorien. Die endgültige Gegenstandsprüfung hat positive Kontrollen für tatsächlich gleiche Aufgaben und komplette Veranstaltungsabsagen. Die Abnahme verlangt sichere Quellenanzeige statt stiller kategorischer Schlussfolgerungen.

## Noch laufende Freigabe

Die abschließenden Modell-/Regressionsläufe und Paketbindung werden vor dem persönlichen Wechsel festgehalten. Bis dahin ist weder eine finale Installation noch eine Veröffentlichung behauptet. Sicherung, Daten-/Konfigurationsvergleich und tatsächlicher Fenstertest gehören zur Auslieferung, nicht nur ein erfolgreicher Build.

## Reproduktion

`probe_memory_core_lifecycle.py` liegt im Repository unter `scripts/`. Für die realen Modellproben in diesem Ordner muss `KINGFISHER_CORE_REPO` auf den Checkout und `KINGFISHER_CORE_PROBE_DIR` auf einen neuen getrennten temporären Ordner zeigen. `data/catalog.json` dort als `catalog.json` kopieren, anschließend `scripts/probe.py intake` und `scripts/probe.py queries` ausführen; `--quotes` prüft den Zitatmodus. Niemals das persönliche Datenverzeichnis als Probeordner verwenden. Die Begleitproben `lifecycle.py` und `incremental.py` erwarten den dokumentierten bereits abgeschlossenen ersten synthetischen Antwortlauf.
