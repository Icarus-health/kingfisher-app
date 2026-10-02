# Gedächtnis-Baseline: Prüfgrundlage, noch keine Modellqualifikation

13. September 2026. Erstes Teilpaket aus M0. Kein Produktionscode verändert,
kein echter Modellaufruf, kein Download und keine privaten Daten verwendet.

## Umgesetzt

- `scripts/memory_probe_support.py`: vorbereitete synthetische Entwicklungsfälle
  validieren; unbekannte/duplizierte Identitäten und Quellenreferenzen, fremde Felder,
  falsche Uhren und ungültige Zitate ablehnen. Quellen bleiben Inline-Daten und werden
  nie als Pfade oder Code ausgeführt. Holdout ist im Entwicklungsformat nicht erlaubt.
- Quellenabruf mit getrennten Zählern für gefunden, fehlend, unerlaubt und zusätzlich.
  Ohne erwartete Quellen ist Recall unbekannt (`None`), nicht automatisch 100 %.
- `RecordingProvider` zeichnet vor der Delegation tiefe Kopien der tatsächlichen
  Provider-Eingaben und danach die Antwort sowie monotone Laufzeit auf. Keine
  Werkzeugausführung. Lokale/Cloud-Kennzeichnung bleibt die des delegierten Providers.
  Fehlermeldungstexte werden nicht ins Trace übernommen; Fehler werden erneut ausgelöst.
- Leere Antwort, Werkzeuganforderung und noch fachlich zu prüfende Antwort bleiben
  verschiedene technische Zustände. `semantic_verdict` bleibt unbeurteilt. Der
  bestehende Reply-Vertrag liefert keine Token-/Finish-Reason-Metadaten; der Trace
  benennt diese Lücke statt Abschneiden oder Tokenzahl zu erraten.
- GitHub-CI führt die neuen Offline-Tests unter Python 3.10 und 3.12 aus.

## Gegenprobe am tatsächlichen Agenten

Zwei getrennte Registry-Identitäten heißen Alex Winter; jede hat eine eigene
synthetische E-Mail-Quelle und eine ausdrücklich vorbereitete bestätigte Aussage.
`Agent.send()` erhält die Frage nach Alex Winters Adresse. Im ersten Aufruf sind
beide Aussagen in den Antwortmetadaten; im tatsächlich aufgezeichneten Providerinput
stehen die beiden vollständigen Testtexte und ihre Quellenreferenzen.

Anschließend wird Quelle 1 ausgeschlossen. Die zweite Runde desselben Agenten liefert
Quelle 2 weiter; Quelle 1 fehlt sowohl in der Auswahl als auch im Providerinput.
Der Fakeprovider liefert nur „Unbewertete Testantwort.“ und besitzt keine Werkzeuge.
Das prüft Recorder/Agent/SQLite-Zusammenspiel, nicht die Fähigkeit eines LLM zur
Identitätsklärung und nicht den Import-/Interpretationspfad.

Bei der ersten Probe erwartete der Test interne Claim-IDs auch im Prompt. Der
Codeabgleich zeigte: diese IDs stehen in den lokalen Antwortmetadaten, während der
Wissensprompt Quellenreferenzen enthält. Die Prüfung gleicht deshalb beide Ebenen
getrennt ab; keine Produktionsänderung, um eine falsche Testannahme zu erfüllen.
Ein allgemeiner automatischer Herkunftsbeweis für beliebigen Prompttext ist dies nicht.

## Verifikation

Anfangs erwarteter Importfehler wegen fehlendem Modul; danach 16 Tests bestanden.
Drei zusätzliche rote Tests für technische Ergebniszustände wurden implementiert.
Abschließend **75 Tests bestanden**, zwei bekannte Starlette-/anyio-Warnungen:

```sh
PYTHONPATH=sidecar .venv/bin/python -m pytest   scripts/test_memory_probe_support.py scripts/test_memory_probe_agent.py   scripts/test_evaluate_cos_models.py sidecar/tests/test_context.py   sidecar/tests/test_calendar_answers.py -q
```

Darunter 25 neue Offline-/Integrationsfälle. Kein erneuter vollständiger lokaler
Produktlauf für diese isolierten Prüfhilfen; die vorhandene Gesamtsuite läuft in CI.

## Nächster Schritt

Die vollständigen 18 Entwicklungsfälle, allgemeine Fixturefabrik, Neustartdiagnose,
Referenzkontextvergleich und begrenzter Live-Runner aus dem
[Implementierungsplan](../../superpowers/plans/2026-09-13-memory-quality-baseline.md)
bleiben offen. Auch 300 Quellen/90 fachliche Fälle/40 adversarielle Abläufe sowie
P95-Ziele und ein vollständiges lernendes Nutzerprofil sind nicht abgenommen.
Der deaktivierte Kalender-Retrieval-Versuch bleibt deaktiviert.

Der Recorder ist für synthetische Daten gedacht. Er enthält absichtlich volle
Eingaben und Antworten und ist kein Redaktionsfilter für private Modellaufrufe.

## Ergänzung: persistierte Abhängigkeiten

Eine zusätzliche Gegenprobe schließt und öffnet die SQLite-Stores erneut: Eine
Kette aus drei belegten Aussagen bleibt zunächst abrufbar; nach Entzug ihres
ursprünglichen Belegs bleibt die abhängige Aussage auch bei erneuter Wiederöffnung
vom tatsächlichen Providerinput ausgeschlossen. Die ursprüngliche Quelle muss
nicht zur Suchfrage passen. Details, Grenzen und die vorhandenen Strukturebenen:
[Gedächtnisstruktur](../../architecture/memory-structure-map-2026-09-13.md).
89 fokussierte Tests bestanden. Dies ersetzt weder den allgemeinen Fixturebuilder
noch eine echte Docker-/Backup-Wiederherstellungsprüfung oder Modellqualifikation.

## Fortsetzung 14. September: gemeinsamer Diagnoseweg

Der Entwicklungsbestand enthält jetzt 18 Fälle in sechs Szenariofamilien; Varianten
sind keine unabhängigen Szenarien. `development-cases-v1.json` trennt Originalquellen,
explizite Identitäten, vorbereitete Aussagen, Ersetzungen, Abhängigkeiten und
Quellenentzug. Der Builder benutzt die tatsächlichen KnowledgeService-/SQLite-Wege.
Er prüft keine automatische Extraktion. Gleiche physische Quellen für mehrere
Fallkennungen werden als nicht unterstützter Fixturezustand abgelehnt, nicht verdeckt
zusammengezählt.

`scripts/probe_memory_pipeline.py` führt jeweils einen Fall mit 1–3 Wiederholungen
entweder durch `Agent.send` oder mit kontrolliertem Referenzkontext aus. Abrufmengen,
tatsächliche Provider-Nutzlast, technische Fehler und fachliche Bewertung sind
getrennt. Fehlende/unerwartete Quellen sind Diagnosebefunde, keine automatische
Bewertung der Modellantwort. Bei direkten Kalenderantworten werden null Modellaufrufe
und der Callback als Auswahlgrundlage ausgewiesen. Der Referenzweg ist kein Nachweis
für den Abruf oder die Rechteprüfung der Anwendung.

Die feste Geschäftsuhr und eine ausdrücklich protokollierte Uhr-Ergänzung im
Systemprompt gelten nur im seriellen Diagnoseprozess und werden danach zurückgesetzt.
Der User-Fragetext bleibt unverändert. Die normale App wird nicht umkonfiguriert.
Die vorhandene OpenAI-kompatible Adapterlogik wird verwendet, ihr HTTP-Client jedoch
für diesen isolierten Prozess auf Loopback, endliche Wartezeiten, keine Umgebungsproxys
und keine Redirects begrenzt. Das ist ein offengelegter Unterschied zum Alltagsbetrieb.

Ergebnisdateien werden exklusiv mit privaten Dateirechten angelegt; jeder Versuch
bleibt einschließlich Fehler oder Abbruch sichtbar. Serverversion, installierter
Gewichts-Digest, Hash der Modellkonfiguration, Commit und Geschäftszeitpunkt werden
protokolliert. Rohe Modellkonfigurationen werden nicht exportiert. Effektive
Laufzeitparameter und Warm-/Kaltzustand bleiben unbekannt, wenn der Adapter sie nicht
liefert. Nicht-Provider-Zeit umfasst weitere Arbeit im Runner und ist keine isolierte
Messung der Suchzeit.

Eine vollständige M0-Auswertung braucht zusätzlich die echten Antworten und ihre
fachliche Prüfung. Ein freigegebener Diagnoserunner ist keine Gedächtnisfreigabe;
M1–M5 und der größere 300/90/40-Prüfbestand bleiben eigenständige Nachweise.

Abschluss der Offline-Implementierung: **165 fokussierte Tests bestanden**, zwei
bekannte Dependency-Warnungen (14. September, Python 3.12). Das unabhängige Review
fand und korrigierte optionale Textvalidierung, einen nicht anlegbaren Testzustand,
eine fehlende Gegenrichtung beim Nutzlastabgleich und unvollständige Servermetadaten.
Der Nutzlastabgleich erfasst nun auch bekannte Quellinhalte ohne passende Auswahl-
metadaten; unerklärte Wissenszeilen ergeben einen Integritätsfehler. Er ist ein
synthetisches Diagnoseinstrument, keine allgemeine Erkennung beliebiger Paraphrasen.
