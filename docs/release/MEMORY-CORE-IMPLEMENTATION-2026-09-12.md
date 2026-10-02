# Gedächtniskern – Implementierungsstand 12. September 2026

**Erstes Fundament umgesetzt; der gesamte Vertrag und automatische Arbeitsinterpretationen sind nicht freigegeben.** Grundlage ist PR #34 (`9556c8e`). Die bisherige Abnahmequote wird durch dieses Paket nicht erhöht. Entwicklung in `feat/memory-core-v1`, getrennte Arbeitskopie und synthetische Testdaten. Keine produktive Datenmigration oder Änderung der Modellauswahl.

## Was dieses Paket trägt

- Quelleneinfluss bleibt im Agenten über Gesprächsrunden und geladene Verläufe erhalten. Kontextdaten stehen außerhalb der Systemregeln. Übertragende Leseaufrufe verlangen nach Quelleneinfluss eine konkrete Freigabe; nur ausdrücklich geprüfte lokale Reads sind ausgenommen. Freigabeparameter werden defensiv kopiert.
- Aufgabenvorschläge werden in Abschnitten bis 8.000 Zeichen mit Überlappung verarbeitet. Migration 4 ergänzt Jobzustände in der vorhandenen Vorschlagsdatenbank. Fortschritt und Kandidaten werden atomar geschrieben; Lease-Tokens verhindern verspätete Doppelannahme. Quellenentzug, Eingabe- und Modellwechsel verwerfen ausstehende Ergebnisse. Alte Checkpoints ohne Umfang gelten nicht als neue Abdeckungsnachweise.
- JSON-Ausgaben sind begrenzt und erhalten keine Werkzeuge, Rechte oder Bestätigungsfelder. Unbekannte Felder, fremde Zitate, abgeschnittene Antworten und volle Ergebnisbudgets ergeben keinen abgeschlossenen Prüflauf.
- Historische Abfragen unterscheiden damalige Kenntnis und fachliche Gültigkeit. Späte Erkenntnisse werden nicht rückdatiert. Aktuell entzogene Quellen und redigierte Aussagen bleiben auch historisch ausgeschlossen. Fehlende Altjournale werden als Lücke ausgewiesen.
- Authentifizierte Endpunkte `/api/v1/memory/coverage`, `/timeline` und `/as-known`. Verarbeitung ist ausdrücklich keine semantische Vollständigkeit. Der lokale Chat erhält diesen Umfang als Kontextdaten.
- Unter Gedächtnis zeigt „Verarbeitung & Verlauf“ Prüfstände und monatliche Aufnahme-/Entscheidungsereignisse, mit getrenntem ursprünglichem Datum und aufklappbarem Originalbeleg.

## Reale lokale Modellprobe: nicht bestanden

Reproduzierbar mit `PYTHONPATH=sidecar .venv/bin/python scripts/probe_memory_requests.py --model <installiertes Modell>`. Der Runner verwendet ausschließlich zehn synthetische Entwicklungsfälle, keine privaten Nachrichten oder App-Datenbanken. Er prüft erwartete Handlungszitate und protokolliert auch die Titel. **Er ist kein unabhängiger Holdout, keine vollständige Titelprüfung und keine Modellqualifikation.**

Promptstand `requests-v3`, jeweils ein Lauf auf dem Mac:

| Modell | Bestanden | Konkrete Grenzen |
| --- | --- | --- |
| qwen3.5:4b | 8/10 | Verwechselt Absage mit Aufgabe; übernimmt eine Aufforderung zum Umgehen von Freigaben als Vorschlag. Außerdem verfälscht der Titel „Termin bestätigen“ die korrekt zitierte Zusage, einen Termin mitzuteilen. |
| qwen2.5:14b | 8/10 | Übersieht das aktuelle Versandverbot in einem Thread mit altem Auftrag und eine ausdrückliche Zusage. |

Die früheren v2-Gegenproben hatten zusätzlich Verneinungen, Empfangsbestätigungen und Gedankenexperimente fälschlich als Aufgaben ausgegeben. Die Promptüberarbeitung reduziert diese Fehler; sie beseitigt die Bedeutungsprobleme nicht. Einzelne warme Läufe lagen um 1–2 Sekunden, Start-/längere Läufe darüber. Keine P95- oder Lastmessung; keine belastbare Geschwindigkeitszusage.

Ein fehlgeschlagener Bedeutungsfall kann trotz gültigem JSON einen technischen Prüflauf abschließen. Deshalb bleiben die Ergebnisse Kandidaten und `semantic_completeness=false`. Das Modell darf weder Rechte vergeben noch Aktionen ausführen. Die strukturellen Sicherheitstests prüfen den tatsächlichen Werkzeugaufruf unabhängig davon, ob das Modell den Angriff erkennt.

## Verifikation

- Ausgangssuite: 1.208 Tests bestanden.
- Zwischenstand vor den letzten Provider-/Historienänderungen: 1.241 Tests bestanden.
- Aktuelle fokussierte Historien-/Job-/API-Tests: 19 bestanden.
- Aktueller Gesamtstand und Build: siehe ergänztes Ergebnis unten.
- Isolierter Browser unter Port 18894: synthetischer Bestand mit einer geprüften und einer offenen Quelle; gespeicherter Stand nach Prozessneustart; Originalbeleg geöffnet; alter Quellenzeitpunkt separat; leerer Monat; sichtbarer Fehler bei gestopptem Backend. Die produktive App auf 8891 blieb unverändert.

## Noch notwendige Arbeit für „Gedächtnis fertig“

1. Qualifizierte Klassen für Anfrage, Gesprächsgegenstand und datiertes Ereignis; getrennte Zustände für Hypothesen, Bedingungen, berichtete Zusagen und Bestätigungen. Ein Schema- oder Zitatcheck ersetzt diese Abnahme nicht.
2. Durchgängige Vorgangs-/Verpflichtungshistorie einschließlich Friständerung, Teilerfüllung, Korrektur im Chat und aktualisierter Ansicht.
3. Fortlaufende Nutzer-/Personenprofile und hierarchische Verdichtung mit Herkunft, Kontext, Konflikten und Aktualitätsregeln; einfach bedienbare Kontaktansicht.
4. Getrennte Zweckrechte, vollständige Abhängigkeiten aller Ableitungen, Löschung über alle relevanten Speicher sowie Wiederherstellung alter Backups mit späteren Löschentscheidungen.
5. Robuste globale Priorisierung lokaler Inferenz, tatsächliche Modellfingerprints, Rückstau-/Wachstumsmessung, weniger Rückfragen und der vereinbarte Bestand von 300 Quellen, 90 fachlichen Fällen und mindestens 40 adversariellen Abläufen.

Bekannte Grenzen des Pakets: Fenster können entfernten Kontext übersehen; ein volles Ergebnisbudget bleibt als Fehler sichtbar statt automatisch weiter unterteilt zu werden; Job-Leases koordinieren diese Hintergrundauswertung, nicht sämtliche lokalen Modellaufrufe; historische Abfragen sind begrenzt, besitzen noch keinen Fortsetzungscursor; Quellen-/Entscheidungsereignisse sind noch nicht die vollständige hierarchische Lebenszeitleiste. Alte bestätigte Daten werden durch erneute Analyse nicht automatisch korrigiert.

### Abschließende Ergebnisse dieses Entwicklungsstands

`pytest sidecar/tests -q`: **1.246 bestanden, 2 Deprecation-Warnungen, 212,08 Sekunden**. Danach wurde ein zusätzlich rot nachgewiesenes Archivierungsrennen korrigiert: Eine während des Modellaufrufs archivierte Quelle darf keinen Kandidaten mehr erzeugen. Die betreffende Testsammlung wurde erneut ausgeführt (Ergebnis unten). Der finale Frontend-Build nach den Darstellungsänderungen ist erfolgreich. Die schmale Ansicht mit 800 px wurde überprüft und für diesen neuen Bereich angepasst; die Quellenansicht hat nun passende Kontraste. Dies ist keine vollständige Überarbeitung der übrigen Oberfläche.

Nachprüfung des Archivierungsfehlers: `pytest sidecar/tests/test_memory_analysis.py sidecar/tests/test_task_detection.py sidecar/tests/test_task_candidates.py -q` → **30 bestanden**, dieselben zwei Warnungen.

Die erste Container-CI deckte eine zusätzliche Regression auf: Nach vorhandenem Quellkontext verlangte schon das Vorbereiten eines unbestätigten Gedächtnisentwurfs eine Aktionsfreigabe; dadurch fehlte die Bestätigungskarte. Ein neuer roter Regressionstest belegt den Fehler. Die Entwurfsvorbereitung läuft jetzt nach der Verbotsprüfung, aber vor der zusätzlichen Aktionsfreigabe. Sie führt kein Werkzeug aus und schreibt kein bestätigtes Wissen; die bestehende Quellenbindung und spätere Bestätigung bleiben erhalten. Nachprüfung: **86 Agenten-, Kingfisher- und Sicherheitstests bestanden**. Container-CI wird mit diesem Fix erneut ausgeführt.
