# Automatisch nutzbare Quellenberichte — 23.09.2026

Dies ist das erste Umsetzungspaket des freigegebenen CoS-V1-Plans, keine Abnahme eines vollständigen oder fehlerfreien Gedächtnisses.

## Verhalten

Erlaubte Dokumente und Nachrichten werden bei eingeschalteter lokaler Modellprüfung automatisch eingeordnet. Abschnitte bleiben Referenzen auf aktuelle Originalquellen; das Modell darf nur bekannte Abschnitts-IDs klassifizieren und auswählen. Es schreibt weder bestätigte Claims noch Aufgaben als Nebenwirkung. Antworten zeigen Quellenberichte mit vollständigem begrenztem Originalkontext, damit Bedingungen und Negationen in anderen Absätzen erhalten bleiben.

Ein neuer Dokument-Upload weckt bei bereits eingeschalteter Automatik den vorhandenen Hintergrundthread. Er priorisiert höchstens fünf konkrete Quellen je Durchlauf, hält höchstens 200 deduplizierte Quellen-IDs vor und verändert den normalen Scan-Cursor nicht. Überlauf und ein Neustart verlieren keine Quellen; diese bleiben für den normalen Lauf gespeichert. Aufnahme und Sicherung werden bei Fälligkeit weiterhin ausgeführt. Einstellungen, Modellwechsel und Quellenentzug werden vor und nach der Modellanfrage geprüft.

Verläufe speichern Referenzen statt kopierter Quellenberichte. Anzeige, Auswahl und Modellhistorie prüfen die aktuelle Grundlage erneut. Neue passende Quellen oder bestätigte Aussagen entwerten alte Antworten auch außerhalb der zwölf angezeigten Treffer; unabhängige neue Informationen tun dies im normalen begrenzten Suchfall nicht. Scheitert die automatische Auswahl, bleiben verwendbare bestätigte Angaben sichtbar, während verworfene automatische Treffer nicht ausgegeben werden.

Im Gespräch lässt sich eine automatische Einordnung verwerfen. Das Original bleibt erhalten; diese Einordnung wird beim nächsten Lauf nicht erneut erzeugt. Ein Quellenentzug sperrt zusätzlich die Verwendung als Wissensbeleg.

## Semantische Gegenprobe mit lokalem Modell

Die unabhängige Prüfung lief auf `c088b07` mit bereits vorhandenem lokalem `qwen3.5:4b`. [Erwartungen](expected.json) wurden vor dem einzigen Durchlauf festgelegt: zwölf synthetische Quellen, acht Fragen. [Rohresultate](results.json) und [unabhängige Bewertung](independent-assessment.md) bleiben unverändert archiviert. **Sieben von acht Entscheidungen waren richtig.** Bei zwei gleichnamigen Personen wurde nach dem geltenden Sachstand statt nach der gemeinten Person gefragt. Es wurde kein einzelnes falsches Datum gewählt.

Eine stärkere Modellanweisung löste das Problem nicht zuverlässig: [erste Nachprüfung](identity-correction-results.json) zeigte auch beim bereits genannten Straßenbezug eine unnötige Rückfrage. Deshalb prüft eine zusätzliche enge Regel gemeinsam ausgewählte Quellen mit vollständigem Absendernamen und verschiedenen E-Mail-Adressen. Sie führt keine Personen zusammen. Eine eindeutige Mailadresse oder eine passende ursprüngliche `Von:`/`Adresse:`-Kopfzeile kann die Auswahl begrenzen; sonst wird nach der Person gefragt. Listen, mehrdeutige oder negierte Zuordnungen und mehrere Teilnehmer werden nicht durch diese Regel aufgelöst. Bestätigte Aussagen behalten ihre gesonderte Konfliktprüfung.

Die anschließende [lokale Nachprüfung](identity-guard-results.json) beantwortete beide Entwicklungsfälle wie erwartet: Personenrückfrage ohne Adresse, passende Quelle bei genannter Anschrift. Das sind zwei nachgebesserte Entwicklungsfälle, **kein nachträglich auf acht von acht hochgerechneter unabhängiger Test**. Eine einzeln falsch ausgewählte Quelle wird durch diese enge Regel nicht erkannt; allgemeine Personenauflösung ist damit nicht bewiesen.

Der eingefrorene Fall C3 mit identischem generischem Absender und Projektnamen ausschließlich im Nachrichtentext bleibt ausdrücklich offen. Unterschiedliche Projektwörter belegen weder unterschiedliche Absender noch verschiedene reale Personen; ohne unterscheidbare Absender-Metadaten erzeugt die Regel deshalb keine automatische Personenrückfrage.

Wiederholung mit dem vorhandenen lokalen Modell, bewusst in eine neue Ergebnisdatei:

```sh
PYTHONPATH=sidecar python docs/evaluations/memory-quality/runs/2026-09-23-working-memory/run_once.py --output /tmp/working-memory-new-results.json
```

## Verifikation

- Gezielte Backend-Prüfungen decken Klassifizierung, Begrenzungen, Quellenänderung während Verarbeitung, Verwerfen, Konflikte, ältere Gespräche und Berechtigungswechsel ab. Zusätzliche konkrete Reviewfehler wurden mit Regressionstests behoben.
- Ein Integrationstest verarbeitet 520 synthetische Quellen, startet nach den ersten 100 neu und prüft Wiederfinden, vollständige Sicherung und Wiederherstellung. Keine erneute Klassifizierung bekannter Quellen; verworfene Einordnung bleibt verworfen. Der wiederhergestellte Bestand bleibt im bestehenden historischen Einsichtsmodus.
- Browserprüfung in einer isolierten Instanz auf `127.0.0.1:19003`, Codex In-app Browser, 1280×720: Quelle hochladen, verarbeiten, Frage stellen, Original öffnen, Einordnung verwerfen. Die Bedingung in einem zweiten Absatz war sichtbar. Danach enthielten Antwort und Seitenleiste keine verworfenen Quelleninhalte mehr; das Original blieb erhalten und der nächste Lauf stellte die Einordnung nicht wieder her. Keine Konsolenfehler. Mobile Ansicht nicht geprüft. Kontrollierter Testanbieter für diesen UI-Ablauf; die echte Modellprüfung steht separat oben.
- UI-Build und Vertrag der vorhandenen Grafiken/Symbole bestanden. Keine neuen Grafiken oder Komponentenbibliotheken.
- Vollständige lokale Regression auf sauberem Produktstand `36f2054`: **2246 Tests und 4 Untertests bestanden**, 182,29 Sekunden, zwei vorhandene Abkündigungswarnungen aus Testabhängigkeiten. Befehl: `PYTHONPATH=sidecar:scripts python -m pytest sidecar/tests scripts -q`. Lokale Testserver und DNS waren freigegeben. Der frühere Lauf ohne diese Freigabe war wegen Socket-/DNS-Sperren kein grüner Gesamtnachweis. UI-Build und Assetprüfung bestanden auf demselben Produktstand. Nachfolgende Dokumentationscommits ändern das Produkt nicht.

## Verbleibende Produktarbeit

Quellen über 12.000 Zeichen, zu lange Absätze oder unvollständige Aufnahmen bleiben sichtbar zurückgestellt. Die Kandidatensuche ist begrenzt und weitgehend lexikalisch; semantische Paraphrasen und beliebig große Bestände sind nicht qualifiziert. Automatische Einordnung kann trotz gültiger Referenzen semantisch falsch sein. Freies Alltagsgespräch als dauerhafte Aufnahme, gemeinsamer Arbeitsstand für Tagesüberblick/Terminvorbereitung/Antwortentwürfe, bequemere inhaltliche Korrekturen und umfassendere unabhängige Alltagstests bleiben V1-Arbeit. Grüne Codeprüfungen ersetzen diese Produktabnahme nicht.
