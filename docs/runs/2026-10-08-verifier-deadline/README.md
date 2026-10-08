# Satzprüfung begrenzen; freie Antworten unabhängig messen

## Begrenzte Codekorrektur

`_ein_urteil()` kehrte nach dem Satzbudget mit `unklar` zurück, während sein lokaler JSON-HTTP-Aufruf noch bis zu30s weiterlaufen konnte. Eine worker-lokale monotone Frist wird jetzt an den bereits vorhandenen JSON-Transport weitergereicht. Nach abgelaufener Modellvorbereitung beginnt keine HTTP-Anfrage. Ein Budget von0 oder weniger startet keinen Modellauftrag. Validatoren, Prompts, Quellenwahl und Satzbelege bleiben unverändert.

Vier neue Fälle scheitern ohne die Korrektur: echter langsamer Loopback-Server, Fristablauf während Modellwarten, Null- und Negativbudget. Danach49 enge und260 erweiterte betroffene Prüfungen bestanden, einschließlich Satzantwort, Quellenprüfung, gespeichertem Verlauf, JSON-/Decision-Transport. Eine bestehende Starlette/httpx-Warnung. Das unabhängige Codereview fand keine konkrete Regression; es las Code und GREEN-Log, führte die Tests nicht selbst erneut aus. Zwei echte lokale Transportprüfungen bestehen zusätzlich im fertigen netzlosen Paket.

**Grenze:** HTTPX begrenzt Transportphasen. Dies ist kein harter Ende-zu-Ende-, Thread- oder GPU-Abbruch. Ein Worker kann weiter auf Modellfreigabe warten; nach deren Freigabe verhindert die Frist eine verspätete JSON-Anfrage. Plain-/Decision-Adapter behalten eigene Grenzen. Keine allgemeine Akkuverbesserung gemessen.

## Tatsächliche freie Antworten: Baseline, keine Wirkungsmessung dieses Fixes

Zwei vollständig abgeschlossene künstliche Kataloge testen den produktiven Antwortweg mit tatsächlicher freier Satzgenerierung und aktiviertem Modellprüfer. Beide messen **Produktcode064a4d9 vor der Transportkorrektur**. Der Originalprozess hatte die Baseline-Module bereits vor der Bearbeitung geladen; die unabhängige Kontrolle importiert eine eingefrorene Paketkopie. Importpfade/-Hashes und Kataloghashes sind erhalten. Diese Läufe belegen keinerlei Qualitätsverbesserung durch den Deadline-Fix.

Eigener nativer Ollama0.35.1 auf127.0.0.1:11439, Apple M2 Max/Metal, Kontext4096, Parallelität1, höchstens zwei Modelle. Vorhandenes qwen3.5:4b für Frage, Auswahl, Formulierung und Prüfung; echtes bge-m3 für den dauerhaften SemanticService. **Dasselbe Modell als Formulierer und Prüfer ist keine unabhängige Wahrheitsprüfung.** Deshalb prüfte ein separater günstiger Reviewagent alle sichtbaren Antworten gegen die Originalquellen; seine ungenauen Abrufstufenangaben wurden anschließend gegen die Rohspuren korrigiert.

Die Quellen sind deterministisch eingeordnet. Kein persönlicher Import-/Einordnungsqualitätstest und kein großer persönlicher Bestand. Jede Frage nutzt einen eigenen Agenten. Keine Cloudinferenz oder Modell-Downloads; native Ausführung ist keine Netzisolierung. Ein eigener Watchdog begrenzt Laufzeit und gesampelten Prozess-RSS, keine harte GPU-/RAM-Grenze. Gesampelter Spitzen-RSS rund5,97GiB bzw.6,28GiB. Beide eigenen Dienste sind danach beendet, Exitcodes0. Produktives Ollama bleibt aus.

| Messung | Originalkatalog | Unabhängige Kontrolle |
|---|---:|---:|
| Fragen |36|23|
| Quellen-/Statuspunkte, keine inhaltliche Vollständigkeitsquote |29/36|20/23|
| Antworten mit freien Sätzen |14|16|
| Angezeigte freie Sätze |16|19|
| Durch Originale gestützte freie Sätze im unabhängigen Review |16/16|19/19|
| Antworten mit Zitat-Rückfall |11|2|
| Median gesamte Antwortzeit |5,137s|6,219s|
| Providerfehler / laufende Provideraufrufe bei Messende |0/0|0/0|
| Quellenentzug erneut geprüft |bestanden|bestanden|

Die35 gestützten Sätze sind ein begrenzter positiver Befund, keine Fehlerfreiheitsgarantie. Die Originalzitate bewahren ihre Quellenformulierungen. Die Prüfung verwirft erfundene Jahre/Datumspräzision und die Abschwächung „erst nach10Uhr“ zu „ab10Uhr“ korrekt.

### Offene, konkret belegte Qualitätslücken

Die folgenden Q-Nummern sind **einsbasiert**; die JSON-Reviewindizes sind ausdrücklich **nullbasiert**.

* Original Q4 undQ18: richtige Quelle unter den Kandidaten, aber bei der Modellauswahl verloren. Q8 undQ32: passende Quelle fehlt bereits im Kandidatenfund. Q16 verliert die gefundene Fotolizenz bei der Auswahl; Grafik/Foto beweist allerdings nicht dieselbe Datei. Q10 hat die Workshopquelle ausgewählt, danach liefert das Formulierungsmodell Nichtwissen; Seminar/Workshop ist ebenfalls nicht zwingend dieselbe Veranstaltung.
* Kontrolle Q2: unnötige Personenrückfrage trotz richtig ausgewählter und gezeigter Nora-/KL-42-Quelle. Ursache durch diesen Lauf nicht belegt.
* Kontrolle Q5: „Freigabe liegt noch nicht vor“ bleibt, die belegte Bedingung „schriftlich durch die Lagerleitung“ wird fälschlich verworfen. Die Verneinung gehört zu einer anderen Aussage im Original.
* Kontrolle Q8: zwei Quellen ausgewählt, danach verschwindet die M-731-Bedingung. Nur M-713 wird beantwortet.
* Kontrolle Q11: beide Terminquellen ausgewählt, danach wird der belegte neue Termin wegen „Änderungsnotiz“ statt „Aktualisierung/Terminänderung“ verworfen. Sichtbar bleibt nur die ausdrücklich erfragte erste Planung. Diese Aussage ist wahr, aber der unvollständige Vergleich hebt den ersetzten Termin hervor: relevant für den täglichen CoS.
* Original Q29:12.000Euro sind korrekt, der freie Satz lässt „Reisekosten eingeschlossen“ weg. Bei der Frage nach der Gesamtsumme keine falsche Zahl; für anschließende Ausgabenplanung wichtige fehlende Einschränkung. Q30 zeigt dagegen das vollständige Zitat.

Nächster Produktblocker: Teilantworten nach einer Verwerfung dürfen wesentliche ausgewählte Quellen/Bedingungen nicht verdecken. Dafür einen reproduzierten allgemeinen Schutz mit Originalrückfall und gespeicherten Antworten bauen; keine neue Synonymliste oder gelockerte Faktenprüfung auf diese Kataloge zuschneiden. Anschließend erneute unabhängige Kontrolle. Abruf-/Auswahlverluste bleiben getrennte Arbeit.

## Liefernachweis

Produktcode `0f0f5da022f0ae929c6c37cabc9ab18aee699e2a`, lokal **1.0.6-local.0f0f5da**. Image `sha256:e08e41a6e099a6b7002e273fb36edcd64dc6bf11479cf13fdf7975e6ab510ab8` enthält byteweise geprüfte264Paket- und112unveränderte UI-Dateien. Wheel gebaut; Imagebuild und Paket-Smoke ohne externes Netz. Buildwerkzeugbeschaffung beim ersten Sandboxversuch nicht erreichbar, anschließend isolierter Wheelbau erfolgreich. Kein neuer vollständiger Backend-/UI-Lauf nötig für diesen begrenzten Transportdiff.

Kalte Sicherung `Kingfisher-Rueckweg/2026-10-08-vor-0f0f5da`:344Original-IDs/Digests und17SQLite-Dateien erhalten/geprüft; Konten, Kalender, Anbieter, Modellrollen und Zeitpläne erhalten. Gleicher Datenvolume, unverändertes natives Programm, ad-hoc Signatur geprüft, Backend gesund. Persönlicher Import pausiert, Mailstatus sichtbar `pausiert`, produktives Ollama aus und Bedeutungssuche deshalb `unavailable`.

Native Fenster-/Alltags-/Akkuprüfung bleibt wegen gesperrtem Mac offen. Kein öffentlicher Release/Registry-Upload, keine CI-Wiederholung, kein neues Abonnement oder Check-in. Der gesamte CoS ist noch nicht abgenommen.

Rohberichte sind bytegetreu komprimiert; `manifest.json` beschreibt SHA-256 der dekomprimierten Originalbytes. `summary.json` zeigt getrennte Abrufstufen. Treiber enthalten Macspezifische Pfade und benötigen für andere Rechner eine ausdrücklich getrennte Testumgebung, passende lokale Gewichte und Baseline-Paketkopie. `independent-content-review.json` hält das externe Review fest, `primary-review-addendum.json` korrigiert die Q29/Q30-Unterscheidung.
