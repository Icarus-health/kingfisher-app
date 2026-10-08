# Abrufprüfung ohne weitere Cloudanfragen

## Umfang

Eine getrennte lokale Kopie des gesicherten Bestands mit 340 Originalquellen
wurde geprüft. Kein großer Import, keine Neueinordnung, keine Modellinferenz
und keine Änderung des laufenden Bestands für die Prüfversuche. Private Fragen,
Originaltexte, Kennungen und vollständige Ergebnisse bleiben außerhalb des
Repositorys. Dieser Bericht enthält ausschließlich aggregierte Befunde;
Regressionstests verwenden künstliche Daten.

Die 20 Fragen und ihre erwarteten Quellen sowie entscheidenden Originalstellen
wurden vor Ausführung der Suche festgelegt. Darunter sind alte Termine,
Absagen, zitierte Nachrichten, Bitten an andere Personen und unbestätigter
Dokumentempfang. Geprüft wurde der produktive Kandidaten-/Kontextweg
`working_memory_answers._candidates`, ohne semantische Erweiterung oder
modellgestützte Umschreibung. Das ist keine zufällige Stichprobe, kein Holdout,
keine vollständige HTTP-Antwortprüfung und kein Beleg für 95 Prozent
Gedächtnisgenauigkeit.

## Gefundene Fehler und Korrekturen

Die Wortsuche des Arbeitsgedächtnisses behandelte Fragewörter wie „habe“, „war“
und „meiner“ als Suchbegriffe. Sie lieferten Scheinbelege, verdrängten ältere
Wortformtreffer und ließen sachfremde neue Quellen gespeicherte Antworten
entwerten. Nur für die Suchanfrage wird nun dieselbe vorhandene
Funktionswortliste wie im Rohquellenindex verwendet – vor Begriffsbudget und
Wortformerweiterung. Persistierte Tokens, Originale, Kategorien und
Quellenfingerabdrücke werden nicht geändert; kein Neuaufbau nötig.

Beim Ausbleiben solcher Treffer fiel beispielsweise „Welche Blutgruppe habe
ich?“ in den freien Chat zurück. Direkte persönliche Faktenfragen der
abgesicherten Formen bleiben jetzt auch bei leerer Suche beleggebunden.
HTTP-Gegenproben mit einem absichtlich erfindenden künstlichen Anbieter zeigen,
dass keine erfundene persönliche Angabe ausgegeben und kein freier Chat
aufgerufen wird. Allgemeine Erklärungen, Ratschläge und ausdrückliche Aktionen
behalten ihren bisherigen Weg. Dies ist eine begrenzte Erweiterung der
deterministischen Erkennung, kein vollständiges Sprachverständnis.

Das unabhängige Review fand anschließend den Gegenfall „… habe ich
eigentlich/denn?“. Drei zusätzliche HTTP-Proben scheiterten zunächst und
bestehen nach Korrektur des begrenzten Satzsuffixes. Ein früher Testentwurf
benutzte irrtümlich den nicht vorhandenen Kontextmanager des EpisodeStore;
nach Korrektur scheiterten sechs der sieben Suchtests am tatsächlichen Fehler,
der Sicherheitsgegenfall bestand bereits. Vier HTTP-Faktenfragen scheiterten
am tatsächlichen Chat-Rückfall, bevor die Routingkorrektur geschrieben wurde.

Zusätzlich benutzen drei bisher eigene ISO-Z-Leser in Kalenderaktionen,
Kalenderfenstern und Terminnachbereitung den vorhandenen zentralen strengen
Parser. Dieselbe Konvertierung und Fehlerbehandlung bleiben erhalten. Der schon
vor diesem Nachtrag rote zentrale Datumsvertrag besteht damit wieder; die
Ausnahmeliste wurde nicht erweitert.

## Gemessener Abruf

| Messung, dieselben 20 Fragen | Vorher | Nachher |
| --- | ---: | ---: |
| Erwartete Quelle und entscheidender Wortlaut im Kontext | 19 | 19 |
| Erwartete Quelle auf Platz 1 | 15 | 14 |
| Gelieferte Kandidaten insgesamt | 300 | 240 |
| Fragen mit begrenzter Auswahl | 17 | 11 |

Die Verringerung der Kandidatenzahl ist kein gemessener Präzisionswert. Ein
erwarteter Treffer rutscht von Platz 1 auf Platz 2, bleibt aber im Kontext.
Die unverändert verfehlte Frage verwendet einen nicht unterstützten Genitiv
und eine Umschreibung zur Besichtigung. Eine alternative Formulierung mit dem
Grundwort findet die Quelle; das löst den ursprünglichen Fehlfall nicht.

Alle 19 gelieferten erwarteten Quellen behalten ihr eigenes Quelldatum.
Nach Ausschluss der 20 erwarteten Quellen in einer zweiten getrennten Kopie
gelangt keine davon mehr in den Kandidatenkontext. Die 19 zuvor gespeicherten
Verweise lassen sich nicht mehr auflösen. Alle 340 Originaldigests bleiben in
dieser Kopie erhalten. Diese Prüfung beweist Quellenentzug und unveränderte
Datumsmetadaten, keine richtige Interpretation von Zitaten oder Fristen.

Der bestehende eingefrorene synthetische Umschreibungskatalog wurde ohne
Modell oder Netzwerk ebenfalls vorher/nachher ausgeführt. Für den Vorherarm
wurde ausschließlich die unveränderte Query-Funktion aus `7568faa` in einem
getrennten Prozess eingesetzt; der Rest des Produktionswegs blieb gleich.

| Katalog, reine Arbeitsgedächtnis-Wortsuche | Vorher | Nachher |
| --- | ---: | ---: |
| Direkte Fragen, erwartete Quelle unter 16 Kandidaten | 16/16 | 16/16 |
| Direkte Fragen, erwartete Quelle auf Platz 1 | 15/16 | 16/16 |
| Umschreibungen, erwartete Quelle unter 16 Kandidaten | 3/16 | 2/16 |
| Unbeantwortbare Fragen mit Kandidaten | 0/4 | 0/4 |

Der verlorene Umschreibungstreffer kam vorher allein über „wurde“ zustande,
nicht über eine erkannte Bedeutung. Trotzdem ist der Rückgang dokumentiert:
**Reine Wortsuche reicht für den gewünschten Alltagseinsatz nicht aus.**
Die produktive Kombination aus Fragenverständnis, Bedeutungssuche und
beleggebundener Antwort muss gesondert gemessen werden. Vorhandene semantische
Funktionen wurden hier weder eingeschaltet noch mit einem Modell qualifiziert.
Auch bei Fragen ohne richtige Antwort können reale Quellen durch Wortteile
als Kandidaten erscheinen; Kandidaten sind niemals schon Antworten.

## Prüfstand

- 115 Such-, Index-, Wortformen-, Wortteile- und Auszugstests bestanden.
- 117 Routing-, Ablauf-, Personen-, Zusage- und Bereichstests bestanden vor
  dem abschließenden Reviewnachtrag.
- 80 Routing-/Suchrauschtests einschließlich Reviewgegenfällen bestanden.
- 57 Datums-, Kalenderaktions-, Kalenderfenster- und Nachbereitungstests
  bestanden, einschließlich des zuvor roten zentralen Parservertrags.
- Vollständiger abschließender Backendlauf und Mac-Installation werden erst
  nach tatsächlichem Abschluss nachgetragen; hier nicht vorweggenommen.

Keine GitHub-CI-Wiederholung. Keine neue Cloudfreigabe, kein weiterer bezahlter
Auftrag und kein freigegebener Bulk-Import. Die ursprüngliche 100-Mail-Probe
bleibt historisch unverändert; diese begrenzte Abrufprüfung hebt ihre offenen
Qualitätsanforderungen nicht auf.
