# Persönlicher Kernablauf auf dem Mac

12. Oktober 2026. Erster Prüfdurchgang: `1.0.6-preview.b7cd321`; erneuter Prüfdurchgang nach Update auf `1.0.6-preview.6940953` weiter unten. Der Nutzer hat den entsperrten Mac, das vorhandene Qwen9B und die Prüfung von Mail, Gedächtnis, Aufgaben und Kalender ausdrücklich freigegeben. Dies ist ein begrenzter tatsächlicher Bediennachweis, keine vollständige Alltags- oder Gedächtnisabnahme.

## Tatsächlich geprüft

| Bereich | Beobachtung | Ergebnis |
|---|---|---|
| Native Sitzung | Alte Sitzung beendet, installierte App frisch geöffnet. Der bewusste native Knopf startet das vorhandene Ollama. | Neuer Fensterstart geprüft; kein Modelldownload. |
| Lokale Antwortwahl | `kingfisher-qwen3.5:9b-32k` über „Speichern und verbinden“ ausgewählt. Bereitschaftstest 6,5 Sekunden. Zusätzlich tatsächliche wirksame Rollen lesend geprüft: Frage und Antwort verwenden diese lokale Wahl; kein Ollama-Cloudweg. | Verbindung bestanden; keine Aussage über Antwortqualität. |
| Mail aufnehmen | Eine gewöhnliche vergangene Veranstaltungsmail geöffnet und ausdrücklich als Quelle gemerkt. Originaldatum und heutige Erfassung erscheinen getrennt. | Original als Rohmaterial erhalten, kein bestätigter Fakt daraus gemacht. |
| Aufgabe aus Mail | Eine ausdrücklich als Funktionstest bezeichnete Aufgabe ohne Fälligkeit gespeichert. Seitenwechsel, direkter Originalbeleg, Abschluss und Anzeige unter „Erledigt“ geprüft. | Eine Testaufgabe samt Quelle erhalten; keine erfundene Frist, kein Versand. |
| Gedächtnisfrage | Zwei lokale Fragen zur gerade gespeicherten Mail, eine ausführliche und eine kurze Kontrollfrage. Beide Antworten melden `selection_failed` und enthalten keinen Beleg. | **Nicht bestanden.** Je rund 37 Sekunden: Frage ca. 6, Suche 0,3–0,4, Auswahl ca. 30 Sekunden. |
| Kalender | Nach neuer Sitzung zunächst ausstehende Freigabe; Anfrage über Kingfisher geöffnet. macOS-Einstellungen zeigen bestehenden Vollzugriff. Danach frische Anzeige mit drei ausgewählten Kalendern. Die zwei heutigen Termine samt Beginn/Ende im tatsächlichen Mac-Kalender und in Kingfisher verglichen. | Heutiges Zeitfenster stimmt überein. Kein Nachweis sämtlicher Konten, Serien oder Zeiträume. |
| Pausierter Betrieb | Mailaufnahme und Hintergrundverarbeitung bleiben in der UI pausiert; globale Pause zusätzlich per Produkt-API geprüft. Abschließend meldet Ollamas `/api/ps` keine geladenen Modelle. | Großen Import nicht fortgesetzt. Keine Akku- oder Tagesmessung daraus ableiten. |

Die Diagnose der Antworten enthält jeweils 16 Einträge in `basis` und 64 Einträge in `candidate_signature`; Bedeutungssuchstatus `partial`. Diese Felder beweisen weder vollständige Suche noch die Eignung der Kandidaten. Der Auswahlfehler ist reproduziert, seine Ursache noch nicht abschließend belegt. Eine bloße Erhöhung von Zeitlimits oder vorsichtig klingende Nichtantwort wäre keine Abnahme des Abrufs.

Persönliche Mailtexte, Screenshots, Belegkennungen, Einwahldaten und Zugriffsschlüssel werden hier nicht veröffentlicht. Die Quelle, die abgeschlossene Testaufgabe und das lokale Testgespräch bleiben auf dem Mac erhalten. Keine Mail versendet, Kalendertermine verändert, Cloudverarbeitung gestartet oder Originale gelöscht. Kingfisher wurde in der geprüften Kalenderansicht hinterlassen.

## Gefundener Zeitzonenfehler und vorbereitete Korrektur

Die Heute-Terminkarte zeigte die richtige lokale Uhrzeit, ihr Briefing-Satz jedoch die zwei Stunden frühere UTC-Uhrzeit. Der Morning-Endpunkt löst die Nutzerzone korrekt auf; sein verschachtelter Dashboard-Aufruf verwendete für den Satz erneut die Containerzeit. Ein interner Datenhelfer gibt nun dieselbe aufgelöste Zeit an beide Ansichten weiter; die öffentliche Dashboard-Signatur bleibt unverändert.

Der unabhängige Review fand zusätzlich eine dadurch betroffene Aufgabenlücke um Mitternacht. Vollständig zeitzonenbehaftete Fälligkeiten werden jetzt vor dem Tagesvergleich in die Briefing-Zone umgerechnet. Reine Datumsangaben und zeitzonenlose Angaben behalten ihren geschriebenen Tag.

Neue tatsächliche Endpunktfälle waren vor der jeweiligen Korrektur rot: Sommer, Winter, Kalender-Tageswechsel sowie lokale Heute-/Morgen-/Gestern-Abgrenzung bei UTC-Fälligkeiten. Enger unabhängiger Abschlussreview ohne verbleibenden konkreten Befund; dieser Review führte keine eigenen Modell- oder Liveprüfungen aus.

Root-Nachprüfung:

```text
PYTHONPATH=sidecar /private/tmp/kingfisher-question-model-venv-20261011/bin/python -m pytest -q sidecar/tests/test_briefing_zeitzone.py sidecar/tests/test_urteil.py sidecar/tests/test_briefing.py sidecar/tests/test_briefing_task_candidates.py sidecar/tests/test_morning_source_dates.py
53 passed, 1 warning in 5.40s
```

Bestehende Starlette/httpx-Abkündigungswarnung; kein vollständiger Backend- oder UI-Neulauf. Finaler Laufzeit-/Testdiff vor Dokumentation SHA-256: `8628a69ccc9b26e3ac3c06f206d5b8690d74c00778720c902bdb278bb34abe16`.

**Stand vor dem nachfolgenden Update:** Die Zeitzonenkorrektur war zunächst nur Quellcode; installiert blieb `b7cd321`. Anschließend wurden Auswahlkorrektur und Zeitzonenkorrektur gemeinsam qualifiziert, gesichert installiert und erneut persönlich geprüft (siehe unten). Kein Main-Merge, öffentlicher Updater oder GitHub-CI-Neustart.

## Auswahlfehler: Ursache und begrenzte Korrektur

Die nachfolgende Diagnose trennt Transport und Quellenverfügbarkeit. Ein kleiner tatsächlicher JSON-Aufruf mit dem vorhandenen lokalen Qwen9B war nach 5,47 Sekunden erfolgreich. Der tatsächliche Auswahlprompt mit 16 Quellen, 34.683 Textzeichen und 11.770 Eingabetokens lief dagegen nach 30,09 Sekunden in einen `ReadTimeout`. Mit einer ausschließlich diagnostisch auf 60 Sekunden gesetzten Transportklasse lieferte derselbe Prompt nach 37,99 Sekunden gültiges JSON. Vorbereitung und Nachbereitung zusammen unter 0,1 Sekunden; keine geerbten Proxyvariablen. Diese Messung belegt den Transportfehler, noch keine passende Antwort.

Commit `6940953` berücksichtigt deshalb die Textmenge des Eingabeprompts: Oberhalb von 12.000 Zeichen nutzt der lokale JSON-Aufruf dieselbe vorhandene 60-Sekunden-Klasse wie größere Ausgaben. Das Ausgabetokenlimit von 256, sämtliche Kandidaten und das Schema bleiben unverändert. Die kürzere Frist des Frageverständnisses gilt weiterhin. Unabhängiger statischer Review ohne konkreten verbleibenden Blocker; kein eigener Modelltest durch den Reviewer.

Die gerade gemerkte Mail war außerdem noch `pending`: Ein gespeichertes Original ist bei pausierter Einordnung noch kein ausgewerteter Antwortbeleg. Auf temporären SQLite-Kopien wurde ausschließlich diese ausdrücklich gewählte Testquelle mit dem bestehenden Worker eingeordnet (`source_ids`, `limit=1`, eigener leerer Zwischenstand). Nach 10,35 Sekunden war sie `complete`. Beide ursprünglichen Fragen lieferten anschließend `reports` und wählten jeweils genau die gesuchte Quelle: 47,01 beziehungsweise 40,64 Sekunden. Dafür galt die diagnostische 60-Sekunden-Transportklasse. Keine Originaldaten oder Einstellungen durch diese Kopienprüfung verändert; dies ersetzt den erneuten Fenstertest nach Installation nicht.

Root-Nachprüfung der betroffenen Tests, einschließlich tatsächlichem localhost-Sockettest:

```text
PYTHONPATH=sidecar /private/tmp/kingfisher-question-model-venv-20261011/bin/python -m pytest -q sidecar/tests/test_json_transport_budget.py sidecar/tests/test_question_transport_deadline.py sidecar/tests/test_local_json_completion.py sidecar/tests/test_briefing_zeitzone.py sidecar/tests/test_briefing.py sidecar/tests/test_briefing_task_candidates.py sidecar/tests/test_morning_source_dates.py
50 passed, 1 warning in 4.80s
```

Diese Änderung behebt den beobachteten Auswahlabbruch. Sie beweist keine allgemeine Abrufvollständigkeit und macht den lokalen Abruf noch nicht schnell. Der große Import bleibt pausiert; nicht ausgewertete Quellen bleiben sichtbar von fertigen Belegen getrennt.

## Gemeinsam installiert und im App-Fenster erneut geprüft

Die lokale App und ihr Backend verwenden jetzt `1.0.6-preview.6940953`, Code-Commit `69409536162aa866a2610bcfbfad7255fd4f645e`. Offline-Overlay auf dem vorhandenen Paket; keine neuen Abhängigkeiten oder Modelle heruntergeladen. 18 synthetische Prüfeinträge des tatsächlichen Paketlaufs bestanden ohne Netzwerk oder persönliche Daten.

Die Oberfläche wurde nach Vergleich der unveränderten Eingaben wiederverwendet. Eine frische Swift-Kompilierung scheiterte am lokalen Command-Line-Tools/SDK-Konflikt. Da auch die Native-Eingaben unverändert sind, wurde das vorhandene ARM64-Executable nach Vergleich seines unsignierten Code-Payloads übernommen, das Bundle neu versioniert und signiert. Read-only-DMG-Abgleich aller sechs Dateien bestanden; ad hoc signiert, nicht notarisiert. Dies ist keine Behauptung einer erfolgreichen frischen Swift-Kompilierung.

Vor dem Austausch wurde der vollständige aktuelle Bestand gesichert: 168 Dateien, 11 Verzeichnisse, 333.421.495 Bytes. Wiederhergestellte Kopie stimmt byteweise einschließlich Eigentümer, Modi, Zeitstempel und erweiterten Attributen überein; 17 SQLite-Integritätsprüfungen bestanden. Geschützte Kopienöffnung und tatsächlicher Dienst erhalten alle 17 Schemas/Versionen, 47 Episoden-/Aufgaben-/Selbstmodelltabellen und sieben weitere Kerntabellen. Datenvolume und Anbieter-/Modellkonfiguration unverändert; nur Image-Selektor gewechselt. Tatsächlich installierte 272 Python- und 112 UI-Dateien sind paketgleich.

Der unabhängige Installerreview fand eine fehlende feste Zielimagebindung und einen falsch geklammerten Pfad-Leseaufruf. Beide vor Installation korrigiert; die tatsächliche Pfadexpression sowie neun SQLite-Erhaltungsgegenproben und Compose-Konfigurationsgegenproben bestanden. Der einzelne Quellenlauf brach bei einem falschen Prüf-Tabellennamen zunächst vor jeder Datenänderung ab; nach lesender Schemaprüfung auf `knowledge_claims` korrigiert und erneut unabhängig gelesen.

Nur die ausdrücklich gewählte Testmail wurde anschließend mit dem bestehenden Worker, frischem Zwischenstand und geprüften lokalen Qwen-Gewichten eingeordnet: `pending` → `complete` in 15,49 Sekunden. Originale, Quellen-Heads, bestätigte Aussagen und Aufgaben davor/danach unverändert. Großen Import nicht fortgesetzt.

| Tatsächliche Bedienprüfung auf dem neuen Paket | Ergebnis |
|---|---|
| Native App beendet und aktualisierte App frisch geöffnet | Erfolgreich. |
| Drei bestehende Mac-Kalender erneut synchronisiert | Bestehende Auswahl erhalten; Freigabe funktioniert, 490 Ereignisse im aktuellen Adapterfenster. Keine neuen Kalender oder Schreibrechte ausgewählt. |
| Beide ursprünglichen Gedächtnisfragen erneut über das normale Gesprächsfeld gestellt | Je `reports`, genau die gesuchte Originalquelle; Ticket-Hinweis im angezeigten Original vorhanden. Ausführliche Frage: Auswahl 59,11 s, insgesamt 65,76 s. Kurze Frage: Auswahl 44,24 s, insgesamt 50,71 s. |
| Originalbeleg geöffnet | Vergangene Mail mit Datum 10. Oktober; Quellenzeit und Erfassung am 12. Oktober bleiben getrennt. Zitatmodus, keine geprüfte Modellprosa oder allgemeine Abrufabnahme. |
| Bestehende Testaufgabe unter Erledigt geöffnet | Abschluss, fehlende Fälligkeit und direkter Originalzugriff erhalten; keine zusätzliche Aufgabe erzeugt. |
| Kalender und Heute-Karte | Beide heutigen Terminzeitspannen wie im vorher geprüften Mac-Original; Karte und Briefing-Satz nennen jetzt übereinstimmend 16:00 statt 16:00/14:00. Seitenübergreifende Ortszeituhr läuft weiter. |
| Verbundene Mailansicht | Aktuelle begrenzte Posteingangsliste wird geladen. Sie zeigt nur die neuesten 30 Mails; der Originalzugriff zur älteren Testmail wurde über den gespeicherten Beleg geprüft. |
| Betrieb | Global pausiert, große Mailaufnahme unverändert bei 1.587 gelesenen Mails. Kein Versand, Kalender-Schreibtest, Cloudlauf oder Löschen. |

Begrenzung: Die ausführliche Frage enthält eine negierte Heute-Formulierung; der vorhandene zeitliche Filter kennzeichnet dabei trotzdem „Quellen von heute“ und die richtige ältere Quelle als außerhalb. Die Quelle wird erhalten und angezeigt, aber diese Zeitbereichsinterpretation ist noch nicht sauber. Die Wartezeit von 51–66 Sekunden und diese Darstellung bleiben konkrete offene Produktpunkte. Keine vollständige Aussagen-, Personen-, Anlagen-, Serien-, Akku- oder Tagesabnahme.

Paketbindung: Quellarchiv SHA-256 `ae3f2e2e48e27667034f83247b6dcc430a7b57bb6b30b3cce8ee1a90e4c5aeb6`; Image `sha256:3684a076c791e222b5e3698695d0c507588c8140c3b0bfe8987eadbc4f78825a`; DMG SHA-256 `3d7ed0f645a6a4f96b085c5cb6316486f34055877a1f0cf7f08c3030e1a36ce9`. Private Sicherung und Testgespräch bleiben lokal; keine persönlichen Mailtexte, Quellenkennungen oder Screenshots in GitHub.
