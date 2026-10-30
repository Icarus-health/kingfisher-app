# Gedächtniskern: Reparaturprüfung vom 30. Oktober 2026

Stand dieses Protokolls: integrierte lokale Regression gezielt geprüft; keine
Mac-Abnahme und keine Freigabe des Großimports. Ausgangspunkt ist `9bfe625`;
die Aufgabenreparatur `49090ab`, Personenreparatur `2e2be48` und deren
Auswahlgrenzenkorrektur `6cc8770` sind integriert. Die Fassung **1.0.30** ist
für den bestehenden Updateweg vorbereitet, damit noch nicht veröffentlicht oder
installiert. Dieses Protokoll bescheinigt keine vollständige Gedächtnisqualität.

## Dauerhafte integrierte Regression

`sidecar/tests/test_memory_core_integration.py` verwendet ausschließlich erfundene
Mails, echte SQLite-Stores und die tatsächlichen HTTP-Routen des Gesprächs.
Der vorhandene Mail-Testhelfer speichert Original, Beteiligte mit Rollen und
Threadkennung. Der echte Einordnungsworker schreibt Textbereiche und Arten;
ein fester geprüfter Sprachvorschlag geht durch die vorhandene Aufgabenautomatik.
Nur Klassifizierungs-/Auswahlantworten und der geprüfte Aufgabenkandidat sind
synthetische Spracheingaben. Weder IMAP-Transport noch Güte eines Sprachmodells
werden damit gemessen.

Die Kette prüft:

1. Bitte mit Frist → eingeordnete Originaltextstelle → Aufgabe für die belegte
   Gegenadresse mit Frist 05.11.2026.
2. Zwei Alex, zunächst drei getrennte Adressen: konkrete Fristfrage klärt die
   Person vor jedem weiteren Sprachaufruf. Erst die Auswahl begrenzt den Belegrahmen.
3. Preview und ausdrückliche Zusammenführung zweier Winter-Adressen; Personenakte
   und neue Rückfrage verwenden denselben bestätigten Rahmen. Alle drei Quellen
   dieser Person sind exakt auflösbar; Sommer bleibt draußen.
4. „Noch nicht fertig, nächste Woche schicken“ lässt die Aufgabe offen und erzeugt
   nur einen Erledigungsvorschlag. Ein Thread/Anhang ist kein Erfüllungsnachweis.
5. Korrektur und Quellenentzug entfernen alte Antwortbelege, bewahren aber den
   Originaltext. Die wörtliche Quelle sagt **Zugang**, nicht „Zugangskarte“.
6. Neue App-/Store-Verbindungen bewahren Aufgabe, Frist, aktive Zusammenführung
   und Entzug. Merge-Undo erzwingt wieder die Personenwahl. Erst explizite
   Bestätigung erledigt die Aufgabe; Aufgaben-Undo öffnet sie und trennt diese Mail.

Die unveränderte Endfassung des Integrationstests wurde in eine mit `git archive
9bfe625` erstellte Kopie gelegt. Dort scheitert sie am tatsächlichen Verhalten:
`working_reports` statt `meaning_choice` bei der konkreten Alex-Frage. Aufnahme,
Klassifizierung und Aufgabenanlage waren davor durchlaufen; kein Import- oder
Fixturefehler wurde als Rotnachweis gezählt.

Der zusätzliche Weiterleitungsgegenfall scheitert auf `6cc8770` mit „Du hast Jonas
Keller … geantwortet“. Er erwartet belegbar „Du hast am … an Jonas Keller
geschrieben“. Die ausgehende Formulierung wurde entsprechend korrigiert; die
Aufgabenentscheidung ändert sich dadurch nicht.

## Zusätzlicher belegter Fristfehler

Die Controller-Gegenprobe zeigte eine echte verbleibende Kernlücke:
`bis zum 2. November 2026 um 18 Uhr` wurde als **23:59 Uhr** angelegt.
Die Auflösung verwendet jetzt die vorhandenen Originalpositionen des Datums,
um genau eine unmittelbar folgende numerische lokale Uhrzeit zu binden.
Ohne Zeitangabe bleibt es bei 23:59 Uhr. Ungültige Uhrzeiten, Alternativen,
Uhrzeiten eines anderen Satzes, zusätzliche Zeitzonen sowie lokale DST-Lücken
oder doppelte Stunden ergeben kein geratenes Datum mit Tagesende.

Eine erkannte, aber unaufgelöste Frist und eine bereits verstrichene exakte Frist
lassen die Aufgabe im bestehenden Vorschlagsweg; die Vorschlagsroute nennt den
Fristgrund. Tagesgenaue Fristen gelten am Fälligkeitstag bis 23:59 Uhr weiter.
Die Tests halten dafür Freitag 30.10.2026, 15 Uhr, fest: eine Donnerstagsmail
„bis Freitag“ und eine Freitagsfrist um 18 Uhr sind noch aktiv; 14 Uhr ist vorbei.
Die vorhandene Regel, dass „bis Freitag“ aus einer Freitagsmail mehrdeutig ist,
bleibt erhalten. Zwei ältere Aufgabenübernahmetests verwendeten genau diese
tagesabhängige Formulierung und scheiterten auch unverändert auf `6cc8770`;
sie verwenden nun ein ausdrückliches Datum statt eines wechselnden Wochentags.

`test_aufgaben_frist_sicherheit.py` enthält 25 feste Gegenfälle. Die ersten
20 Fälle waren vor der Reparatur **18 rot, 2 grün**; DST-, ungültige
Nutzerzonen- und zusätzliche Mehrdeutigkeitsfälle wurden ebenfalls rot belegt.
Die Vorlage des Vorschlags und dessen unveränderte Übernahme verwenden nun
dieselbe quellgeprüfte Frist. `frist_vorschlag=null` darf in der Oberfläche
nicht über `valid_until` aus einem Modell wieder ein Datum erhalten. Ein neu
gewählter Tag ist weiterhin eine ausdrückliche Nutzerwahl mit Tagesende.
Die zwei neuen Verhaltenstests im vorhandenen `task-workflow.test.mjs` waren
zuerst rot: einmal wurde 18 Uhr zu 23:59 Uhr, einmal kehrte die abgelehnte
Quellenfrist über die Modellfrist zurück. Eine veraltete reine Quelltextprüfung
auf `item.frist_vorschlag` wurde durch diese Verhaltensprüfungen abgelöst.

Gezieltes Prüfkommando (keine Vollsuite):

```sh
PYTHONPATH=sidecar .venv/bin/python -m pytest -q sidecar/tests/test_memory_core_integration.py sidecar/tests/test_aufgaben_post.py sidecar/tests/test_aufgaben_post_sicherheit.py sidecar/tests/test_aufgaben_von_selbst.py sidecar/tests/test_aufgaben_frist_sicherheit.py sidecar/tests/test_person_retrieval_repair.py sidecar/tests/test_source_correction_flow.py sidecar/tests/test_fristen.py sidecar/tests/test_task_candidates.py sidecar/tests/test_task_review.py
```

Ergebnis: **185 bestanden**, eine vorhandene Starlette/httpx-Deprecation-Warnung,
38,41 s. Nach der letzten Begrenzung der Fristenprüfung auf den bestehenden
Automatikentscheidungszweig nochmals die 50 direkt betroffenen Fristen-,
Aufgabenautomatik- und Integrationstests: **50 bestanden**, 5,39 s, gleiche Warnung.
12 gezielte UI-Tests und `npm run typecheck` bestanden. `compileall`,
`git diff --check` und die lokale Release-Vorprüfung für `v1.0.30` bestanden.
In der aktuellen Testumgebung wurde zusätzlich das bereitgestellte
Python-Abhängigkeitsverzeichnis im `PYTHONPATH` verwendet; der Test hat keine
Abhängigkeit von Dateien unter `/private/tmp`.

## Bereits gemessene lokale Teilproben des Controllers

Die folgenden JSON-Nachweise wurden vom Controller bereitgestellt und hier nur
gelesen/kopiert. Dieser Integrationsschritt hat keine Modelle oder externen APIs
aufgerufen. Alle Proben sind synthetisch, ohne Cloud und ohne Änderung am
Alltagsbestand. Die Messungen sind getrennt vom Regressionstest zu bewerten.

| Probe | Gemessener Umfang | Aussage und Grenze |
|---|---|---|
| [Qwen erster Teil](qwen-small-catalog.json) + [Grenzfälle](qwen-boundary-catalog.json) | `kingfisher-qwen3.5:9b-32k`: 3 + 5 Quellen vollständig eingeordnet; alle 8 innerhalb der vorgegebenen zulässigen Arten; je 2,714–9,063 s | Kleine Blockartenprobe, keine vollständige Aufnahme-/Aufgaben-/Zuordnungsqualität. Bei manchen Fällen sind mehrere Arten zugelassen. Der erste Lauf übersprang den nächsten Fall wegen des Speicherschutzes; der zweite Teil ist ein eigener begrenzter Lauf. Druckstufe zeitweise 2, freier Anteil bis 22 %. |
| [BGE-M3](bge-small-catalog.json) | 3 Fragen gegen 3 Texte; jeweils erwarteter Text auf Rang 1, 1,535 s, 1.024 Dimensionen | Semantischer Rangtest, keine Identitäts- oder Wahrheitsbestätigung; eine semantisch ähnliche Frage beweist keinen zusätzlichen Gegenstand im Original. |
| [Qwen-Aufgabenerkennung](qwen-task-extraction.json) und [Übernahme desselben Vorschlags](qwen-task-acceptance.json) | 1 analysierte Quelle, 1 semantisch geprüfter Vorschlag, 0 Fehler, 11,315 s; anschließende Übernahme ohne neue Modellaufrufe | Richtige belegte Gegenadresse und 02.11.2026 **18:00 Uhr** bestätigt. Ein einzelner synthetischer Auftrag, keine Aussage über Vollständigkeit, Namensvetter, Negation oder beliebige Mailbestände. |
| [Lebenszyklus 10.000](lifecycle-10000.json) | 10.000 Originale, Neustart/Transportwiederholung, 1.000 Labeldubletten ohne Neueinordnung, 10 neue Quellen, Ersetzung und Entzug; 110,492 s | Mechanik mit synthetischer Klassifizierung/Vektoren, kein LLM und kein Nachweis der Einbettungsqualität. Alle gespeicherten Originalfassungen erhalten. |

Diese Teilproben ersetzen weder eine zusammenhängende repräsentative
Alltagsprüfung noch eine native Mac-Bedienprobe. Die historische Abrufprobe mit
„Zugangskarte“ ist kein Beleg für einen Kartenort: Das zugehörige Original
spricht nur vom Zugang. Ein wörtlicher Abruf darf daraus keine Karte erfinden.

## Integrierte Schlussprüfung des Controllers

Produktionscode-Stand `39ab8ce` (nachfolgender Dokumentationscommit ändert keinen
Produktionscode). Vollständige lokale Backend-Regression in UTC mit zwei
niedrig priorisierten Workern: **8.224 bestanden, 1 übersprungen, 26 Untertests
bestanden**, 752,64 s. Zwei bestehende Starlette/httpx-Warnungen.
Die zuvor abgebrochene Vollprüfung mit sechs Fehlern ist kein Bestehensnachweis;
deren Ursachen und die Reviewkorrekturen sind in den Reparaturcommits behoben.

UI: **953 bestanden**, Produktionsbuild bestanden (bekannte Warnung für die
Paketgröße). Ergänzende Diagnose-/Messlatten-/Mac-Logiktests auf dem finalen
Code: **581 bestanden, 1 übersprungen**, 93,19 s; vorhandene Starlette-Warnung.
Der Swift-Modulcache liegt für diese Prüfung in einem beschreibbaren temporären
Ordner. Assetvertrag (11 Dateien, 14 Icons), Beispielschema und lokale
Release-Vorprüfung bestanden. Unabhängiges Gesamt- und gezieltes Nachreview
geben den Code ohne offene wichtige Befunde frei.

[Native Bedienprobe](native-window-acceptance.json): bestehende Mac-Hülle,
getrennte künstliche Daten auf Port 8893, Qwen9B/BGE-M3, keine Cloud. Personenwahl,
bestätigte Zusammenführung, Quellenöffnung und -entzug, erneuter Abruf,
Aufgabenübernahme und Neustart wurden durch tatsächliche Bedienung geprüft.
Die Protokollaufgabe bleibt nach „noch nicht fertig“ offen; der vorsichtige
Erledigt-Vorschlag wurde im Fenster verworfen. **03.11.2026, 18:30 Uhr** bleibt
im gespeicherten Auftrag und im belegten Fristabruf erhalten.

Der erste Nora-Testhelfer hatte den Quellenstand nach `record` nicht wie der
echte Mailimport weitergeschaltet. Deshalb bedeutete sein `work.ok` noch keine
Einordnung. Nach Korrektur des **Testhelfers** wurden `state=complete`, tragfähige
Referenzen und der erfolgreiche Abruf ausdrücklich geprüft. Kein Produktfix
oder nachträgliches positives Zählen dieses unvollständigen Versuchs.

Die native App lud zunächst noch das ältere bereits geöffnete UI-Paket; nach
dem normalen Neuladen zeigte auch die Vorschlagszeile die richtige Uhrzeit.
Gemessene lokale Antworten dauerten 7,8 bis 19 Sekunden. Bei der Ressourcenprobe
vor dem einzelnen Modelllauf: normaler Speicherdruck (1), 39 Prozent freier
Anteil. Das ist keine dauerhafte Lastgarantie bei anderen gleichzeitig laufenden
Modellen. Indexabdeckung wurde teilweise als begrenzt ausgewiesen; ein
zusätzliches Satzprüfmodell ist nicht eingerichtet.

Der echte Bestand wurde bis hier nur lesend auf frühere automatische
Aufgabenänderungen geprüft: keine solchen Gründe gefunden. Keine Altänderung
wurde zurückgesetzt. Installation, Sicherung und Bestandsvergleich des
persönlichen Macs sind ein gesonderter Auslieferungsschritt. Bis zur
repräsentativen Qualitätsabnahme bleibt der Großimport pausiert.

## Nachtrag: Im nativen Fenster gefundener Themenfehler

Nach dem Ausschließen der privaten synthetischen Zugangsquelle blieb der alte
Beleg korrekt gesperrt. Die erneute **gleiche** Zugangsfrage zeigte jedoch
Druckdatenfristen derselben Person und desselben Projekts. Das ist keine
belegte Antwort auf die Frage, auch wenn die Zitate selbst unverändert sind.
Die gezielte Korrektur präzisiert deshalb die vorhandene Auswahlanweisung:
gemeinsame Identität und Aktenbezug sind Suchrahmen, keine Antwortrelevanz.
Sinngleiche Aussagen, Übersichten und Belege zu einzelnen Teilfragen bleiben
ausdrücklich erlaubt. Kein zusätzlicher Modellaufruf, keine neue Suchregel.

[Mit den sieben tatsächlich angebotenen künstlichen Kandidaten](native-selection-focus-comparison.json)
lieferte Qwen9B vorher zweimal die falschen Druckdaten-IDs, danach zweimal
`no_relevant_sources` und keine IDs. Die Wiederholungen sind deterministische
Wiederholungen desselben Falls mit Prompt-Cache, **keine vier unabhängigen
Qualitätsfälle**. [Vier kleinere Kontrollfälle](selection-focus-comparison.json)
behalten sinngleichen Zutritt/Safe-Beleg, Personenübersicht und aktuelle
Druckdatenfrist; der einfachere negative Zugangsfall war bereits vorher richtig.
Die größere native Gegenprobe bleibt für den Fehlernachweis entscheidend.

Grenze: Das ist eine gemessene Verbesserung der probabilistischen
Quellenauswahl, kein deterministischer Beweis beliebiger Antwortrelevanz.
Eine absichtlich falsch auswählende Attrappe wäre weiterhin falsch; ein Test
auf den Wortlaut der Anweisung würde diese Qualitätsgrenze nicht prüfen.
Die nativen Gegenproben mit dem tatsächlich geladenen Patch folgen gesondert.
