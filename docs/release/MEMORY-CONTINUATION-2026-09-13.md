# Gedächtnis: Fortsetzung am 13. September 2026

Der gesamte Gedächtnisvertrag bleibt offen. Dieses Folgepaket beseitigt die bisherige harte Grenze im historischen Abruf und ergänzt den Vergleich lokaler Modelle.

## Historischer Abruf

`/memory/as-known` und `/memory/timeline` liefern `next_cursor`, `scanned`, `budget_truncated` und seitenbezogene Lücken. Die Reihenfolge ist auch bei gleichen Zeitstempeln eindeutig. Seiten ohne zugängliche Ergebnisse können fortgesetzt werden; ein Arbeitsbudget ist kein Nachweis, dass keine weiteren Einträge existieren.

Cursor sind Abfragen zugeordnet und auf zulässige Werte begrenzt. Vor jeder Seite werden Quellenrechte erneut geprüft. Numerische Zeilengrenzen sind mit der Identität der Grenzzeile verbunden: Wird diese gelöscht oder ersetzt, muss die Navigation neu beginnen. Das ist ausdrücklich keine Transaktionsmomentaufnahme über alle Stores. Timeline-Fortsetzungen übernehmen den zurückgegebenen Zeitraum; die Oberfläche erledigt dies automatisch.

Im Verlauf führt „Ältere Einträge anzeigen“ zur nächsten Seite mit höchstens 100 Einträgen. Die Ansicht sammelt nicht unbegrenzt Inhalte im Browser. Monatswechsel und Aktualisierung verwerfen verspätete Ergebnisse vorheriger Abrufe.

Das unabhängige Review fand drei behobene Fehler: wechselnde Standard-Zeitgrenzen, unzulässige Cursorzahlen mit Serverfehler und Wiederverwendung einer SQLite-Zeilennummer nach Löschung. Regressionstests sind ergänzt.

## Lokale Modelle

Live geprüft: Apple M2 Max, 32 GB RAM. Gemma3:12b ist bereits vorhanden und bestand mit unverändertem Prompt `requests-v3` 9/10 Entwicklungsfälle. Nicht erkannt wurde die ausdrückliche Zusage, einen bestätigten Termin mitzuteilen. Einzelne Titel verlieren Details wie Entwurfsnummern. Die Zitatprüfung ist daher keine vollständige Bedeutungsabnahme. Rohresultat: `model-probes/2026-09-13-gemma3-12b.jsonl`.

Vergleich aus vorigem Lauf: qwen3.5:4b und qwen2.5:14b jeweils 8/10. Kleine synthetische Entwicklungsfälle, kein Holdout, kein Präzisionsnachweis für reale Postfächer, keine automatische Modellumstellung.

Qwen3.5:9b wird als zusätzlicher Testkandidat geladen (offizielle Ollama-Bibliothek: ca. 6,6 GB). Der Download war während dieser Umsetzung sehr langsam; noch kein Ergebnis mit diesem Modell. Gemma4:12b (ca. 7,6 GB) ist eine weitere mögliche Vergleichsoption, wurde aber nicht installiert. Die deutlich größeren 18–23 GB Qwen3.6-Varianten lassen weniger Reserve für macOS, Docker und Kontextspeicher. Diese Auswahl ist eine Hardware-Abwägung, kein gemessener Qualitätsvorsprung.

Quellen, am 12. September eingesehen:
- https://ollama.com/library/qwen3.5:9b
- https://ollama.com/library/gemma4
- https://ollama.com/library/qwen3.6

Nachprüfung: Gemma3:12b bestand auch im wiederholten Lauf 9/10 Fälle; der Runner protokolliert nun Zeitpunkt und Gewichts-Digest und prüft vor/nach dem Lauf, ob die Gewichte unverändert sind. Gemessene Version: `f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a`.

Fokussierte lokale Nachprüfung: 38 Historien-, API- und Claim-Tests bestanden. Frontend-Build erfolgreich. Isolierter Browserlauf: 107 synthetische Quellen, erste Seite 100, zweite Seite 7 Einträge; Datum/Zeitraum und Quellenansicht erhalten. Keine produktiven Nutzerdaten verwendet.

Gesamtsuite: **1.265 Tests bestanden**, zwei bestehende Deprecation-Warnungen, 181,70 Sekunden. Nachprüfung des unabhängigen Reviews: keine offenen konkreten Befunde im Backend-Paginierungsdiff; 24 Historientests erneut bestanden.

## Aufgabenhistorie als weiterer Baustein

TaskStore-Migration v2 ergänzt `task_events` in der bestehenden Aufgaben-Datenbank. Zustandsänderung und Journal werden gemeinsam unter einer SQLite-Schreibtransaktion übernommen. Ein reproduzierter konkurrierender Schreibfehler zwischen zwei Verbindungen ist behoben. Wiederholungen ohne Änderung und erneut übernommene identische Vorschläge erzeugen keine doppelten Ereignisse.

Bestehende Aufgaben erhalten nur einen ausdrücklich benannten `preexisting_snapshot` zum tatsächlichen Migrationszeitpunkt. Frühere Entscheidungen und handelnde Personen werden nicht erfunden. Die Historie kopiert weder Titel, Notizen noch Quellzitate; Zustand, Projektbezug und Warteperson bleiben enthalten und sind bei der späteren vollständigen Löschung mit zu berücksichtigen.

Der authentifizierte Endpoint `/api/v1/tasks/{id}/history` und die eingeklappte Anzeige „Verlauf öffnen“ machen dies in der Aufgabenliste zugänglich. Anzeige höchstens 100 Ereignisse, begrenzter Abruf. Aufzeichnen, Warten, Zurückholen und im Browser Erledigen wurden an synthetischen Aufgaben überprüft. Das ersetzt noch nicht die geplante Matter-/Obligation-Erkennung für Bitten, berichtete Zusagen, Bedingungen und Abschlüsse.

Review: Der Schutz gegen Änderungen am Journal wurde nach einem reproduzierten `INSERT OR REPLACE`-Gegenfall um einen Einfüge-Guard ergänzt. Aufbewahrung/Löschung bleiben ein gesonderter, noch nicht freigegebener Gesamtpfad.

Prüfungen: 1.276 Backendtests bestanden, zwei bestehende Dependency-Warnungen (178,35 Sekunden); danach elf fokussierte Journal-/API-Tests erneut bestanden. Frontend-Build erfolgreich. Kein Laufzeitwechsel mit produktiven Daten.

## Modellstrategie und Verbindungspause

Auf Nutzerwunsch wegen schlechter ICE-Verbindung keine weiteren Modelldownloads starten. Bei der aktuellen Prüfung lief kein Ollama-Pull-Prozess mehr; Qwen3.5:9b ist weiterhin nicht installiert. Keine automatische Fortsetzung vorgesehen.

Spezialisierung wird vorerst als Evaluationsvorhaben geführt: erst Aufgabenklassen und getrennte Prüf-/Trainingsbeispiele, danach Vergleich bestehender Modelle und gegebenenfalls ein LoRA-Versuch. Persönliche Fakten verbleiben in der korrigierbaren Datenablage; trainiert werden soll das Einordnen, nicht das Einbrennen veränderlicher Fakten. Kein Training oder Upload privater Daten gestartet.

## Belegketten beim Gesprächsabruf

Der lokale Gesprächsabruf prüft jetzt auch die Originalbelege aller Abhängigkeiten einer passenden Wissensaussage. Ein gültiger direkter Beleg genügt nicht, wenn eine zugrunde liegende Quelle ausgeschlossen, verschwunden, verändert oder durch eine generierte Zusammenfassung ersetzt ist. Dies wurde am tatsächlichen `Agent.send`-Pfad mit einem Provider geprüft, der den empfangenen Kontext aufzeichnet. Der Test mit einer ausgeschlossenen indirekten Quelle lieferte zuvor fälschlich die abgeleitete Aussage aus.

Archivierung ist dagegen kein Widerruf: `archive_before` und Verdichtung legen erhaltene Originale ins Archiv. Solche Belege bleiben im aktuellen Abruf verwendbar; der historische Wissensabruf wurde entsprechend korrigiert. Ausgeschlossene Quellen bleiben dort weiterhin gesperrt.

Die Kandidatenauswahl liest maximal 5.000 aktive Datensätze, ohne zuvor rekursiv den gesamten Bestand auszuwerten. Pro passender Aussage werden höchstens 128 verschiedene Aussagen in der Belegkette geprüft; Datenbankabrufe für Abhängigkeiten beginnen erst nach der Budgetprüfung. Zyklen und Budgetüberschreitungen geben die Aussage nicht frei. Ein persistierter Pfad jenseits der Python-Rekursionsgrenze stürzte zuvor ab und ist jetzt abgesichert. Das ist ein begrenzter Abruf, keine Garantie vollständiger semantischer Suche im Gesamtbestand.

Unabhängiges Review deckte zwei zusätzliche Budgetlücken auf (rekursive Vorauswahl und vorzeitiges Laden aller Abhängigkeiten); beide wurden mit Gegenbeispielen reproduziert und behoben.

Nächster zusammenhängender Schritt: situativer Kalenderkontext mit eindeutiger Termin-ID, Zeitfenster, Abruf-/Synchronisationszeit und partiellen Quellenfehlern. Zuvor bzw. gemeinsam damit müssen lokale Kontextdaten samt abgeleiteten Gesprächsantworten gegenüber einem späteren Cloudwechsel abgegrenzt werden. Ein Titel-/Ortswort wie „Mainz“ darf eine Rückfrage begründen, aber keine Personen-/Projektbeziehung erzeugen. Diese Erweiterung wurde untersucht, noch nicht implementiert. Auch das Entfernen alter Gesprächsableitungen bei reinen Quellenänderungen ist damit noch nicht vollständig abgedeckt.

Abschlussprüfung dieses Schritts: **1.287 Backendtests bestanden**, zwei bestehende Dependency-Warnungen, 184,10 Sekunden. Unabhängige Nachprüfung: 40 Kontext-/Historientests bestanden und keine weiteren konkreten Befunde im geänderten Abrufweg. Kein Frontend geändert, kein produktiver Laufzeitwechsel, keine Modelldownloads gestartet.

## Gesprächsverlauf beim Wechsel von lokal zu Cloud

Jede neue Modellrunde kennzeichnet ihren Verlauf als `local_only` oder `external`, anhand des tatsächlich ausführenden Providers. Diese Kennzeichnung bleibt in den gespeicherten Antwortmetadaten erhalten und wird beim Laden sowie beim Wiederholen einer fehlgeschlagenen Antwort weitergereicht. Auch ein direkter Providerwechsel am Agent entfernt lokal entstandenen Verlauf vor dem nächsten externen Modellaufruf. Das ist eine Empfängergrenze, keine Klassifikation sämtlicher Inhalte als öffentlich.

Ein gespeicherter Verlauf mit lokalen oder ungekennzeichneten Antworten wird für externe Anfragen vollständig ausgelassen, einschließlich möglicher späterer Ableitungen in Nutzerbeiträgen. Die Oberfläche erhält einen Hinweis; gespeicherte Nachrichten werden nicht gelöscht. Durchgängig gekennzeichnete Cloudverläufe bleiben nutzbar. Gemischte Gespräche verlieren dadurch vorerst bei jeder Cloudanfrage den älteren Gesprächskontext; ein neues Cloudgespräch ist die einfache Alternative. Die aktuelle ausdrücklich gestellte Frage (beim Wiederholen die ursprüngliche Frage) wird weiterhin dem gewählten Modell übergeben. Dies ersetzt keine vollständige Zweck-/Quellenfreigabe für direkte Werkzeugergebnisse oder neu eingegebenen Text.

Regression zunächst nachgewiesen: fünf gezielte Tests scheiterten am unerwünschten Verlaufsexport bzw. fehlenden Label. Anschließend 24 Kontexttests einschließlich echter Agent-Provider-Nutzlasten und persistierter API-Wege erfolgreich. Kein produktiver Laufzeitwechsel und keine Downloads. Situativer Kalenderkontext bleibt der nächste Funktionsschritt.

Gesamtprüfung: **1.296 Backendtests bestanden**, zwei bestehende Dependency-Warnungen, 194,59 Sekunden. `git diff --check` ohne Befund. Keine Frontendänderung.

## Situativer Kalenderkontext im lokalen Gespräch

Die tatsächliche lokale Modellrunde erhält jetzt automatisch einen begrenzten Ausschnitt aus dem bestehenden EventKit-Schnappschuss: laufende und bevorstehende Termine innerhalb von sieben Tagen, höchstens zwölf Einträge und ein gemeinsames Zeichenbudget. Kalenderfreigabe und Auswahl bleiben maßgeblich. Ein einzelner kohärenter Lesezugriff liefert Termin-/Quellenkennungen, Titel, Zeit mit UTC-Offset, Ort, Ganztagsmerkmal, Synchronisations-/Beobachtungszeit und Abdeckungsstatus. Teilnehmerdetails werden in diesem Überblick nicht zusätzlich kopiert. Keine Netzwerkanfrage, kein zweiter Kalenderbestand und keine neue dauerhafte Personen-/Projektbeziehung.

Snapshots ohne Freigabe, mit Quellenfehler, ohne Synchronisation, aus der Zukunft oder älter als fünf Minuten liefern keine Termine an den Agent. Rohe Fehlertexte werden nicht in den Kontext übernommen. Fehlende Abdeckung bleibt `unknown`; eine unvollständige Abdeckung bleibt `partial`. Ungültige Datumswerte, Fremdkalender und außerhalb des Zeitfensters liegende Termine werden nicht übernommen. Begrenzung und ungültige Einträge bleiben sichtbar. Der Ausschnitt umfasst nur ausgewählte Mac-Kalender; weitere CalDAV-/iCalendar-Quellen werden dadurch nicht automatisch abgerufen und es wird keine Vollständigkeit über sämtliche Kalender behauptet.

Kalenderinhalte stehen im Datenblock, niemals im Systemprompt. Die Systemregeln erlauben eine kurze Rückfrage anhand eines passenden Termintitels, untersagen aber erfundene Personen-/Projektbeziehungen. Der Ausschnitt und seine semantische Kennung werden in den Antwortmetadaten gespeichert. Eine inhaltliche Änderung oder veränderte Verfügbarkeit stellt ältere Kalenderableitungen im Modellverlauf zurück. Ein gespeicherter Kontext-Neubeginn verhindert, dass danach jede Folgefrage erneut ihren Verlauf verliert. Reine Synchronisationszeitänderungen setzen den Verlauf nicht zurück. Die gespeicherte Gesprächsanzeige bleibt unverändert erhalten.

Die Providergrenze wird vor dem Kalenderabruf geprüft, auch bei einer abgespaltenen Agentenrolle. Cloudmodelle erhalten diesen automatischen Kalenderzusatz nicht; der zuvor implementierte Verlaufsschutz gilt weiterhin. Dieses Paket prüft den Snapshot zum Beginn der Modellrunde, nicht nochmals während der laufenden Generierung. Antworten beziehen sich auf den gespeicherten Beobachtungszeitpunkt.

Gezielt geprüft: echte Agent-Nutzlast, Rollenweitergabe, Cloud-Ausschluss, Herkunftsmarkierung, Änderung/Staleness samt Verlauf, fortgesetzter Dialog nach einem Kontextwechsel sowie der tatsächliche API-Weg mit synthetischem Mac-Kalender und anschließendem Trennen. Die Rückfrageformulierung wurde als Modellanweisung eingebaut; ihre Zuverlässigkeit mit einem realen lokalen Modell ist noch gesondert zu evaluieren. Keine produktiven Daten geändert, keine Downloads und kein Laufzeitwechsel.

Abschlussprüfung: **1.309 Backendtests bestanden**, zwei bestehende Dependency-Warnungen, 198,06 Sekunden. Unabhängiges Review fand die fehlende UTC-Z-Normalisierung für das weiterhin unterstützte Python 3.10; korrigiert entsprechend dem bestehenden MacCalendar-Parser. Anschließend **38 Kontext-/Kalendertests am finalen Stand bestanden**, einschließlich zusätzlichem Worker-UTC-Z-Fall. Ausgeführt unter Python 3.12; kein eigener Python-3.10-Gesamtlauf. Keine weiteren konkreten Reviewbefunde. `git diff --check` ohne Befund.

## Echte lokale Modellprüfung: Alltagsfreigabe bleibt gesperrt

Der Kalenderkontext wurde mit synthetischen Daten am tatsächlichen Agent-/Ollama-Pfad geprüft. Ergebnis und Rohtexte: `docs/evaluations/calendar-context/README.md`. Qwen3.5:4b lieferte im ersten Fall nach 83,05 Sekunden keinen sichtbaren Text. Qwen2.5:14b antwortete in 2,76–15,26 Sekunden, behauptete aber bei veraltetem Stand fälschlich Terminabwesenheit und befolgte eine Anweisung im Termintitel. Das sind konkrete Gegenbeispiele gegen die hinreichende Wirksamkeit der bisherigen Promptregeln, keine bloß hypothetischen Risiken. Kein produktiver Laufzeitwechsel und keine Alltagsfreigabe für diese Erweiterung.

Eine leere OpenAI-kompatible Modellantwort ohne Toolaufruf wird jetzt als Providerfehler erkannt und führt zum bestehenden Fehlerhinweis im Agent. Vier Regressionen scheiterten vorher; sechs gezielte Providerfälle sowie insgesamt 51 Provider-/Routing-/Kontexttests bestanden nach der Korrektur. Dies behebt nicht die semantischen Fehler oder die Antwortlatenz. Der nächste Arbeitsschritt muss die deterministische Grenze für Kalenderstatus/Zeitzonen sowie die Modellqualifikation behandeln, bevor weitere Kalenderautomatik aktiviert wird.

Gesamtprüfung am finalen Korrekturstand: **1.316 Backendtests bestanden**, zwei bestehende Dependency-Warnungen, 191,26 Sekunden. Die grüne technische Testsuite hebt die dokumentierten semantischen Modellfehler ausdrücklich nicht auf.

## Technische Ausgabegrenze für einfache Kalenderfragen

`calendar_answers.py` beantwortet einen kleinen expliziten Satz von Termin-/Verfügbarkeitsfragen direkt und kann bei „Was ist mit …?“ anhand vollständiger Titelwörter eine Rückfrage mit höchstens drei Terminen stellen. Diese Übereinstimmung erzeugt keine Personen-/Projektbeziehung. Unverfügbare/veraltete Daten bestätigen keine Termine oder freie Zeit. Auch eine leere, abgedeckte Auswahl bestätigt keine global freie Woche. Einträge werden mit Quelle und UTC-Offset als maskierter Text angezeigt. Ganztagsbeginn bleibt ausdrücklich ein Quellenzeitpunkt; die Nutzerzeitzone wird nicht erraten.

Der fehlgeschlagene automatische Versand freier Kalendertexte an das Modell ist zurückgenommen. Für direkte Antworten findet keine Inferenz statt. Antwortmetadaten behalten den nachvollziehbaren Kalenderstand; angezeigte Kalendertexte sowie entsprechend markierte ältere Kalenderableitungen werden beim Wiederladen nicht in Modellhistory übernommen. Neue allgemeine Modellantworten tragen `calendar_model_context=false`. Das ändert weder gespeicherte Nachrichten noch die bestehende lokale Zugriffsschranke. Explizite Kalenderwerkzeuge und beliebige natürlichsprachliche Fragen sind noch kein vollständig qualifizierter Ausführungspfad.

Die Gegenbeispiele wurden wiederholt: vier direkte Datenantworten, jeweils 0 Modellaufrufe und unter 0,01 Sekunden. Das ist keine nachträgliche Qualifikation von Qwen. Neue gezielte Tests decken Status/Abdeckung, Ortsrückfragen, zusammengesetzte Aufträge, Textmaskierung, Quellenzeitzone/Ganztagsbeginn, Provider-Bypass und History-Reload einschließlich alter Kalenderantworten ab. Unabhängige Codeprüfung fand keine weiteren konkreten Befunde; kein Browser-Renderingtest und kein produktiver Laufzeitwechsel.

Abschlussprüfung: **1.324 Backendtests bestanden**, zwei bestehende Dependency-Warnungen, 181,49 Sekunden; davor 46 fokussierte Kalender-/Kontexttests bestanden. `git diff --check` ohne Befund. Die bestätigte Grenze bleibt der eng definierte direkte Datenpfad; keine allgemeine Modell- oder Kalenderautomatikfreigabe.
