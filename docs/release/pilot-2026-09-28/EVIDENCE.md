# Nachweise und Grenzen

## Gedächtnis

Der unveränderte Fallbestand `cos-workweek-memory-v1` mit zehn synthetischen Quellen und elf Fragen besteht 11/11 Beleg-/Statusprüfungen; Integritätsprüfungen (Originalerhalt, Entdopplung, Entzug im Verlauf) bestanden. Lokales `qwen3.5:4b`, keine Cloud, 19 Modellaufrufe, 46,732 Sekunden gemessene Modellzeit. Zuvor 8/11. `workweek.json` enthält die Originalantworten und Modellaufrufe.

Provenienz: Der Runner wurde vor dem Commit gestartet und nennt daher Basis `046b3ae`; geprüft wurden bereits die uncommitteten Gedächtnisänderungen, anschließend unverändert in `6a4e07a` festgehalten. Das ist kein Lauf auf unverändertem main. Szenario und Erwartungen wurden nicht geändert.

Die drei Korrekturen sind begrenzt: fehlende Belege bei Lieferfragen bleiben im Belegpfad; explizit andere Reisebelegkategorien werden nicht als Antwort eingesetzt; mehrere wörtlich passende volle Namen bei einer singulären Lieferfrage lösen eine Rückfrage aus. Dies ist keine allgemeine Erkennung aller Personen, Synonyme oder Sprachformen. Mehrdeutige, indirekte Aussagen und unbekannte Umschreibungen bleiben Gegenstand des Piloten.

Neue HTTP-Regressionsfälle: zunächst fünf erwartete Fehler, danach inklusive zusätzlicher Gegenkontrollen 227 betroffene Routing-/Arbeitsgedächtnistests bestanden. Unabhängige kleine Modellprüfung fand in diesem Diff keinen weiteren konkreten Fehler; direkte Funktionsgegenproben wurden ausgeführt. Das ist keine Garantie der Fehlerfreiheit.

## Größerer Bestand

`scale.json`: 1.000 und 10.000 synthetische Nachrichten, je 40 vorab bestimmte eindeutige Angaben. Alle 40 erreichen den Kontext der Auswahlstufe. Bei 10.000 Nachrichten: Aufnahme 10,228 s, deterministische Einordnung 66,330 s, Suchmedian 0,1422 s, p95 0,1687 s, Datenbank etwa 60,42 MB. Alle Antworten haben einen begrenzten Kandidatenrahmen.

Dieser Test simuliert die Einordnung ohne Modell. Er misst weder den Durchsatz echter Modelle noch Antwortgenauigkeit, große Einzeldateien oder vollständige Erschließung echter Archive. Zeiten gelten für diesen Mac/Lauf; parallel liefen weitere Programme.

## Zusammenhängender Ablauf

Siehe `../PILOT-CORE-FLOW-2026-09-28.md`: ein gemeinsamer synthetischer HTTP-/Store-Ablauf durch Mailaufnahme, Quelle, Projekt, Aufgabenübernahme, Kalender-Vorbereitung, Briefing, Quellenfrage, Freigabeprüfung und Neustart. Konnektoren und externe Ausführung sind Testadapter. Doppelte Aufgabenübernahme gibt dieselbe Aufgabe zurück, doppelte ausgeführte Freigabe bleibt abgewiesen. Kein SMTP-Versand oder echter Kalenderzugriff in diesem Lauf.

## Korrekturen und Betrieb

Aufgaben erhalten eine Bearbeitung für Titel, Termin und Notiz. Identität, Herkunft, Projekt und Wartestatus bleiben erhalten; ausgelassene Felder bleiben unverändert, null leert optionale Felder. Der Verlauf protokolliert die Bearbeitung ohne dauerhafte Kopien von Titel/Notiz, damit Quellenentzug nicht durch ein Textarchiv unterlaufen wird. 19 betroffene Tests und Frontend-Build bestanden.

Restore prüft registrierte Schema-Versionen vor Dateiaustausch. Negative oder zukünftige Versionen werden abgewiesen, ältere zulässige Versionen bleiben wiederherstellbar. Das ersetzt keine vollständige Schema-Strukturprüfung. Der echte Docker-Lauf deckte zudem einen WAL-Snapshot auf, der auf einem schreibgeschützten Medium nicht lesbar war. Regression vor Fix rot; finalized Snapshots werden nun unveränderlich/lesend geöffnet, Live-Datenbanken weiterhin WAL-bewusst gesichert. 44 Backup-/Recovery-/Restore-Tests bestanden. Keine historischen Freigaben werden automatisch reaktiviert.

Persönliche Konten, echte externe Zustellung, Kalenderänderungen und mehrtägige Alltagserfahrung sind noch offene Abnahmen. Die erste Bereitstellung ist ein begleiteter Pilot, keine Freigabe zur alleinigen Termin- oder Fristenverwaltung.

## Abschließende lokale Abnahme

- Gesamter Backend-Lauf auf dem beim Start geladenen Stand `85e1865`: 2.486 bestanden, drei Setupfehler und ein fehlgeschlagener Test. Alle vier Ursachen waren `PermissionError` beim lokalen Socket-Bind in der Sandbox. Die vollständigen betroffenen Dateien wurden mit erlaubtem lokalen Zugriff erneut geprüft: `test_modelle.py` 10/10, `test_restored_app_launcher.py` 5/5. Damit sind alle 2.490 Fälle dieses Gesamtlaufs abgedeckt; es wird kein durchgehend grüner einzelner Lauf behauptet.
- Spätere Ergänzungen wurden gezielt geprüft: Read-only-Snapshot-Korrektur mit 44 Recovery-Tests beziehungsweise 81 betroffenen Backup-/Migrationsprüfungen; Aufgabenbearbeitung mit 19 betroffenen Tests. Abschließend Bearbeitung und gemeinsamer Kernablauf nochmals zusammen: 2/2 bestanden. Keine unnötige Vollwiederholung nach diesen begrenzten Änderungen.
- Docker-Image `9d6f190`: Frontend-Build und Imagebau bestanden. Reale lokale Aufnahme und belegte Antwort, Container-Neustart mit erhaltenen Quellen/Aufgaben/Gesprächen sowie aktive Automatisierung wurden auf dem Vorläufer `6a4e07a` geprüft. Dessen Datenvolume wurde anschließend unverändert mit dem finalen Image weiterverwendet.
- Wiederherstellung im finalen Image aus einem **schreibgeschützt eingebundenen** Snapshot: Originalquelle, erledigte Aufgabe und Gespräch vorhanden; historische Ansicht aktiv, schreibende Aktion mit HTTP 423 gesperrt. `runtime.json` hält die unterschiedlichen Image-Stände ausdrücklich fest.
- Browserprüfung im finalen Image: aus Quellenangebot übernommene Aufgabe geöffnet, Titel/Datum/Notiz bearbeitet, gespeichert und Seite neu geladen. Werte erhalten; Originalquelle samt Bedingung und Verlaufseintrag „Details bearbeitet“ sichtbar. Screenshot `task-edited.png` verwendet ausschließlich synthetische Daten.
- Unabhängige Prüfung von Aufgabenbearbeitung und Read-only-Backup fand keinen weiteren konkreten Defekt. Quellen-Ausschluss ist gemäß bestehendem Vertrag eine reversible Nutzungssperre, keine endgültige Rohdatenlöschung; ausdrückliche menschliche Einsicht bleibt möglich.

## Lokale Übergabe

Einmalig leerer Bestand auf `http://127.0.0.1:8892`, Container `kingfisher-pilot`, persistentes Volume `kingfisher-pilot-data`. Leere Aufgaben-/Dokument-/Kontenlisten und aktive lokale Einordnung geprüft; Browser zeigt 0 aufgenommene Quellen und `Aktiv mit qwen3.5:4b`. Vorheriger Testcontainer und Volume bleiben erhalten, zusätzlich wurde dessen Snapshot außerhalb des Volumes gesichert. Zugangsdaten liegen ausschließlich in einer lokalen Datei mit Modus 0600; sie sind kein Bestandteil dieser Dokumentation.

Die vorhandene Mac-App wurde mit Rückfallkopie aktualisiert und ihre Signatur überprüft. Beim Kopieren verlorene Ausführungsrechte des Starters wurden vor Übergabe korrigiert. Anschließender Start über die Mac-App öffnete sichtbar Safari mit `127.0.0.1:8892/today`; die lokalen Helfer wurden gestartet. Das separate Fenster ohne Browserleisten bleibt zurückgestellt.
