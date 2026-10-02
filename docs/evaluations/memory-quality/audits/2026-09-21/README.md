# Gedächtnisprüfung gegen das CoS-Ziel

Stand: 21. September 2026. Geprüfte Ausgangsbasis: `7e397db87103539cdb93a986e0e15d9e81d26bfd`.
Maßstab: [Gedächtnisvertrag v0.1](../../../../architecture/kingfisher-memory-sicherheitsvertrag-v0.1.md), insbesondere Identität, Zeit, Abdeckung, widerspruchsabhängige Antworten und die Abnahme in Abschnitt 13.

**Ergebnis: Eine brauchbare technische Grundlage besteht; ein verlässliches CoS-Gedächtnis ist noch nicht nachgewiesen. Es gibt reproduzierte funktionale Hindernisse.** Die bisherige Freigabe einzelner Änderungen ersetzt diese Produktabnahme nicht. Der Bericht unterscheidet aktuelle Fehler, bewusst begrenzte Funktionen und noch fehlende Architektur.

## Vorgehen und Aussagegrenzen

- Vier getrennte Prüfbereiche: Aufnahme/Abdeckung, Identität/Zeit, Antworten/Verlauf und Abruf/Gesamtvertrag. Aktueller Code, Tests und bestehende Produktdokumente wurden verglichen.
- Neue Gegenbeispiele liefen mit synthetischen Quellen und kontrollierten lokalen Provider-Doubles über echte Stores und teilweise HTTP-Routen. Ein absichtlich falsches Provider-Ergebnis beweist eine fehlende Prüfgrenze, keine natürliche Fehlerrate eines konkreten Sprachmodells.
- Keine privaten Unterlagen, Cloud-Modellaufrufe, neuen Modellinstallationen oder GitHub-CI-Wiederholungen. Der bisherige mehrtägige Nutzungsnachweis wird nicht durch diesen Lauf ersetzt.
- Kein vollständiges Sicherheitsgutachten aller Module. Die Aussagen „umgesetzt“ beziehen sich jeweils auf den geprüften Pfad, nicht auf alle Ansichten, Exporte und Wiederherstellungen.

## Nachgewiesene Korrekturen dieses Pakets

| Fehler | Vorher | Korrektur und Grenze |
|---|---|---|
| Verdichtungsfehler verschwinden aus dem Rückstau | Ungültiges JSON/Schema wurde als leere Vorschlagsliste gelesen; die Episode anschließend als verdichtet markiert. | Fehler gehen in den vorhandenen Fehlerpfad; Quelle bleibt erneut prüfbar. Ein gültiges `[]` bleibt erfolgreicher Nullbefund. Das prüft Struktur, nicht semantische Vollständigkeit. |
| Abgeschnittene Mail wirkt fertig verarbeitet | Der erhaltene 20.000-Zeichen-Ausschnitt wurde fertig analysiert und als `coverage.completed` gezählt, obwohl ein Kürzungsflag vorlag. | Abdeckung zählt die Quelle als `partial`, nennt gekürzte Quellen und den fehlenden Originalrest. Der technische Job bleibt fertig, damit derselbe Ausschnitt nicht endlos neu verarbeitet wird. Fehlenden Text/Anlagen holt dieser Fix nicht nach. |
| Falsche Aufgabe an Person | „Rückfrage an Joanna“ erschien bei „Ann“, weil der Name Teil des Titels war. | Nur das ausdrückliche Feld `wartet_auf` ordnet die Aufgabe zu. Die Aufgabe bleibt erhalten. Gleiche Namen in diesem Feld sind noch keine gelöste Identitätsfrage. |
| Import- und Annahmezeit werden Ereigniszeit | Undatierte Quelle erschien als Kontakt „heute“; spät angenommene Aussagen datierten den Beleg auf den Annahmetag um. | Personen-/Projektprojektion und Digest erhalten unbekannte Ereigniszeit als `null`, Aufnahme-/Annahmezeit separat. Kein erfundenes letztes Kontaktdatum; Cacheversion erneuert. Die relative Fristinterpretation eines realen Modells ist damit noch nicht qualifiziert. |
| Interpretation erscheint als Originalzitat | Gespeicherte Paraphrase stand in Anführungszeichen unter „In den ausgewählten Belegen steht“, normalisierter Wert als „Wert laut Quelle“. | Darstellung nennt gespeicherte Aussage und gespeicherten Wert. Eine echte inhaltliche Prüfung gegen das Original fehlt weiterhin. |

Zusätzlicher Reviewfund behoben: Wird eine bereits gesammelte Rohquelle während der Claim-Prüfung entzogen, wurde ihr alter Text zuvor noch als Rohbeleg an den Personen-Digest geliefert. Die aktuelle Fassung entfernt ihn; eine unabhängige gültige Quelle bleibt nutzbar. Eine Gegenprobe durch den Reviewer und eine HTTP-/Provider-Regression bestätigen genau dieses Rennen. Das ist keine universelle Aussage über alle Entzugszeitpunkte.

Die Regressionen prüfen falsches Verhalten vor dem Fix und richtige Ergebnisse danach. Die Einzelberichte enthalten die genaue Reichweite; Gesamtprüfung und UI-Nachweis stehen unten.

## Die verbleibenden Hindernisse

| Bereich | Tatsächlicher Stand | Konsequenz für das Produkt |
|---|---|---|
| Rohquelle → beantwortbare Erinnerung | Upload und Rohtextsuche funktionieren. Im Gegenbeispiel findet die Rohtextsuche den Kira-Fakt; `answer_memory` bleibt leer, auch nach Verdichtung und Annahme im SelfModel. Der Antwortpfad liest den getrennten ClaimStore. | Ein erfolgreicher Import oder eine bestätigte Verdichtung garantiert heute kein Wiederfinden im Belegmodus. Gemeinsamer Abrufvertrag für Rohquellen, Arbeitsinterpretationen und bestätigtes Wissen fehlt. |
| Vollständige Quellen | Mailtext wird begrenzt aufgenommen; Anlagen fehlen in diesem Pfad. DOCX-Kopfzeilen/Fußnoten fehlen im geprüften Import. Gleicher Dokumenttext in zwei Upload-Fundstellen kann die zweite Projekt-/Dateizuordnung verlieren. | Quelle, Fundstelle und Textdarstellung müssen getrennt erfasst werden. Umfang, ausgelassene Teile und Fehler gehören an die Antwort. |
| Personen | Explizite Entitätskennungen schützen bestätigte Claims. Teilnehmernamen bilden daneben ältere, namensbasierte Personenprofile. Zwei unabhängige „Alex Winter“ landen in einer Akte und einem gemeinsamen KI-Eingang. | Namensgleichheit darf keine Identitätsentscheidung sein. Namen ohne bestätigte Bindung als unaufgelöste Erwähnungen führen; keine personenspezifische Aggregation daraus ableiten. |
| Fristen und Konflikte | Bestätigte Ersetzungen und Gültigkeitsgrenzen existieren. Eine angenommene Frist 22. September und ein gültiger widersprechender Kandidat 26. September erzeugen eine offene Klärung; die Antwort liefert dennoch den 22. ohne Konflikthinweis. | Konfliktzustand muss den Antwortvertrag beeinflussen. Der neue Kandidat ist dabei noch kein bestätigter neuer Termin. |
| Faktenfragen | Der eingeschränkte Belegmodus arbeitet ohne freie Modellprosa. Viele Formulierungen wie „Wer ist für Aurora verantwortlich?“ oder „Bis wann muss Aurora fertig sein?“ landen stattdessen im freien Chat. | Ein gemeinsamer Vertrag für persönliche Faktenfragen fehlt. Eine weitere Liste einzelner Frageformen würde diese Lücke nur verkleinern. |
| Bedeutung | Belegexistenz, Schema und Referenzen werden geprüft. Der Selektor sieht gespeicherte Aussagefelder, nicht das Originalzitat samt Sprecher-/Bedingungskontext. | „Quelle vorhanden“ ist kein Beweis, dass die Aussage aus der Quelle folgt. Negation, Sprecher, Bedingungen und Zeit müssen eigenständig bewertet werden. |
| Wiederfinden | Der bekannte Entwicklungssatz liefert 13/22 exakte Belegmengen: sieben unvollständig, zwei mit Zusatztreffern. Die Fälle enthalten vorbereitete angenommene Claims. | Keine Gesamtgenauigkeit und keine Aufnahmeabnahme. Wortformen/Synonyme helfen punktuell; ein breiter Rohquellen- und Bedeutungsnachweis fehlt. |
| Semantische Suche | Experimentell und standardmäßig aus. Reproduktion mit 130 Claims: trotz Inventargrenze 512 nur 128 im Cache, korrekt als Teilabdeckung gemeldet; ein ausgelassener Treffer fehlt. Derselbe Treffer ist per explizitem Snapshot und exakter Wortsuche erreichbar. | Die Arbeit pro Modellantwort darf begrenzt sein, die durchsuchbare Sammlung muss trotzdem den Bestand abdecken. Dieser Gegenfall verwendet künstliche Vektoren und misst keine Embeddingqualität. |
| Alte Antworten | Entzogene Quelle wird nicht erneut an das Modell geliefert. Alte Nachrichten bleiben jedoch mit ihrem damaligen Antwortstatus ohne sichtbare Entwertung erhalten. | Historie erhalten, aber alte Antworten als früheren bzw. inzwischen ungültigen Stand kenntlich machen. Quellenentzug ist nicht automatisch Löschauftrag. |
| Vorgänge/Zusagen | Aufgaben und bestätigte Claims existieren. Der vollständige Ablauf Bitte → bedingte Zusage → Friständerung → Teillieferung → Empfang ist kein durchgehend implementiertes Vorgangsmodell. | Eine Aufgabe mit Datum reicht als Gedächtnis für einen CoS nicht aus. Rolle, Bedingung, Verpflichtung und Erledigungsnachweis müssen getrennt bleiben. |

Zusätzlich verursacht die derzeitige Rückfrageprüfung unnötige Auswahlfragen bei Projektübersichten mit mehreren beteiligten Personen. Vorsicht allein macht eine Antwort noch nicht nützlich.

## Umsetzung ab hier: erst ein vollständiger Arbeitsablauf

Die bestehende [Memory-first-Roadmap](../../../../release/MEMORY-FIRST-ROADMAP.md) bleibt der Rahmen. Folgende Reihenfolge konkretisiert ihre offenen M0–M3-Pakete anhand der neuen Befunde. Keine neue Datenbank und kein Austausch des gesamten Produkts sind aus diesem Audit abgeleitet.

1. **Abnahme aus Rohquellen einführen.** Zuerst ein kleiner, fester Entwicklungssatz aus vollständigen Mails/Dokumenten/Gesprächen mit unabhängig festgelegten Sollfeldern: Person, Projekt, Handlung, Bedingung, Ereigniszeit, Frist, Status, Beleg. Keine vorbereiteten Claims als Ersatz für Aufnahme. Fehler pro Stufe und nötige Nutzerkorrekturen zählen. Die folgenden Pakete benutzen denselben durchgehenden Ablauf.
2. **Quellen und Erwähnungen sauber verbinden.** Original/Fundstelle/Version/Abdeckungsstatus erhalten; gleiche Namen und Kopien getrennt halten. Unaufgelöste Erwähnungen dürfen gefunden werden, aber keine Personenakten oder Kontakte als gesicherte Identität erzeugen. Bestehende explizite Identitäten weiterverwenden. Bereits zusammengefallene alte Fundstellen nur aus vorhandenen Originalen oder nach erneuter Aufnahme rekonstruieren; nichts erfinden.
3. **Einen gemeinsamen, belegten Abruf schaffen.** Rohquellen auch ohne vorherige Einordnung finden; SelfModel und Claims mit unterschiedlichem Status zugänglich machen. Strukturierte Suche plus Bestandssuche plus begrenzte semantische Kandidaten. Pro Antwort wenige geprüfte Treffer; keine willkürlich nur neuesten 128 Erinnerungen als Suchraum. Index und Cache bleiben neu aufbaubare Ableitungen.
4. **Den Faktenantwortvertrag durchziehen.** Persönliche Faktenfragen, Übersichten und Follow-ups verwenden dieselbe Evidenzprüfung. Originalausschnitt, Sprecher, Bedingungen, Identität, Zeit und offene Konflikte begleiten jede Antwort. Ergebnis: belegte Aussage, ausgewiesener Konflikt, gezielte Rückfrage oder konkrete Such-/Verarbeitungslücke. Ungeprüfte Modellprosa darf keine verlässliche Frist oder Personenzuordnung vortäuschen.
5. **Änderungen als vollständige Ereignisfolge prüfen.** Korrektur, Widerruf, neue Frist, Teilabschluss und Empfang durch Suche, Akte, Antwort, alte Unterhaltung und Wiederherstellung verfolgen. Alte Ansichten erkennbar historisch halten; keine stille Wiederbelebung. Vorgangsstatus und Ausführungsnachweis getrennt führen.
6. **Erst danach breiter freigeben.** Den im Vertrag vorgeschlagenen Bestand von 300 Quellen/90 fachlichen Fällen und 40 adversariellen Abläufen aufbauen. Ganze Szenarien zwischen Entwicklung und Holdout trennen; der implementierende Agent darf den Holdout nicht mitoptimieren. Anschließend mehrtägige lokale Nutzung, Geschwindigkeit und Korrekturaufwand messen. Die Ziele 98 % Präzision/95 % Erkennung gelten als vorgeschlagene Arbeitsziele mit getrennten Feldwerten; bekannte schwere Personen-/Fristfehler blockieren die betroffene Freigabe unabhängig vom Durchschnitt.

**Investitionsentscheidung:** Nicht aus bisherigen Credits weiterbauen, sondern am nächsten durchgehenden Rohquellenlauf entscheiden. Verbesserung muss weniger übersehene Fakten, weniger falsche Zuordnungen und weniger manuelle Nacharbeit bringen. Wenn derselbe Ablauf nach gezielter Kernkorrektur nicht tragfähig wird, wird die Architektur neu bewertet, bevor weitere Produktfunktionen oder Modellversuche bezahlt werden. Eine belastbare Dauer-/Credit-Schätzung lässt sich aus den heutigen Testzahlen nicht ableiten.

**Aufgabenteilung:** Architekturgrenzen, konkurrierende Änderungen, Identität/Zeit und unabhängiges Review brauchen den sorgfältigsten Agenten. Ein günstigerer Agent kann abgegrenzte Fixtures, bestehende Testlücken, Importadapter nach festem Vertrag und Nachweisdokumentation bearbeiten. Fine-Tuning, mehrere Spezialmodelle und weitere UI-Funktionen bleiben nachgeordnet. Wiederholte Volltests, CI-Neustarts und reine Statusabfragen liefern keinen zusätzlichen Qualitätsgewinn.

## Nachweise

- `identity-time.md`: Identität, Zeit, Aufgaben und verbleibendes Vorgangsmodell.
- `ingestion-coverage.md`: Aufnahme, Verdichtung, Abdeckung und getrennte Stores.
- `answer-validity.md`: Antwortpfade, offene Fristkonflikte, Darstellung und Verlauf.
- `retrieval-scope.json` / `retrieval_scope.py`: reproduzierbare Grenze des semantischen Arbeitsbestands.
- `verification.json`: endgültiger Code `cda54ad`, **2.097 verschiedene Tests und vier Subtests bestanden**. Im eingeschränkten Vollaufruf bestanden 2.081, 16 wurden durch Socket-/DNS-Sperren blockiert. Fünf wurden über die Fehlerauswahl und elf weitere über zwei explizite Testdateien erfolgreich wiederholt (dort 14 Tests inklusive drei bereits grüner Fälle). Keine verbleibenden Testfehler; zwei bekannte Bibliothekswarnungen.
- TypeScript/Vite-Build und Asset-Vertrag bestanden. Docker-Image `kingfisher:memory-audit-cda54ad` gebaut. Browser: unbekanntes Kontaktdatum, Zitatdatum unbekannt, ehrliche Aussagebeschriftung und Teilabdeckung/Erklärung sichtbar. Derselbe Personenüberblick blieb nach echtem Containerneustart verfügbar, ohne Ereignisdatum zu erfinden. Ausschließlich kontrollierter Provider, keine Bewertung eines echten LLM.
- Der erste Vollaufruf auf `33a5bfc` wurde nach 940 bestandenen Tests bewusst unterbrochen, um den zusätzlichen Entzugsfund zu korrigieren. Die oben genannten Ergebnisse gehören zur abschließenden Codefassung. Nachweisdateien wurden danach ergänzt; keine erneute fachliche Codeänderung.
- Das unveränderte Offline-Ergebnis 13/22 ist weiterhin eine Entwicklungsdiagnose. Integration dieser Korrekturen ist keine Freigabe der oben offenen CoS-Fähigkeiten.
