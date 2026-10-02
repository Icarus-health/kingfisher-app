# Fortlaufende CoS-Gedächtniswoche – Ausgangsmessung

28.09.2026. Produktcode basiert auf Main `65f014648d464fb8eb1fb9390a709c119f509acb`. Kein Produktfix und keine Cloud-Anbindung in diesem Änderungspaket.

## Durchlauf

Ein temporärer App-/SQLite-Bestand bleibt über fünf logisch aufeinanderfolgende Tage bestehen. Zehn synthetische Dokumente durchlaufen Upload-HTTP-API und den echten lokalen Einordnungs-Callback. Elf neue Gespräche fragen den jeweils aktuellen Bestand ab. Donnerstag enthält neue Stornierungs-/Freigabequellen, Freitag einen doppelten Upload und Quellenentzug. Bereits vorhandene Test-/Produktdaten werden nicht verwendet.

Modell `qwen3.5:4b`, installierte Gewichte im Rohbericht. Semantische Suche aus, kein Modell-Download. Fester Endpunkt localhost:11434. Die beiden archivierten Läufe verwendeten den direkten lokalen Provider. Nach Gegenprüfung verwendet der Runner vor jedem Aufruf die bestehende positive Ollama-Gewichtsprüfung und deaktiviert Proxy-Vererbung/Redirects auch für die Inferenz. Er setzt weiterhin einen vertrauenswürdigen lokalen Ollama-Dienst voraus. Für persönliche Daten ist diese synthetische Prüfung nicht freigegeben.

Die Aufrufe sind sequenziell, keine real verstrichene Woche. Die Einordnung wird synchron angestoßen; Scheduler-Durchsatz und Zeitsteuerung sind damit nicht getestet. Kalender und Buchungen sind dokumentierte Sachverhalte, keine tatsächlich ausgeführten externen Aktionen.

## Ergebnisse und Grenzen der Bewertung

| Lauf | Sachfragen mit allen festen Prüfungen | Modellaufrufe | Summe Modellzeit |
| --- | ---: | ---: | ---: |
| Erster Lauf, `4e96a95` | 7/11 | 21 | 36,357 s |
| Verschärfte Verlaufsprüfung, `f44acf5` | 7/11 | 22 | 26,506 s |

Die Unterschiede der Modellaufrufe/Laufzeiten sind keine Performanceverbesserung: gleicher Produktcode, neuer Lauf. Kein Cloudverbrauch. Diese Zahlen sind **kein Genauigkeitswert für den CoS**. Geprüft werden ausgewählte Quellen, Antwortstatus und Wortlaut; das beweist keine korrekte freie Schlussfolgerung. Erlaubte unklare Antworten sind ein Mindestschutz und können weiterhin unnötige Rückfragen enthalten. Manuelle Sichtung der Fehlfälle folgt unten.

- **Personenmehrdeutigkeit:** Beide Leas werden zitiert, die nötige Rückfrage fehlt. Reproduziert die bekannte Lücke innerhalb einer Quelle.
- **Buchungsbestätigung:** Die Frage „Liegt jetzt eine Hotelbuchung … vor?“ erhält eine falsche Verneinung trotz vorhandener Bestätigung. Die protokollierte Modellanfrage enthält keinen Arbeitsgedächtnisbeleg. Codeprüfung: `working_memory_answers.is_question` erkennt diesen Frageanfang nicht; der automatische Belegpfad wird damit umgangen. Das ist primär eine Routinglücke, kein Beleg dafür, dass allein ein besserer Extraktor hilft.
- **Buchungsart:** Auf die Frage nach einer Zugbuchung kommen Hotelbestätigung/Stornierung und eine Konfliktrückfrage. Die thematische Auswahl ist zu weit.
- **Nach Quellenentzug:** „Ich weiß dazu nichts“ ist inhaltlich angemessen, hat aber keinen `answer_contract` und verfehlt deshalb die vorher festgelegte Statusprüfung. Separat als Vertragslücke gewertet, nicht als falsche Tatsachenbehauptung.

Originaltexte blieben in beiden Läufen unverändert; doppelter Upload liefert dieselbe Quellen-ID. Der erste Verlaufstest verglich nur einen ganzen Quellabsatz und war zu schwach. Die Gegenprüfung verlangt jetzt, dass konkrete Faktenfragmente in allen zurückgegebenen Nachrichten fehlen und keine aktiven Quellenlinks verbleiben.

Der zweite Rohbericht markiert Verlauf zunächst rot, weil er auch historische, ausdrücklich ungültig gemachte Fingerprint-Referenzen verbot. Sichtprüfung des gespeicherten Verlaufs und des UI-Vertrags zeigt: Inhalt ersetzt, `working_unavailable`, `source_links: []`; interne Abstammungsreferenzen bleiben erhalten. Der korrigierte Prüfer unterscheidet dies von aktiven Belegen. Nachprüfung **derselben gespeicherten Antwort**, ohne neue Modellaufrufe, bestanden: `withdrawal-readback-review.json`. Beide ursprünglichen Berichte unverändert erhalten. Kein Nachweis für Netzwerkausleitung oder weitere spätere Gesprächsrunden daraus abgeleitet.

## Wiederholen

```sh
PYTHONPATH=sidecar:scripts python scripts/probe_cos_workweek.py \
  --model qwen3.5:4b --output /tmp/kingfisher-workweek-new.json
PYTHONPATH=scripts python -m pytest scripts/test_probe_cos_workweek.py -q
```

Ausgabe muss neu sein. Der Runner beendet sich bei nicht erfüllter Abnahme mit Exitcode 1. Die sechs Prüfer-Tests bestehen; absichtlich falsche Quellen, fehlende Bedingungen, falscher Status und paraphrasierte zurückgezogene Fakten werden nicht als bestanden gewertet. Keine vollständige Backend-Wiederholung für dieses isolierte Evaluationspaket.

## Nächste fachliche Schritte

1. Belegpfad für natürliche Gedächtnisfragen schließen, einschließlich „Liegt … vor?“, „Gibt es …?“ und Gegenfällen, die tatsächlich Aktionsaufträge sind. Keine freie negative Tatsachenbehauptung aus leerem Kontext.
2. Buchungsarten und Personenbeziehungen prüfen, statt nur Wortähnlichkeit/korrektes Ausgabeformat zu bewerten. Dieselben festgelegten Fälle bleiben bestehen, neue Gegenbeispiele ergänzen sie.
3. Erst danach lokale Spezialisten oder eine genehmigte synthetische Cloud-Variante an exakt diesem Ablauf vergleichen. JEV-Bewertung: `JEV.md`.
4. Die noch fehlenden Integrationsphasen für Aufgabenverantwortung, echte Kalenderzustände, Berechtigungen und doppelte Aktionausführung ergänzen; dazu Last und Wiederanlauf. Bis dahin ausdrücklich keine vollständige CoS-Abnahme.

Abschlussprüfung des abgesicherten Runners (`fac04c0`): erster Tag 3/3, 6 lokale Modellaufrufe, 6,289 Sekunden Modellzeit; `transport-smoke.json` und `smoke-fixture.json`. Dies ersetzt nicht die vollständigen Ausgangsläufe. Sechs Prüfer-Tests plus 19 bestehende Local-Guard-Tests: **25 bestanden**.
