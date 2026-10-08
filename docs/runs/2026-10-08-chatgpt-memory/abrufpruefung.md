# Abrufprüfung ohne weitere Cloudanfragen

## Umfang

Eine getrennte lokale Kopie des gesicherten Bestands mit 340 Originalquellen
wurde geprüft. Diese Offlineprüfung erfolgte ohne großen Import, Neueinordnung,
Modellinferenz oder Änderung des laufenden Bestands. Die anschließenden
Bedienproben sind unten separat dokumentiert. Private Fragen,
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

Die anschließende positive Bedienprobe fand einen weiteren echten Fehler:
Eine ausdrücklich wörtliche Quellenfrage wurde bei bereits eingeordneten
Quellen zuerst an die Modellauswahl gegeben. War das lokale Modell aus,
scheiterte die Anzeige trotz vorhandener Originalstelle. Ein neuer HTTP-Test
reproduzierte `working_selection_failed`. Nun hat diese eng begrenzte Anzeige
Vorrang vor Fragenmodell, Bedeutungssuche und Auswahlmodell. Der Test verlangt
null Aufrufe von `complete` und `complete_json` und prüft anschließend den
Quellenentzug im alten Gespräch. Lokaler Zugriffsschutz, Quellenfingerabdruck,
Prüfung revidierter Ableitungen und die Abgrenzung zu Anschlussfragen bleiben
erhalten. Zehn Quellenantwort-HTTP-Tests und 183 betroffene Abruf-/Verlaufs-/
Routingtests bestehen; das unabhängige Review fand keine weiteren konkreten
Blocker in diesem Nachtrag.

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
- 17 Diagnoseskripttests bestanden. Die bestehende 22-Fragen-Probe für den
  separaten vorbereiteten Claim-Abruf bleibt bei 13/22 exakten Ergebnissen;
  dafür wurde kein Embedder oder Modell initialisiert.
- Der breite Lauf vor dem letzten Quellenanzeige-Nachtrag bestand mit 5.174
  Tests, einem übersprungenen Test und zwei vorhandenen Warnungen. Der
  abschließende Gesamtlauf von `83da66f` bestand mit **5.178 Tests, einem
  übersprungenen Test und zwei vorhandenen Warnungen** in 13:51 Minuten.
  Ein zunächst ohne lokale Socketfreigabe gestarteter Zusatzlauf
  wurde nach reproduzierten Sandboxfehlern der künstlichen DNS-/HTTP-Server
  abgebrochen und mit Freigabe neu gestartet; keine Produktionskorrektur an
  diesen Tests.

## Mac-Installation und tatsächliche Bedienung

Installiert ist **1.0.6-local.83da66f**, Code
`83da66f82b840d7c875d9e595b93cbfffb7e8151`. Der Container wurde aus einem
sauberen Git-Archiv ohne private Daten gebaut; die bestehende native Hülle
wurde mit aktualisierter Fassung erneut lokal signiert. Kein neuer universeller
Mac-Build wird behauptet. Datenvolume und ausschließlich lokale Portbindung
bleiben erhalten.

Vor jedem Austausch wurden App, private Einstellungen und das gesamte kalte
Datenvolume außerhalb des Repositorys gesichert. Der abschließende Rückweg
liegt unter `Kingfisher-Rueckweg/2026-10-08-83da66f-installed` im Codex-
Dokumentenordner. Die separate Bestandskopie behält Schema 19, alle Originale
und alle geprüften Ableitungstabellen unverändert. Die 342 unmittelbar vor
diesem Austausch vorhandenen Episoden behalten ihre Digests; darunter sind
die 340 ursprünglichen Quellen und zwei vorherige Bedienprüfungsfragen.
17 SQLite-Dateien bestehen `quick_check`. ChatGPT-Anmeldung und Intake-
Einstellungen bleiben erhalten. Die lokale Modellauswertung bleibt aus;
der Mailabruf selbst ist nicht pausiert.

Im tatsächlichen nativen App-Fenster wurden nach Installation geprüft:

- Eine ausdrücklich wörtliche Suche zeigt eine vorhandene historische
  Absage als „Quelle berichtet · nicht bestätigt“, mit ihrem ursprünglichen
  Quelldatum aus 2021 und getrenntem Erfassungsdatum aus 2026. Antwortvertrag:
  `source_report`, ein Originalverweis, kein Aufruf des Antwortmodells.
- Die unbelegte persönliche Faktenfrage wird als nicht beantwortbar angezeigt.
  Antwortvertrag: `unknown`, kein Aufruf des Antwortmodells.
- Beide Prüfungsfragen sind reine Abrufe und werden nicht als neue
  persönliche Tatsachen gelernt. Das Fenster steht anschließend wieder in
  **Gedächtnis → Bereiche**.

Diese zwei Bedienproben belegen die geprüften Fälle, keine generelle richtige
Interpretation aller Mails. Es wurden weder Ollama-Modelle gestartet noch
weitere Cloudanfragen oder Neu-Einordnungen ausgeführt.

## Nächster Qualitätsnachweis

Der nächste Schritt ist ein begrenzter Vergleich des bereits vorhandenen
vollständigen Abrufwegs – Fragenverständnis, kombinierte Suche und beleggebundene
Auswahl – auf vorab festgelegten, nicht zum Nachbessern benutzten Fragen. Dazu
gehören Umschreibungen, gleichnamige Personen, historische und abgesagte Termine,
Zitate sowie Fragen ohne belegbare Antwort. Erwartet werden Originalquelle,
entscheidender Wortlaut, Person, Zeitbezug und Aussagevorbehalt; bloße Wort-
oder Namensübereinstimmung zählt nicht als richtige Antwort.

Quellenabruf und fertige Antwort werden getrennt bewertet, ebenso falsche
Antworten und ehrliche Nichtantworten. Laufzeit, Modellaufrufe und Speicherbedarf
gehören zur Prüfung. Weitere Synonymlisten oder ein Modellwechsel gelten erst
nach diesem Vergleich als Verbesserung. Ein kostenpflichtiger oder privater
Cloudvergleich wird durch diesen Plan nicht aktiviert. Danach folgt die
vollständige 100-Mail-Qualitätsprobe; der große Import bleibt bis zur technischen
und inhaltlichen Freigabe geschlossen. Bestehende Daten müssen dafür nicht
gelöscht oder neu aufgebaut werden.

Keine GitHub-CI-Wiederholung. Keine neue Cloudfreigabe, kein weiterer bezahlter
Auftrag und kein freigegebener Bulk-Import. Die ursprüngliche 100-Mail-Probe
bleibt historisch unverändert; diese begrenzte Abrufprüfung hebt ihre offenen
Qualitätsanforderungen nicht auf.
